from django.test import TestCase

from deduplication.models import (
    MergedRecord,
    PipelineRun,
    RecordLineage,
    SourceRecord,
)
from deduplication.services.lineage import record_lineage


class RecordLineageTests(TestCase):
    def setUp(self):
        self.pipeline_run = PipelineRun.objects.create()

        self.source_a = self.make_source_record(
            record_id="CUST-001",
            record_type="CUSTOMER",
            source_system="CRM",
            raw_data={"name": "Priya"},
            normalized_data={"name": "priya"},
        )

        self.source_b = self.make_source_record(
            record_id="CUST-002",
            record_type="CUSTOMER",
            source_system="ERP",
            raw_data={"phone": "9876543210"},
            normalized_data={"phone": "9876543210"},
        )

        self.merged = MergedRecord.objects.create(
            record_type="CUSTOMER",
            merged_data={
                "name": "Priya",
                "phone": "9876543210",
            },
            survivorship_explanation={},
            run=self.pipeline_run,
        )

    def make_source_record(
        self,
        record_id,
        record_type,
        source_system,
        raw_data,
        normalized_data,
        run=None,
    ):
        return SourceRecord.objects.create(
            source_record_id=record_id,
            record_type=record_type,
            source_system=source_system,
            raw_data=raw_data,
            normalized_data=normalized_data,
            is_valid=True,
            validation_errors=[],
            run=run or self.pipeline_run,
        )

    def test_creates_lineage_for_one_source(self):
        result = record_lineage(
            self.merged,
            [self.source_a],
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            RecordLineage.objects.filter(
                merged_record=self.merged,
            ).count(),
            1,
        )
        self.assertEqual(result[0].source_record, self.source_a)

    def test_creates_lineage_for_multiple_sources(self):
        result = record_lineage(
            self.merged,
            [self.source_a, self.source_b],
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(
            RecordLineage.objects.filter(
                merged_record=self.merged,
            ).count(),
            2,
        )

    def test_repeated_call_does_not_duplicate_lineage(self):
        record_lineage(
            self.merged,
            [self.source_a, self.source_b],
        )

        record_lineage(
            self.merged,
            [self.source_a, self.source_b],
        )

        self.assertEqual(
            RecordLineage.objects.filter(
                merged_record=self.merged,
            ).count(),
            2,
        )

    def test_saves_contribution_details(self):
        details = {
            self.source_a.pk: {
                "fields_contributed": ["name"],
            },
            self.source_b.pk: {
                "fields_contributed": ["phone"],
            },
        }

        record_lineage(
            self.merged,
            [self.source_a, self.source_b],
            contributions=details,
        )

        lineage = RecordLineage.objects.get(
            merged_record=self.merged,
            source_record=self.source_a,
        )

        self.assertEqual(
            lineage.contribution_details,
            {"fields_contributed": ["name"]},
        )

    def test_rejects_empty_source_list(self):
        with self.assertRaises(ValueError):
            record_lineage(self.merged, [])

    def test_rejects_unsaved_merged_record(self):
        unsaved_merged = MergedRecord(
            record_type="CUSTOMER",
            merged_data={},
            survivorship_explanation={},
            run=self.pipeline_run,
        )

        with self.assertRaises(ValueError):
            record_lineage(
                unsaved_merged,
                [self.source_a],
            )

    def test_rejects_source_from_another_pipeline_run(self):
        another_run = PipelineRun.objects.create()

        source_from_another_run = self.make_source_record(
            record_id="CUST-003",
            record_type="CUSTOMER",
            source_system="CRM",
            raw_data={"name": "Other"},
            normalized_data={"name": "other"},
            run=another_run,
        )

        with self.assertRaises(ValueError):
            record_lineage(
                self.merged,
                [source_from_another_run],
            )

        self.assertEqual(RecordLineage.objects.count(), 0)

    def test_rejects_source_with_different_record_type(self):
        product = self.make_source_record(
            record_id="PROD-001",
            record_type="PRODUCT",
            source_system="ERP",
            raw_data={"name": "Laptop"},
            normalized_data={"name": "laptop"},
        )

        with self.assertRaises(ValueError):
            record_lineage(
                self.merged,
                [product],
            )

        self.assertEqual(RecordLineage.objects.count(), 0)

    def test_rejects_duplicate_source_records_in_input(self):
        with self.assertRaises(ValueError):
            record_lineage(
                self.merged,
                [self.source_a, self.source_a],
            )

        self.assertEqual(RecordLineage.objects.count(), 0)

    def test_rejects_non_dictionary_contributions(self):
        with self.assertRaises(TypeError):
            record_lineage(
                self.merged,
                [self.source_a],
                contributions=[],
            )

        self.assertEqual(RecordLineage.objects.count(), 0)

    def test_rejects_non_dictionary_contribution_details(self):
        with self.assertRaises(TypeError):
            record_lineage(
                self.merged,
                [self.source_a],
                contributions={
                    self.source_a.pk: "invalid details",
                },
            )

        self.assertEqual(RecordLineage.objects.count(), 0)