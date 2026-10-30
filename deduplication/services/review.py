from django.core.exceptions import ValidationError
from django.db import transaction

from deduplication.models import DuplicateReview, SourceRecord
from deduplication.services.candidate_generation import (
    generate_candidate_pairs,
)
from deduplication.services.matching import match_records


def create_duplicate_reviews(source_records, threshold=0.70):
    """
    Generate candidate pairs and compare only those pairs.

    Valid records with normalized data are considered. Candidate pairs
    are compared using the existing matching service. Exact and probable
    matches that meet the threshold are saved as PENDING reviews.

    Existing review pairs are not duplicated.

    Returns the created or existing review objects.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0.")

    records = list(source_records)

    # Validate every input before filtering invalid records.
    for record in records:
        if not isinstance(record, SourceRecord):
            raise TypeError(
                "Every item must be a SourceRecord instance."
            )

        if record.pk is None:
            raise ValueError(
                "All source records must be saved before matching."
            )

    # Keep only valid records with normalized data.
    eligible_records = [
        record
        for record in records
        if record.is_valid and record.normalized_data
    ]

    # Candidate generation avoids comparing every possible pair.
    candidate_pairs = generate_candidate_pairs(eligible_records)

    reviews = []

    with transaction.atomic():
        for record_a, record_b in candidate_pairs:
            if record_a.pk == record_b.pk:
                continue

            if record_a.record_type != record_b.record_type:
                continue

            result = match_records(
                record_a.normalized_data,
                record_b.normalized_data,
                record_a.record_type,
            )

            if result["match_type"] not in {
                "PROBABLE_DUPLICATE",
                "EXACT_DUPLICATE",
            }:
                continue

            if result["score"] < threshold:
                continue

            # Canonicalize the pair so A/B and B/A are equivalent.
            first_id, second_id = sorted(
                (record_a.pk, record_b.pk)
            )

            review, _ = DuplicateReview.objects.get_or_create(
                record_a_id=first_id,
                record_b_id=second_id,
                defaults={
                    "confidence_score": result["score"],
                    "explanation": result["explanation"],
                    "status": DuplicateReview.ReviewStatus.PENDING,
                },
            )

            reviews.append(review)

    return reviews


def resolve_duplicate_review(review, decision):
    """
    Resolve a pending duplicate review.

    decision must be CONFIRMED or NOT_DUPLICATE.
    This records the review decision; it does not merge records.
    """
    if not isinstance(review, DuplicateReview):
        raise TypeError("review must be a DuplicateReview instance.")

    if review.pk is None:
        raise ValueError("Save the review before resolving it.")

    if decision not in {
        DuplicateReview.ReviewStatus.CONFIRMED,
        DuplicateReview.ReviewStatus.NOT_DUPLICATE,
    }:
        raise ValueError(
            "decision must be CONFIRMED or NOT_DUPLICATE."
        )

    with transaction.atomic():
        review = DuplicateReview.objects.select_for_update().get(
            pk=review.pk
        )

        if review.status != DuplicateReview.ReviewStatus.PENDING:
            raise ValidationError(
                "Only pending reviews can be resolved."
            )

        review.status = decision
        review.save(update_fields=["status"])

    return review
