import calendar
import csv
import json
import re
from datetime import date, timedelta
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.utils import timezone

from . import availability
from .models import Assignment, CareerLevel, CatalogValue, Demand, DemandCandidate, Staff
from .search import (
    STAGES,
    OfferingMappingMissing,
    search_candidates,
    stage_for_staff,
)


DEMAND_FIELDS = {
    "title": "title",
    "role": "role",
    "industry": "industry",
    "offering": "offering",
    "occupancy": "occupancy",
    "skills": "skills",
    "seniority": "seniority",
    "location": "location",
    "modality": "modality",
    "startDate": "start_date",
    "duration": "duration",
    "description": "description",
    "status": "status",
}
STATUS_NEW = "Nueva"
STATUS_SEARCHING = "Búsqueda en curso"
STATUS_REVIEW = "En revisión"
STATUS_COVERED = "Cubierta"
STATUS_CANCELLED = "Cancelada"
DEMAND_STATUSES = {
    STATUS_NEW,
    STATUS_SEARCHING,
    STATUS_REVIEW,
    STATUS_COVERED,
    STATUS_CANCELLED,
}
CLOSED_STATUSES = {STATUS_COVERED, STATUS_CANCELLED}
FLEXIBLE = "flexible"


def health_check(request):
    return JsonResponse({
        "status": "ok",
        "service": "staffing-backend"
    })


@require_http_methods(["GET"])
def catalog(request):
    values = {kind: [] for kind in CatalogValue.Kind.values}
    for item in CatalogValue.objects.all():
        values[item.kind].append({"value": item.value, "detail": item.detail})
    return JsonResponse(
        {
            "industries": [item["value"] for item in values["industry"]],
            "areas": [item["value"] for item in values["area"]],
            "locations": values["location"],
            "levels": [
                {
                    "name": level.name,
                    "rank": level.rank,
                    "unavailableAtPercent": float(level.unavailable_at_percent),
                }
                for level in CareerLevel.objects.all()
            ],
        }
    )


def _candidate_data(staff):
    """Minimal profile of a staff member; the stable id is the employee id."""
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
        "resourceFte": staff.resource_fte,
    }


def _demand_data(demand):
    return {
        "id": demand.code,
        "title": demand.title,
        "role": demand.role,
        "industry": demand.industry,
        "offering": demand.offering,
        "occupancy": demand.occupancy,
        "skills": demand.skills,
        "seniority": demand.seniority,
        "location": demand.location,
        "modality": demand.modality,
        "startDate": demand.start_date.isoformat(),
        "duration": demand.duration,
        "description": demand.description,
        "created": demand.created_at.isoformat(),
        "status": demand.status,
    }


def _json_body(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"error": "Request body must be valid JSON."}, status=400
        )
    if not isinstance(payload, dict):
        return None, JsonResponse(
            {"error": "Request body must be a JSON object."}, status=400
        )
    return payload, None


def _catalog_errors(payload):
    """Industry, offering, location and seniority must come from the catalog."""
    allowed = {
        "industry": {v.casefold(): v for v in CatalogValue.objects.filter(kind="industry").values_list("value", flat=True)},
        "offering": {v.casefold(): v for v in CatalogValue.objects.filter(kind="area").values_list("value", flat=True)},
        "location": {v.casefold(): v for v in CatalogValue.objects.filter(kind="location").values_list("value", flat=True)},
        "seniority": {v.casefold(): v for v in CareerLevel.objects.values_list("name", flat=True)},
    }
    errors = {}
    for field, options in allowed.items():
        value = payload.get(field)
        if not options or not isinstance(value, str) or not value.strip():
            continue
        if field == "location" and value.strip().casefold() in {"remoto", "remote"}:
            continue
        canonical = options.get(value.strip().casefold())
        if canonical is None:
            errors[field] = [f"Use one of: {', '.join(options.values())}."]
        else:
            payload[field] = canonical
    return errors


