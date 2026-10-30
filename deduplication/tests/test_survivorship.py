
from django.test import SimpleTestCase

from deduplication.services.survivorship import select_survivor


class SurvivorshipTests(SimpleTestCase):

    def test_higher_priority_source_wins(self):
        records = [
            {
                "source_system": "store",
                "source_record_id": "S2",
                "name": "Sreeja",
                "email": "sreeja@example.com",
            },
            {
                "source_system": "crm",
                "source_record_id": "C1",
                "name": "Sreeja Naraharisetty",
                "email": "sreeja@example.com",
            },
        ]

        merged, explanation = select_survivor(
            records,
            source_priority={"crm": 1, "store": 2},
        )

        self.assertEqual(merged["name"], "Sreeja Naraharisetty")
        self.assertEqual(explanation["name"]["source_system"], "crm")

    def test_fills_missing_fields_from_other_records(self):
        records = [
            {
                "source_system": "crm",
                "source_record_id": "C1",
                "name": "Sreeja",
                "email": "",
            },
            {
                "source_system": "store",
                "source_record_id": "S2",
                "name": "Sreeja",
                "email": "sreeja@example.com",
            },
        ]

        merged, explanation = select_survivor(
            records,
            source_priority={"crm": 1, "store": 2},
        )

        self.assertEqual(merged["email"], "sreeja@example.com")
        self.assertEqual(explanation["email"]["source_system"], "store")

    def test_excludes_source_metadata_from_merged_data(self):
        record = {
            "source_system": "crm",
            "source_record_id": "C1",
            "updated_at": "2026-10-28",
            "name": "Sreeja",
        }

        merged, _ = select_survivor([record])

        self.assertEqual(merged, {"name": "Sreeja"})

    def test_empty_input_raises_error(self):
        with self.assertRaises(ValueError):
            select_survivor([])

    def test_invalid_record_raises_error(self):
        with self.assertRaises(ValueError):
            select_survivor([{"name": "Sreeja"}, "invalid"])

    def test_result_is_deterministic(self):
        record_a = {
            "source_system": "crm",
            "source_record_id": "C1",
            "name": "Sreeja",
        }
        record_b = {
            "source_system": "store",
            "source_record_id": "S2",
            "name": "Sreeja Rao",
        }

        result_a = select_survivor(
            [record_a, record_b],
            source_priority={"crm": 1, "store": 1},
        )
        result_b = select_survivor(
            [record_b, record_a],
            source_priority={"crm": 1, "store": 1},
        )

        self.assertEqual(result_a, result_b)
