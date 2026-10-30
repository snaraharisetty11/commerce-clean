
import re


def validate_record(record, record_type):
    """
    Validate a customer or product record.

    Returns a list of validation errors.
    An empty list means the record passed these checks.
    """
    errors = []

    # The record must be a dictionary.
    if not isinstance(record, dict):
        return ["Record must be a dictionary/object."]

    # Accept record types regardless of letter case or extra spaces.
    if isinstance(record_type, str):
        record_type = record_type.strip().upper()
    else:
        record_type = ""

    if record_type == "CUSTOMER":
        name = record.get("name")
        email = record.get("email")

        if not isinstance(name, str) or not name.strip():
            errors.append("Customer name is required.")

        if not isinstance(email, str) or not email.strip():
            errors.append("Customer email is required.")
        elif not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            email.strip(),
        ):
            errors.append("Customer email format is invalid.")

    elif record_type == "PRODUCT":
        name = record.get("name")
        sku = record.get("sku")
        price = record.get("price")

        if not isinstance(name, str) or not name.strip():
            errors.append("Product name is required.")

        if not isinstance(sku, str) or not sku.strip():
            errors.append("Product SKU is required.")

        if price is None or (
            isinstance(price, str) and not price.strip()
        ):
            errors.append("Product price is required.")
        elif isinstance(price, bool):
            errors.append("Product price must be numeric.")
        else:
            try:
                numeric_price = float(price)

                if not re.fullmatch(
                    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",
                    str(price).strip(),
                ):
                    errors.append("Product price must be numeric.")
                elif numeric_price != numeric_price:
                    errors.append("Product price must be numeric.")
                elif numeric_price in (float("inf"), float("-inf")):
                    errors.append("Product price must be finite.")
                elif numeric_price < 0:
                    errors.append("Product price cannot be negative.")

            except (TypeError, ValueError, OverflowError):
                errors.append("Product price must be numeric.")

    else:
        errors.append("Record type must be CUSTOMER or PRODUCT.")

    return errors
