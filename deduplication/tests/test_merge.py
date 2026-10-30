from django.test import TestCase

from deduplication.models import (
    DuplicateReview,
    MergedRecord,
    PipelineRun,
    RecordLineage,
    SourceRecord,
)
from deduplication.services.merge import merge_confirmed_review


class MergeServiceTests(TestCase):
    def setUp(self):
        self.pipeline_run = PipelineRun.objects.create()

        self.record_a = self.make_source_record(
            record_id="M001",
            record_type="CUSTOMER",
            source_system="CRM",
            raw_data={
                "name": "Alice Smith",
                "email": "alice@example.com",
            },
            normalized_data={
                "name": "alice smith",
                "email": "alice@example.com",
            },
        )

        self.record_b = self.make_source_record(
            record_id="M002",
            record_type="CUSTOMER",
            source_system="ERP",
            raw_data={
                "name": "Alice Smith",
                "email": "alice@example.com",
                "phone": "1234567890",
            },
            normalized_data={
                "name": "alice smith",
                "email": "alice@example.com",
                "phone": "1234567890",
            },
        )

        self.review = self.create_review(
            self.record_a,
            self.record_b,
            status=DuplicateReview.ReviewStatus.CONFIRMED,
        )

    def make_source_record(
        self,
        record_id,
        record_type,
        source_system,
        raw_data,
        normalized_data,
        run=None,
        is_valid=True,
    ):
        return SourceRecord.objects.create(
            source_record_id=record_id,
            record_type=record_type,
            source_system=source_system,
            raw_data=raw_data,
            normalized_data=normalized_data,
            is_valid=is_valid,
            validation_errors=[],
            run=run or self.pipeline_run,
        )

    def create_review(self, record_a, record_b, status):
        first, second = sorted(
            (record_a, record_b),
            key=lambda record: record.pk,
        )

        return DuplicateReview.objects.create(
            record_a=first,
            record_b=second,
            confidence_score=0.95,
            explanation="Matching record details",
            status=status,
        )

    def test_confirmed_review_creates_merged_record(self):
        merged = merge_confirmed_review(self.review)

        self.assertIsInstance(merged, MergedRecord)
        self.assertEqual(merged.record_type, "CUSTOMER")
        self.assertEqual(merged.run.pk, self.pipeline_run.pk)
        self.assertEqual(MergedRecord.objects.count(), 1)

    def test_merge_creates_lineage_for_both_sources(self):
        merged = merge_confirmed_review(self.review)

        self.assertEqual(
            RecordLineage.objects.filter(
                merged_record=merged,
            ).count(),
            2,
        )

    def test_merge_preserves_original_source_records(self):
        merge_confirmed_review(self.review)

        self.assertTrue(
            SourceRecord.objects.filter(
                pk=self.record_a.pk,
            ).exists()
        )

        self.assertTrue(
            SourceRecord.objects.filter(
                pk=self.record_b.pk,
            ).exists()
        )

    def test_pending_review_cannot_be_merged(self):
        self.review.status = DuplicateReview.ReviewStatus.PENDING
        self.review.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            merge_confirmed_review(self.review)

        self.assertEqual(MergedRecord.objects.count(), 0)

    def test_invalid_source_record_cannot_be_merged(self):
        self.record_b.is_valid = False
        self.record_b.save(update_fields=["is_valid"])

        with self.assertRaises(ValueError):
            merge_confirmed_review(self.review)

        self.assertEqual(MergedRecord.objects.count(), 0)

    def test_repeated_merge_does_not_create_another_record(self):
        first = merge_confirmed_review(self.review)
        second = merge_confirmed_review(self.review)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(MergedRecord.objects.count(), 1)
        self.assertEqual(RecordLineage.objects.count(), 2)

    def test_rejects_source_records_from_different_pipeline_runs(self):
        another_run = PipelineRun.objects.create()

        record_from_another_run = self.make_source_record(
            record_id="M003",
            record_type="CUSTOMER",
            source_system="OTHER",
            raw_data={"name": "Alice Smith"},
            normalized_data={"name": "alice smith"},
            run=another_run,
        )

        review = self.create_review(
            self.record_a,
            record_from_another_run,
            status=DuplicateReview.ReviewStatus.CONFIRMED,
        )

        with self.assertRaises(ValueError):
            merge_confirmed_review(review)

        self.assertEqual(MergedRecord.objects.count(), 0)
        self.assertEqual(RecordLineage.objects.count(), 0)

    def test_rejects_source_records_with_different_types(self):
        product = self.make_source_record(
            record_id="M004",
            record_type="PRODUCT",
            source_system="ERP",
            raw_data={"name": "Laptop"},
            normalized_data={"name": "laptop"},
        )

        review = self.create_review(
            self.record_a,
            product,
            status=DuplicateReview.ReviewStatus.CONFIRMED,
        )

        with self.assertRaises(ValueError):
            merge_confirmed_review(review)

        self.assertEqual(MergedRecord.objects.count(), 0)
        self.assertEqual(RecordLineage.objects.count(), 0)

    def test_rejects_non_dictionary_normalized_data(self):
        self.record_b.normalized_data = "invalid data"
        self.record_b.save(update_fields=["normalized_data"])

        with self.assertRaises(ValueError):
            merge_confirmed_review(self.review)

        self.assertEqual(MergedRecord.objects.count(), 0)
        self.assertEqual(RecordLineage.objects.count(), 0)

    def test_rejects_empty_normalized_data(self):
        self.record_b.normalized_data = {}
        self.record_b.save(update_fields=["normalized_data"])

        with self.assertRaises(ValueError):
            merge_confirmed_review(self.review)

        self.assertEqual(MergedRecord.objects.count(), 0)
        self.assertEqual(RecordLineage.objects.count(), 0)