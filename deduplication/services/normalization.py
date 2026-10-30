
import re
import unicodedata


def normalize_text(value):
    """Trim whitespace, normalize Unicode, and standardize case."""
    if value is None:
        return ""

    value = unicodedata.normalize("NFKC", str(value))
    value = value.strip().casefold()
    value = re.sub(r"\s+", " ", value)

    return value


def normalize_email(value):
    """Normalize an email for comparison."""
    return normalize_text(value)


def normalize_phone(value):
    """Keep digits only for basic phone-number comparison."""
    if value is None:
        return ""

    return re.sub(r"\D", "", str(value))


def normalize_record(record, record_type):
    """Return a normalized copy without modifying the original."""

    if not isinstance(record, dict):
        raise TypeError("Record must be a dictionary/object.")

    if isinstance(record_type, str):
        record_type = record_type.strip().upper()
    else:
        record_type = ""

    normalized = {}

    for key, value in record.items():
        normalized_key = normalize_text(key)

        if normalized_key in normalized:
            raise ValueError(
                "Record contains duplicate keys after normalization."
            )

        if isinstance(value, str):
            normalized[normalized_key] = normalize_text(value)
        else:
            normalized[normalized_key] = value

    if record_type == "CUSTOMER":
        if "email" in normalized:
            normalized["email"] = normalize_email(
                normalized["email"]
            )

        if "phone" in normalized:
            normalized["phone"] = normalize_phone(
                normalized["phone"]
            )

    elif record_type == "PRODUCT":
        if "sku" in normalized:
            normalized["sku"] = normalize_text(
                normalized["sku"]
            )

    return normalized
