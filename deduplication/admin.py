
from django.contrib import admin

from .models import (
    PipelineRun,
    SourceRecord,
    DuplicateReview,
    MergedRecord,
    RecordLineage,
)


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = (
        "run_id",
        "status",
        "input_count",
        "valid_count",
        "rejected_count",
        "published_count",
        "started_at",
    )
    list_filter = ("status",)
    search_fields = ("run_id",)


@admin.register(SourceRecord)
class SourceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "source_record_id",
        "record_type",
        "source_system",
        "is_valid",
        "run",
    )
    list_filter = ("record_type", "is_valid", "source_system")
    search_fields = ("source_record_id",)


@admin.register(DuplicateReview)
class DuplicateReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "record_a",
        "record_b",
        "confidence_score",
        "status",
    )
    list_filter = ("status",)
    search_fields = ("explanation",)


@admin.register(MergedRecord)
class MergedRecordAdmin(admin.ModelAdmin):
    list_display = ("canonical_id", "record_type", "run", "created_at")
    list_filter = ("record_type",)
    search_fields = ("canonical_id",)


@admin.register(RecordLineage)
class RecordLineageAdmin(admin.ModelAdmin):
    list_display = ("id", "merged_record", "source_record")
