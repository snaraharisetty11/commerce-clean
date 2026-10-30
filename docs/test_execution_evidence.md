# CommerceClean - Test Execution Evidence

## 1. Overview

This document records the automated testing and synthetic benchmark results for CommerceClean, a Django-based data deduplication and entity resolution application.

The evidence covers application tests, core functionality, and large-scale synthetic candidate-generation performance.

## 2. Test Environment

| Component | Version / Configuration |
|---|---|
| Language | Python 3.14.7 |
| Framework | Django 6.1.2 |
| Database | PostgreSQL 18 (with SQLite configuration available) |
| Test framework | Django automated test runner |

## 3. Automated Test Execution

**Command:**

```powershell
python manage.py test
```

**Latest recorded result:**

```text
Ran 100 tests in 1.624s

OK
```

**Result:** 100 tests passed.

The automated test suite covers:

- Candidate generation
- CSV ingestion
- Group merging
- Data ingestion
- Record lineage
- Duplicate matching
- Merge operations
- Data normalization
- Pipeline execution
- Duplicate review workflows
- Survivorship rules
- Data validation

## 4. Synthetic Benchmark Results

A synthetic dataset containing 100,000 input records was used to evaluate candidate generation.

| Metric | Result |
|---|---:|
| Input records | 100,000 |
| Valid records | 86,000 |
| Rejected records | 14,000 |
| Expected duplicate pairs | 20,435 |
| Generated candidates | 20,440 |
| True positives | 20,435 |
| False positives | 5 |
| False negatives | 0 |
| Precision | 99.98% |
| Recall | 100% |
| Candidate generation time | 1.06 seconds |

### Benchmark interpretation

The synthetic benchmark achieved 99.98% precision and 100% recall for the evaluated candidate-generation dataset.

These figures represent performance on the generated benchmark data and should not be interpreted as guaranteed real-world accuracy.

## 5. Merge and Lineage Validation

Separate automated tests validate:

- Merging confirmed duplicate reviews.
- Creating merged records.
- Recording source-to-merged-record lineage.
- Preserving original source records.
- Preventing invalid or pending reviews from being merged.
- Idempotency of merge operations.
- Cross-run and record-type validation.
- Validation of normalized data.

The merge and lineage tests are separate from the 100,000-record candidate-generation benchmark.

## 6. Benchmark Scope and Limitations

The 100,000-record benchmark evaluated candidate generation.

It did not merge the 20,435 pending duplicate reviews. Therefore, the benchmark run contained zero merged records and zero lineage entries.

Candidate generation relies substantially on normalized email and phone blocking for customer records. Duplicates where both values are missing or changed may not be identified by the current blocking strategy.

## 7. Reproduction Instructions

1. Clone the repository.
2. Create and activate a Python virtual environment.
3. Install dependencies using `pip install -r requirements.txt`.
4. Configure the required environment variables.
5. Apply database migrations using `python manage.py migrate`.
6. Execute the automated tests:

```powershell
python manage.py test
```

7. Generate synthetic data using the dataset generator in `scripts/generate_dataset.py`.

Refer to the main README for complete environment configuration and execution instructions.

## 8. Evidence Integrity

The test results and benchmark metrics documented here are based on previously recorded project execution results.

For independent verification, evaluators should execute the automated test command and reproduce the synthetic benchmark using the supplied generator and project configuration.
