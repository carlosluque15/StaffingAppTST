import json
import csv
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Assignment, CriterionMapping, Demand, DemandCandidate, Staff


class StaffingApiTests(TestCase):
    def create_demand(self, code="DEM-1001"):
        return Demand.objects.create(
            code=code,
            title="Data Engineer",
            role="Data Engineer",
            industry="Banca",
            offering="Data & AI",
            occupancy="100%",
            skills=["Python"],
            seniority="Senior",
            location="Madrid",
            modality="Híbrido",
            start_date="2026-12-01",
            duration="6 meses",
        )

    def test_lists_candidates_from_database(self):
        Staff.objects.create(
            source_row=1,
            accenture_id="A-1001",
            name="Ada",
            surname="Lovelace",
            role="Data Engineer",
            organization_unit="Data & AI",
            deployment_city="Madrid",
            resource_fte="1",
            career_level_group="Senior",
            source_data={"Email": "ada@example.com"},
        )

        response = self.client.get(reverse("candidates"))

        self.assertEqual(response.status_code, 200)
        candidate = response.json()["candidates"][0]
        self.assertEqual(candidate["id"], "A-1001")
        self.assertNotIn("email", json.dumps(candidate).lower())
        self.assertEqual(candidate["name"], "Ada Lovelace")
        self.assertEqual(candidate["resourceFte"], "1")
        self.assertNotIn("skills", candidate)

    def test_excludes_staff_marked_as_deleted(self):
        Staff.objects.create(
            source_row=1,
            accenture_id="A-1001",
            name="Former",
            surname="Employee",
            is_deleted=True,
        )

        response = self.client.get(reverse("candidates"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidates"], [])

    def test_lists_demands_from_database(self):
        Demand.objects.create(
            code="DEM-1001",
            title="Data Engineer",
            role="Data Engineer",
            industry="Banca",
            offering="Data & AI",
            occupancy="100%",
            skills=["Python"],
            seniority="Senior",
            location="Madrid",
            modality="Híbrido",
            start_date="2026-12-01",
            duration="6 meses",
        )

        response = self.client.get(reverse("demands"))

        self.assertEqual(response.status_code, 200)
        demand = response.json()["demands"][0]
        self.assertEqual(demand["id"], "DEM-1001")
        self.assertEqual(demand["startDate"], "2026-12-01")

    def test_creates_demand_in_database(self):
        payload = {
            "title": "Data Engineer para banca",
            "role": "Data Engineer",
            "industry": "Financial Services",
            "offering": "Digital Foundations",
            "location": "Madrid",
            "startDate": "2026-12-01",
            "skills": ["Python", "SQL"],
            "seniority": "Manager",
            "occupancy": "100%",
            "modality": "Híbrido",
            "duration": "6 meses",
            "description": "Proyecto de prueba",
        }

        response = self.client.post(
            reverse("demands"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["id"].startswith("DEM-"))
        self.assertEqual(Demand.objects.count(), 1)
        self.assertEqual(Demand.objects.get().skills, ["Python", "SQL"])

    def test_rejects_invalid_demand_payloads(self):
        responses = (
            self.client.post(
                reverse("demands"),
                data="{invalid json",
                content_type="application/json",
            ),
            self.client.post(
                reverse("demands"),
                data=json.dumps({"title": "Incomplete"}),
                content_type="application/json",
            ),
            self.client.post(
                reverse("demands"),
                data=json.dumps({
                    "title": "Demand",
                    "role": "Role",
                    "industry": "Industry",
                    "offering": "Offering",
                    "location": "Madrid",
                    "startDate": "not-a-date",
                    "skills": ["Python"],
                }),
                content_type="application/json",
            ),
        )

        self.assertEqual([response.status_code for response in responses], [400, 400, 400])
        self.assertEqual(Demand.objects.count(), 0)

    def test_updates_demand_fields_and_status(self):
        demand = self.create_demand()
        response = self.client.patch(
            reverse("demand-detail", args=[demand.code]),
            data=json.dumps({"status": "Búsqueda en curso", "title": "Updated title"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        demand.refresh_from_db()
        self.assertEqual(demand.title, "Updated title")
        self.assertEqual(demand.status, "Búsqueda en curso")

    def test_rejects_invalid_status_and_unknown_fields(self):
        demand = self.create_demand()
        invalid_status = self.client.patch(
            reverse("demand-detail", args=[demand.code]),
            data=json.dumps({"status": "Unknown"}),
            content_type="application/json",
        )
        unknown_field = self.client.patch(
            reverse("demand-detail", args=[demand.code]),
            data=json.dumps({"madeUp": True}),
            content_type="application/json",
        )

        self.assertEqual(invalid_status.status_code, 400)
        self.assertEqual(unknown_field.status_code, 400)
        demand.refresh_from_db()
        self.assertEqual(demand.status, "Nueva")

    def test_selected_candidates_no_longer_include_deleted_staff(self):
        demand = self.create_demand()
        staff = Staff.objects.create(
            source_row=42,
            accenture_id="A-1042",
            name="Ada",
            is_deleted=True,
        )
        DemandCandidate.objects.create(
            demand=demand,
            staff=staff,
            search_stage=DemandCandidate.SearchStage.INITIAL,
        )

        response = self.client.get(
            reverse("demand-candidates", args=[demand.code])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidates"], [])

    def test_deleting_demand_also_deletes_candidate_selections(self):
        demand = self.create_demand()
        staff = Staff.objects.create(source_row=1, accenture_id="A-1")
        DemandCandidate.objects.create(
            demand=demand,
            staff=staff,
            search_stage=DemandCandidate.SearchStage.INITIAL,
        )

        response = self.client.delete(reverse("demand-detail", args=[demand.code]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Demand.objects.filter(code=demand.code).exists())
        self.assertEqual(DemandCandidate.objects.count(), 0)


def post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


class SearchAndSelectionTests(TestCase):
    """Staged search, capacity rules and persisted selections (synthetic data)."""

    OU = "Technology Transformation Delivery"

    def setUp(self):
        self.today = timezone.localdate()
        self.demand = Demand.objects.create(
            code="DEM-1",
            title="Demand",
            role="Role",
            industry="Financial Services",
            offering="Technology Transformation Delivery",
            occupancy="50%",
            skills=["x"],
            seniority="Consultant",
            location="Madrid",
            modality="Híbrido",
            start_date=timezone.localdate(),
            duration="6 meses",
        )
        self.row = 0
        # Catalog, levels and offering mappings come from migration 0006.
        self.in_offering = self.make_staff("A-IN", organization_unit=self.OU)
        self.other = self.make_staff("A-OUT", organization_unit="Digital Foundations")
        self.deleted = self.make_staff(
            "A-DEL", organization_unit=self.OU, is_deleted=True
        )
        # Analyst of another Organization Unit -> Bolsa transversal.
        self.analyst = self.make_staff(
            "A-NONE", organization_unit="Digital Foundations",
            career_level_group="Analyst",
        )

    def make_staff(self, accenture_id, role="", **extra):
        self.row += 1
        values = {
            "source_row": self.row,
            "accenture_id": accenture_id,
            "name": "Name" + accenture_id,
            "role": role,
            "deployment_city": "Madrid",
            "resource_fte": "1",
            "career_level_group": "Consultant",
            "industry": "Financial Services",
        }
        values.update(extra)
        return Staff.objects.create(**values)

    def assign(self, staff, percent, days_left=30, **extra):
        values = {
            "source_id": f"S{Assignment.objects.count()}",
            "resource": staff.accenture_id,
            "sold": "True",
            "confirmed_end": "False",
            "starting_on": self.today - timedelta(days=10),
            "finishing_on": self.today + timedelta(days=days_left),
            "assignment_percent": percent,
        }
        values.update(extra)
        return Assignment.objects.create(**values)

    def search(self, stage="initial", demand=None):
        demand = demand or self.demand
        return self.client.get(
            reverse("demand-search", args=[demand.code]), {"stage": stage}
        )

    def ids(self, response):
        return [item["id"] for item in response.json()["candidates"]]

    def test_stages_are_disjoint_and_other_unit_analysts_go_to_transversal_pool(self):
        first = self.search("initial").json()
        second = self.search("expanded").json()

        self.assertEqual(self.ids(self.search("initial")), ["A-IN"])
        self.assertEqual(self.ids(self.search("expanded")), ["A-OUT"])
        for data in (first, second):
            self.assertEqual(data["transversal"]["name"], "Bolsa transversal")
            self.assertEqual([c["id"] for c in data["transversal"]["candidates"]], ["A-NONE"])
            self.assertEqual(data["transversal"]["candidates"][0]["searchStage"], "transversal")
        everyone = (
            self.ids(self.search("initial")) + self.ids(self.search("expanded"))
            + ["A-NONE"]
        )
        self.assertNotIn("A-DEL", everyone)
        self.assertEqual(len(everyone), len(set(everyone)))

    def test_transversal_analyst_ignores_demand_seniority_and_capacity_applies(self):
        self.demand.seniority = "Manager"
        self.demand.save()
        self.assertEqual(
            [c["id"] for c in self.search().json()["transversal"]["candidates"]],
            ["A-NONE"],
        )
        self.assign(self.analyst, 80)
        self.assertEqual(self.search().json()["transversal"]["candidates"], [])
        # An analyst of the demand unit is initial, never transversal.
        self.make_staff("A-OWN", organization_unit=self.OU, career_level_group="Analyst")
        data = self.search("expanded").json()
        self.assertNotIn("A-OWN", [c["id"] for c in data["transversal"]["candidates"]])

    def test_demand_role_is_optional(self):
        payload = {
            "title": "T", "industry": "Financial Services",
            "offering": "Digital Foundations", "location": "Madrid",
            "startDate": "2026-12-01", "skills": ["x"], "seniority": "Manager",
            "occupancy": "100%",
            "modality": "Remoto", "duration": "6 meses",
        }
        response = post_json(self.client, reverse("demands"), payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], "")

    def test_search_blocked_without_offering_mapping(self):
        CriterionMapping.objects.all().delete()

        response = self.search()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "offering_mapping_missing")

    def test_invalid_stage_and_unknown_demand(self):
        self.assertEqual(self.search("later").status_code, 400)
        self.assertEqual(
            self.client.get(reverse("demand-search", args=["DEM-NOPE"])).status_code, 404
        )

    def test_capacity_uses_active_assignments_at_reference_date(self):
        self.assign(self.in_offering, 60)
        data = self.search().json()
        self.assertEqual(data["candidates"], [])
        self.assertEqual(data["excluded"], {"insufficientCapacity": 1})

        self.demand.occupancy = "40%"
        self.demand.save()
        candidate = self.search().json()["candidates"][0]
        self.assertEqual(candidate["assignedPercent"], 60)
        self.assertEqual(candidate["availablePercent"], 40)

    def test_assignments_add_up_and_level_threshold_marks_unavailable(self):
        self.assign(self.in_offering, 100)
        self.assign(self.in_offering, 50)
        self.demand.occupancy = "Flexible"
        self.demand.save()

        data = self.search().json()

        self.assertEqual(data["candidates"], [])
        self.assertEqual(data["excluded"], {"levelUnavailable": 1})

    def test_each_level_uses_its_own_unavailability_threshold(self):
        self.in_offering.career_level_group = "Manager"
        self.in_offering.save()
        self.demand.seniority = "Manager"
        self.demand.occupancy = "Flexible"
        self.demand.save()

        self.assign(self.in_offering, 85)
        candidate = self.search().json()["candidates"][0]
        self.assertEqual(candidate["unavailableAtPercent"], 85.6)

        self.assign(self.in_offering, 1)
        self.assertEqual(self.ids(self.search()), [])

    def test_ended_unsold_and_confirmed_assignments_are_ignored(self):
        self.assign(self.in_offering, 100, days_left=-1)
        self.assign(self.in_offering, 100, sold="False")
        self.assign(self.in_offering, 100, confirmed_end="True")

        self.assertEqual(self.ids(self.search()), ["A-IN"])

    def test_availability_horizon_counts_assignments_ending_before_it(self):
        self.assign(self.in_offering, 100, days_left=20)

        self.assertEqual(self.ids(self.search()), [])
        self.demand.start_date = self.today + timedelta(days=30)
        self.demand.save()
        self.assertEqual(self.ids(self.search()), ["A-IN"])

    def test_fte_limits_capacity_and_unknown_fte_is_reported(self):
        self.in_offering.resource_fte = "0.6"
        self.in_offering.save()
        self.demand.occupancy = "80%"
        self.demand.save()
        self.assertEqual(self.ids(self.search()), [])

        self.in_offering.resource_fte = "n/a"
        self.in_offering.save()
        data = self.search().json()
        self.assertEqual(data["candidates"], [])
        self.assertEqual(data["excluded"], {"unknownCapacity": 1})

    def test_location_filter_and_remote_demands(self):
        self.in_offering.deployment_city = "Bilbao"
        self.in_offering.save()
        self.assertEqual(self.ids(self.search()), [])

        self.demand.location = "Remoto"
        self.demand.save()
        self.assertEqual(self.ids(self.search()), ["A-IN"])

    def test_seniority_and_industry_filters_use_catalog_values(self):
        self.demand.seniority = "Manager"
        self.demand.save()
        self.assertEqual(self.ids(self.search()), [])

        self.demand.seniority = "Consultant"
        self.demand.save()
        self.assertEqual(self.ids(self.search()), ["A-IN"])

        self.demand.industry = "Resources"
        self.demand.save()
        self.assertEqual(self.search().json()["excluded"], {"industry": 1})
        self.assertEqual(self.ids(self.search()), [])

        self.in_offering.industry = ""
        self.demand.industry = "Financial Services"
        self.demand.save()
        self.in_offering.save()
        # No known industry: kept and flagged, not excluded.
        self.assertEqual(self.ids(self.search()), ["A-IN"])
        self.assertFalse(self.search().json()["candidates"][0]["industryKnown"])
        self.assign(self.in_offering, 10, industry="Resources")
        self.assertEqual(self.ids(self.search()), [])
        self.assertEqual(self.search().json()["excluded"], {"industry": 1})
        self.in_offering.industry = "Financial Services"
        self.in_offering.save()
        self.assertEqual(self.ids(self.search()), ["A-IN"])
        self.assertTrue(self.search().json()["candidates"][0]["industryKnown"])

    def test_candidate_without_any_assignment_is_flagged(self):
        candidate = self.search().json()["candidates"][0]
        self.assertFalse(candidate["assignmentDataKnown"])
        self.assertEqual(candidate["assignedPercent"], 0)
        self.assign(self.in_offering, 10)
        candidate = self.search().json()["candidates"][0]
        self.assertTrue(candidate["assignmentDataKnown"])

    def test_catalog_endpoint_lists_levels_with_thresholds(self):
        data = self.client.get(reverse("catalog")).json()

        self.assertIn("Financial Services", data["industries"])
        self.assertIn("Digital Foundations", data["areas"])
        self.assertIn("Technology Strategy & Transformation", data["areas"])
        self.assertEqual([x["value"] for x in data["locations"]], ["Madrid", "Barcelona", "Bilbao"])
        thresholds = {x["name"]: x["unavailableAtPercent"] for x in data["levels"]}
        self.assertEqual(thresholds["Manager"], 85.6)
        self.assertEqual(thresholds["Accenture Leadership"], 46)

    def test_select_persists_server_stage_and_prevents_duplicates(self):
        url = reverse("demand-candidates", args=[self.demand.code])

        created = post_json(self.client, url, {"staffId": "A-OUT"})
        again = post_json(self.client, url, {"staffId": "A-OUT", "searchStage": "expanded"})

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["searchStage"], "expanded")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(self.demand.candidate_selections.count(), 1)
        listed = self.client.get(url).json()["candidates"]
        self.assertEqual([item["id"] for item in listed], ["A-OUT"])
        flags = {
            item["id"]: item["selected"]
            for item in self.search("expanded").json()["candidates"]
        }
        self.assertEqual(flags, {"A-OUT": True})

    def test_transversal_candidate_is_selectable_from_any_stage(self):
        url = reverse("demand-candidates", args=[self.demand.code])

        response = post_json(self.client, url, {"staffId": "A-NONE", "searchStage": "transversal"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["searchStage"], "transversal")
        for stage in ("initial", "expanded"):
            pool = self.search(stage).json()["transversal"]["candidates"]
            self.assertTrue(pool[0]["selected"])

    def test_select_rejects_wrong_stage_deleted_unknown_and_bad_payloads(self):
        url = reverse("demand-candidates", args=[self.demand.code])
        cases = [
            ({"staffId": "A-IN", "searchStage": "expanded"}, 400),
            ({"staffId": "A-DEL"}, 404),
            ({"staffId": "NOPE"}, 404),
            ({"staffId": 5}, 400),
            ({"staffId": "A-IN", "searchStage": "later"}, 400),
            ({}, 400),
        ]
        for payload, status in cases:
            with self.subTest(payload=payload):
                self.assertEqual(post_json(self.client, url, payload).status_code, status)
        self.assertEqual(DemandCandidate.objects.count(), 0)
        self.assertEqual(
            self.client.post(url, data="{bad", content_type="application/json").status_code,
            400,
        )

    def test_select_blocked_without_mapping_and_ambiguous_ids(self):
        url = reverse("demand-candidates", args=[self.demand.code])
        self.make_staff("A-IN", organization_unit="Digital Foundations")
        self.assertEqual(post_json(self.client, url, {"staffId": "A-IN"}).status_code, 409)

        CriterionMapping.objects.all().delete()
        self.assertEqual(post_json(self.client, url, {"staffId": "A-OUT"}).status_code, 409)

    def test_status_transitions_follow_selections(self):
        url = reverse("demand-candidates", args=[self.demand.code])
        post_json(self.client, url, {"staffId": "A-IN"})
        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, "En revisión")

        post_json(self.client, url, {"staffId": "A-OUT"})
        self.client.delete(reverse("demand-candidate-detail", args=[self.demand.code, "A-IN"]))
        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, "En revisión")

        removed = self.client.delete(
            reverse("demand-candidate-detail", args=[self.demand.code, "A-OUT"])
        )
        self.assertEqual(removed.status_code, 204)
        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, "Búsqueda en curso")
        missing = self.client.delete(
            reverse("demand-candidate-detail", args=[self.demand.code, "A-OUT"])
        )
        self.assertEqual(missing.status_code, 404)

    def test_closed_demands_reject_selection_changes(self):
        url = reverse("demand-candidates", args=[self.demand.code])
        post_json(self.client, url, {"staffId": "A-IN"})
        for status in ("Cubierta", "Cancelada"):
            self.demand.status = status
            self.demand.save()
            with self.subTest(status=status):
                self.assertEqual(post_json(self.client, url, {"staffId": "A-OUT"}).status_code, 409)
                self.assertEqual(
                    self.client.delete(
                        reverse("demand-candidate-detail", args=[self.demand.code, "A-IN"])
                    ).status_code,
                    409,
                )
        self.assertEqual(self.demand.candidate_selections.count(), 1)

    def test_demand_validation_for_dates_availability_and_occupancy(self):
        base = {
            "title": "T", "role": "R", "industry": "Financial Services",
            "offering": "Digital Foundations",
            "location": "Madrid", "startDate": "2026-12-01", "skills": ["x"],
            "seniority": "Manager", "occupancy": "100%",
            "modality": "Remoto", "duration": "6 meses",
        }
        for override in (
            {"startDate": "2026-13-45"},
            {"occupancy": "150%"},
            {"occupancy": "abc"},
            {"skills": "Python"},
            {"industry": "Banca"},
            {"offering": "Data & AI"},
            {"seniority": "Senior"},
            {"location": "Valencia"},
        ):
            with self.subTest(override=override):
                response = post_json(self.client, reverse("demands"), {**base, **override})
                self.assertEqual(response.status_code, 400)
        ok = post_json(self.client, reverse("demands"), {**base, "occupancy": "Flexible"})
        self.assertEqual(ok.status_code, 201)

    def test_demand_can_be_created_without_skills(self):
        payload = {
            "title": "T", "role": "R", "industry": "Financial Services",
            "offering": "Digital Foundations", "location": "Madrid",
            "startDate": "2026-12-01", "seniority": "Manager",
            "occupancy": "100%", "modality": "Remoto", "duration": "6 meses",
        }
        response = post_json(self.client, reverse("demands"), payload)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["skills"], [])

    def test_demand_detail_get_and_not_found(self):
        self.assertEqual(
            self.client.get(reverse("demand-detail", args=[self.demand.code])).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("demand-detail", args=["DEM-NOPE"])).status_code, 404
        )
        self.assertEqual(
            self.client.delete(reverse("demand-detail", args=["DEM-NOPE"])).status_code, 404
        )


class CsvImportTests(TestCase):
    def test_imports_staff_and_assignments_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            staff_csv = Path(directory) / "Staff.csv"
            assignments_csv = Path(directory) / "Assignments.csv"

            with staff_csv.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "Accenture Id", "Name", "Surname", "Email", "isDeletedText"
                    ],
                )
                writer.writeheader()
                writer.writerows([
                    {
                        "Accenture Id": "A-100",
                        "Name": "Ada",
                        "Surname": "Lovelace",
                        "Email": "ada@example.com",
                        "isDeletedText": "no",
                    },
                    {
                        "Accenture Id": "A-100",
                        "Name": "Grace",
                        "Surname": "Hopper",
                        "Email": "grace@example.com",
                        "isDeletedText": "yes",
                    },
                ])

            today = timezone.localdate()
            active_start = (today - timedelta(days=1)).strftime("%m/%d/%Y")
            active_end = (today + timedelta(days=1)).strftime("%m/%d/%Y")
            past_date = (today - timedelta(days=10)).strftime("%m/%d/%Y")
            with assignments_csv.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "ID", "Resource", "Project", "Sold",
                        "Starting Date", "Finishing Date", "Confirmed end",
                        "% Assignment",
                    ],
                )
                writer.writeheader()
                writer.writerows([
                    {
                        "ID": "500",
                        "Resource": "A-100",
                        "Project": "Current",
                        "Sold": "True",
                        "Starting Date": active_start,
                        "Finishing Date": active_end,
                        "Confirmed end": "False",
                        "% Assignment": "70%",
                    },
                    {
                        "ID": "501",
                        "Resource": "A-100",
                        "Project": "Not sold",
                        "Sold": "False",
                        "Starting Date": active_start,
                        "Finishing Date": active_end,
                        "Confirmed end": "False",
                    },
                    {
                        "ID": "502",
                        "Resource": "A-100",
                        "Project": "Ended",
                        "Sold": "True",
                        "Starting Date": past_date,
                        "Finishing Date": past_date,
                        "Confirmed end": "False",
                    },
                    {
                        "ID": "503",
                        "Resource": "A-100",
                        "Project": "End confirmed",
                        "Sold": "True",
                        "Starting Date": active_start,
                        "Finishing Date": active_end,
                        "Confirmed end": "True",
                    },
                ])

            for _ in range(2):
                call_command(
                    "import_staffing_csvs",
                    staff_csv=str(staff_csv),
                    assignments_csv=str(assignments_csv),
                    stdout=None,
                )

        self.assertEqual(Staff.objects.count(), 2)
        self.assertEqual(Staff.objects.filter(is_deleted=True).count(), 1)
        self.assertEqual(Assignment.objects.count(), 4)
        current = Assignment.objects.get(source_id="500")
        self.assertEqual(current.assignment_percent, 70)
        self.assertEqual(current.starting_on, today - timedelta(days=1))
        self.assertEqual(
            list(Staff.objects.order_by("source_row").values_list("name", flat=True)),
            ["Ada", "Grace"],
        )
        self.assertEqual(
            Staff.objects.get(name="Ada").source_data["Email"],
            "ada@example.com",
        )


    def _import(self, staff_text):
        from io import StringIO

        err = StringIO()
        with tempfile.TemporaryDirectory() as directory:
            staff_csv = Path(directory) / "Staff.csv"
            assignments_csv = Path(directory) / "Assignments.csv"
            staff_csv.write_text(staff_text)
            assignments_csv.write_text(
                "ID,Sold,Starting Date,Finishing Date,Confirmed end\n"
            )
            call_command(
                "import_staffing_csvs",
                staff_csv=str(staff_csv),
                assignments_csv=str(assignments_csv),
                stdout=StringIO(),
                stderr=err,
            )
        return err.getvalue()

    def test_duplicate_active_ids_import_one_row_with_warning(self):
        warnings = self._import(
            "Accenture Id,Surname,Role,isDeletedText\n"
            "A-1,Russo Bertolez,Analyst,no\n"
            "a-1,Russo,,no\n"
        )
        self.assertEqual(Staff.objects.count(), 1)
        # Most filled columns wins.
        self.assertEqual(Staff.objects.get().surname, "Russo Bertolez")
        self.assertIn("duplicado", warnings)

    def test_active_staff_without_id_is_skipped_with_warning(self):
        warnings = self._import(
            "Accenture Id,Surname,isDeletedText\n,Nobody,no\nA-2,Ok,no\n"
        )
        self.assertEqual(list(Staff.objects.values_list("accenture_id", flat=True)), ["A-2"])
        self.assertIn("sin Accenture Id", warnings)


