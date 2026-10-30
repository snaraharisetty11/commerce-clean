
import csv
import io
import shutil
import tempfile

from django.db import IntegrityError, transaction
from django.utils import timezone

from deduplication.models import (
    IngestionReject,
    PipelineRun,
    SourceRecord,
)
from deduplication.services.csv_ingestion import (
    iter_csv_records,
    iter_csv_records_with_row_numbers,
)
from deduplication.services.normalization import normalize_record
from deduplication.services.validation import validate_record


def _prepare_seekable_stream(file_obj):
    """Return a seekable text stream, its starting position, and ownership."""
    try:
        start_position = file_obj.tell()
        file_obj.seek(start_position)
        sample = file_obj.read(0)
    except (AttributeError, OSError, ValueError):
        start_position = None
        sample = file_obj.read(0)

    if isinstance(sample, bytes):
        if start_position is not None:
            file_obj.seek(start_position)

        wrapper = io.TextIOWrapper(
            file_obj,
            encoding="utf-8-sig",
            newline="",
        )
        temporary_stream = tempfile.SpooledTemporaryFile(
            mode="w+t",
            encoding="utf-8",
            newline="",
        )

        try:
            shutil.copyfileobj(wrapper, temporary_stream)
            temporary_stream.seek(0)
        except Exception:
            temporary_stream.close()
            raise
        finally:
            try:
                wrapper.detach()
            except (ValueError, OSError):
                pass

        return temporary_stream, 0, True

    if start_position is not None:
        return file_obj, start_position, False

    temporary_stream = tempfile.SpooledTemporaryFile(
        mode="w+t",
        encoding="utf-8",
        newline="",
    )
    try:
        shutil.copyfileobj(file_obj, temporary_stream)
        temporary_stream.seek(0)
    except Exception:
        temporary_stream.close()
        raise

    return temporary_stream, 0, True


def _set_failed(run, message, input_count=None):
    """Mark a pipeline run as failed."""
    run.status = "FAILED"
    run.error_message = message
    run.finished_at = timezone.now()

    if input_count is not None:
        run.input_count = input_count

    run.save()


