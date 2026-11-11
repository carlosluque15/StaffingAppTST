"""Reusable availability / occupancy calculation per person.

* An assignment is active on date D when it is sold, not ``confirmed_end`` and
  ``starting_on <= D <= finishing_on``.
* Occupancy = sum of ``assignment_percent`` of the active assignments.
* Capacity = ``Resource FTE * 100``; available = ``max(0, capacity - occupancy)``.
* ``None`` is returned only when the FTE or an assignment percent is not
  parseable; ``unknown`` then lists the reasons.
* ``Assignment.resource`` is matched with ``Staff.accenture_id`` ignoring case.
"""

from decimal import Decimal, InvalidOperation

from django.db.models.functions import Lower

from .models import Assignment

TRUE_VALUES = {"true", "yes", "1"}


def is_true(value):
    return (value or "").strip().casefold() in TRUE_VALUES


def parse_fte(value):
    try:
        fte = Decimal(value.strip().replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None
    return fte if fte.is_finite() and fte >= 0 else None


def capacity_percent(staff):
    fte = parse_fte(staff.resource_fte)
    return None if fte is None else int(fte * 100)


def _is_live(assignment):
    return is_true(assignment.sold) and not is_true(assignment.confirmed_end)


def is_active_on(assignment, on_date):
    return (
        _is_live(assignment)
        and assignment.starting_on is not None
        and assignment.finishing_on is not None
        and assignment.starting_on <= on_date <= assignment.finishing_on
    )


def assignments_by_resource(accenture_ids):
    """Sold, unconfirmed-end assignments grouped by lowercase resource id.

    One query for the whole group; date filtering is done by the caller.
    """
    keys = {value.casefold() for value in accenture_ids if value}
    rows = (
        Assignment.objects.annotate(resource_key=Lower("resource"))
        .filter(resource_key__in=keys)
        .order_by("starting_on", "source_id")
    )
    grouped = {}
    for row in rows:
        if _is_live(row):
            grouped.setdefault(row.resource.casefold(), []).append(row)
    return grouped


def resources_with_any_assignment(accenture_ids):
    """Lowercase ids that have at least one assignment row of any kind.

    Someone absent from this set has no assignment data at all, so a
    0% occupancy means "unknown", not "free".
    """
    keys = {value.casefold() for value in accenture_ids if value}
    return set(
        Assignment.objects.annotate(resource_key=Lower("resource"))
        .filter(resource_key__in=keys)
        .values_list("resource_key", flat=True)
        .distinct()
    )


def _sum_percent(assignments):
    percents = [item.assignment_percent for item in assignments]
    return None if any(p is None for p in percents) else sum(percents)


def occupancy(staff, on_date, assignments=None):
    """Occupancy of ``staff`` on ``on_date``.

    ``assignments`` may be the pre-fetched list from ``assignments_by_resource``
    for this person; otherwise it is queried.
    """
    if assignments is None:
        assignments = assignments_by_resource([staff.accenture_id]).get(
            staff.accenture_id.casefold(), []
        )
    active = [a for a in assignments if is_active_on(a, on_date)]
    assigned = _sum_percent(active)
    capacity = capacity_percent(staff)
    unknown = []
    if capacity is None:
        unknown.append("resource_fte not parseable")
    if assigned is None:
        unknown.append("assignment percent not parseable")
    available = (
        None if capacity is None or assigned is None else max(0, capacity - assigned)
    )
    return {
        "assignedPercent": assigned,
        "capacityPercent": capacity,
        "availablePercent": available,
        "unknown": unknown,
        "assignments": active,
    }


def timeline(staff, assignments=None):
    """Occupancy at every date where it changes (starts, and day after ends)."""
    from datetime import timedelta

    if assignments is None:
        assignments = assignments_by_resource([staff.accenture_id]).get(
            staff.accenture_id.casefold(), []
        )
    dated = [a for a in assignments if a.starting_on and a.finishing_on]
    points = sorted(
        {a.starting_on for a in dated}
        | {a.finishing_on + timedelta(days=1) for a in dated}
    )
    result = []
    for point in points:
        info = occupancy(staff, point, dated)
        result.append({
            "from": point.isoformat(),
            "assignedPercent": info["assignedPercent"],
            "availablePercent": info["availablePercent"],
        })
    return result
