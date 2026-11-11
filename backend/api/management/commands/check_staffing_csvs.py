from django.core.management.base import BaseCommand, CommandError

from api.management.commands.import_staffing_csvs import (
    ASSIGNMENT_FIELDS,
    STAFF_FIELDS,
    Command as ImportCommand,
)
from api.models import Assignment, Staff


class Command(BaseCommand):
    help = "Compare the database with Staff.csv and Assignments.csv (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--staff-csv", required=True)
        parser.add_argument("--assignments-csv", required=True)

    def handle(self, *args, **options):
        reader = ImportCommand()
        staff_rows = reader._read_csv(options["staff_csv"], ("Accenture Id", "isDeletedText"))
        assignment_rows = reader._read_csv(options["assignments_csv"], ("ID",))
        staff_rows, discarded = reader.dedupe_staff(staff_rows)
        for message in discarded:
            self.stdout.write(f"Duplicado esperado: {message}")
        problems = 0

        db_staff = {s.source_row: s for s in Staff.objects.all()}
        problems += self._report("Staff rows", len(staff_rows), len(db_staff))
        for number, row in staff_rows:
            obj = db_staff.get(number)
            if obj is None:
                continue
            expected = {f: reader._value(row, c) for c, f in STAFF_FIELDS.items()}
            expected["is_deleted"] = reader._parse_bool(
                reader._value(row, "isDeletedText"), f"Staff.csv row {number}"
            )
            problems += self._diff(f"Staff row {number}", obj, expected)

        db_assignments = {a.source_id: a for a in Assignment.objects.all()}
        csv_ids = {reader._value(r, "ID") for r in assignment_rows}
        problems += self._report("Assignments", len(assignment_rows), len(db_assignments))
        for missing in sorted(csv_ids - db_assignments.keys()):
            self.stdout.write(f"Assignment {missing}: in CSV, missing in DB")
            problems += 1
        for extra in sorted(db_assignments.keys() - csv_ids):
            self.stdout.write(f"Assignment {extra}: in DB, not in CSV")
            problems += 1
        for row in assignment_rows:
            obj = db_assignments.get(reader._value(row, "ID"))
            if obj is None:
                continue
            expected = {f: reader._value(row, c) for c, f in ASSIGNMENT_FIELDS.items()}
            problems += self._diff(f"Assignment {obj.source_id}", obj, expected)

        if problems:
            raise CommandError(
                f"{problems} difference(s) found; fix with "
                "import_staffing_csvs --replace."
            )
        self.stdout.write(self.style.SUCCESS("Database matches the CSV files."))

    def _report(self, label, csv_count, db_count):
        if csv_count == db_count:
            return 0
        self.stdout.write(f"{label}: CSV has {csv_count}, DB has {db_count}")
        return 1

    def _diff(self, label, obj, expected):
        count = 0
        for field, value in expected.items():
            if getattr(obj, field) != value:
                self.stdout.write(
                    f"{label}.{field}: CSV={value!r} DB={getattr(obj, field)!r}"
                )
                count += 1
        return count
