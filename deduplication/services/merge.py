from django.db import transaction

from deduplication.models import (
    DuplicateReview,
    MergedRecord,
    RecordLineage,
)
from deduplication.services.lineage import record_lineage
from deduplication.services.survivorship import select_survivor


@transaction.atomic
def merge_confirmed_review(review, source_priority=None):
    """
    Merge the two source records associated with a confirmed duplicate review.

    The operation is transactional and idempotent. If both source records
    have already been linked to the same merged record, that record is
    returned instead of creating a duplicate.
    """
    if not isinstance(review, DuplicateReview):
        raise TypeError("review must be a DuplicateReview instance.")

    if review.pk is None:
        raise ValueError("The duplicate review must be saved before merging.")

    try:
        locked_review = (
            DuplicateReview.objects.select_for_update().get(pk=review.pk)
        )
    except DuplicateReview.DoesNotExist as exc:
        raise ValueError("The duplicate review no longer exists.") from exc

    # Use the stored choice value directly to avoid Pylance's
    # unrecognized DuplicateReview.Status attribute.
    if locked_review.status != "CONFIRMED":
        raise ValueError("Only confirmed duplicate reviews can be merged.")

    record_a = locked_review.record_a
    record_b = locked_review.record_b

    if record_a.pk == record_b.pk:
        raise ValueError("A source record cannot be merged with itself.")

    if record_a.record_type != record_b.record_type:
        raise ValueError("Source records must have the same record type.")

    if record_a.run.pk != record_b.run.pk:
        raise ValueError("Source records must belong to the same pipeline run.")

    if not record_a.is_valid or not record_b.is_valid:
        raise ValueError("Only valid source records can be merged.")

    for record in (record_a, record_b):
        if not isinstance(record.normalized_data, dict):
            raise ValueError(
                f"Normalized data for source record {record.pk} "
                "must be a dictionary."
            )

        if not record.normalized_data:
            raise ValueError(
                f"Normalized data for source record {record.pk} "
                "cannot be empty."
            )

    source_ids = {record_a.pk, record_b.pk}

    # Read the related objects instead of accessing Django-generated
    # foreign-key ID attributes that Pylance may not recognize.
    existing_lineages = list(
        RecordLineage.objects.select_related(
            "merged_record",
            "source_record",
        ).filter(
            source_record__pk__in=source_ids
        )
    )

    if existing_lineages:
        merged_record_ids = {
            lineage.merged_record.pk
            for lineage in existing_lineages
        }

        linked_source_ids = {
            lineage.source_record.pk
            for lineage in existing_lineages
        }

        if len(merged_record_ids) != 1:
            raise ValueError(
                "The source records are already linked to "
                "different merged records."
            )

        if linked_source_ids != source_ids:
            raise ValueError(
                "Incomplete existing lineage found for the source records."
            )

        existing_merged_record = existing_lineages[0].merged_record

        if existing_merged_record.run.pk != record_a.run.pk:
            raise ValueError(
                "The existing merged record belongs to a "
                "different pipeline run."
            )

        if existing_merged_record.record_type != record_a.record_type:
            raise ValueError(
                "The existing merged record has a different record type."
            )

        return existing_merged_record

    source_data = []

    for record in (record_a, record_b):
        data = dict(record.normalized_data)

        data["source_system"] = record.source_system
        data["source_record_id"] = str(record.source_record_id)

        source_data.append(data)

    merged_data, survivorship_explanation = select_survivor(
        source_data,
        source_priority=source_priority,
    )

    merged_record = MergedRecord.objects.create(
        run=record_a.run,
        record_type=record_a.record_type,
        merged_data=merged_data,
        survivorship_explanation=survivorship_explanation,
    )

    decision_value = str(locked_review.status)

    record_lineage(
        merged_record=merged_record,
        source_records=[record_a, record_b],
        contributions={
            record_a.pk: {
                "review_id": locked_review.pk,
                "decision": decision_value,
            },
            record_b.pk: {
                "review_id": locked_review.pk,
                "decision": decision_value,
            },
        },
    )

    return merged_record