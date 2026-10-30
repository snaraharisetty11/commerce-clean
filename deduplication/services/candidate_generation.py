
from collections import defaultdict
from itertools import combinations

from .normalization import normalize_text


def _clean(value):
    """Return normalized text for candidate blocking."""
    return normalize_text(value)


def _candidate_keys(record):
    """
    Generate selective blocking keys.

    Customers:
    - Exact normalized email
    - Exact normalized phone

    Products:
    - Exact normalized SKU
    - Existing name-token prefixes
    - Exact normalized brand

    Broad first-character blocks are intentionally excluded.
    """
    data = record.normalized_data or {}

    if not isinstance(data, dict):
        raise ValueError(
            f"Record {record.pk} has invalid normalized_data; "
            "expected a dictionary."
        )

    record_type = record.record_type
    keys = set()

    if record_type == "CUSTOMER":
        email = _clean(data.get("email"))
        phone = "".join(
            character
            for character in str(data.get("phone") or "")
            if character.isdigit()
        )

        if email:
            keys.add(("email", email))

        if phone:
            keys.add(("phone", phone))

    elif record_type == "PRODUCT":
        sku = _clean(data.get("sku"))
        name = _clean(data.get("name"))
        brand = _clean(data.get("brand"))

        if sku:
            keys.add(("sku", sku))

        for token in name.split():
            if len(token) >= 2:
                keys.add(("product_name_prefix", token[:2]))

        if brand:
            keys.add(("brand", brand))

    else:
        raise ValueError("Unsupported source record type.")

    return keys


def generate_candidate_pairs(source_records):
    """
    Generate unique candidate pairs in deterministic primary-key order.

    Only valid records of the same type are compared. Each pair is
    returned once, even when it shares multiple blocking keys.
    """
    records = list(source_records)

    for record in records:
        if record.pk is None:
            raise ValueError(
                "All source records must be saved before blocking."
            )

        if record.record_type not in {"CUSTOMER", "PRODUCT"}:
            raise ValueError("Unsupported source record type.")

    blocks = defaultdict(dict)

    for record in records:
        if not record.is_valid or not record.normalized_data:
            continue

        for key in _candidate_keys(record):
            blocks[(record.record_type, key)][record.pk] = record

    pairs_by_id = {}

    for block_records in blocks.values():
        ordered_records = sorted(
            block_records.values(),
            key=lambda item: item.pk,
        )

        for record_a, record_b in combinations(ordered_records, 2):
            pair_key = (record_a.pk, record_b.pk)
            pairs_by_id[pair_key] = (record_a, record_b)

    return [
        pairs_by_id[pair_key]
        for pair_key in sorted(pairs_by_id)
    ]
