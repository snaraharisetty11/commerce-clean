import json
from pathlib import Path
from django.db.models import Count
from django.utils import timezone
from deduplication.models import (
    PipelineRun, SourceRecord, DuplicateReview,
    MergedRecord, RecordLineage
)

statuses = {
    row["status"]: row["count"]
    for row in DuplicateReview.objects.values("status").annotate(count=Count("pk"))
}

merged_types = {
    row["record_type"]: row["count"]
    for row in MergedRecord.objects.values("record_type").annotate(count=Count("pk"))
}

unmerged_confirmed = 0
for review in DuplicateReview.objects.filter(status="CONFIRMED").select_related("record_a", "record_b"):
    linked = RecordLineage.objects.filter(
        source_record_id__in=[review.record_a_id, review.record_b_id]
    ).exists()
    if not linked:
        unmerged_confirmed += 1

report = {
    "generated_at": timezone.now().isoformat(),
    "source": "Actual Django application database",
    "pipeline_runs": PipelineRun.objects.count(),
    "source_records": SourceRecord.objects.count(),
    "duplicate_reviews": DuplicateReview.objects.count(),
    "review_status_counts": statuses,
    "merged_records": MergedRecord.objects.count(),
    "merged_records_by_type": merged_types,
    "lineage_entries": RecordLineage.objects.count(),
    "confirmed_reviews_without_lineage": unmerged_confirmed,
    "interpretation": "Confirmed reviews without lineage are not counted as completed merges."
}

Path("outputs/reconciliation_report.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8"
)
print(json.dumps(report, indent=2))