class AvailabilityTests(SearchAndSelectionTests):
    """Per-person occupancy and the availability endpoint."""

    def url(self, staff_id):
        return reverse("staff-availability", args=[staff_id])

    def occ(self, staff, on_date=None):
        from .availability import occupancy

        return occupancy(staff, on_date or self.today)

    def test_sums_overlapping_assignments(self):
        self.assign(self.in_offering, 30)
        self.assign(self.in_offering, 20)
        info = self.occ(self.in_offering)
        self.assertEqual(info["assignedPercent"], 50)
        self.assertEqual(info["capacityPercent"], 100)
        self.assertEqual(info["availablePercent"], 50)

    def test_available_never_negative(self):
        self.assign(self.in_offering, 80)
        self.assign(self.in_offering, 50)
        self.assertEqual(self.occ(self.in_offering)["availablePercent"], 0)

    def test_partial_fte(self):
        staff = self.make_staff("A-PART", resource_fte="0.6")
        self.assign(staff, 20)
        info = self.occ(staff)
        self.assertEqual(info["capacityPercent"], 60)
        self.assertEqual(info["availablePercent"], 40)

    def test_unparseable_fte_and_percent(self):
        bad_fte = self.make_staff("A-BADFTE", resource_fte="x")
        self.assertIsNone(self.occ(bad_fte)["availablePercent"])
        self.assertTrue(self.occ(bad_fte)["unknown"])
        self.assign(self.in_offering, None)
        info = self.occ(self.in_offering)
        self.assertIsNone(info["assignedPercent"])
        self.assertIsNone(info["availablePercent"])

    def test_inactive_assignments_are_ignored(self):
        self.assign(self.in_offering, 10, sold="False")
        self.assign(self.in_offering, 10, confirmed_end="True")
        self.assign(self.in_offering, 10, starting_on=self.today - timedelta(days=50),
                    finishing_on=self.today - timedelta(days=20))
        self.assign(self.in_offering, 10, starting_on=self.today + timedelta(days=5),
                    finishing_on=self.today + timedelta(days=30))
        self.assertEqual(self.occ(self.in_offering)["assignedPercent"], 0)

    def test_future_assignment_counts_at_horizon(self):
        self.assign(self.in_offering, 100, starting_on=self.today + timedelta(days=60),
                    finishing_on=self.today + timedelta(days=200))
        self.assertEqual(self.occ(self.in_offering)["availablePercent"], 100)
        self.assertEqual(
            self.occ(self.in_offering, self.today + timedelta(days=90))["availablePercent"], 0
        )
        self.demand.start_date = self.today + timedelta(days=90)
        self.demand.save()
        self.assertEqual(self.ids(self.search()), [])

    def test_resource_case_insensitive(self):
        self.assign(self.in_offering, 40, resource="a-in")
        self.assertEqual(self.occ(self.in_offering)["assignedPercent"], 40)

    def test_endpoint(self):
        self.assign(self.in_offering, 40)
        data = self.client.get(self.url("A-IN")).json()
        self.assertEqual(data["assignedPercent"], 40)
        self.assertEqual(data["availablePercent"], 60)
        self.assertEqual(len(data["assignments"]), 1)
        self.assertTrue(data["timeline"])
        self.assertIsNotNone(data["unavailableAtPercent"])
        later = self.today + timedelta(days=100)
        data = self.client.get(self.url("A-IN"), {"date": later.isoformat()}).json()
        self.assertEqual(data["assignedPercent"], 0)

    def test_endpoint_errors(self):
        self.assertEqual(self.client.get(self.url("NOPE")).status_code, 404)
        self.assertEqual(self.client.get(self.url("A-DEL")).status_code, 404)
        self.assertEqual(self.client.get(self.url("A-IN"), {"date": "bad"}).status_code, 400)
        self.assertEqual(
            self.client.get(self.url("A-IN"), {"date": "2026-13-45"}).status_code, 400
        )


