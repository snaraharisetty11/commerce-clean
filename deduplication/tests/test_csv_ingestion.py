
from io import StringIO

from django.test import SimpleTestCase

from deduplication.services.csv_ingestion import (
    iter_csv_records_with_row_numbers,
    read_csv_records,
)


class CSVIngestionTests(SimpleTestCase):
    def test_reads_multiple_rows(self):
        csv_data = StringIO(
            "source_record_id,name,email\n"
            "C001,Priya,priya@example.com\n"
            "C002,Rahul,rahul@example.com\n"
        )

        records = read_csv_records(csv_data)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["name"], "Priya")
        self.assertEqual(records[1]["source_record_id"], "C002")

    def test_preserves_empty_fields(self):
        records = read_csv_records(
            StringIO("source_record_id,name,email\nC001,Anu,\n")
        )
        self.assertEqual(records[0]["email"], "")

    def test_skips_blank_lines(self):
        records = read_csv_records(
            StringIO(
                "source_record_id,name\n"
                "C001,Priya\n"
                "\n"
                "C002,Rahul\n"
            )
        )
        self.assertEqual(len(records), 2)

    def test_rejects_missing_header(self):
        with self.assertRaisesRegex(ValueError, "header row"):
            read_csv_records(StringIO(""))

    def test_rejects_duplicate_headers(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            read_csv_records(StringIO("name,Name\nPriya,Priya S.\n"))

    def test_rejects_extra_values(self):
        with self.assertRaisesRegex(ValueError, "extra values"):
            read_csv_records(
                StringIO("name,email\nPriya,p@example.com,extra\n")
            )

    def test_rejects_missing_columns(self):
        with self.assertRaisesRegex(ValueError, "missing columns"):
            read_csv_records(StringIO("name,email\nPriya\n"))

    def test_utf8_bom_is_removed_from_first_header(self):
        records = read_csv_records(
            StringIO("\ufeffsource_record_id,name\nC001,Priya\n")
        )
        self.assertEqual(records[0]["source_record_id"], "C001")

    def test_row_aware_iterator_preserves_physical_line_numbers(self):
        records = list(
            iter_csv_records_with_row_numbers(
                StringIO(
                    "source_record_id,name\n"
                    "C001,Priya\n"
                    "\n"
                    "C002,Rahul\n"
                )
            )
        )

        self.assertEqual([number for number, _ in records], [2, 4])
        self.assertEqual(records[1][1]["source_record_id"], "C002")

    def test_row_number_is_start_of_multiline_quoted_record(self):
        records = list(
            iter_csv_records_with_row_numbers(
                StringIO(
                    "source_record_id,name\n"
                    'C001,"Priya\nSharma"\n'
                    "C002,Rahul\n"
                )
            )
        )

        self.assertEqual([number for number, _ in records], [2, 4])
        self.assertEqual(records[0][1]["name"], "Priya\nSharma")
