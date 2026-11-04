from django.contrib import admin

from .models import Assignment, CareerLevel, CatalogValue, CriterionMapping, Demand, DemandCandidate, Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        "accenture_id",
        "name",
        "surname",
        "is_deleted",
        "role",
        "organization_unit",
        "deployment_city",
    )
    search_fields = ("accenture_id", "name", "surname", "role", "organization_unit")
    list_filter = (
        "is_deleted",
        "career_level_group",
        "deployment_country",
        "organization_unit",
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "source_id", "resource", "project_new", "project", "client", "starting_date"
    )
    search_fields = ("source_id", "resource", "project_new", "project", "client")
    list_filter = ("industry", "sold")


@admin.register(Demand)
class DemandAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "role", "offering", "status", "start_date")
    search_fields = ("code", "title", "role", "offering")
    list_filter = ("status", "offering", "location")


@admin.register(DemandCandidate)
class DemandCandidateAdmin(admin.ModelAdmin):
    list_display = ("demand", "staff", "search_stage", "selected_at")
    search_fields = ("demand__code", "demand__title", "staff__accenture_id", "staff__name")
    list_filter = ("search_stage", "demand__status")


@admin.register(CriterionMapping)
class CriterionMappingAdmin(admin.ModelAdmin):
    list_display = ("criterion", "demand_value", "staff_field", "staff_value")
    list_filter = ("criterion", "staff_field")
    search_fields = ("demand_value", "staff_value")


@admin.register(CatalogValue)
class CatalogValueAdmin(admin.ModelAdmin):
    list_display = ("kind", "value", "detail")
    list_filter = ("kind",)


@admin.register(CareerLevel)
class CareerLevelAdmin(admin.ModelAdmin):
    list_display = ("name", "rank", "unavailable_at_percent")
