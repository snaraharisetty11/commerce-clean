
from django.db import transaction

from deduplication.models import (
    MergedRecord,
    RecordLineage,
    SourceRecord,
)


def record_lineage(merged_record, source_records, contributions=None):
    """Link a merged record to its original contributing source records."""

    if not isinstance(merged_record, MergedRecord):
        raise TypeError("merged_record must be a MergedRecord instance.")

    if merged_record.pk is None:
        raise ValueError("Save the merged record before recording lineage.")

    source_records = list(source_records)

    if not source_records:
        raise ValueError("At least one source record is required.")

    for source_record in source_records:
        if not isinstance(source_record, SourceRecord):
            raise TypeError(
                "Every source record must be a SourceRecord instance."
            )

        if source_record.pk is None:
            raise ValueError(
                "Save every source record before recording lineage."
            )

        if source_record.run.pk != merged_record.run.pk:
            raise ValueError(
                "Source and merged records must belong to the same pipeline run."
            )

        if source_record.record_type != merged_record.record_type:
            raise ValueError(
                "Source and merged records must have the same record type."
            )

    source_ids = [record.pk for record in source_records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Source records must not contain duplicates.")

    if contributions is None:
        contributions = {}

    if not isinstance(contributions, dict):
        raise TypeError("contributions must be a dictionary.")

    lineage_records = []

    with transaction.atomic():
        for source_record in source_records:
            details = contributions.get(source_record.pk, {})

            if not isinstance(details, dict):
                raise TypeError(
                    "Each contribution detail must be a dictionary."
                )

            lineage, _ = RecordLineage.objects.update_or_create(
                merged_record=merged_record,
                source_record=source_record,
                defaults={"contribution_details": details},
            )
            lineage_records.append(lineage)

    return lineage_records
