import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Assignment, Staff


STAFF_FIELDS = {
    "Accenture Id": "accenture_id",
    "Name": "name",
    "Surname": "surname",
    "Role": "role",
    "Career Level Group": "career_level_group",
    "Deployment City": "deployment_city",
    "Deployment Country": "deployment_country",
    "Organization Unit": "organization_unit",
    "Talent Segment": "talent_segment",
    "Sub-alignment": "sub_alignment",
    "Industry": "industry",
    "Resource FTE": "resource_fte",
}

ASSIGNMENT_FIELDS = {
    "Resource": "resource",
    "Project": "project",
    "Project_new": "project_new",
    "Client": "client",
    "Industry": "industry",
    "Sold": "sold",
    "Starting Date": "starting_date",
    "Finishing Date": "finishing_date",
    "Confirmed end": "confirmed_end",
    "Responsible": "responsible",
    "% Assignment": "assignment_percentage",
    "Comments": "comments",
}


class Command(BaseCommand):
    help = (
        "Import Staff.csv and every row of Assignments.csv (full history and future)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--staff-csv", required=True)
        parser.add_argument("--assignments-csv", required=True)
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Replace all existing staff and assignment rows.",
        )

    def handle(self, *args, **options):
        staff_rows = self._read_csv(
            options["staff_csv"], ("Accenture Id", "isDeletedText")
        )
        assignment_rows = self._read_csv(
            options["assignments_csv"],
            ("ID", "Sold", "Starting Date", "Finishing Date", "Confirmed end"),
        )
        self._check_unique_active_staff_ids(staff_rows)

        with transaction.atomic():
            if options["replace"]:
                Staff.objects.all().delete()
                Assignment.objects.all().delete()

            staff_created, deleted_staff = self._import_staff(staff_rows)
            assignments_created = self._import_assignments(assignment_rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(staff_rows)} staff rows "
                f"({staff_created} new, {deleted_staff} marked as deleted); "
                f"imported {len(assignment_rows)} assignments "
                f"({assignments_created} new)."
            )
        )

    def _read_csv(self, path, required_columns):
        try:
            with open(path, newline="", encoding="utf-8-sig") as source:
                reader = csv.DictReader(source)
                missing_columns = set(required_columns) - set(reader.fieldnames or [])
                if missing_columns:
                    raise CommandError(
                        f"{path} is missing required columns: "
                        + ", ".join(sorted(missing_columns))
                    )
                rows = list(reader)
        except OSError as error:
            raise CommandError(f"Could not read CSV file: {path}") from error

        if any(None in row for row in rows):
            raise CommandError(f"{path} contains a row with more values than headers.")
        return rows

    def _check_unique_active_staff_ids(self, rows):
        seen = set()
        for source_row, row in enumerate(rows, start=1):
            accenture_id = self._value(row, "Accenture Id").casefold()
            is_deleted = self._parse_bool(
                self._value(row, "isDeletedText"),
                f"Staff.csv row {source_row}: isDeletedText",
            )
            if is_deleted:
                continue
            if not accenture_id:
                raise CommandError(
                    f"Staff.csv row {source_row}: active staff without Accenture Id."
                )
            if accenture_id in seen:
                raise CommandError(
                    f"Staff.csv row {source_row}: duplicate Accenture Id among "
                    "active staff; it is the stable candidate identifier."
                )
            seen.add(accenture_id)

    def _import_staff(self, rows):
        created = 0
        deleted_count = 0
        for source_row, row in enumerate(rows, start=1):
            accenture_id = self._value(row, "Accenture Id")
            is_deleted = self._parse_bool(
                self._value(row, "isDeletedText"),
                f"Staff.csv row {source_row}: isDeletedText",
            )
            deleted_count += is_deleted
            defaults = {
                field: self._value(row, column)
                for column, field in STAFF_FIELDS.items()
                if field != "accenture_id"
            }
            defaults["source_data"] = row
            _, was_created = Staff.objects.update_or_create(
                source_row=source_row,
                defaults={
                    **defaults,
                    "accenture_id": accenture_id,
                    "is_deleted": is_deleted,
                },
            )
            created += was_created
        return created, deleted_count

    def _import_assignments(self, rows):
        created = 0
        for row in rows:
            source_id = self._value(row, "ID")
            if not source_id:
                raise CommandError("Assignments.csv contains a row without an ID.")
            defaults = {
                field: self._value(row, column)
                for column, field in ASSIGNMENT_FIELDS.items()
            }
            defaults["source_data"] = row
            defaults["starting_on"] = self._parse_date(defaults["starting_date"])
            defaults["finishing_on"] = self._parse_date(defaults["finishing_date"])
            defaults["assignment_percent"] = self._parse_percent(
                defaults["assignment_percentage"]
            )
            _, was_created = Assignment.objects.update_or_create(
                source_id=source_id,
                defaults=defaults,
            )
            created += was_created
        return created

    @staticmethod
    def _value(row, column):
        return (row.get(column) or "").strip()

    @staticmethod
    def _parse_bool(value, label):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
        raise CommandError(f"{label} must be a boolean value, got {value!r}.")

    @staticmethod
    def _parse_percent(value):
        text = value.strip().removesuffix("%").strip()
        return int(text) if text.isdigit() else None

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        for date_format in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        raise CommandError(f"Unrecognized assignment date: {value!r}.")
