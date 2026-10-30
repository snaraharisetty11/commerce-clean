
from difflib import SequenceMatcher

from .normalization import normalize_record, normalize_text


VALID_RECORD_TYPES = {"CUSTOMER", "PRODUCT"}


def similarity(value_a, value_b):
    """Return normalized text similarity between 0.0 and 1.0."""
    normalized_a = normalize_text(value_a)
    normalized_b = normalize_text(value_b)

    if not normalized_a or not normalized_b:
        return 0.0

    return SequenceMatcher(
        None,
        normalized_a,
        normalized_b,
    ).ratio()


def _has_exact_match_identity(record, record_type):
    """Require meaningful identity evidence before declaring an exact match."""
    if record_type == "CUSTOMER":
        return bool(record.get("email") or record.get("phone"))

    return bool(record.get("sku") or record.get("name"))


def _business_fields(record):
    """
    Exclude the source-specific ID from equality comparison.

    Different source IDs identify separate ingested rows; they do not
    necessarily identify different real-world customers or products.
    """
    return {
        key: value
        for key, value in record.items()
        if key != "source_record_id"
    }


def match_records(record_a, record_b, record_type):
    """
    Compare two customer or product records.

    Identical normalized business fields with sufficient identity evidence
    are exact duplicates. Stronger-than-threshold non-identical records
    are probable duplicates. No records are merged here.
    """
    if not isinstance(record_type, str):
        raise ValueError("record_type must be CUSTOMER or PRODUCT")

    record_type = record_type.strip().upper()

    if record_type not in VALID_RECORD_TYPES:
        raise ValueError("record_type must be CUSTOMER or PRODUCT")

    if not isinstance(record_a, dict) or not isinstance(record_b, dict):
        raise TypeError("Both records must be dictionaries.")

    a = normalize_record(record_a, record_type)
    b = normalize_record(record_b, record_type)

    business_a = _business_fields(a)
    business_b = _business_fields(b)

    if (
        business_a == business_b
        and _has_exact_match_identity(a, record_type)
    ):
        return {
            "match_type": "EXACT_DUPLICATE",
            "score": 1.0,
            "explanation": (
                "All normalized business fields match exactly, "
                "excluding the source-specific record ID, and "
                "identity evidence is present."
            ),
        }

    score = 0.0
    reasons = []

    if record_type == "CUSTOMER":
        email_a = a.get("email")
        email_b = b.get("email")
        phone_a = a.get("phone")
        phone_b = b.get("phone")

        if email_a and email_a == email_b:
            score += 0.45
            reasons.append("Email matches")

        if phone_a and phone_a == phone_b:
            score += 0.30
            reasons.append("Phone matches")

        name_score = similarity(a.get("name"), b.get("name"))
        score += 0.25 * name_score

        if name_score >= 0.80:
            reasons.append("Names are similar")

    else:
        sku_a = a.get("sku")
        sku_b = b.get("sku")

        if sku_a and sku_a == sku_b:
            score += 0.60
            reasons.append("SKU matches")

        name_score = similarity(a.get("name"), b.get("name"))
        score += 0.30 * name_score

        if name_score >= 0.80:
            reasons.append("Product names are similar")

        brand_a = a.get("brand")
        brand_b = b.get("brand")
        brand_score = similarity(brand_a, brand_b)

        score += 0.10 * brand_score

        if (
            brand_a
            and brand_b
            and brand_score >= 0.80
        ):
            reasons.append("Brand matches closely")

    score = round(min(score, 1.0), 4)

    if score >= 0.70:
        match_type = "PROBABLE_DUPLICATE"
        explanation = (
            "; ".join(reasons)
            or "Similarity score exceeds the review threshold."
        )
    else:
        match_type = "NOT_DUPLICATE"
        explanation = (
            "; ".join(reasons)
            or "Insufficient matching evidence."
        )

    return {
        "match_type": match_type,
        "score": score,
        "explanation": explanation,
    }
