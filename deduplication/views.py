
import csv
import json

from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from deduplication.models import (
    DuplicateReview,
    IngestionReject,
    MergedRecord,
    PipelineRun,
    SourceRecord,
)
from deduplication.services.pipeline import (
    merge_confirmed_reviews,
    run_pipeline,
)
from deduplication.services.review import resolve_duplicate_review


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def json_for_display(value):
    """Convert Python data into readable JSON for templates."""
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def get_review_counts(reviews):
    """Return duplicate-review counts for the supplied queryset."""
    return {
        "total": reviews.count(),
        "pending": reviews.filter(status="PENDING").count(),
        "confirmed": reviews.filter(status="CONFIRMED").count(),
        "not_duplicate": reviews.filter(status="NOT_DUPLICATE").count(),
        "exact": reviews.filter(
            explanation__icontains="exact"
        ).count(),
    }


def get_run_or_404(run_id):
    """Fetch a pipeline run or return a 404 response."""
    return get_object_or_404(PipelineRun, run_id=run_id)


def csv_response(filename, headers, rows):
    """Create a downloadable CSV response."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    writer = csv.writer(response)
    writer.writerow(headers)

    for row in rows:
        writer.writerow(row)

    return response


def serialize_json(value):
    """Serialize JSON-compatible values for CSV export."""
    return json.dumps(value, ensure_ascii=False, default=str)


# ---------------------------------------------------------
# Dashboard
# ---------------------------------------------------------

def dashboard(request):
    runs = PipelineRun.objects.order_by("-started_at")

    total_runs = runs.count()

    totals = SourceRecord.objects.aggregate(
        valid_count=Count("pk", filter=Q(is_valid=True)),
        rejected_count=Count("pk", filter=Q(is_valid=False)),
    )

    review_counts = get_review_counts(DuplicateReview.objects.all())

    context = {
        "run_count": total_runs,
        "valid_count": totals["valid_count"] or 0,
        "rejected_count": totals["rejected_count"] or 0,
        "pending_count": review_counts["pending"],
        "review_counts": review_counts,
        "recent_runs": runs[:10],
    }

    return render(
        request,
        "deduplication/dashboard.html",
        context,
    )


# ---------------------------------------------------------
# CSV upload and pipeline execution
# ---------------------------------------------------------

def upload_csv(request):
    # GET: Display the CSV upload form
    if request.method == "GET":
        return render(request, "deduplication/upload.html")

    # POST: Process the uploaded CSV
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])

    uploaded_file = request.FILES.get("file")
    record_type = request.POST.get("record_type", "CUSTOMER").upper()
    source_system = request.POST.get("source_system", "CSV").strip()

    if not uploaded_file:
        messages.error(request, "Please select a CSV file.")
        return redirect("upload_csv")

    if not uploaded_file.name.lower().endswith(".csv"):
        messages.error(request, "Please upload a CSV file.")
        return redirect("upload_csv")

    if record_type not in {"CUSTOMER", "PRODUCT"}:
        messages.error(request, "Select a valid record type.")
        return redirect("upload_csv")

    if not source_system:
        source_system = "CSV"

    try:
        result = run_pipeline(
            file_obj=uploaded_file,
            record_type=record_type,
            source_system=source_system,
            source_file=uploaded_file.name,
        )

        run_id = result.get("run_id")

        if run_id:
            messages.success(
                request,
                "CSV processing finished. Review the run results below.",
            )
            return redirect("run_detail", run_id=run_id)

        messages.warning(
            request,
            "The pipeline returned without a run ID. "
            "Check the latest pipeline run for details.",
        )
        return redirect("run_list")

    except Exception:
        messages.error(
            request,
            "CSV processing failed. Check the Django terminal logs "
            "for the technical error.",
        )
        return redirect("upload_csv")


# ---------------------------------------------------------
# Pipeline run details
# ---------------------------------------------------------


def run_detail(request, run_id):
    run = get_run_or_404(run_id)

    # 1. Source records
    records_qs = SourceRecord.objects.filter(
        run=run
    ).order_by("source_file", "source_row_number")

    # 2. Rejected records
    # Invalid records are stored in SourceRecord for this workflow.
    rejects_qs = SourceRecord.objects.filter(
        run=run,
        is_valid=False
    ).order_by("source_file", "source_row_number")

    # 3. Published merged records
    merged_records_qs = (
        MergedRecord.objects.filter(run=run)
        .prefetch_related("lineage__source_record")
        .order_by("-created_at")
    )

    # 4. Duplicate reviews belonging to this run
    reviews_qs = (
        DuplicateReview.objects.filter(
            record_a__run=run,
            record_b__run=run,
        )
        .select_related("record_a", "record_b")
        .order_by("-created_at")
    )

    # Overall review counts, independent of pagination
    review_counts = get_review_counts(reviews_qs)

    # 5. Independent pagination: 25 entries per page
    records_page = Paginator(records_qs, 25).get_page(
        request.GET.get("records_page")
    )

    rejects_page = Paginator(rejects_qs, 25).get_page(
        request.GET.get("rejects_page")
    )

    merged_page = Paginator(merged_records_qs, 25).get_page(
        request.GET.get("merged_page")
    )

    reviews_page = Paginator(reviews_qs, 25).get_page(
        request.GET.get("reviews_page")
    )

    # 6. Template context
    context = {
        "run": run,

        "records": records_page,
        "rejects": rejects_page,
        "merged_records": merged_page,
        "reviews": reviews_page,

        "records_page": records_page,
        "rejects_page": rejects_page,
        "merged_page": merged_page,
        "reviews_page": reviews_page,

        "review_counts": review_counts,
        "pending_count": review_counts.get("pending", 0),
    }

    return render(
        request,
        "deduplication/run_detail.html",
        context,
    )


# ---------------------------------------------------------
# Duplicate review inbox
# ---------------------------------------------------------


def duplicate_reviews(request):
    reviews = DuplicateReview.objects.select_related(
        "record_a",
        "record_b",
        "record_a__run",
        "record_b__run",
    ).order_by("-created_at")

    status_filter = request.GET.get("status", "").upper().strip()
    record_type_filter = request.GET.get("record_type", "").upper().strip()
    run_filter = request.GET.get("run", "").strip()

    allowed_statuses = {
        "PENDING",
        "CONFIRMED",
        "NOT_DUPLICATE",
    }

    if status_filter in allowed_statuses:
        reviews = reviews.filter(status=status_filter)

    if record_type_filter in {"CUSTOMER", "PRODUCT"}:
        reviews = reviews.filter(
            record_a__record_type=record_type_filter,
            record_b__record_type=record_type_filter,
        )

    if run_filter:
        try:
            reviews = reviews.filter(
                record_a__run__run_id=run_filter,
                record_b__run__run_id=run_filter,
            )
        except (TypeError, ValueError):
            reviews = reviews.none()

    # Calculate aggregate review counts without loading every review.
    review_counts = get_review_counts(reviews)

    # Load only 25 reviews per page.
    paginator = Paginator(reviews, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "reviews": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "review_counts": review_counts,
        "status_filter": status_filter,
        "record_type_filter": record_type_filter,
        "run_filter": run_filter,
        "runs": PipelineRun.objects.order_by("-started_at")[:50],
    }

    return render(
        request,
        "deduplication/duplicate_reviews.html",
        context,
    )


@require_POST
def decide_duplicate_review(request, review_id):
    review = get_object_or_404(
        DuplicateReview.objects.select_related("record_a", "record_b"),
        pk=review_id,
    )

    decision = request.POST.get("decision", "").upper().strip()

    if decision not in {"CONFIRMED", "NOT_DUPLICATE"}:
        messages.error(request, "Invalid duplicate-review decision.")
        return redirect("duplicate_reviews")

    try:
        resolve_duplicate_review(review, decision)
        messages.success(
            request,
            f"Review #{review.pk} updated to {decision}.",
        )
    except (ValueError, TypeError):
        messages.error(
            request,
            "The review could not be updated. "
            "Check whether it has already been resolved.",
        )
    except Exception:
        messages.error(
            request,
            "The review could not be updated. "
            "Check the Django terminal logs for details.",
        )

    return redirect("duplicate_reviews")


# ---------------------------------------------------------
# Merge confirmed duplicate groups
# ---------------------------------------------------------

@require_POST
def merge_run(request, run_id):
    run = get_run_or_404(run_id)

    try:
        result = merge_confirmed_reviews(run)

        messages.success(
            request,
            "Confirmed duplicate records were processed for merging.",
        )

        if isinstance(result, dict):
            detail = result.get("message")
            if detail:
                messages.info(request, str(detail))

    except Exception:
        messages.error(
            request,
            "The merge operation failed. Check the Django terminal logs "
            "for the underlying error.",
        )

    return redirect("run_detail", run_id=run_id)


# ---------------------------------------------------------
# Merged records
# ---------------------------------------------------------

def merged_records(request):
    records = (
        MergedRecord.objects.select_related("run")
        .prefetch_related("lineage__source_record")
        .order_by("-created_at")
    )

    record_type_filter = (
        request.GET.get("record_type", "").upper().strip()
    )

    if record_type_filter in {"CUSTOMER", "PRODUCT"}:
        records = records.filter(record_type=record_type_filter)

    context = {
        "records": records,
        "record_type_filter": record_type_filter,
    }

    return render(
        request,
        "deduplication/merged_records.html",
        context,
    )


# ---------------------------------------------------------
# CSV exports
# ---------------------------------------------------------

def export_run(request, run_id, kind):
    run = get_run_or_404(run_id)
    kind = kind.lower().strip()

    if kind == "records":
        records = SourceRecord.objects.filter(
            run=run
        ).order_by("source_file", "source_row_number")

        rows = (
            [
                record.source_record_id,
                record.record_type,
                record.source_system,
                record.source_file,
                record.source_row_number,
                record.is_valid,
                serialize_json(record.raw_data),
                serialize_json(record.normalized_data),
                serialize_json(record.validation_errors),
            ]
            for record in records
        )

        return csv_response(
            f"commerceclean_records_{run.run_id}.csv",
            [
                "source_record_id",
                "record_type",
                "source_system",
                "source_file",
                "source_row_number",
                "is_valid",
                "raw_data",
                "normalized_data",
                "validation_errors",
            ],
            rows,
        )

    if kind == "reviews":
        reviews = DuplicateReview.objects.filter(
            record_a__run=run,
            record_b__run=run,
        ).select_related("record_a", "record_b")

        rows = (
            [
                review.pk,
                review.record_a.source_record_id,
                review.record_b.source_record_id,
                review.confidence_score,
                review.status,
                review.explanation,
                review.created_at,
            ]
            for review in reviews
        )

        return csv_response(
            f"commerceclean_reviews_{run.run_id}.csv",
            [
                "review_id",
                "record_a_id",
                "record_b_id",
                "confidence_score",
                "status",
                "explanation",
                "created_at",
            ],
            rows,
        )

    if kind == "rejects":
        rejects = IngestionReject.objects.filter(
            run=run
        ).order_by("source_file", "source_row_number")

        rows = (
            [
                reject.source_file,
                reject.source_row_number,
                serialize_json(reject.raw_data),
                serialize_json(reject.rejection_errors),
            ]
            for reject in rejects
        )

        return csv_response(
            f"commerceclean_rejects_{run.run_id}.csv",
            [
                "source_file",
                "source_row_number",
                "raw_data",
                "rejection_errors",
            ],
            rows,
        )

    if kind == "merged":
        records = (
            MergedRecord.objects.filter(run=run)
            .prefetch_related("lineage__source_record")
            .order_by("-created_at")
        )

        rows = (
            [
                record.canonical_id,
                record.record_type,
                serialize_json(record.merged_data),
                serialize_json(record.survivorship_explanation),
                record.created_at,
            ]
            for record in records
        )

        return csv_response(
            f"commerceclean_merged_{run.run_id}.csv",
            [
                "canonical_id",
                "record_type",
                "merged_data",
                "survivorship_explanation",
                "created_at",
            ],
            rows,
        )

    raise Http404("Unknown export type.")

def run_list(request):
    return render(
        request,
        "deduplication/run_list.html",
        {
            "runs": PipelineRun.objects.order_by("-started_at")
        },
    )