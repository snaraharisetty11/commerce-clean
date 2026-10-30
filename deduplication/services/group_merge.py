
from django.db import transaction

from deduplication.models import (
    DuplicateReview,
    MergedRecord,
    PipelineRun,
    RecordLineage,
    SourceRecord,
)
from deduplication.services.lineage import record_lineage
from deduplication.services.survivorship import select_survivor


def _build_connected_groups(edges):
    """Return connected components containing at least two source records."""
    adjacency = {}

    for record_a_id, record_b_id in edges:
        adjacency.setdefault(record_a_id, set()).add(record_b_id)
        adjacency.setdefault(record_b_id, set()).add(record_a_id)

    groups = []
    visited = set()

    for start_id in sorted(adjacency):
        if start_id in visited:
            continue

        stack = [start_id]
        visited.add(start_id)
        group = []

        while stack:
            current_id = stack.pop()
            group.append(current_id)

            for neighbor_id in sorted(adjacency[current_id], reverse=True):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    stack.append(neighbor_id)

        if len(group) >= 2:
            groups.append(sorted(group))

    return groups


def _source_data_for(records):
    """Prepare normalized source data for field-level survivorship."""
    return [
        {
            **record.normalized_data,
            "source_system": record.source_system,
            "source_record_id": record.source_record_id,
        }
        for record in records
    ]


@transaction.atomic
def _merge_group(
    run,
    record_ids,
    review_ids,
    source_priority=None,
):
    """Merge one connected group, preserving all source records and lineage."""
    records = list(
        SourceRecord.objects.select_for_update()
        .filter(
            run=run,
            pk__in=record_ids,
        )
        .order_by("pk")
    )

    if len(records) != len(record_ids):
        raise ValueError(
            "A source record in the duplicate group is missing "
            "from this pipeline run."
        )

    if any(not record.is_valid for record in records):
        raise ValueError(
            "Invalid source records cannot be merged."
        )

    record_types = {record.record_type for record in records}
    if len(record_types) != 1:
        raise ValueError(
            "All records in a duplicate group must have the same type."
        )

    if any(not record.normalized_data for record in records):
        raise ValueError(
            "Every record in a duplicate group must have normalized data."
        )

    existing_lineage = list(
        RecordLineage.objects.filter(
            source_record_id__in=record_ids,
        ).select_related("merged_record")
    )

    existing_merged_ids = {
        entry.merged_record.pk for entry in existing_lineage
    }

    if len(existing_merged_ids) > 1:
        raise ValueError(
            "Records in this group already belong to different merged "
            "records; manual reconciliation is required."
        )

    merged_data, explanation = select_survivor(
        _source_data_for(records),
        source_priority=source_priority,
    )

    if existing_merged_ids:
        merged_record = MergedRecord.objects.select_for_update().get(
            pk=next(iter(existing_merged_ids))
        )

        # Extend the existing canonical record instead of creating
        # a second one when some group members already have lineage.
        merged_record.merged_data = merged_data
        merged_record.survivorship_explanation = explanation
        merged_record.save(
            update_fields=[
                "merged_data",
                "survivorship_explanation",
            ]
        )
    else:
        merged_record = MergedRecord.objects.create(
            record_type=records[0].record_type,
            merged_data=merged_data,
            survivorship_explanation=explanation,
            run=run,
        )

    contributions = {
        record.pk: {
            "review_ids": review_ids,
            "decision": "CONFIRMED",
        }
        for record in records
    }

    record_lineage(
        merged_record,
        records,
        contributions=contributions,
    )

    return merged_record


def merge_confirmed_groups(run, source_priority=None):
    """
    Merge connected groups of confirmed duplicate reviews for one run.

    A connected group of two or more source records produces one
    canonical merged record. Original source records are retained.

    Returns merged group summaries and errors for groups that could
    not be merged.
    """
    if not isinstance(run, PipelineRun) or run.pk is None:
        raise ValueError("run must be a saved PipelineRun instance.")

    reviews = list(
        DuplicateReview.objects.filter(
            status=DuplicateReview.ReviewStatus.CONFIRMED,
            record_a__run=run,
            record_b__run=run,
        )
        .order_by("pk")
        .values_list("pk", "record_a_id", "record_b_id")
    )

    if not reviews:
        return {
            "run_id": str(run.run_id),
            "group_count": 0,
            "merged_count": 0,
            "merged_record_ids": [],
            "groups": [],
            "errors": [],
        }

    edges = [
        (record_a_id, record_b_id)
        for _, record_a_id, record_b_id in reviews
    ]
    review_ids_by_edge = {}

    for review_id, record_a_id, record_b_id in reviews:
        edge = tuple(sorted((record_a_id, record_b_id)))
        review_ids_by_edge.setdefault(edge, []).append(review_id)

    groups = _build_connected_groups(edges)
    group_results = []
    errors = []
    merged_ids = set()

    for record_ids in groups:
        group_set = set(record_ids)
        group_review_ids = sorted({
            review_id
            for edge, ids in review_ids_by_edge.items()
            if set(edge).issubset(group_set)
            for review_id in ids
        })

        try:
            merged_record = _merge_group(
                run=run,
                record_ids=record_ids,
                review_ids=group_review_ids,
                source_priority=source_priority,
            )
            merged_ids.add(merged_record.pk)
            group_results.append({
                "source_record_ids": record_ids,
                "merged_record_id": str(merged_record.canonical_id),
            })

        except Exception as exc:
            errors.append({
                "source_record_ids": record_ids,
                "error": str(exc),
            })

    return {
        "run_id": str(run.run_id),
        "group_count": len(groups),
        "merged_count": len(merged_ids),
        "merged_record_ids": [
            str(
                MergedRecord.objects.get(pk=merged_id).canonical_id
            )
            for merged_id in sorted(merged_ids)
        ],
        "groups": group_results,
        "errors": errors,
    }
