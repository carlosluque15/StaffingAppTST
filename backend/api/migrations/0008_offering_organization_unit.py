from django.db import migrations, models

OLD_AREAS = {
    "Enterprise Architecture": "Enterprise Architect",
    "Technology Strategy": "Technology Strategy",
    "Transformation Excellence": "Transformation Excellence",
}
# Main Organization Units of Staff.csv; the import adds any new value it finds.
ORG_UNITS = [
    "Industry Tech Strategy & Enterprise Arch",
    "Digital Foundations",
    "Strategic Technology Effectiveness",
    "Technology Transformation Delivery",
    "Technology Strategy & Transformation",
]


def to_organization_units(apps, schema_editor):
    CatalogValue = apps.get_model("api", "CatalogValue")
    CriterionMapping = apps.get_model("api", "CriterionMapping")
    CatalogValue.objects.filter(kind="area").delete()
    CriterionMapping.objects.filter(criterion="offering").delete()
    for unit in ORG_UNITS:
        CatalogValue.objects.get_or_create(kind="area", value=unit)
        CriterionMapping.objects.get_or_create(
            criterion="offering", demand_value=unit,
            staff_field="organization_unit", staff_value=unit,
        )


def to_role_areas(apps, schema_editor):
    CatalogValue = apps.get_model("api", "CatalogValue")
    CriterionMapping = apps.get_model("api", "CriterionMapping")
    CatalogValue.objects.filter(kind="area").delete()
    CriterionMapping.objects.filter(criterion="offering").delete()
    for area, prefix in OLD_AREAS.items():
        CatalogValue.objects.get_or_create(kind="area", value=area)
        CriterionMapping.objects.get_or_create(
            criterion="offering", demand_value=area,
            staff_field="role_prefix", staff_value=prefix,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_staff_career_counselor"),
    ]

    operations = [
        migrations.AlterField(
            model_name="demand",
            name="role",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AlterField(
            model_name="catalogvalue",
            name="kind",
            field=models.CharField(choices=[("industry", "Industria"), ("area", "Offering (Organization Unit)"), ("location", "Localización")], max_length=16),
        ),
        migrations.RunPython(to_organization_units, to_role_areas),
    ]
