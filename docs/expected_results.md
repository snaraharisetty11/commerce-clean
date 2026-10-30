
# Commerce Clean — Sample Data and Expected Results

## Purpose

The sample CSV files demonstrate ingestion, validation,
normalization, duplicate candidate generation, and review creation.

## Source schemas

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

## Sample customer dataset

File: `data/sample_customers.csv`

- Input rows: 6
- Expected valid records: 3
- Expected rejected records: 3
- Expected duplicate source IDs skipped: 0
- Expected duplicate candidate: C001 and C002

The rejected records include an invalid email, a missing customer name,
and a missing source_record_id.

## Sample product dataset

File: `data/sample_products.csv`

- Input rows: 5
- Expected valid records: 3
- Expected rejected records: 2
- Expected duplicate source IDs skipped: 0
- Expected duplicate candidate: P001 and P002

The rejected records include a negative price and a missing SKU.

## Generate larger datasets

From the project root, run:

```powershell
python scripts/generate_dataset.py --customers 1000 --products 1000 --seed 42
```

Output files:

- `data/generated/customers.csv`
- `data/generated/products.csv`

Repeat the same command with the same parameters to reproduce the
same generated CSV contents.

To generate a larger benchmark input:

```powershell
python scripts/generate_dataset.py --customers 10000 --products 10000 --seed 42
```

## Important count definitions

- Input count: nonblank CSV data rows.
- Valid count: records passing business validation and successfully saved.
- Rejected count: invalid business records plus records rejected for
  a missing source_record_id.
- Duplicate count: repeated source_record_id values skipped during
  ingestion, not business entities identified as duplicate candidates.
- Review count: duplicate candidate reviews created or retrieved by
  the matching service.
- Published count: currently the number of MergedRecord rows assigned
  to a pipeline run, as defined by the current implementation.

## Verification

Run the existing tests:

```powershell
python manage.py test deduplication.tests
```

Expected current baseline: 70 passing tests.

Expected sample counts should be confirmed by running each CSV through
the actual pipeline. Benchmark timing and memory usage must be measured
separately; generated row counts alone do not prove scalability.
