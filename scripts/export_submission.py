import csv
import json
from pathlib import Path
from collections import Counter
from django.db.models import Count
from django.utils import timezone

from deduplication.models import (
    PipelineRun, SourceRecord, DuplicateReview,
    MergedRecord, RecordLineage
)

out = Path("outputs")
out.mkdir(exist_ok=True)

def json_value(value):
    return json.dumps(value, ensure_ascii=False, default=str)

# 1. Export actual merged records
merged_fields = [
    "merged_record_id", "run_id", "record_type",
    "merged_data", "survivorship_explanation"
]

with (out / "sample_merged_records.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(f, fieldnames=merged_fields)
    writer.writeheader()

    for record in MergedRecord.objects.all().order_by("pk"):
        writer.writerow({
            "merged_record_id": record.pk,
            "run_id": record.run_id,
            "record_type": record.record_type,
            "merged_data": json_value(record.merged_data),
            "survivorship_explanation": json_value(
                record.survivorship_explanation
            ),
        })

# 2. Export all reviews, including pending and confirmed
review_fields = [
    "review_id", "run_id", "record_type", "status",
    "confidence_score", "explanation",
    "record_a_id", "record_b_id",
    "source_a_system", "source_a_id",
    "source_b_system", "source_b_id",
    "has_lineage", "merged_record_ids"
]

status_counts = Counter()
confirmed_without_lineage = 0

with (out / "sample_review_queue.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(f, fieldnames=review_fields)
    writer.writeheader()

    reviews = DuplicateReview.objects.select_related(
        "record_a", "record_b", "record_a__run"
    ).order_by("pk")

    for review in reviews.iterator(chunk_size=2000):
        a = review.record_a
        b = review.record_b

        lineages = RecordLineage.objects.filter(
            source_record_id__in=[a.pk, b.pk]
        )
        merged_ids = list(
            lineages.values_list("merged_record__pk", flat=True).distinct()
        )

        has_lineage = bool(merged_ids)
        status = str(review.status)
        status_counts[status] += 1

        if status == "CONFIRMED" and not has_lineage:
            confirmed_without_lineage += 1

        writer.writerow({
            "review_id": review.pk,
            "run_id": a.run_id,
            "record_type": a.record_type,
            "status": status,
            "confidence_score": review.confidence_score,
            "explanation": review.explanation,
            "record_a_id": a.pk,
            "record_b_id": b.pk,
            "source_a_system": a.source_system,
            "source_a_id": a.source_record_id,
            "source_b_system": b.source_system,
            "source_b_id": b.source_record_id,
            "has_lineage": has_lineage,
            "merged_record_ids": json_value(merged_ids),
        })

# 3. Build reconciliation report from actual database counts
merged_by_type = {
    row["record_type"]: row["count"]
    for row in MergedRecord.objects.values("record_type").annotate(
        count=Count("pk")
    )
}

report = {
    "generated_at": timezone.now().isoformat(),
    "source": "Actual Django application database",
    "pipeline_runs": PipelineRun.objects.count(),
    "source_records": SourceRecord.objects.count(),
    "duplicate_reviews": DuplicateReview.objects.count(),
    "review_status_counts": dict(status_counts),
    "merged_records": MergedRecord.objects.count(),
    "merged_records_by_type": merged_by_type,
    "lineage_entries": RecordLineage.objects.count(),
    "confirmed_reviews_without_lineage": confirmed_without_lineage,
    "interpretation": (
        "Confirmed reviews without lineage are reported separately. "
        "They are not counted as completed merges."
    ),
    "files": [
        "sample_merged_records.csv",
        "sample_review_queue.csv",
        "reconciliation_report.json"
    ]
}

(out / "reconciliation_report.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps(report, indent=2))
print("\nCreated submission files:")
for path in sorted(out.iterdir()):
    print(f"{path} — {path.stat().st_size:,} bytes")