def _apply_demand_payload(demand, payload, *, partial):
    unknown_fields = sorted(set(payload) - DEMAND_FIELDS.keys())
    if unknown_fields:
        return JsonResponse(
            {"error": "Unknown demand fields.", "fields": unknown_fields},
            status=400,
        )

    missing_fields = [
        field for field in ("title", "industry", "offering", "location", "startDate")
        if not partial and not payload.get(field)
    ]
    if missing_fields:
        return JsonResponse(
            {"error": "Required fields are missing.", "fields": missing_fields},
            status=400,
        )

    text_fields = set(DEMAND_FIELDS) - {"skills"}
    invalid_text_fields = [
        field for field in text_fields
        if field in payload and not isinstance(payload[field], str)
    ]
    if invalid_text_fields:
        return JsonResponse(
            {"error": "Text fields must be strings.", "fields": invalid_text_fields},
            status=400,
        )

    if "skills" in payload and (
        not isinstance(payload["skills"], list)
        or not all(isinstance(skill, str) and skill.strip() for skill in payload["skills"])
    ):
        return JsonResponse(
            {"error": "skills must be a list of non-empty strings."}, status=400
        )

    if "status" in payload:
        if not isinstance(payload["status"], str) or payload["status"] not in DEMAND_STATUSES:
            return JsonResponse(
                {
                    "error": "Unsupported demand status.",
                    "allowed_statuses": sorted(DEMAND_STATUSES),
                },
                status=400,
            )

    catalog_errors = _catalog_errors(payload)
    if catalog_errors:
        return JsonResponse(
            {"error": "Value not in the staffing catalog.", "fields": catalog_errors},
            status=400,
        )

    if "occupancy" in payload:
        text = payload["occupancy"].strip().removesuffix("%")
        if payload["occupancy"].strip().casefold() != FLEXIBLE and not (
            text.isdigit() and 0 < int(text) <= 100
        ):
            return JsonResponse(
                {
                    "error": "Unsupported occupancy.",
                    "fields": {"occupancy": [
                        "Use a percentage between 1% and 100% or Flexible."
                    ]},
                },
                status=400,
            )

    for api_field, model_field in DEMAND_FIELDS.items():
        if api_field not in payload:
            continue
        value = payload[api_field]
        if api_field == "startDate":
            try:
                value = parse_date(value)
            except ValueError:
                value = None
            if value is None:
                return JsonResponse(
                    {"error": "startDate must be a valid ISO date (YYYY-MM-DD)."},
                    status=400,
                )
        elif api_field == "skills":
            value = [skill.strip() for skill in value]
        elif api_field in text_fields:
            value = value.strip()
        setattr(demand, model_field, value)

    try:
        demand.full_clean()
    except ValidationError as error:
        return JsonResponse(
            {"error": "Demand validation failed.", "fields": error.message_dict},
            status=400,
        )
    return None


@require_http_methods(["GET"])
def candidates(request):
    return JsonResponse(
        {
            "candidates": [
                _candidate_data(item) for item in Staff.objects.filter(is_deleted=False).exclude(accenture_id="")
            ]
        }
    )


@require_http_methods(["GET"])
def talent(request):
    """All active staff with their occupancy today."""
    people = list(Staff.objects.filter(is_deleted=False).exclude(accenture_id=""))
    on_date = timezone.localdate()
    grouped = availability.assignments_by_resource([s.accenture_id for s in people])
    with_data = availability.resources_with_any_assignment(
        [s.accenture_id for s in people]
    )
    thresholds = {
        level.name.casefold(): float(level.unavailable_at_percent)
        for level in CareerLevel.objects.all()
    }
    data = []
    for staff in people:
        info = availability.occupancy(
            staff, on_date, grouped.get(staff.accenture_id.casefold(), [])
        )
        required = thresholds.get(staff.career_level_group.strip().casefold())
        assigned = info["assignedPercent"]
        meets = None if required is None or assigned is None else assigned >= required
        data.append({
            **_candidate_data(staff),
            "capacityPercent": info["capacityPercent"],
            "assignedPercent": info["assignedPercent"],
            "availablePercent": info["availablePercent"],
            "assignmentDataKnown": staff.accenture_id.casefold() in with_data,
            "requiredPercent": required,
            "meetsRequired": meets,
        })
    return JsonResponse({"talent": data})


