"""Staged candidate search over the imported Staff and Assignment tables.

Rules (no skills, scores or LLM):

* Identity: ``Staff.accenture_id`` (``Assignment.resource`` holds the same value).
* Catalog: seniority = ``Career Level Group``, industry = ``Staff.industry`` or the
  industry of an active assignment, location = ``Deployment City``. Values match
  the staffing catalog exactly, so no mapping is needed.
* Offering = ``Organization Unit``, resolved through ``CriterionMapping``;
  without a mapping the search is blocked instead of guessing.
* Sections: ``initial`` (staff of the demand offering), ``expanded`` (other
  offerings, except analysts) and the **Bolsa transversal** (analysts of other
  offerings, shown in every search whatever the stage; the demand seniority is
  not applied to it).
* Availability: a person is *not available* when the sum of their active
  assignments reaches the threshold of their ``CareerLevel``. Additionally the
  free capacity (FTE*100 - assigned) must cover the demand ``occupancy``;
  "Flexible" does not filter. The reference date is the demand ``start_date``
  (never earlier than today).
"""

from django.db.models import Q
from django.utils import timezone

from .availability import (
    assignments_by_resource,
    is_active_on,
    occupancy,
    resources_with_any_assignment,
)
from .models import CareerLevel, CriterionMapping, DemandCandidate, Staff

REMOTE_LOCATIONS = {"", "remoto", "remote"}
TRANSVERSAL_LEVEL = "Analyst"
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


def _eligible_staff():
    return Staff.objects.filter(is_deleted=False).exclude(accenture_id="")


def stage_for_staff(demand, staff):
    """Section in which ``staff`` is offered for ``demand``."""
    mappings = _offering_mappings(demand)
    base = _eligible_staff().filter(pk=staff.pk)
    if base.filter(_offering_q(mappings)).exists():
        return DemandCandidate.SearchStage.INITIAL.value
    if base.filter(career_level_group__iexact=TRANSVERSAL_LEVEL).exists():
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

    if section != TRANSVERSAL:
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
    with_assignment_data = resources_with_any_assignment(
        [staff.accenture_id for staff in staff_list]
    )
    assignments = {
        key: [a for a in rows if is_active_on(a, reference_date)]
        for key, rows in all_assignments.items()
    }

    def known_industries(staff):
        names = {staff.industry.strip().casefold()}
        names |= {
            a.industry.strip().casefold()
            for a in assignments.get(staff.accenture_id.casefold(), [])
        }
        return {name for name in names if name}

    industry = demand.industry.strip().casefold()
    if industry:
        # "No data" is not "no match": only people with known industries that
        # all differ from the demand are excluded.
        kept = [
            staff for staff in staff_list
            if not known_industries(staff) or industry in known_industries(staff)
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
        item["industryKnown"] = bool(known_industries(staff))
        item["assignmentDataKnown"] = (
            staff.accenture_id.casefold() in with_assignment_data
        )
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
    analyst_q = Q(career_level_group__iexact=TRANSVERSAL_LEVEL)

    base = _eligible_staff()
    if stage == DemandCandidate.SearchStage.INITIAL:
        stage_pool = base.filter(offering_q)
    else:
        stage_pool = base.exclude(offering_q).exclude(analyst_q)
    transversal_pool = base.filter(analyst_q).exclude(offering_q)

    reference_date = max(today, demand.start_date)
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
        {"criterion": "seniority", "applied": True,
         "detail": "Career Level Group (no aplica a la bolsa transversal)"},
        {"criterion": "location",
         "applied": demand.location.strip().casefold() not in REMOTE_LOCATIONS,
         "detail": "Deployment City; remoto sin filtro"},
        {"criterion": "industry", "applied": bool(demand.industry.strip()),
         "detail": "Industria de Staff o de asignaciones activas; sin dato no excluye"},
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