class CompleteDemandTests(SearchAndSelectionTests):
    """Completing a demand registers its selected people as assignments."""

    def complete(self, body=None, demand=None):
        return self.client.post(
            reverse("demand-complete", args=[(demand or self.demand).code]),
            json.dumps({"client": "Cliente", **(body or {})}),
            content_type="application/json",
        )

    def select(self, staff):
        DemandCandidate.objects.create(
            demand=self.demand, staff=staff, search_stage="initial"
        )

    def test_requires_selected_candidates(self):
        self.assertEqual(self.complete().status_code, 409)
        self.assertEqual(Assignment.objects.count(), 0)

    def test_creates_assignment_and_closes_demand(self):
        self.demand.start_date = "2026-12-15"
        self.demand.duration = "6 meses"
        self.demand.save()
        self.select(self.in_offering)
        response = self.complete()
        self.assertEqual(response.status_code, 201)
        assignment = Assignment.objects.get()
        self.assertEqual(assignment.resource, "A-IN")
        self.assertEqual(assignment.assignment_percent, 50)
        self.assertEqual(assignment.project_new, "Demand")
        self.assertEqual(assignment.project, "")
        self.assertEqual(assignment.source_id, "1")
        self.assertEqual(assignment.starting_date, "12/15/2026")
        self.assertEqual(assignment.comments, "")
        self.assertEqual(assignment.source_data["Created By"], "Staffing app")
        self.assertEqual(str(assignment.starting_on), "2026-12-15")
        self.assertEqual(str(assignment.finishing_on), "2027-06-14")
        self.assertEqual(assignment.sold, "True")
        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, "Cubierta")
        # The new assignment now counts for availability.
        from .availability import occupancy
        from datetime import date

        info = occupancy(self.in_offering, date(2027, 1, 10))
        self.assertEqual(info["assignedPercent"], 50)
        self.assertEqual(self.complete().status_code, 409)
        self.assertEqual(Assignment.objects.count(), 1)

    def test_open_ended_and_flexible(self):
        self.demand.duration = "Indefinida"
        self.demand.occupancy = "Flexible"
        self.demand.start_date = "2026-12-15"
        self.demand.save()
        self.assign(self.in_offering, 30, finishing_on=self.today + timedelta(days=900))
        self.select(self.in_offering)
        self.assertEqual(self.complete().status_code, 201)
        created = Assignment.objects.get(resource="A-IN", project_new="Demand")
        self.assertEqual(created.assignment_percent, 70)
        self.assertEqual(str(created.finishing_on), "2099-12-31")

    def test_staff_ids_subset_and_not_found(self):
        self.select(self.in_offering)
        self.select(self.other)
        self.assertEqual(self.complete({"staffIds": ["A-OUT"]}).status_code, 201)
        self.assertEqual(
            list(Assignment.objects.values_list("resource", flat=True)), ["A-OUT"]
        )
        missing = self.complete(demand=Demand(code="NOPE"))
        self.assertEqual(missing.status_code, 404)

    def test_edit_demand_with_patch(self):
        response = self.client.patch(
            reverse("demand-detail", args=[self.demand.code]),
            json.dumps({"title": "Nuevo título", "occupancy": "80%"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.demand.refresh_from_db()
        self.assertEqual((self.demand.title, self.demand.occupancy), ("Nuevo título", "80%"))

    def test_complete_with_form_data_and_preview(self):
        self.select(self.in_offering)
        preview = self.client.get(reverse("demand-complete", args=[self.demand.code])).json()
        self.assertEqual(preview["defaults"]["project"], "Demand")
        self.assertIn("A-IN", [p["id"] for p in preview["responsibles"]])
        self.assertEqual(preview["candidates"][0]["id"], "A-IN")
        self.assertEqual(self.complete({"responsible": "nadie", "client": "X"}).status_code, 400)
        self.assertEqual(self.complete({"client": ""}).status_code, 400)
        bad = self.complete({"assignmentPercent": 150, "client": "BBVA", "finishingOn": "2020-01-01",
                             "startingOn": "2026-12-01"})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(Assignment.objects.count(), 0)
        ok = self.complete({
            "project": "Proyecto X", "client": "BBVA", "responsible": "a-out",
            "assignmentPercent": 40, "startingOn": "2026-12-01",
            "finishingOn": "2027-03-31", "comments": "ok",
        })
        self.assertEqual(ok.status_code, 201)
        a = Assignment.objects.get()
        self.assertEqual((a.project_new, a.client, a.responsible, a.assignment_percent),
                         ("Proyecto X", "BBVA", "A-OUT", 40))
        self.assertEqual(str(a.finishing_on), "2027-03-31")


    def test_sold_and_confirmed_end_are_persisted_and_validated(self):
        self.select(self.in_offering)
        self.assertEqual(self.complete({"sold": "yes"}).status_code, 400)
        self.assertEqual(self.complete({"confirmedEnd": 1}).status_code, 400)
        self.assertEqual(Assignment.objects.count(), 0)
        ok = self.complete({"sold": False, "confirmedEnd": True})
        self.assertEqual(ok.status_code, 201)
        a = Assignment.objects.get()
        self.assertEqual((a.sold, a.confirmed_end), ("False", "True"))


class MentorTests(TestCase):
    def person(self, aid, counselor="", deleted=False, row=[0]):
        row[0] += 1
        return Staff.objects.create(
            source_row=row[0], accenture_id=aid, name=aid, career_counselor=counselor,
            is_deleted=deleted, resource_fte="1",
        )

    def test_mentors_and_mentees(self):
        self.person("boss.one")
        self.person("gone.boss", deleted=True)
        self.person("a", "Boss.One@accenture.com")
        self.person("b", " boss.one ")
        self.person("c", "ghost.id")
        self.person("d", "gone.boss")
        self.person("e")
        self.person("f", "boss.one", deleted=True)
        data = {m["id"]: m for m in self.client.get(reverse("mentors")).json()["mentors"]}
        self.assertEqual(data["boss.one"]["menteeCount"], 2)
        self.assertTrue(data["boss.one"]["found"])
        self.assertFalse(data["ghost.id"]["found"])
        self.assertTrue(data["gone.boss"]["deleted"])
        self.assertEqual(data["_none"]["menteeCount"], 2)
        mentees = self.client.get(reverse("mentor-mentees", args=["boss.one"])).json()["mentees"]
        self.assertEqual(sorted(m["id"] for m in mentees), ["a", "b"])
        self.assertTrue(all(m["assignmentDataKnown"] is False for m in mentees))
        Assignment.objects.create(
            source_id="as-a", resource="A", assignment_percent=50,
            sold="True", confirmed_end="False",
        )
        mentees = self.client.get(reverse("mentor-mentees", args=["boss.one"])).json()["mentees"]
        self.assertEqual({m["id"]: m["assignmentDataKnown"] for m in mentees}, {"a": True, "b": False})
        none = self.client.get(reverse("mentor-mentees", args=["_none"])).json()
        self.assertEqual(sorted(m["id"] for m in none["mentees"]), ["boss.one", "e"])
        self.assertEqual(
            self.client.get(reverse("mentor-mentees", args=["nobody"])).status_code, 404
        )


class TalentTests(TestCase):
    def person(self, aid, deleted=False, row=[1000]):
        row[0] += 1
        return Staff.objects.create(
            source_row=row[0], accenture_id=aid, name=aid, is_deleted=deleted,
            resource_fte="1",
        )

    def test_talent_lists_active_with_availability(self):
        busy = self.person("busy")
        self.person("free")
        self.person("gone", deleted=True)
        self.person("")
        today = timezone.localdate()
        Assignment.objects.create(
            source_id="as-1", resource="busy", assignment_percent=40,
            starting_on=today - timedelta(days=5), finishing_on=today + timedelta(days=5),
            sold="True", confirmed_end="False",
        )
        data = self.client.get(reverse("talent")).json()["talent"]
        by_id = {p["id"]: p for p in data}
        self.assertEqual(sorted(by_id), ["busy", "free"])
        self.assertEqual(by_id["busy"]["availablePercent"], 60)
        self.assertEqual(by_id["busy"]["assignedPercent"], 40)
        self.assertEqual(by_id["free"]["availablePercent"], 100)
        self.assertTrue(by_id["busy"]["assignmentDataKnown"])
        self.assertFalse(by_id["free"]["assignmentDataKnown"])

    def test_talent_required_percent_by_level(self):
        from .models import CareerLevel
        CareerLevel.objects.update_or_create(name="Analyst", defaults={"rank": 1, "unavailable_at_percent": 100})
        CareerLevel.objects.update_or_create(name="Manager", defaults={"rank": 2, "unavailable_at_percent": "85.6"})
        today = timezone.localdate()
        for aid, level, pct in [("an", "Analyst", 100), ("mg", "Manager", 50), ("xx", "Otro", 10)]:
            person = self.person(aid)
            person.career_level_group = level
            person.save()
            Assignment.objects.create(
                source_id=f"as-{aid}", resource=aid, assignment_percent=pct,
                starting_on=today - timedelta(days=5), finishing_on=today + timedelta(days=5),
                sold="True", confirmed_end="False",
            )
        by_id = {p["id"]: p for p in self.client.get(reverse("talent")).json()["talent"]}
        self.assertEqual(by_id["an"]["requiredPercent"], 100)
        self.assertTrue(by_id["an"]["meetsRequired"])
        self.assertEqual(by_id["mg"]["requiredPercent"], 85.6)
        self.assertFalse(by_id["mg"]["meetsRequired"])
        self.assertIsNone(by_id["xx"]["requiredPercent"])
        self.assertIsNone(by_id["xx"]["meetsRequired"])


class ReportTests(TestCase):
    def setUp(self):
        Staff.objects.create(source_row=1, name="Ana", source_data={"Name": "Ana", "Role": "Analista, Sr", "isDeletedText": "No"})
        Staff.objects.create(source_row=2, is_deleted=True, source_data={"Name": "José", "Role": "=cmd()", "isDeletedText": "Yes"})
        Assignment.objects.create(source_id="1", source_data={"ID": "1", "Pct": "-50"})
        Assignment.objects.create(source_id="2", source_data={"ID": "2", "Pct": "100%"})

    def test_staff_export(self):
        response = self.client.get(reverse("report-staff"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("staff.csv", response["Content-Disposition"])
        text = response.content.decode("utf-8-sig")
        rows = list(csv.reader(text.splitlines()))
        self.assertEqual(rows[0], ["Name", "Role", "isDeletedText"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][1], "Analista, Sr")
        self.assertEqual(rows[2][0], "José")
        self.assertEqual(rows[2][1], "'=cmd()")

    def test_assignments_export(self):
        response = self.client.get(reverse("report-assignments"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("assignments.csv", response["Content-Disposition"])
        rows = list(csv.reader(response.content.decode("utf-8-sig").splitlines()))
        self.assertEqual(rows[0], ["ID", "Pct"])
        self.assertEqual([row[1] for row in rows[1:]], ["-50", "100%"])


class AssignmentsViewTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.n = 2000

    def person(self, aid, level="Manager", industry="", deleted=False):
        self.n += 1
        return Staff.objects.create(
            source_row=self.n, accenture_id=aid, name=aid, is_deleted=deleted,
            career_level_group=level, industry=industry,
        )

    def assign(self, sid, resource, start=-5, end=5, sold="True", confirmed="False", **extra):
        return Assignment.objects.create(
            source_id=sid, resource=resource, assignment_percent=50, sold=sold,
            confirmed_end=confirmed,
            starting_on=self.today + timedelta(days=start),
            finishing_on=self.today + timedelta(days=end), **extra,
        )

    def get(self, scope=None):
        url = reverse("assignments") + (f"?scope={scope}" if scope else "")
        return {a["id"]: a for a in self.client.get(url).json()["assignments"]}

    def test_active_excludes_ended_unsold_confirmed_and_deleted(self):
        self.person("ok")
        self.person("gone", deleted=True)
        self.assign("a-ok", "ok")
        self.assign("a-old", "ok", start=-20, end=-10)
        self.assign("a-unsold", "ok", sold="False")
        self.assign("a-conf", "ok", confirmed="True")
        self.assign("a-gone", "gone")
        self.assertEqual(list(self.get()), ["a-ok"])

    def test_all_includes_everything_with_flags(self):
        self.person("gone", deleted=True)
        self.assign("a-gone", "gone")
        self.assign("a-old", "gone", start=-20, end=-10)
        rows = self.get("all")
        self.assertEqual(sorted(rows), ["a-gone", "a-old"])
        self.assertTrue(rows["a-gone"]["personDeleted"])
        self.assertTrue(rows["a-gone"]["active"])
        self.assertFalse(rows["a-old"]["active"])

    def test_level_industry_fallback_and_case_insensitive_join(self):
        self.person("AbC", level="Analyst", industry="Banca")
        self.assign("a1", "abc")
        self.assign("a2", "abc", industry="Energía")
        self.assign("a3", "nobody")
        rows = self.get()
        self.assertEqual(rows["a1"]["careerLevel"], "Analyst")
        self.assertEqual(rows["a1"]["industry"], "Banca")
        self.assertEqual(rows["a2"]["industry"], "Energía")
        self.assertEqual(rows["a3"]["careerLevel"], "")

    def test_invalid_scope(self):
        self.assertEqual(self.client.get(reverse("assignments") + "?scope=x").status_code, 400)