@require_http_methods(["GET"])
def assignments(request):
    """Assignment rows linked to their person; grouping is done by the client."""
    scope = request.GET.get("scope", "active")
    if scope not in ("active", "all"):
        return JsonResponse({"error": "scope must be active or all."}, status=400)
    on_date = timezone.localdate()
    people = {
        s.accenture_id.casefold(): s
        for s in Staff.objects.exclude(accenture_id="")
    }
    data = []
    for row in Assignment.objects.order_by("starting_on", "source_id"):
        active = availability.is_active_on(row, on_date)
        if scope == "active" and not active:
            continue
        person = people.get(row.resource.casefold())
        deleted = bool(person and person.is_deleted)
        if scope == "active" and deleted:
            continue
        data.append({
            "id": row.source_id,
            "resource": row.resource,
            "personName": person.name if person else "",
            "careerLevel": person.career_level_group.strip() if person else "",
            "personDeleted": deleted,
            "project": row.project_name,
            "client": row.client,
            "industry": row.industry or (person.industry if person else ""),
            "startingOn": row.starting_on.isoformat() if row.starting_on else None,
            "finishingOn": row.finishing_on.isoformat() if row.finishing_on else None,
            "assignmentPercent": row.assignment_percent,
            "sold": row.sold,
            "confirmedEnd": row.confirmed_end,
            "active": active,
        })
    return JsonResponse({"assignments": data})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def demands(request):
    if request.method == "GET":
        return JsonResponse(
            {"demands": [_demand_data(item) for item in Demand.objects.all()]}
        )

    code = f"DEM-{uuid4().hex[:16].upper()}"
    payload, error = _json_body(request)
    if error:
        return error
    demand = Demand(code=code, status="Nueva")
    error = _apply_demand_payload(demand, payload, partial=False)
    if error:
        return error
    demand.save()
    return JsonResponse(_demand_data(demand), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def demand_detail(request, code):
    try:
        demand = Demand.objects.get(code=code)
    except Demand.DoesNotExist:
        return JsonResponse({"error": "Demand not found."}, status=404)

    if request.method == "GET":
        return JsonResponse(_demand_data(demand))
    if request.method == "DELETE":
        demand.delete()
        return HttpResponse(status=204)

    payload, error = _json_body(request)
    if error:
        return error
    error = _apply_demand_payload(demand, payload, partial=True)
    if error:
        return error
    demand.save()
    return JsonResponse(_demand_data(demand))


def _get_demand(code):
    try:
        return Demand.objects.get(code=code), None
    except Demand.DoesNotExist:
        return None, JsonResponse({"error": "Demand not found."}, status=404)


def _mapping_missing_response(error):
    return JsonResponse(
        {
            "error": "offering_mapping_missing",
            "message": (
                "No hay una correspondencia configurada entre el offering de la "
                "demanda y los datos de Staff. Un administrador debe crearla en "
                "Django Admin (Criterion mappings) antes de buscar candidatos."
            ),
            "offering": str(error),
        },
        status=409,
    )


@require_http_methods(["GET"])
def demand_search(request, code):
    demand, error = _get_demand(code)
    if error:
        return error
    stage = request.GET.get("stage", DemandCandidate.SearchStage.INITIAL)
    if stage not in STAGES:
        return JsonResponse(
            {"error": "stage must be 'initial' or 'expanded'.", "allowed_stages": STAGES},
            status=400,
        )
    try:
        return JsonResponse(search_candidates(demand, stage))
    except OfferingMappingMissing as missing:
        return _mapping_missing_response(missing)


def _selection_data(selection):
    return {
        **_candidate_data(selection.staff),
        "searchStage": selection.search_stage,
        "selectedAt": selection.selected_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def demand_candidates(request, code):
    demand, error = _get_demand(code)
    if error:
        return error

    if request.method == "GET":
        selections = demand.candidate_selections.filter(
            staff__is_deleted=False
        ).select_related("staff")
        return JsonResponse(
            {"candidates": [_selection_data(selection) for selection in selections]}
        )

    payload, error = _json_body(request)
    if error:
        return error
    staff_id = payload.get("staffId")
    requested_stage = payload.get("searchStage")
    if not isinstance(staff_id, str) or not staff_id.strip():
        return JsonResponse({"error": "staffId must be an employee id."}, status=400)
    if requested_stage is not None and requested_stage not in DemandCandidate.SearchStage.values:
        return JsonResponse(
            {
                "error": "searchStage must be 'initial', 'expanded' or 'transversal'.",
                "allowed_stages": DemandCandidate.SearchStage.values,
            },
            status=400,
        )
    matches = list(Staff.objects.filter(accenture_id=staff_id.strip(), is_deleted=False)[:2])
    if not matches:
        return JsonResponse({"error": "Active staff candidate not found."}, status=404)
    if len(matches) > 1:
        return JsonResponse(
            {"error": "Employee id is ambiguous among active staff."}, status=409
        )
    staff = matches[0]

    try:
        stage = stage_for_staff(demand, staff)
    except OfferingMappingMissing as missing:
        return _mapping_missing_response(missing)
    if requested_stage is not None and requested_stage != stage:
        return JsonResponse(
            {
                "error": "searchStage does not match the stage of this candidate.",
                "searchStage": stage,
            },
            status=400,
        )

    with transaction.atomic():
        demand = Demand.objects.select_for_update().get(pk=demand.pk)
        if demand.status in CLOSED_STATUSES:
            return JsonResponse(
                {"error": f"Demand is {demand.status}; selections are closed."},
                status=409,
            )
        selection, created = DemandCandidate.objects.get_or_create(
            demand=demand, staff=staff, defaults={"search_stage": stage}
        )
        if demand.status in {STATUS_NEW, STATUS_SEARCHING}:
            demand.status = STATUS_REVIEW
            demand.save(update_fields=["status"])
    return JsonResponse(
        {**_selection_data(selection), "demandStatus": demand.status},
        status=201 if created else 200,
    )


@csrf_exempt
@require_http_methods(["DELETE"])
def demand_candidate_detail(request, code, staff_id):
    demand, error = _get_demand(code)
    if error:
        return error
    with transaction.atomic():
        demand = Demand.objects.select_for_update().get(pk=demand.pk)
        if demand.status in CLOSED_STATUSES:
            return JsonResponse(
                {"error": f"Demand is {demand.status}; selections are closed."},
                status=409,
            )
        deleted, _ = DemandCandidate.objects.filter(
            demand=demand, staff__accenture_id=staff_id
        ).delete()
        if not deleted:
            return JsonResponse({"error": "Selected candidate not found."}, status=404)
        if demand.status == STATUS_REVIEW and not demand.candidate_selections.exists():
            demand.status = STATUS_SEARCHING
            demand.save(update_fields=["status"])
    return HttpResponse(status=204)


@require_http_methods(["GET"])
def staff_availability(request, accenture_id):
    staff = (
        Staff.objects.filter(accenture_id__iexact=accenture_id, is_deleted=False)
        .order_by("source_row")
        .first()
    )
    if staff is None:
        return JsonResponse({"error": "Staff not found."}, status=404)
    raw_date = request.GET.get("date")
    if raw_date:
        try:
            on_date = parse_date(raw_date)
        except ValueError:
            on_date = None
        if on_date is None:
            return JsonResponse({"error": "date must be YYYY-MM-DD."}, status=400)
    else:
        on_date = timezone.localdate()

    all_assignments = availability.assignments_by_resource([staff.accenture_id]).get(
        staff.accenture_id.casefold(), []
    )
    info = availability.occupancy(staff, on_date, all_assignments)
    level = CareerLevel.objects.filter(name__iexact=staff.career_level_group.strip()).first()
    return JsonResponse({
        "id": staff.accenture_id,
        "referenceDate": on_date.isoformat(),
        "resourceFte": staff.resource_fte,
        "capacityPercent": info["capacityPercent"],
        "assignedPercent": info["assignedPercent"],
        "availablePercent": info["availablePercent"],
        "unknown": info["unknown"],
        "unavailableAtPercent": (
            None if level is None else float(level.unavailable_at_percent)
        ),
        "assignments": [
            {
                "id": a.source_id,
                "project": a.project_name,
                "client": a.client,
                "startingOn": a.starting_on.isoformat() if a.starting_on else None,
                "finishingOn": a.finishing_on.isoformat() if a.finishing_on else None,
                "assignmentPercent": a.assignment_percent,
            }
            for a in info["assignments"]
        ],
        "timeline": availability.timeline(staff, all_assignments),
    })


NO_END_DATE = date(2099, 12, 31)
ASSIGNMENT_AUTHOR = "Staffing app"


def _add_months(start, months):
    """Last day of an assignment of ``months`` months starting on ``start``."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day) - timedelta(days=1)


def _demand_end_date(demand):
    match = re.match(r"\s*(\d+)\s*mes", demand.duration.casefold())
    if not match:
        return NO_END_DATE
    return _add_months(demand.start_date, int(match.group(1)))


def _csv_date(value):
    """Date as written in Assignments.csv (m/d/YYYY, no zero padding)."""
    return f"{value.month}/{value.day}/{value.year}"


def _csv_timestamp(value):
    hour = value.hour % 12 or 12
    return (f"{value.month}/{value.day}/{value.year} {hour}:{value.minute:02d} "
            f"{'AM' if value.hour < 12 else 'PM'}")


def _next_assignment_id():
    """Numeric ``ID`` following the highest one already in the table."""
    numeric = [int(v) for v in Assignment.objects.values_list("source_id", flat=True)
               if v.isdigit()]
    return str(max(numeric, default=0) + 1)


def _assignment_defaults(demand):
    return {
        "project": demand.title,
        "client": "",
        "industry": demand.industry,
        "responsible": "",
        "startingOn": demand.start_date.isoformat(),
        "finishingOn": _demand_end_date(demand).isoformat(),
        "assignmentPercent": _demand_percent_value(demand),
        "comments": "",
        "sold": True,
        "confirmedEnd": False,
    }


def _demand_percent_value(demand):
    text = demand.occupancy.strip().removesuffix("%").strip()
    return int(text) if text.isdigit() else None


def _text_field(payload, key, default, errors, max_length=200):
    value = payload.get(key, default)
    if not isinstance(value, str) or len(value.strip()) > max_length:
        errors[key] = [f"Debe ser texto de hasta {max_length} caracteres."]
        return ""
    return value.strip()


def _bool_field(payload, key, default, errors):
    value = payload.get(key, default)
    if not isinstance(value, bool):
        errors[key] = ["Debe ser verdadero o falso."]
        return default
    return value


def _date_field(payload, key, default, errors):
    raw = payload.get(key) or default
    try:
        value = parse_date(raw) if isinstance(raw, str) else None
    except ValueError:
        value = None
    if value is None:
        errors[key] = ["Fecha no válida (YYYY-MM-DD)."]
    return value


@csrf_exempt
@require_http_methods(["GET", "POST"])
def complete_demand(request, code):
    """GET: prefilled assignment data. POST: close the demand and register
    its selected people as assignments with the submitted data."""
    if request.method == "GET":
        demand, error = _get_demand(code)
        if error:
            return error
        selections = demand.candidate_selections.filter(
            staff__is_deleted=False
        ).select_related("staff")
        return JsonResponse({
            "responsibles": [
                {"id": p.accenture_id, "name": _candidate_data(p)["name"]}
                for p in Staff.objects.filter(is_deleted=False)
                .exclude(accenture_id="").order_by("name", "surname")
            ],
            "defaults": _assignment_defaults(demand),
            "candidates": [
                {**_candidate_data(s.staff), "availablePercent": availability.occupancy(
                    s.staff, demand.start_date)["availablePercent"]}
                for s in selections
            ],
        })

    payload = {}
    if request.body:
        payload, error = _json_body(request)
        if error:
            return error
    staff_ids = payload.get("staffIds")
    if staff_ids is not None and (
        not isinstance(staff_ids, list) or not all(isinstance(i, str) for i in staff_ids)
    ):
        return JsonResponse({"error": "staffIds must be a list of employee ids."}, status=400)

    try:
        with transaction.atomic():
            try:
                demand = Demand.objects.select_for_update().get(code=code)
            except Demand.DoesNotExist:
                return JsonResponse({"error": "Demand not found."}, status=404)
            if demand.status in CLOSED_STATUSES:
                return JsonResponse(
                    {"error": f"Demand is already {demand.status}."}, status=409
                )
            defaults = _assignment_defaults(demand)
            errors = {}
            project = _text_field(payload, "project", defaults["project"], errors)
            client = _text_field(payload, "client", defaults["client"], errors)
            if not client and "client" not in errors:
                errors["client"] = ["El cliente es obligatorio."]
            industry = _text_field(payload, "industry", defaults["industry"], errors, 120)
            responsible = _text_field(payload, "responsible", "", errors, 160)
            if responsible:
                owner = Staff.objects.filter(
                    accenture_id__iexact=responsible, is_deleted=False
                ).first()
                if owner is None:
                    errors["responsible"] = ["Debe ser una persona de Staff."]
                else:
                    responsible = owner.accenture_id
            comments = _text_field(payload, "comments", "", errors, 2000)
            sold = _bool_field(payload, "sold", defaults["sold"], errors)
            confirmed_end = _bool_field(
                payload, "confirmedEnd", defaults["confirmedEnd"], errors
            )
            start = _date_field(payload, "startingOn", defaults["startingOn"], errors)
            end = _date_field(payload, "finishingOn", defaults["finishingOn"], errors)
            if not project and "project" not in errors:
                errors["project"] = ["El proyecto es obligatorio."]
            if start and end and end < start:
                errors["finishingOn"] = ["La fecha de fin no puede ser anterior al inicio."]
            percent = payload.get("assignmentPercent", defaults["assignmentPercent"])
            if percent is not None:
                if isinstance(percent, str) and percent.strip().removesuffix("%").isdigit():
                    percent = int(percent.strip().removesuffix("%"))
                if not isinstance(percent, int) or isinstance(percent, bool) or not 1 <= percent <= 100:
                    errors["assignmentPercent"] = ["Debe estar entre 1 y 100."]
            if errors:
                return JsonResponse(
                    {"error": "Datos de la asignación no válidos.", "fields": errors},
                    status=400,
                )

            selections = demand.candidate_selections.filter(
                staff__is_deleted=False
            ).select_related("staff")
            if staff_ids is not None:
                wanted = {i.casefold() for i in staff_ids}
                selections = [
                    s for s in selections if s.staff.accenture_id.casefold() in wanted
                ]
            selections = list(selections)
            if not selections:
                return JsonResponse(
                    {"error": "Selecciona al menos un candidato antes de completar la demanda."},
                    status=409,
                )

            created = []
            now = timezone.localtime()
            stamp = _csv_timestamp(now)
            next_id = int(_next_assignment_id())
            for selection in selections:
                staff = selection.staff
                value = percent
                if value is None:  # "Flexible": take the free capacity
                    value = availability.occupancy(staff, start)["availablePercent"] or None
                if value is None:
                    raise ValueError(
                        f"{staff.accenture_id} no tiene capacidad libre para asignar; "
                        "indica un porcentaje."
                    )
                created.append(Assignment.objects.create(
                    source_id=str(next_id),
                    resource=staff.accenture_id,
                    project_new=project,
                    client=client,
                    industry=industry,
                    responsible=responsible,
                    sold=str(sold),
                    confirmed_end=str(confirmed_end),
                    starting_date=_csv_date(start),
                    finishing_date=_csv_date(end),
                    starting_on=start,
                    finishing_on=end,
                    assignment_percentage=f"{value}%",
                    assignment_percent=value,
                    comments=comments,
                    source_data={
                        "demand": demand.code,
                        "role": demand.role,
                        "Created By": ASSIGNMENT_AUTHOR,
                        "Modified By": ASSIGNMENT_AUTHOR,
                        "Created": stamp,
                        "Modified": stamp,
                    },
                ))
                next_id += 1
            demand.status = STATUS_COVERED
            demand.save(update_fields=["status"])
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=409)
    return JsonResponse({
        "demand": _demand_data(demand),
        "assignments": [
            {
                "id": a.source_id,
                "staffId": a.resource,
                "project": a.project_name,
                "startingOn": a.starting_on.isoformat(),
                "finishingOn": a.finishing_on.isoformat(),
                "assignmentPercent": a.assignment_percent,
            }
            for a in created
        ],
    }, status=201)



NO_MENTOR = "_none"


def _mentor_key(value):
    """Normalized mentor id: trimmed, lowercase, without the email domain."""
    key = (value or "").strip().casefold()
    return key.removesuffix("@accenture.com")


def _staff_by_key():
    """Staff by normalized id; active people win over deleted/duplicate rows."""
    result = {}
    for staff in Staff.objects.exclude(accenture_id="").order_by("source_row"):
        key = _mentor_key(staff.accenture_id)
        current = result.get(key)
        if current is None or (current.is_deleted and not staff.is_deleted):
            result[key] = staff
    return result


def _active_mentees():
    return Staff.objects.filter(is_deleted=False).order_by("surname", "name", "source_row")


@require_http_methods(["GET"])
def mentors(request):
    people = _staff_by_key()
    counts = {}
    for counselor in _active_mentees().values_list("career_counselor", flat=True):
        key = _mentor_key(counselor) or NO_MENTOR
        counts[key] = counts.get(key, 0) + 1
    result = []
    for key, count in counts.items():
        staff = people.get(key)
        result.append({
            "id": key,
            "name": _candidate_data(staff)["name"] if staff else key,
            "found": staff is not None or key == NO_MENTOR,
            "deleted": bool(staff and staff.is_deleted),
            "menteeCount": count,
        })
    result.sort(key=lambda m: (m["id"] == NO_MENTOR, m["name"].casefold()))
    for mentor in result:
        if mentor["id"] == NO_MENTOR:
            mentor["name"] = "Sin mentor asignado"
    return JsonResponse({"mentors": result})


@require_http_methods(["GET"])
def mentor_mentees(request, mentor_id):
    key = mentor_id.strip().casefold()
    mentees = [
        s for s in _active_mentees()
        if (_mentor_key(s.career_counselor) or NO_MENTOR) == key
    ]
    if not mentees:
        return JsonResponse({"error": "Mentor not found."}, status=404)
    on_date = timezone.localdate()
    grouped = availability.assignments_by_resource([s.accenture_id for s in mentees])
    with_data = availability.resources_with_any_assignment(
        [s.accenture_id for s in mentees]
    )
    data = []
    for staff in mentees:
        assignments = grouped.get(staff.accenture_id.casefold(), [])
        info = availability.occupancy(staff, on_date, assignments)
        data.append({
            **_candidate_data(staff),
            "capacityPercent": info["capacityPercent"],
            "assignedPercent": info["assignedPercent"],
            "availablePercent": info["availablePercent"],
            "assignmentDataKnown": staff.accenture_id.casefold() in with_data,
            "assignments": [
                {
                    "id": a.source_id,
                    "project": a.project_name,
                    "client": a.client,
                    "startingOn": a.starting_on.isoformat() if a.starting_on else None,
                    "finishingOn": a.finishing_on.isoformat() if a.finishing_on else None,
                    "assignmentPercent": a.assignment_percent,
                }
                for a in info["assignments"]
            ],
        })
    mentor = _staff_by_key().get(key)
    return JsonResponse({
        "mentor": {
            "id": key,
            "name": "Sin mentor asignado" if key == NO_MENTOR
            else (_candidate_data(mentor)["name"] if mentor else key),
            "found": mentor is not None or key == NO_MENTOR,
            "deleted": bool(mentor and mentor.is_deleted),
        },
        "referenceDate": on_date.isoformat(),
        "mentees": data,
    })


def _csv_cell(value):
    """Neutralise spreadsheet formulas, leaving pure numbers untouched."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if text and text[0] in "=+-@":
        try:
            float(text.replace(",", "."))
        except ValueError:
            return "'" + text
    return text


def _csv_response(filename, queryset):
    """Export ``source_data`` rows, reproducing the original CSV columns."""
    headers = []
    seen = set()
    for data in queryset.values_list("source_data", flat=True).iterator():
        for key in data:
            if key not in seen:
                seen.add(key)
                headers.append(key)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(headers)
    for data in queryset.values_list("source_data", flat=True).iterator():
        writer.writerow([_csv_cell(data.get(header)) for header in headers])
    return response


@require_http_methods(["GET"])
def export_staff(request):
    return _csv_response("staff.csv", Staff.objects.order_by("source_row"))


@require_http_methods(["GET"])
def export_assignments(request):
    return _csv_response("assignments.csv", Assignment.objects.order_by("id"))
