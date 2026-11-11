from django.db import models


class Staff(models.Model):
    source_row = models.PositiveIntegerField(unique=True)
    accenture_id = models.CharField(max_length=120, blank=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    name = models.CharField(max_length=160, blank=True)
    surname = models.CharField(max_length=160, blank=True)
    role = models.CharField(max_length=160, blank=True)
    career_level_group = models.CharField(max_length=120, blank=True)
    deployment_city = models.CharField(max_length=120, blank=True)
    deployment_country = models.CharField(max_length=120, blank=True)
    organization_unit = models.CharField(max_length=160, blank=True)
    talent_segment = models.CharField(max_length=120, blank=True)
    sub_alignment = models.CharField(max_length=120, blank=True)
    industry = models.CharField(max_length=120, blank=True)
    resource_fte = models.CharField(max_length=40, blank=True)
    career_counselor = models.CharField(max_length=160, blank=True, db_index=True)
    source_data = models.JSONField(default=dict)

    class Meta:
        ordering = ["surname", "name", "source_row"]

    def __str__(self):
        return f"{self.accenture_id or self.source_row} - {self.name} {self.surname}".strip()


class Assignment(models.Model):
    source_id = models.CharField(max_length=80, unique=True)
    resource = models.CharField(max_length=160, blank=True, db_index=True)
    project = models.CharField(max_length=200, blank=True)
    project_new = models.CharField(max_length=200, blank=True)
    client = models.CharField(max_length=200, blank=True)
    industry = models.CharField(max_length=120, blank=True)
    sold = models.CharField(max_length=40, blank=True)
    starting_date = models.CharField(max_length=80, blank=True)
    finishing_date = models.CharField(max_length=80, blank=True)
    confirmed_end = models.CharField(max_length=80, blank=True)
    responsible = models.CharField(max_length=160, blank=True)
    assignment_percentage = models.CharField(max_length=40, blank=True)
    # Parsed copies of the raw text columns above, used for capacity queries.
    starting_on = models.DateField(null=True, blank=True)
    finishing_on = models.DateField(null=True, blank=True)
    assignment_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)
    source_data = models.JSONField(default=dict)

    class Meta:
        ordering = ["resource", "starting_date"]

    @property
    def project_name(self):
        """``Project_new`` is the current name; ``Project`` is the legacy column."""
        return self.project_new or self.project

    def __str__(self):
        return f"{self.source_id} - {self.resource} - {self.project_name}".strip()


class CatalogValue(models.Model):
    """Allowed values of the staffing catalog (industries, areas, locations)."""

    class Kind(models.TextChoices):
        INDUSTRY = "industry", "Industria"
        AREA = "area", "Offering (Organization Unit)"
        LOCATION = "location", "Localización"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    value = models.CharField(max_length=120)
    detail = models.CharField(max_length=120, blank=True, help_text="País (localizaciones).")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("kind", "value"), name="unique_catalog_value")
        ]
        ordering = ["kind", "id"]

    def __str__(self):
        return f"{self.kind}: {self.value}"


class CareerLevel(models.Model):
    """Career level from the catalog with its availability threshold.

    A person of this level is *not available* once the sum of their active
    assignments reaches ``unavailable_at_percent``.
    """

    name = models.CharField(max_length=120, unique=True)
    rank = models.PositiveSmallIntegerField(help_text="Valor del catálogo.")
    unavailable_at_percent = models.DecimalField(max_digits=5, decimal_places=1)

    class Meta:
        ordering = ["-rank"]

    def __str__(self):
        return f"{self.name} ({self.unavailable_at_percent}%)"


class CriterionMapping(models.Model):
    """Business-managed link between a demand area/offering and Staff data.

    Areas of the catalog are not a column of the Staff export, so the link must
    be explicit. Several rows with the same ``demand_value`` are combined with
    OR. ``role_prefix`` matches the start of ``Staff.role``.
    """

    class Criterion(models.TextChoices):
        OFFERING = "offering", "Offering / área"

    class StaffField(models.TextChoices):
        ROLE_PREFIX = "role_prefix", "Role (empieza por)"
        ORGANIZATION_UNIT = "organization_unit", "Organization Unit"
        TALENT_SEGMENT = "talent_segment", "Talent Segment"
        SUB_ALIGNMENT = "sub_alignment", "Sub-alignment"

    criterion = models.CharField(max_length=16, choices=Criterion.choices)
    demand_value = models.CharField(max_length=120)
    staff_field = models.CharField(max_length=32, choices=StaffField.choices)
    staff_value = models.CharField(max_length=160)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("criterion", "demand_value", "staff_field", "staff_value"),
                name="unique_criterion_mapping",
            )
        ]
        ordering = ["criterion", "demand_value", "staff_field", "staff_value"]

    def __str__(self):
        return f"{self.demand_value} -> {self.staff_field}={self.staff_value}"


class Demand(models.Model):
    code = models.CharField(max_length=32, primary_key=True)
    title = models.CharField(max_length=200)
    role = models.CharField(max_length=160, blank=True)
    industry = models.CharField(max_length=120)
    offering = models.CharField(max_length=120)
    occupancy = models.CharField(max_length=32)
    skills = models.JSONField(default=list, blank=True)
    seniority = models.CharField(max_length=80)
    location = models.CharField(max_length=120)
    modality = models.CharField(max_length=80)
    start_date = models.DateField()
    duration = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=80, default="Nueva")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"


class DemandCandidate(models.Model):
    class SearchStage(models.TextChoices):
        INITIAL = "initial", "Offering inicial"
        EXPANDED = "expanded", "Resto de offerings"
        TRANSVERSAL = "transversal", "Bolsa transversal"

    demand = models.ForeignKey(
        Demand, on_delete=models.CASCADE, related_name="candidate_selections"
    )
    staff = models.ForeignKey(
        Staff, on_delete=models.CASCADE, related_name="demand_selections"
    )
    search_stage = models.CharField(max_length=16, choices=SearchStage.choices)
    selected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("demand", "staff"), name="unique_staff_per_demand"
            )
        ]
        ordering = ["-selected_at"]

    def __str__(self):
        return f"{self.demand.code} - {self.staff.accenture_id}"
