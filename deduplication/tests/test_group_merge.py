
from django.test import TestCase

from deduplication.models import (
    DuplicateReview,
    MergedRecord,
    PipelineRun,
    RecordLineage,
    SourceRecord,
)
from deduplication.services.group_merge import merge_confirmed_groups


class GroupMergeTests(TestCase):
    def setUp(self):
        self.pipeline_run = PipelineRun.objects.create()

    def make_customer(self, record_id, name, email):
        return SourceRecord.objects.create(
            source_record_id=record_id,
            record_type="CUSTOMER",
            source_system="CSV",
            raw_data={
                "name": name,
                "email": email,
            },
            normalized_data={
                "name": name.casefold(),
                "email": email.casefold(),
            },
            is_valid=True,
            validation_errors=[],
            run=self.pipeline_run,
        )

    def confirm_review(self, record_a, record_b):
        first, second = sorted(
            (record_a, record_b),
            key=lambda record: record.pk,
        )
        return DuplicateReview.objects.create(
            record_a=first,
            record_b=second,
            confidence_score=0.95,
            explanation="Test-confirmed duplicate",
            status=DuplicateReview.ReviewStatus.CONFIRMED,
        )

    def test_three_connected_records_create_one_merged_record(self):
        first = self.make_customer(
            "C001", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C002", "Alice Smith", "alice@example.com"
        )
        third = self.make_customer(
            "C003", "Alice Smith", "alice@example.com"
        )

        self.confirm_review(first, second)
        self.confirm_review(second, third)

        result = merge_confirmed_groups(self.pipeline_run)

        self.assertEqual(result["group_count"], 1)
        self.assertEqual(result["merged_count"], 1)
        self.assertEqual(len(result["errors"]), 0)
        self.assertEqual(MergedRecord.objects.count(), 1)
        self.assertEqual(RecordLineage.objects.count(), 3)

    def test_repeated_group_merge_is_idempotent(self):
        first = self.make_customer(
            "C004", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C005", "Alice Smith", "alice@example.com"
        )
        self.confirm_review(first, second)

        first_result = merge_confirmed_groups(self.pipeline_run)
        second_result = merge_confirmed_groups(self.pipeline_run)

        self.assertEqual(first_result["merged_record_ids"],
                         second_result["merged_record_ids"])
        self.assertEqual(MergedRecord.objects.count(), 1)
        self.assertEqual(RecordLineage.objects.count(), 2)

    def test_pending_reviews_are_not_merged(self):
        first = self.make_customer(
            "C006", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C007", "Alice Smith", "alice@example.com"
        )
        first, second = sorted(
            (first, second),
            key=lambda record: record.pk,
        )
        DuplicateReview.objects.create(
            record_a=first,
            record_b=second,
            status=DuplicateReview.ReviewStatus.PENDING,
        )

        result = merge_confirmed_groups(self.pipeline_run)

        self.assertEqual(result["group_count"], 0)
        self.assertEqual(MergedRecord.objects.count(), 0)
        self.assertEqual(RecordLineage.objects.count(), 0)

    def test_unconnected_groups_merge_separately(self):
        first = self.make_customer(
            "C008", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C009", "Alice Smith", "alice@example.com"
        )
        third = self.make_customer(
            "C010", "Bob Jones", "bob@example.com"
        )
        fourth = self.make_customer(
            "C011", "Bob Jones", "bob@example.com"
        )

        self.confirm_review(first, second)
        self.confirm_review(third, fourth)

        result = merge_confirmed_groups(self.pipeline_run)

        self.assertEqual(result["group_count"], 2)
        self.assertEqual(result["merged_count"], 2)
        self.assertEqual(MergedRecord.objects.count(), 2)
        self.assertEqual(RecordLineage.objects.count(), 4)
