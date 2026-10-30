
import csv



def _validated_reader(file_obj):
    """Create a CSV reader and validate its first nonblank header row."""
    reader = csv.reader(file_obj, strict=True)

    try:
        raw_headers = next(reader)

        # Skip blank lines before the actual header.
        while not raw_headers or all(
            not str(value).strip() for value in raw_headers
        ):
            raw_headers = next(reader)

    except StopIteration:
        raise ValueError(
            "CSV file must contain a non-empty header row."
        ) from None
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV header: {exc}") from exc

    headers = [
        header.strip() if header else ""
        for header in raw_headers
    ]

    if headers:
        headers[0] = headers[0].lstrip("\ufeff")

    if any(not header for header in headers):
        raise ValueError("CSV column names cannot be blank.")

    normalized_headers = [header.casefold() for header in headers]

    if len(normalized_headers) != len(set(normalized_headers)):
        raise ValueError("CSV column names must be unique.")

    return reader, headers



def iter_csv_records_with_row_numbers(file_obj):
    """
    Yield (physical_start_line, record) pairs.

    Supports quoted values containing commas and multiline fields.
    Rejects rows with missing or extra columns.
    """
    reader, headers = _validated_reader(file_obj)
    previous_line_number = reader.line_num

    while True:
        start_line_number = previous_line_number + 1

        try:
            values = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            raise ValueError(
                f"Invalid CSV near row {start_line_number}: {exc}"
            ) from exc

        previous_line_number = reader.line_num

        if not values or all(
            value is None or not str(value).strip()
            for value in values
        ):
            continue

        if len(values) != len(headers):
            if len(values) > len(headers):
                raise ValueError(
                    f"CSV row {start_line_number} contains "
                    f"{len(values) - len(headers)} extra values. "
                    f"Expected {len(headers)} columns, "
                    f"found {len(values)}."
                )

            raise ValueError(
                f"CSV row {start_line_number} has "
                f"{len(headers) - len(values)} missing columns. "
                f"Expected {len(headers)} columns, "
                f"found {len(values)}."
            )

        yield start_line_number, dict(zip(headers, values))


def iter_csv_records(file_obj):
    """Yield CSV records without row numbers."""
    for _, record in iter_csv_records_with_row_numbers(file_obj):
        yield record


def read_csv_records(file_obj):
    """Read all CSV records into a list."""
    return list(iter_csv_records(file_obj))