def _ingest_seekable_csv(
    file_obj,
    start_position,
    record_type,
    source_system,
    run,
    source_file,
):
    """Validate and ingest CSV records while preserving source traceability."""
    summary = {
        "run_id": str(run.run_id),
        "status": "",
        "input_count": 0,
        "valid_count": 0,
        "rejected_count": 0,
        "duplicate_count": 0,
        "published_count": 0,
        "errors": [],
    }

    # Pass 1: validate the entire CSV structure before database writes.
    try:
        file_obj.seek(start_position)
        input_count = sum(
            1 for _ in iter_csv_records_with_row_numbers(file_obj)
        )
    except (ValueError, csv.Error) as exc:
        _set_failed(run, str(exc))
        summary["status"] = "FAILED"
        summary["errors"].append(str(exc))
        return summary

    summary["input_count"] = input_count

    # Inspect headers, including files that contain no data records.

    # Inspect headers, including files with leading blank lines.
    try:
        file_obj.seek(start_position)
        header_reader = csv.reader(file_obj, strict=True)

        headers = next(header_reader, None)

        while headers is not None and (
            not headers or all(
                not str(value).strip() for value in headers
            )
        ):
            headers = next(header_reader, None)

        if headers is None:
            raise ValueError(
                "CSV file must contain a non-empty header row."
            )

        headers = [
            header.strip() if header else ""
            for header in headers
        ]

        if headers:
            headers[0] = headers[0].lstrip("\ufeff")

    except (StopIteration, csv.Error, ValueError) as exc:
        message = str(exc) or "CSV file must contain a header row."
        _set_failed(run, message, input_count)
        summary["status"] = "FAILED"
        summary["errors"].append(message)
        return summary

    header_map = {
        header.casefold(): header
        for header in headers
    }

    if "source_record_id" not in header_map:
        message = "CSV must contain a source_record_id column."
        _set_failed(run, message, input_count)
        summary["status"] = "FAILED"
        summary["errors"].append(message)
        return summary

    if input_count == 0:
        run.status = "COMPLETED"
        run.input_count = 0
        run.valid_count = 0
        run.rejected_count = 0
        run.published_count = 0
        run.error_message = ""
        run.finished_at = timezone.now()
        run.save()

        summary["status"] = "COMPLETED"
        return summary

    valid_count = 0
    rejected_count = 0
    duplicate_count = 0
    errors = []

    existing_ids = set(
        SourceRecord.objects.filter(
            run=run,
            source_system=source_system,
        ).values_list("source_record_id", flat=True)
    )
    seen_ids = set(existing_ids)

    try:
        file_obj.seek(start_position)

        with transaction.atomic():
            for index, raw_row in iter_csv_records_with_row_numbers(file_obj):
                raw_data = {
                    key.strip().casefold(): value
                    for key, value in raw_row.items()
                }

                source_record_id = raw_data.get("source_record_id")
                if source_record_id is not None:
                    source_record_id = source_record_id.strip()

                # Preserve records that cannot become SourceRecords.
                if not source_record_id:
                    rejection_message = "source_record_id is required."

                    IngestionReject.objects.update_or_create(
                        run=run,
                        source_file=source_file,
                        source_row_number=index,
                        defaults={
                            "raw_data": raw_data,
                            "rejection_errors": [rejection_message],
                        },
                    )

                    rejected_count += 1
                    errors.append(
                        f"CSV record {index}: {rejection_message}"
                    )
                    continue

                # Skip duplicate IDs within this run and source system.
                if source_record_id in seen_ids:
                    duplicate_count += 1
                    errors.append(
                        f"CSV record {index}: duplicate source_record_id "
                        f"'{source_record_id}' was skipped."
                    )
                    continue

                validation_errors = validate_record(
                    raw_data,
                    record_type,
                )
                is_valid = not validation_errors

                try:
                    with transaction.atomic():
                        SourceRecord.objects.create(
                            source_record_id=source_record_id,
                            record_type=record_type,
                            source_system=source_system,
                            source_file=source_file,
                            source_row_number=index,
                            raw_data=raw_data,
                            normalized_data=(
                                normalize_record(raw_data, record_type)
                                if is_valid
                                else {}
                            ),
                            is_valid=is_valid,
                            validation_errors=validation_errors,
                            run=run,
                        )
                except IntegrityError:
                    duplicate_exists = SourceRecord.objects.filter(
                        run=run,
                        source_system=source_system,
                        source_record_id=source_record_id,
                    ).exists()

                    if not duplicate_exists:
                        raise

                    duplicate_count += 1
                    errors.append(
                        f"CSV record {index}: source record ID "
                        f"'{source_record_id}' already exists in this run."
                    )
                    seen_ids.add(source_record_id)
                    continue

                seen_ids.add(source_record_id)

                if is_valid:
                    valid_count += 1
                else:
                    rejected_count += 1
                    errors.extend(
                        f"CSV record {index}: {message}"
                        for message in validation_errors
                    )

    except Exception as exc:
        # The transaction has rolled back before this handler runs.
        run.status = "FAILED"
        run.input_count = input_count
        run.valid_count = 0
        run.rejected_count = 0
        run.published_count = 0
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.save()

        summary.update({
            "status": "FAILED",
            "valid_count": 0,
            "rejected_count": 0,
            "duplicate_count": duplicate_count,
            "errors": errors + [str(exc)],
        })
        raise

    run.status = "COMPLETED"
    run.input_count = input_count
    run.valid_count = valid_count
    run.rejected_count = rejected_count
    run.published_count = 0
    run.error_message = "\n".join(errors)
    run.finished_at = timezone.now()
    run.save()

    summary.update({
        "status": "COMPLETED",
        "valid_count": valid_count,
        "rejected_count": rejected_count,
        "duplicate_count": duplicate_count,
        "published_count": 0,
        "errors": errors,
    })

    return summary


def ingest_csv(
    file_obj,
    record_type,
    source_system="CSV",
    run=None,
    source_file="",
):
    """
    Validate and ingest CSV records incrementally.

    Structural errors are detected before database writes. Unexpected
    processing errors roll back the ingestion batch and mark the run failed.
    """
    if not isinstance(record_type, str):
        raise ValueError("Record type must be CUSTOMER or PRODUCT.")

    record_type = record_type.strip().upper()
    if record_type not in {"CUSTOMER", "PRODUCT"}:
        raise ValueError("Record type must be CUSTOMER or PRODUCT.")

    if not isinstance(source_system, str) or not source_system.strip():
        raise ValueError("Source system must be a non-empty string.")

    source_system = source_system.strip()

    if not isinstance(source_file, str):
        raise ValueError("Source file must be a string.")

    source_file = source_file.strip()

    if run is None:
        run = PipelineRun.objects.create()
    elif not isinstance(run, PipelineRun) or run.pk is None:
        raise ValueError("run must be a saved PipelineRun instance.")

    stream, start_position, owns_stream = _prepare_seekable_stream(file_obj)

    try:
        return _ingest_seekable_csv(
            stream,
            start_position,
            record_type,
            source_system,
            run,
            source_file,
        )
    finally:
        if owns_stream:
            stream.close()
