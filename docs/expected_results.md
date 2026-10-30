# CommerceClean — Sample Data and Expected Results

## Purpose

The sample CSV files demonstrate ingestion, validation, normalization, duplicate candidate generation, and review creation.

This document describes the sample customer and product schemas, expected sample results, synthetic dataset generation, and verification instructions.

## Source Schemas

### Customers

| Column | Expected type | Rule |
|---|---|---|
| source_record_id | String | Required for ingestion |
| name | String | Required |
| email | String | Required; must have valid email format |
| phone | String | Optional |

### Products

| Column | Expected type | Rule |
|---|---|---|
| source_record_id | String | Required for ingestion |
| name | String | Required |
| sku | String | Required |
| price | Decimal-like string | Required, numeric, finite, non-negative |
| brand | String | Optional |

---

## Sample Customer Dataset

File: `data/sample_customers.csv`

Expected results:

- Input rows: 6
- Expected valid records: 3
- Expected rejected records: 3
- Expected duplicate source IDs skipped: 0
- Expected duplicate candidate: C001 and C002

The rejected records include:

- An invalid email.
- A missing customer name.
- A missing `source_record_id`.

## Sample Product Dataset

File: `data/sample_products.csv`

Expected results:

- Input rows: 5
- Expected valid records: 3
- Expected rejected records: 2
- Expected duplicate source IDs skipped: 0
- Expected duplicate candidate: P001 and P002

The rejected records include:

- A negative price.
- A missing SKU.

---

## Generate Larger Datasets

From the project root, run the following commands.

### Generate a 1,000-record demo dataset

```powershell
python scripts/generate_dataset.py --size 1000 --seed 42 --output-dir data/generated/demo
```

### Generate a 100,000-record benchmark dataset

```powershell
python scripts/generate_dataset.py --size 100000 --seed 42 --output-dir data/generated/large
```

### Generated output files

The generator currently creates the following files:

- `customers.csv`
- `expected_labels.csv`
- `dataset_manifest.json`

The output directory is determined by the `--output-dir` argument.

### Verified demo dataset

The 1,000-record dataset was successfully generated using seed `42`.

| Scenario | Records |
|---|---:|
| Normal | 650 |
| Exact duplicate | 100 |
| Near duplicate | 80 |
| Missing name | 50 |
| Missing email | 50 |
| Invalid email | 40 |
| Boundary | 30 |
| **Total** | **1,000** |

The generator currently produces synthetic customer records only. Product sample data is maintained separately in `data/sample_products.csv`.

Using the same seed and generation parameters is intended to reproduce the same synthetic dataset.

**Important:** `expected_labels.csv` contains evaluation ground truth. It must not be supplied as input to the matching pipeline.

---

## Important Count Definitions

- **Input count:** Nonblank CSV data rows.
- **Valid count:** Records passing business validation and successfully saved.
- **Rejected count:** Invalid business records plus records rejected for a missing `source_record_id`.
- **Duplicate count:** Repeated `source_record_id` values skipped during ingestion, not business entities identified as duplicate candidates.
- **Review count:** Duplicate candidate reviews created or retrieved by the matching service.
- **Published count:** Currently the number of `MergedRecord` rows assigned to a pipeline run, as defined by the current implementation.

---

## Verification

CommerceClean provides automated tests covering the main application workflows.

### Configure the SQLite test environment

In PowerShell:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.sqlite_settings"
$env:DJANGO_SECRET_KEY = "local-development-only-change-this-key"
```

### Run database migrations

```powershell
python manage.py migrate
```

### Run Django system checks

```powershell
python manage.py check
```

### Execute the automated test suite

```powershell
python manage.py test
```

### Verified test baseline

The automated test suite was successfully executed from a fresh repository clone using SQLite.

| Metric | Verified result |
|---|---:|
| Tests discovered | 100 |
| Tests passed | 100 |
| Tests failed | 0 |
| Execution time | 0.626 seconds |

Expected test completion:

```text
Found 100 test(s).

Ran 100 tests in 0.626s

OK
```

The test suite covers validation, ingestion, matching, review, survivorship, merging, lineage, and invalid-operation handling.

### Benchmark interpretation

Benchmark timing, memory usage, and matching accuracy must be evaluated separately.

Synthetic expected labels provide ground truth for evaluating candidate generation and matching. Generated row counts alone do not prove scalability or real-world accuracy.

The 100,000-record benchmark results documented in the main README are synthetic benchmark measurements and should not be interpreted as guaranteed production performance.