"""Staged candidate search over the imported Staff and Assignment tables.

Rules (no skills, scores or LLM):

* Identity: ``Staff.accenture_id`` (``Assignment.resource`` holds the same value).
* Catalog: seniority = ``Career Level Group``, industry = ``Staff.industry`` or the
  industry of an active assignment, location = ``Deployment City``. Values match
  the staffing catalog exactly, so no mapping is needed.
* Offering/area: not a Staff column. It is resolved through ``CriterionMapping``;
  without a mapping the search is blocked instead of guessing.
* Sections: ``initial`` (staff of the demand offering), ``expanded`` (everyone
  else with an offering) and the **Bolsa transversal** (staff without offering,
  shown in every search whatever the stage).
* Availability: a person is *not available* when the sum of their active
  assignments reaches the threshold of their ``CareerLevel``. Additionally the
  free capacity (FTE*100 - assigned) must cover the demand ``occupancy``;
  "Flexible" does not filter. The reference date comes from ``availability``.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .availability import assignments_by_resource, is_active_on, occupancy
from .models import CareerLevel, CriterionMapping, DemandCandidate, Staff

# Day offsets for the labels offered by the demand form.
AVAILABILITY_DAYS = {"inmediata": 0, "2 semanas": 14, "1 mes": 30, "3 meses": 90,
                     "flexible": 0}
REMOTE_LOCATIONS = {"", "remoto", "remote"}
UNASSIGNED_VALUES = ("", "Empty")
STAGES = [
    DemandCandidate.SearchStage.INITIAL.value,
    DemandCandidate.SearchStage.EXPANDED.value,
]
TRANSVERSAL = DemandCandidate.SearchStage.TRANSVERSAL.value
TRANSVERSAL_NAME = "Bolsa transversal"


class OfferingMappingMissing(Exception):
    """The demand offering has no configured mapping to Staff data."""


def _field_lookup(mapping):
    if mapping.staff_field == CriterionMapping.StaffField.ROLE_PREFIX:
        return Q(role__istartswith=mapping.staff_value)
    return Q(**{f"{mapping.staff_field}__iexact": mapping.staff_value})


def _offering_mappings(demand):
    mappings = list(
        CriterionMapping.objects.filter(
            criterion=CriterionMapping.Criterion.OFFERING,
            demand_value__iexact=demand.offering.strip(),
        )
    )
    if not mappings:
        raise OfferingMappingMissing(demand.offering)
    return mappings


def _offering_q(mappings):
    query = Q()
    for mapping in mappings:
        query |= _field_lookup(mapping)
    return query


def _unassigned_q(mappings):
    """Staff with no value in every field used to resolve the offering."""
    query = Q()
    for field in {m.staff_field for m in mappings}:
        column = "role" if field == CriterionMapping.StaffField.ROLE_PREFIX else field
        empty = Q()
        for value in UNASSIGNED_VALUES:
            empty |= Q(**{f"{column}__iexact": value})
        query = empty if not query else query & empty
    return query


def _eligible_staff():
    return Staff.objects.filter(is_deleted=False).exclude(accenture_id="")


def stage_for_staff(demand, staff):
    """Section in which ``staff`` is offered for ``demand``."""
    mappings = _offering_mappings(demand)
    base = _eligible_staff().filter(pk=staff.pk)
    if base.filter(_offering_q(mappings)).exists():
        return DemandCandidate.SearchStage.INITIAL.value
    if base.filter(_unassigned_q(mappings)).exists():
        return TRANSVERSAL
    return DemandCandidate.SearchStage.EXPANDED.value


def _parse_required_percent(value):
    text = value.strip().removesuffix("%").strip()
    if text.isdigit() and 0 < int(text) <= 100:
        return int(text)
    return None


def _candidate(staff, section, assignments, assigned, available, threshold):
    return {
        "id": staff.accenture_id,
        "name": " ".join(part for part in (staff.name, staff.surname) if part)
        or staff.accenture_id,
        "role": staff.role,
        "careerLevel": staff.career_level_group,
        "organizationUnit": staff.organization_unit,
        "talentSegment": staff.talent_segment,
        "subAlignment": staff.sub_alignment,
        "location": staff.deployment_city or staff.deployment_country,
        "industry": staff.industry,
        "activeIndustries": sorted({a.industry for a in assignments if a.industry}),
        "resourceFte": staff.resource_fte,
        "assignedPercent": assigned,
        "availablePercent": available,
        "unavailableAtPercent": None if threshold is None else float(threshold),
        "searchStage": section,
    }


def _filter_pool(pool, demand, section, reference_date, required, thresholds, selected_ids):
    """Apply the demand criteria to one section; returns (candidates, excluded)."""
    excluded = {}

    def note(reason, count):
        if count:
            excluded[reason] = count

    before = pool.count()
    pool = pool.filter(career_level_group__iexact=demand.seniority.strip())
    note("seniority", before - pool.count())

    location = demand.location.strip()
    if location.casefold() not in REMOTE_LOCATIONS:
        before = pool.count()
        pool = pool.filter(deployment_city__iexact=location)
        note("location", before - pool.count())

    staff_list = list(pool)
    all_assignments = assignments_by_resource(
        [staff.accenture_id for staff in staff_list]
    )
    assignments = {
        key: [a for a in rows if is_active_on(a, reference_date)]
        for key, rows in all_assignments.items()
    }

    industry = demand.industry.strip().casefold()
    if industry:
        kept = [
            staff for staff in staff_list
            if industry == staff.industry.strip().casefold()
            or industry in {
                a.industry.strip().casefold()
                for a in assignments.get(staff.accenture_id.casefold(), [])
            }
        ]
        note("industry", len(staff_list) - len(kept))
        staff_list = kept

    candidates = []
    counts = {"levelUnavailable": 0, "insufficientCapacity": 0, "unknownCapacity": 0}
    for staff in staff_list:
        info = occupancy(
            staff, reference_date, all_assignments.get(staff.accenture_id.casefold(), [])
        )
        staff_assignments = info["assignments"]
        assigned = info["assignedPercent"]
        available = info["availablePercent"]
        threshold = thresholds.get(staff.career_level_group.strip().casefold())
        if threshold is not None:
            if assigned is None:
                counts["unknownCapacity"] += 1
                continue
            if assigned >= threshold:
                counts["levelUnavailable"] += 1
                continue
        if required is not None:
            if available is None:
                counts["unknownCapacity"] += 1
                continue
            if available < required:
                counts["insufficientCapacity"] += 1
                continue
        item = _candidate(staff, section, staff_assignments, assigned, available, threshold)
        item["selected"] = item["id"] in selected_ids
        candidates.append(item)
    for reason, count in counts.items():
        note(reason, count)
    return candidates, excluded


def search_candidates(demand, stage, today=None):
    """Return the candidates of ``stage`` plus the Bolsa transversal.

    Raises ``OfferingMappingMissing`` when the demand offering is not mapped.
    """
    today = today or timezone.localdate()
    mappings = _offering_mappings(demand)
    offering_q = _offering_q(mappings)
    unassigned_q = _unassigned_q(mappings)

    base = _eligible_staff()
    if stage == DemandCandidate.SearchStage.INITIAL:
        stage_pool = base.filter(offering_q)
    else:
        stage_pool = base.exclude(offering_q).exclude(unassigned_q)
    transversal_pool = base.filter(unassigned_q).exclude(offering_q)

    days = AVAILABILITY_DAYS.get(demand.availability.strip().casefold(), 0)
    reference_date = today + timedelta(days=days)
    required = _parse_required_percent(demand.occupancy)
    thresholds = {
        level.name.casefold(): level.unavailable_at_percent
        for level in CareerLevel.objects.all()
    }
    selected_ids = set(
        demand.candidate_selections.values_list("staff__accenture_id", flat=True)
    )

    candidates, excluded = _filter_pool(
        stage_pool, demand, stage, reference_date, required, thresholds, selected_ids
    )
    pool_candidates, pool_excluded = _filter_pool(
        transversal_pool, demand, TRANSVERSAL, reference_date, required,
        thresholds, selected_ids,
    )

    criteria = [
        {"criterion": "offering", "applied": True,
         "detail": "Offering de la demanda" if stage == "initial" else "Resto de offerings"},
        {"criterion": "seniority", "applied": True, "detail": "Career Level Group"},
        {"criterion": "location",
         "applied": demand.location.strip().casefold() not in REMOTE_LOCATIONS,
         "detail": "Deployment City; remoto sin filtro"},
        {"criterion": "industry", "applied": bool(demand.industry.strip()),
         "detail": "Industry de Staff o de asignaciones activas"},
        {"criterion": "levelAvailability", "applied": bool(thresholds),
         "detail": "No disponible al alcanzar el umbral de su nivel"},
        {"criterion": "capacity", "applied": required is not None,
         "detail": (
             f"Capacidad libre >= {required}% a fecha {reference_date.isoformat()}"
             if required is not None
             else "Ocupación flexible: sin filtro de capacidad"
         )},
    ]
    return {
        "demandId": demand.code,
        "stage": stage,
        "referenceDate": reference_date.isoformat(),
        "criteria": criteria,
        "excluded": excluded,
        "candidates": candidates,
        "transversal": {
            "name": TRANSVERSAL_NAME,
            "excluded": pool_excluded,
            "candidates": pool_candidates,
        },
    }
