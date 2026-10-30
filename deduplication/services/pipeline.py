
from django.utils import timezone

from deduplication.models import (
    DuplicateReview,
    MergedRecord,
    PipelineRun,
    SourceRecord,
)
from deduplication.services.ingestion import ingest_csv
from deduplication.services.group_merge import merge_confirmed_groups
from deduplication.services.review import create_duplicate_reviews


def run_pipeline(
    file_obj,
    record_type,
    source_system="CSV",
    source_priority=None,
    run=None,
    source_file="",
):
    """
    Ingest a CSV and create duplicate-review candidates.

    Exact and probable duplicates remain pending until reviewed.
    This function does not automatically merge pending candidates.

    Returns a dictionary containing the ingestion summary and
    duplicate-review candidate IDs.
    """
    summary = ingest_csv(
        file_obj=file_obj,
        record_type=record_type,
        source_system=source_system,
        run=run,
        source_file=source_file,
    )

    summary["review_count"] = 0
    summary["review_ids"] = []

    if summary["status"] != "COMPLETED":
        return summary

    pipeline_run = PipelineRun.objects.get(
        run_id=summary["run_id"]
    )

    try:
        source_records = list(
            SourceRecord.objects.filter(
                run=pipeline_run,
                source_system=source_system.strip(),
                is_valid=True,
            ).order_by("pk")
        )

        reviews = create_duplicate_reviews(source_records)

        summary["review_count"] = len(reviews)
        summary["review_ids"] = [
            review.pk for review in reviews
        ]

    except Exception as exc:
        pipeline_run.status = "FAILED"
        pipeline_run.error_message = str(exc)
        pipeline_run.finished_at = timezone.now()
        pipeline_run.save(
            update_fields=[
                "status",
                "error_message",
                "finished_at",
            ]
        )

        summary["status"] = "FAILED"
        summary["errors"].append(str(exc))
        raise

    return summary




def merge_confirmed_reviews(run, source_priority=None):
    """
    Merge connected groups of confirmed duplicate reviews for a run.

    Pending reviews are never merged. Connected confirmed groups are
    merged into canonical records, with lineage preserved.
    """
    if not isinstance(run, PipelineRun) or run.pk is None:
        raise ValueError("run must be a saved PipelineRun instance.")

    result = merge_confirmed_groups(
        run,
        source_priority=source_priority,
    )

    published_count = MergedRecord.objects.filter(run=run).count()

    run.published_count = published_count
    run.save(update_fields=["published_count"])

    return {
        "run_id": str(run.run_id),
        "group_count": result["group_count"],
        "merged_count": result["merged_count"],
        "merged_record_ids": result["merged_record_ids"],
        "published_count": published_count,
        "groups": result["groups"],
        "errors": result["errors"],
    }
