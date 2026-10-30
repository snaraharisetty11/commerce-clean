
from django.test import SimpleTestCase

from deduplication.services.validation import validate_record


class ValidationTests(SimpleTestCase):

    def test_valid_customer(self):
        customer = {
            "name": "Sreeja",
            "email": "sreeja@example.com",
        }
        self.assertEqual(validate_record(customer, "CUSTOMER"), [])

    def test_customer_missing_name(self):
        customer = {"email": "sreeja@example.com"}
        errors = validate_record(customer, "CUSTOMER")
        self.assertTrue(any("name is required" in e for e in errors))

    def test_customer_invalid_email(self):
        customer = {"name": "Sreeja", "email": "invalid-email"}
        errors = validate_record(customer, "CUSTOMER")
        self.assertTrue(any("email format is invalid" in e for e in errors))

    def test_valid_product(self):
        product = {"name": "Mouse", "sku": "M-101", "price": 499}
        self.assertEqual(validate_record(product, "PRODUCT"), [])

    def test_product_negative_price(self):
        product = {"name": "Mouse", "sku": "M-101", "price": -10}
        errors = validate_record(product, "PRODUCT")
        self.assertTrue(any("cannot be negative" in e for e in errors))

    def test_malformed_record(self):
        errors = validate_record("not a dictionary", "CUSTOMER")
        self.assertTrue(errors)

    def test_unknown_record_type(self):
        errors = validate_record({"name": "Test"}, "ORDER")
        self.assertTrue(errors)
