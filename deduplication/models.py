
from django.db import models
import uuid


class PipelineRun(models.Model):
    """Tracks one execution of the data processing pipeline."""

    run_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    status = models.CharField(max_length=20, default="PENDING")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    input_count = models.PositiveIntegerField(default=0)
    valid_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    exact_duplicate_count = models.PositiveIntegerField(default=0)
    probable_duplicate_count = models.PositiveIntegerField(default=0)
    published_count = models.PositiveIntegerField(default=0)

    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"Run {self.run_id} - {self.status}"


class SourceRecord(models.Model):
    """Stores an original customer or product record."""

    class RecordType(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        PRODUCT = "PRODUCT", "Product"

    source_record_id = models.CharField(max_length=100)
    record_type = models.CharField(
        max_length=20,
        choices=RecordType.choices,
    )
    source_system = models.CharField(max_length=100, default="CSV")
    raw_data = models.JSONField(default=dict)
    normalized_data = models.JSONField(default=dict, blank=True)

    is_valid = models.BooleanField(default=True)
    validation_errors = models.JSONField(default=list, blank=True)
    source_file = models.CharField(max_length=255,blank=True,default="")
    source_row_number = models.PositiveIntegerField(null=True,blank=True)

    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.PROTECT,
        related_name="source_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "source_system", "source_record_id"],
                name="unique_source_record_per_run",
            )
        ]

    def __str__(self):
        return f"{self.record_type}: {self.source_record_id}"



class IngestionReject(models.Model):
    """Stores rejected CSV rows that cannot become SourceRecords."""

    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.PROTECT,
        related_name="ingestion_rejects",
    )
    source_file = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    source_row_number = models.PositiveIntegerField()
    raw_data = models.JSONField(default=dict)
    rejection_errors = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "source_file", "source_row_number"],
                name="unique_ingestion_reject_per_row",
            )
        ]

    def __str__(self):
        return (
            f"Rejected row {self.source_row_number} "
            f"in {self.source_file or 'unknown file'}"
        )


class DuplicateReview(models.Model):
    """Stores duplicate candidates that need review."""

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed duplicate"
        NOT_DUPLICATE = "NOT_DUPLICATE", "Not a duplicate"

    record_a = models.ForeignKey(
        SourceRecord,
        on_delete=models.PROTECT,
        related_name="review_candidates_a",
    )
    record_b = models.ForeignKey(
        SourceRecord,
        on_delete=models.PROTECT,
        related_name="review_candidates_b",
    )
    confidence_score = models.FloatField(default=0.0)
    explanation = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["record_a", "record_b"],
                name="unique_ordered_review_pair",
            ),
            models.CheckConstraint(
                condition=~models.Q(record_a=models.F("record_b")),
                name="review_records_must_differ",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    record_a__lt=models.F("record_b")
                ),
                name="review_pair_canonical_order",
            ),
        ]

    def __str__(self):
        return (
            f"Review #{self.pk}: "
            f"{self.record_a_id} vs {self.record_b_id}"
        )



class MergedRecord(models.Model):
    """Stores a clean, published customer or product record."""

    record_type = models.CharField(
        max_length=20,
        choices=SourceRecord.RecordType.choices,
    )
    canonical_id = models.UUIDField(default=uuid.uuid4, unique=True)
    merged_data = models.JSONField(default=dict)
    survivorship_explanation = models.JSONField(default=dict, blank=True)
    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.PROTECT,
        related_name="merged_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.record_type}: {self.canonical_id}"


class RecordLineage(models.Model):
    """Links a merged record to its original source records."""

    merged_record = models.ForeignKey(
        MergedRecord,
        on_delete=models.PROTECT,
        related_name="lineage",
    )
    source_record = models.ForeignKey(
        SourceRecord,
        on_delete=models.PROTECT,
        related_name="lineage_entries",
    )
    contribution_details = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["merged_record", "source_record"],
                name="unique_lineage_pair",
            )
        ]

    def __str__(self):
        return f"Source {self.source_record_id} → {self.merged_record_id}"
