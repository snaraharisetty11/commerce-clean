
from django.test import TestCase

from deduplication.models import PipelineRun, SourceRecord
from deduplication.services.candidate_generation import (
    generate_candidate_pairs,
)


class CandidateGenerationTests(TestCase):
    def setUp(self):
        self.pipeline_run = PipelineRun.objects.create()

    def make_customer(self, record_id, name, email, phone=""):
        return SourceRecord.objects.create(
            source_record_id=record_id,
            record_type="CUSTOMER",
            source_system="CSV",
            raw_data={
                "name": name,
                "email": email,
                "phone": phone,
            },
            normalized_data={
                "name": name.casefold(),
                "email": email.casefold(),
                "phone": "".join(
                    character for character in phone
                    if character.isdigit()
                ),
            },
            is_valid=True,
            validation_errors=[],
            run=self.pipeline_run,
        )

    def make_product(self, record_id, name, sku, brand=""):
        return SourceRecord.objects.create(
            source_record_id=record_id,
            record_type="PRODUCT",
            source_system="CSV",
            raw_data={
                "name": name,
                "sku": sku,
                "brand": brand,
            },
            normalized_data={
                "name": name.casefold(),
                "sku": sku.casefold(),
                "brand": brand.casefold(),
            },
            is_valid=True,
            validation_errors=[],
            run=self.pipeline_run,
        )

    def test_matching_email_generates_candidate_pair(self):
        first = self.make_customer(
            "B001", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "B002", "Alice Smith", "alice@example.com"
        )

        pairs = generate_candidate_pairs([first, second])

        self.assertEqual(len(pairs), 1)
        self.assertEqual(
            {pairs[0][0].pk, pairs[0][1].pk},
            {first.pk, second.pk},
        )

    def test_same_pair_is_not_repeated_for_multiple_keys(self):
        first = self.make_customer(
            "B003",
            "Alice Smith",
            "alice@example.com",
            "1234567890",
        )
        second = self.make_customer(
            "B004",
            "Alice Smith",
            "alice@example.com",
            "1234567890",
        )

        pairs = generate_candidate_pairs([first, second])

        self.assertEqual(len(pairs), 1)

    def test_unrelated_records_do_not_share_candidates(self):
        first = self.make_customer(
            "B005", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "B006", "Robert Jones", "robert@example.org"
        )

        pairs = generate_candidate_pairs([first, second])

        self.assertEqual(pairs, [])

    def test_invalid_records_are_excluded(self):
        first = self.make_customer(
            "B007", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "B008", "Alice Smith", "alice@example.com"
        )
        second.is_valid = False
        second.save(update_fields=["is_valid"])

        pairs = generate_candidate_pairs([first, second])

        self.assertEqual(pairs, [])

    def test_unsaved_records_are_rejected(self):
        unsaved = SourceRecord(
            source_record_id="B009",
            record_type="CUSTOMER",
            source_system="CSV",
            raw_data={},
            normalized_data={},
            is_valid=True,
            validation_errors=[],
            run=self.pipeline_run,
        )

        with self.assertRaises(ValueError):
            generate_candidate_pairs([unsaved])

    def test_product_records_generate_candidates_from_matching_sku(self):
        first = self.make_product(
            "P001", "Wireless Mouse", "WM-101", "TechPro"
        )
        second = self.make_product(
            "P002", "Wireless Mouse", "WM-101", "TechPro"
        )

        pairs = generate_candidate_pairs([first, second])

        self.assertEqual(len(pairs), 1)
        self.assertEqual(
            {pairs[0][0].pk, pairs[0][1].pk},
            {first.pk, second.pk},
        )

    def test_customer_and_product_records_are_not_paired(self):
        customer = self.make_customer(
            "B010", "Wireless Mouse", "mouse@example.com"
        )
        product = self.make_product(
            "P010", "Wireless Mouse", "mouse@example.com"
        )

        pairs = generate_candidate_pairs([customer, product])

        self.assertEqual(pairs, [])

    def test_pairs_are_unique_and_ordered_by_primary_key(self):
        first = self.make_customer(
            "B011", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "B012", "Alice Jones", "alice@example.com"
        )
        third = self.make_customer(
            "B013", "Alice Brown", "alice@example.com"
        )

        pairs_forward = generate_candidate_pairs(
            [first, second, third]
        )
        pairs_reverse = generate_candidate_pairs(
            [third, second, first]
        )

        expected = [
            (first.pk, second.pk),
            (first.pk, third.pk),
            (second.pk, third.pk),
        ]

        self.assertEqual(
            [(a.pk, b.pk) for a, b in pairs_forward],
            expected,
        )
        self.assertEqual(
            [(a.pk, b.pk) for a, b in pairs_reverse],
            expected,
        )

    def test_records_without_normalized_data_are_excluded(self):
        first = self.make_customer(
            "B014", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "B015", "Alice Smith", "alice@example.com"
        )
        second.normalized_data = {}
        second.save(update_fields=["normalized_data"])

        pairs = generate_candidate_pairs([first, second])

        self.assertEqual(pairs, [])

    def test_invalid_normalized_data_type_raises_clear_error(self):
        record = self.make_customer(
            "B016", "Alice Smith", "alice@example.com"
        )
        record.normalized_data = ["not", "a", "dictionary"]
        record.save(update_fields=["normalized_data"])

        with self.assertRaisesMessage(
            ValueError,
            "invalid normalized_data",
        ):
            generate_candidate_pairs([record])
