
from django.test import SimpleTestCase

from deduplication.services.matching import match_records, similarity


class MatchingTests(SimpleTestCase):
    def test_exact_customer_duplicate(self):
        customer_a = {
            "name": "Sreeja",
            "email": "sreeja@example.com",
            "phone": "9876543210",
        }
        customer_b = {
            "name": " SREEJA ",
            "email": "SREEJA@example.com",
            "phone": "9876543210",
        }

        result = match_records(customer_a, customer_b, "CUSTOMER")

        self.assertEqual(result["match_type"], "EXACT_DUPLICATE")
        self.assertEqual(result["score"], 1.0)

    def test_probable_customer_duplicate(self):
        customer_a = {
            "name": "Sreeja Naraharisetty",
            "email": "sreeja@example.com",
            "phone": "9876543210",
        }
        customer_b = {
            "name": "Sreeja N.",
            "email": "sreeja@example.com",
            "phone": "9876543210",
        }

        result = match_records(customer_a, customer_b, "CUSTOMER")

        self.assertEqual(result["match_type"], "PROBABLE_DUPLICATE")
        self.assertGreaterEqual(result["score"], 0.70)
        self.assertIn("Email matches", result["explanation"])
        self.assertIn("Phone matches", result["explanation"])

    def test_different_customers(self):
        customer_a = {
            "name": "Sreeja",
            "email": "sreeja@example.com",
            "phone": "9876543210",
        }
        customer_b = {
            "name": "Ravi Kumar",
            "email": "ravi@example.com",
            "phone": "9000000000",
        }

        result = match_records(customer_a, customer_b, "CUSTOMER")

        self.assertEqual(result["match_type"], "NOT_DUPLICATE")

    def test_exact_product_duplicate(self):
        product = {
            "name": "Wireless Mouse",
            "sku": "WM-101",
            "brand": "TechPro",
            "price": 499,
        }

        result = match_records(product, product.copy(), "PRODUCT")

        self.assertEqual(result["match_type"], "EXACT_DUPLICATE")
        self.assertEqual(result["score"], 1.0)

    def test_identical_customer_name_without_identifiers_is_not_exact(self):
        first = {"name": "Alice"}
        second = {"name": "Alice"}

        result = match_records(first, second, "CUSTOMER")

        self.assertNotEqual(result["match_type"], "EXACT_DUPLICATE")
        self.assertEqual(result["match_type"], "NOT_DUPLICATE")

    def test_identical_unrelated_fields_are_not_exact_duplicates(self):
        first = {"notes": "preferred customer"}
        second = {"notes": "preferred customer"}

        result = match_records(first, second, "CUSTOMER")

        self.assertNotEqual(result["match_type"], "EXACT_DUPLICATE")

    def test_blank_records_are_not_exact_duplicates(self):
        result = match_records(
            {"name": "", "email": ""},
            {"name": "", "email": ""},
            "CUSTOMER",
        )

        self.assertEqual(result["match_type"], "NOT_DUPLICATE")
        self.assertEqual(result["score"], 0.0)

    def test_similarity_ignores_case_and_extra_whitespace(self):
        self.assertEqual(similarity(" Alice  Smith ", "alice smith"), 1.0)

    def test_similarity_returns_zero_for_missing_values(self):
        self.assertEqual(similarity("", "Alice"), 0.0)
        self.assertEqual(similarity(None, "Alice"), 0.0)
        self.assertEqual(similarity("Alice", None), 0.0)

    def test_invalid_record_type_raises_error(self):
        with self.assertRaises(ValueError):
            match_records({"name": "Test"}, {"name": "Test"}, "ORDER")

    def test_non_string_record_type_raises_error(self):
        with self.assertRaises(ValueError):
            match_records({"name": "Test"}, {"name": "Test"}, None)

    def test_non_dictionary_records_raise_error(self):
        with self.assertRaises(TypeError):
            match_records([], {"name": "Test"}, "CUSTOMER")
