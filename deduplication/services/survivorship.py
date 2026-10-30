
import json


METADATA_FIELDS = {
    "source_system",
    "source_record_id",
    "updated_at",
}


def is_empty(value):
    """Return True when a field has no useful value."""
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def select_survivor(records, source_priority=None):
    """
    Merge records using transparent field-level survivorship rules.

    Rules:
    1. Prefer sources with a lower configured priority number.
    2. If priorities tie, prefer the more complete record.
    3. If still tied, use a deterministic record-content tie-break.
    4. For each field, select the first non-empty value.
    5. Record the source and rule used for every selected field.

    Returns:
        (merged_data, explanation)
    """
    if not records:
        raise ValueError("At least one record is required.")

    source_priority = source_priority or {}

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Every record must be a dictionary.")

    def completeness(record):
        return sum(
            1
            for key, value in record.items()
            if key not in METADATA_FIELDS and not is_empty(value)
        )

    def sort_key(record):
        source = record.get("source_system", "")
        priority = source_priority.get(source, 999)

        return (
            priority,
            -completeness(record),
            str(record.get("source_record_id", "")),
            json.dumps(record, sort_keys=True, default=str),
        )

    ordered_records = sorted(records, key=sort_key)

    fields = sorted({
        key
        for record in ordered_records
        for key in record
        if key not in METADATA_FIELDS
    })

    merged_data = {}
    explanation = {}

    for field in fields:
        for record in ordered_records:
            value = record.get(field)

            if not is_empty(value):
                merged_data[field] = value
                explanation[field] = {
                    "selected_value": value,
                    "source_system": record.get(
                        "source_system", "UNKNOWN"
                    ),
                    "source_record_id": record.get(
                        "source_record_id", "UNKNOWN"
                    ),
                    "rule": (
                        "First non-empty value according to "
                        "source priority, completeness, and "
                        "deterministic tie-break."
                    ),
                }
                break

    return merged_data, explanation
