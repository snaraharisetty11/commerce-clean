
from io import BytesIO, StringIO
from unittest.mock import patch

from django.test import TestCase

from deduplication.models import (
    IngestionReject,
    PipelineRun,
    SourceRecord,
)
from deduplication.services.ingestion import ingest_csv


class IngestionServiceTests(TestCase):
    def test_valid_customer_is_saved_as_valid(self):
        csv_data = StringIO(
            "source_record_id,name,email\n"
            "C001,Alice,alice@example.com\n"
        )

        result = ingest_csv(csv_data, record_type="CUSTOMER")

        record = SourceRecord.objects.get(source_record_id="C001")

        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(record.is_valid)
        self.assertEqual(record.validation_errors, [])
        self.assertEqual(record.normalized_data["name"], "alice")
        self.assertEqual(result["valid_count"], 1)

    def test_invalid_customer_is_saved_with_errors(self):
        csv_data = StringIO(
            "source_record_id,name,email\n"
            "C002,,not-an-email\n"
        )

        result = ingest_csv(csv_data, record_type="CUSTOMER")
        record = SourceRecord.objects.get(source_record_id="C002")

        self.assertFalse(record.is_valid)
        self.assertTrue(record.validation_errors)
        self.assertEqual(record.normalized_data, {})
        self.assertEqual(result["rejected_count"], 1)

    def test_duplicate_id_in_same_csv_is_skipped(self):
        csv_data = StringIO(
            "source_record_id,name,email\n"
            "C003,Alice,alice@example.com\n"
            "C003,Bob,bob@example.com\n"
        )

        result = ingest_csv(csv_data, record_type="CUSTOMER")

        self.assertEqual(
            SourceRecord.objects.filter(source_record_id="C003").count(),
            1,
        )
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["valid_count"], 1)

    def test_malformed_csv_fails_run_without_saving_records(self):
        csv_data = StringIO(
            "source_record_id,name,email\n"
            "C004,Alice,alice@example.com,EXTRA\n"
        )

        result = ingest_csv(csv_data, record_type="CUSTOMER")

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(SourceRecord.objects.count(), 0)

        run = PipelineRun.objects.get(run_id=result["run_id"])
        self.assertEqual(run.status, "FAILED")
        self.assertTrue(run.error_message)

    def test_missing_source_record_id_header_fails_run(self):
        csv_data = StringIO(
            "name,email\n"
            "Alice,alice@example.com\n"
        )

        result = ingest_csv(csv_data, record_type="CUSTOMER")

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(SourceRecord.objects.count(), 0)

    def test_invalid_record_type_is_rejected(self):
        with self.assertRaises(ValueError):
            ingest_csv(
                StringIO(
                    "source_record_id,name,email\n"
                    "C005,Alice,alice@example.com\n"
                ),
                record_type="ORDER",
            )

    def test_duplicate_id_against_existing_record_is_skipped(self):
        run = PipelineRun.objects.create()

        SourceRecord.objects.create(
            source_record_id="C006",
            record_type="CUSTOMER",
            source_system="CSV",
            raw_data={
                "name": "Alice",
                "email": "alice@example.com",
            },
            normalized_data={},
            is_valid=True,
            validation_errors=[],
            run=run,
        )

        result = ingest_csv(
            StringIO(
                "source_record_id,name,email\n"
                "C006,Bob,bob@example.com\n"
            ),
            record_type="CUSTOMER",
            run=run,
        )

        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(
            SourceRecord.objects.filter(
                run=run,
                source_record_id="C006",
            ).count(),
            1,
        )

    def test_unexpected_error_rolls_back_batch_records(self):
        csv_data = StringIO(
            "source_record_id,name,email\n"
            "C007,Alice,alice@example.com\n"
            "C008,Bob,bob@example.com\n"
        )

        with patch(
            "deduplication.services.ingestion.normalize_record",
            side_effect=[
                {"name": "alice", "email": "alice@example.com"},
                RuntimeError("Simulated processing failure"),
            ],
        ):
            with self.assertRaises(RuntimeError):
                ingest_csv(csv_data, record_type="CUSTOMER")

        self.assertEqual(SourceRecord.objects.count(), 0)

        failed_run = PipelineRun.objects.latest("started_at")
        self.assertEqual(failed_run.status, "FAILED")
        self.assertIn(
            "Simulated processing failure",
            failed_run.error_message,
        )

    def test_source_filename_and_row_number_are_saved(self):
        result = ingest_csv(
            StringIO(
                "source_record_id,name,email\n"
                "C101,Alice,alice@example.com\n"
            ),
            record_type="CUSTOMER",
            source_file="sample_customers.csv",
        )

        record = SourceRecord.objects.get(
            run_id=result["run_id"],
            source_record_id="C101",
        )

        self.assertEqual(record.source_file, "sample_customers.csv")
        self.assertEqual(record.source_row_number, 2)

    def test_missing_source_id_is_saved_as_ingestion_reject(self):
        result = ingest_csv(
            StringIO(
                "source_record_id,name,email\n"
                ",Missing ID,missing@example.com\n"
            ),
            record_type="CUSTOMER",
            source_file="sample_customers.csv",
        )

        reject = IngestionReject.objects.get(
            run_id=result["run_id"],
            source_file="sample_customers.csv",
            source_row_number=2,
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["input_count"], 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(reject.raw_data["name"], "Missing ID")
        self.assertIn(
            "source_record_id is required.",
            reject.rejection_errors,
        )

    def test_rejected_row_preserves_source_filename_and_row_number(self):
        result = ingest_csv(
            StringIO(
                "source_record_id,name,email\n"
                "C102,Alice,alice@example.com\n"
                ",Missing ID,missing@example.com\n"
            ),
            record_type="CUSTOMER",
            source_file="audit_sample.csv",
        )

        reject = IngestionReject.objects.get(
            run_id=result["run_id"],
            source_file="audit_sample.csv",
            source_row_number=3,
        )

        self.assertEqual(result["valid_count"], 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(reject.raw_data["email"], "missing@example.com")

    def test_binary_csv_upload_with_utf8_bom_is_supported(self):
        csv_data = BytesIO(
            b"\xef\xbb\xbfsource_record_id,name,email\n"
            b"C201,Alice,alice@example.com\n"
        )

        result = ingest_csv(
            csv_data,
            record_type="CUSTOMER",
            source_file="bom_customers.csv",
        )

        record = SourceRecord.objects.get(
            run_id=result["run_id"],
            source_record_id="C201",
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(record.is_valid)
        self.assertEqual(record.source_row_number, 2)

    def test_reject_row_number_is_correct_after_blank_line(self):
        result = ingest_csv(
            StringIO(
                "source_record_id,name,email\n"
                "C202,Alice,alice@example.com\n"
                "\n"
                ",Missing ID,missing@example.com\n"
            ),
            record_type="CUSTOMER",
            source_file="blank_line_customers.csv",
        )

        reject = IngestionReject.objects.get(
            run_id=result["run_id"],
            source_file="blank_line_customers.csv",
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["valid_count"], 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(reject.source_row_number, 4)
