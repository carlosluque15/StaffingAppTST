from django.urls import path
from .views import (
    catalog,
    candidates,
    complete_demand,
    demand_candidate_detail,
    demand_candidates,
    demand_detail,
    demand_search,
    demands,
    health_check,
    staff_availability,
)

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("catalog/", catalog, name="catalog"),
    path("candidates/", candidates, name="candidates"),
    path("staff/<str:accenture_id>/availability/", staff_availability, name="staff-availability"),
    path("demands/", demands, name="demands"),
    path("demands/<str:code>/", demand_detail, name="demand-detail"),
    path("demands/<str:code>/search/", demand_search, name="demand-search"),
    path("demands/<str:code>/complete/", complete_demand, name="demand-complete"),
    path("demands/<str:code>/candidates/", demand_candidates, name="demand-candidates"),
    path(
        "demands/<str:code>/candidates/<str:staff_id>/",
        demand_candidate_detail,
        name="demand-candidate-detail",
    ),
]