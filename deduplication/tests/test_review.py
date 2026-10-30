
from django.core.exceptions import ValidationError
from django.test import TestCase

from deduplication.models import (
    DuplicateReview,
    PipelineRun,
    SourceRecord,
)
from deduplication.services.review import (
    create_duplicate_reviews,
    resolve_duplicate_review,
)


class DuplicateReviewServiceTests(TestCase):
    def setUp(self):
        self.pipeline_run = PipelineRun.objects.create()

    def make_customer(self, record_id, name, email, phone=""):
        return SourceRecord.objects.create(
            source_record_id=record_id,
            record_type="CUSTOMER",
            source_system="CSV",
            raw_data={
                "name": name,
                "email": email,
                "phone": phone,
            },
            normalized_data={
                "name": name.casefold(),
                "email": email.casefold(),
                "phone": "".join(
                    character for character in phone
                    if character.isdigit()
                ),
            },
            is_valid=True,
            validation_errors=[],
            run=self.pipeline_run,
        )

    def test_probable_match_creates_pending_review(self):
        first = self.make_customer(
            "C101", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C102", "Alice Smith", "alice@example.com"
        )

        reviews = create_duplicate_reviews([first, second])

        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].status, "PENDING")
        self.assertEqual(DuplicateReview.objects.count(), 1)

    def test_non_match_does_not_create_review(self):
        first = self.make_customer(
            "C103", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C104", "Bob Jones", "bob@example.com"
        )

        create_duplicate_reviews([first, second])

        self.assertEqual(DuplicateReview.objects.count(), 0)

    def test_repeated_matching_does_not_duplicate_review(self):
        first = self.make_customer(
            "C105", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C106", "Alice Smith", "alice@example.com"
        )

        create_duplicate_reviews([first, second])
        create_duplicate_reviews([second, first])

        self.assertEqual(DuplicateReview.objects.count(), 1)

    def test_review_can_be_confirmed(self):
        first = self.make_customer(
            "C107", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C108", "Alice Smith", "alice@example.com"
        )

        review = create_duplicate_reviews([first, second])[0]
        resolved = resolve_duplicate_review(
            review, DuplicateReview.ReviewStatus.CONFIRMED
        )

        self.assertEqual(resolved.status, "CONFIRMED")

    def test_review_can_be_rejected(self):
        first = self.make_customer(
            "C109", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C110", "Alice Smith", "alice@example.com"
        )

        review = create_duplicate_reviews([first, second])[0]
        resolved = resolve_duplicate_review(
            review, DuplicateReview.ReviewStatus.NOT_DUPLICATE
        )

        self.assertEqual(resolved.status, "NOT_DUPLICATE")

    def test_resolved_review_cannot_be_resolved_again(self):
        first = self.make_customer(
            "C111", "Alice Smith", "alice@example.com"
        )
        second = self.make_customer(
            "C112", "Alice Smith", "alice@example.com"
        )

        review = create_duplicate_reviews([first, second])[0]
        resolve_duplicate_review(
            review, DuplicateReview.ReviewStatus.CONFIRMED
        )

        with self.assertRaises(ValidationError):
            resolve_duplicate_review(
                review, DuplicateReview.ReviewStatus.NOT_DUPLICATE
            )
