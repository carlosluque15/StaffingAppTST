from django.db import migrations, models


def fill_career_counselor(apps, schema_editor):
    Staff = apps.get_model("api", "Staff")
    for staff in Staff.objects.all():
        value = (staff.source_data.get("Career Counselor") or "").strip()
        if value:
            staff.career_counselor = value
            staff.save(update_fields=["career_counselor"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_catalog_and_level_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="staff",
            name="career_counselor",
            field=models.CharField(blank=True, db_index=True, max_length=160),
        ),
        migrations.RunPython(fill_career_counselor, migrations.RunPython.noop),
    ]
