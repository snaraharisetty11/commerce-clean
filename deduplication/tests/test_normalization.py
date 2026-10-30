
from django.test import SimpleTestCase

from deduplication.services.normalization import (
    normalize_text,
    normalize_email,
    normalize_phone,
    normalize_record,
)


class NormalizationTests(SimpleTestCase):

    def test_removes_extra_spaces_and_lowercases(self):
        self.assertEqual(normalize_text("  SREEJA   Rao  "), "sreeja rao")

    def test_normalizes_email(self):
        self.assertEqual(
            normalize_email(" Sreeja@Example.COM "),
            "sreeja@example.com",
        )

    def test_normalizes_phone(self):
        self.assertEqual(
            normalize_phone("+91 98765-43210"),
            "919876543210",
        )

    def test_handles_none_text(self):
        self.assertEqual(normalize_text(None), "")

    def test_normalizes_customer_without_modifying_original(self):
        original = {
            "name": " SREEJA ",
            "email": "SREEJA@EXAMPLE.COM",
            "phone": "+91 98765 43210",
        }

        result = normalize_record(original, "CUSTOMER")

        self.assertEqual(result["name"], "sreeja")
        self.assertEqual(result["email"], "sreeja@example.com")
        self.assertEqual(result["phone"], "919876543210")
        self.assertEqual(original["name"], " SREEJA ")
