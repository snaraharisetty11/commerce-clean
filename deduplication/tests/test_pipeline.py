
from io import StringIO

from django.test import TestCase

from deduplication.models import (
    DuplicateReview,
    MergedRecord,
    PipelineRun,
    RecordLineage,
    SourceRecord,
)
from deduplication.services.pipeline import (
    merge_confirmed_reviews,
    run_pipeline,
)


class PipelineIntegrationTests(TestCase):
    def test_pipeline_ingests_records_and_creates_review(self):
        csv_data = (
            "source_record_id,name,email\n"
            "P001,Alice Smith,alice@example.com\n"
            "P002,Alice Smith,alice@example.com\n"
        )

        result = run_pipeline(
            StringIO(csv_data),
            record_type="CUSTOMER",
            source_system="CSV",
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["review_count"], 1)
        self.assertEqual(DuplicateReview.objects.count(), 1)

        # Exactly one review should exist for this test.
        review = DuplicateReview.objects.get()
        self.assertEqual(
            review.status,
            DuplicateReview.ReviewStatus.PENDING,
        )

    def test_pipeline_does_not_auto_merge_pending_reviews(self):
        csv_data = (
            "source_record_id,name,email\n"
            "P003,Alice Smith,alice@example.com\n"
            "P004,Alice Smith,alice@example.com\n"
        )

        run_pipeline(
            StringIO(csv_data),
            record_type="CUSTOMER",
        )

        # Reviews must be manually confirmed before merging.
        self.assertEqual(MergedRecord.objects.count(), 0)

    def test_confirmed_review_can_be_merged_through_pipeline(self):
        csv_data = (
            "source_record_id,name,email\n"
            "P005,Alice Smith,alice@example.com\n"
            "P006,Alice Smith,alice@example.com\n"
        )

        result = run_pipeline(
            StringIO(csv_data),
            record_type="CUSTOMER",
        )

        review = DuplicateReview.objects.get(
            pk=result["review_ids"][0]
        )
        review.status = DuplicateReview.ReviewStatus.CONFIRMED
        review.save(update_fields=["status"])

        run = PipelineRun.objects.get(
            run_id=result["run_id"]
        )

        merge_result = merge_confirmed_reviews(run)

        self.assertEqual(merge_result["merged_count"], 1)
        self.assertEqual(MergedRecord.objects.count(), 1)
        self.assertEqual(RecordLineage.objects.count(), 2)

    def test_invalid_records_are_not_reviewed(self):
        csv_data = (
            "source_record_id,name,email\n"
            "P007,,invalid-email\n"
            "P008,,invalid-email\n"
        )

        result = run_pipeline(
            StringIO(csv_data),
            record_type="CUSTOMER",
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["rejected_count"], 2)
        self.assertEqual(result["review_count"], 0)
        self.assertEqual(DuplicateReview.objects.count(), 0)

    def test_malformed_csv_fails_pipeline(self):
        csv_data = (
            "source_record_id,name,email\n"
            "P009,Alice,alice@example.com,EXTRA\n"
        )

        result = run_pipeline(
            StringIO(csv_data),
            record_type="CUSTOMER",
        )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(SourceRecord.objects.count(), 0)
        self.assertTrue(result["errors"])

    def test_pipeline_preserves_source_filename_and_row_number(self):
        csv_data = (
            "source_record_id,name,email\n"
            "P010,Alice,alice@example.com\n"
        )

        result = run_pipeline(
            StringIO(csv_data),
            record_type="CUSTOMER",
            source_system="CSV",
            source_file="pipeline_customers.csv",
        )

        record = SourceRecord.objects.get(
            run_id=result["run_id"],
            source_record_id="P010",
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(
            record.source_file,
            "pipeline_customers.csv",
        )
        self.assertEqual(record.source_row_number, 2)
