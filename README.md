# CommerceClean
### Entity Resolution, Duplicate Detection & Data Survivorship

CommerceClean is a Django-based data deduplication and entity resolution system. It ingests customer and product records, validates and normalizes data, identifies potential duplicates, applies configurable matching and survivorship logic, and maintains lineage for merged records.

The project focuses on data quality, explainable decisions, traceability, and safe record merging.

## 1. Problem Statement

Data from multiple systems can contain duplicate, incomplete, inconsistent, or incorrectly formatted records. These issues affect reporting, analytics, and downstream business operations.

CommerceClean addresses this by providing a structured pipeline that:

- Validates incoming records.
- Normalizes fields for consistent comparison.
- Generates duplicate candidates.
- Classifies potential duplicates.
- Routes uncertain matches for human review.
- Applies survivorship rules to confirmed duplicates.
- Preserves source records and merge lineage.

## 2. Key Features

- **Data ingestion:** Processes structured source records and CSV input.
- **Validation:** Identifies invalid records and maintains validation errors.
- **Normalization:** Standardizes values before matching.
- **Candidate generation:** Uses blocking strategies to reduce unnecessary pair comparisons.
- **Duplicate detection:** Identifies exact and probable duplicate candidates.
- **Review workflow:** Supports pending, confirmed, and not-duplicate decisions.
- **Survivorship:** Selects values from source records using configurable source-priority logic.
- **Record merging:** Creates consolidated records from confirmed duplicates.
- **Data lineage:** Records source-to-merged-record relationships and field contribution details.
- **Pipeline tracking:** Maintains run-level processing information and operational counts.
- **Automated testing:** Includes tests for validation, ingestion, matching, merging, survivorship, and lineage.

## 3. Architecture

CommerceClean follows a modular Django service architecture.

### Processing flow

```text
        Source Data / CSV
               |
               v
         Data Ingestion
               |
               v
       Schema Validation
          /         \
         v           v
   Valid Records   Rejected Records
         |
         v
     Normalization
         |
         v
   Candidate Generation
         |
         v
     Duplicate Matching
         |
         v
      Review Queue
       /        \
      v          v
  Confirmed   Not Duplicate
      |
      v
 Survivorship Rules
      |
      v
  Merged Record
      |
      v
  Record Lineage
```

### Main application components

| Component | Responsibility |
|---|---|
| `models.py` | Database models and relationships |
| `validation.py` | Record validation |
| `normalization.py` | Data standardization |
| `csv_ingestion.py` | CSV processing |
| `ingestion.py` | Record ingestion workflow |
| `candidate_generation.py` | Candidate pair generation |
| `matching.py` | Duplicate classification |
| `review.py` | Duplicate review operations |
| `survivorship.py` | Survivor selection |
| `merge.py` | Confirmed record merging |
| `lineage.py` | Source contribution tracking |

### Core data models

- `PipelineRun` — tracks an execution of the processing pipeline.
- `SourceRecord` — stores original source records and normalized data.
- `DuplicateReview` — stores candidate pairs, confidence, explanation, and review status.
- `MergedRecord` — stores consolidated records.
- `RecordLineage` — links source records to merged records and stores contribution details.

## 4. Technology Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.14.7 | Core programming language |
| Django | 6.1.2 | Web framework and ORM |
| python-dotenv | 1.1.1 | Environment variable loading |
| PostgreSQL | 18 | Relational database |
| psycopg2-binary | 2.9.10 | PostgreSQL adapter |
| SQLite | As configured | Alternative local database |

## 5. Data Dictionary

| Entity | Important fields | Description |
|---|---|---|
| PipelineRun | `run_id`, `status`, input/valid/rejected counts | Processing execution metadata |
| SourceRecord | `source_record_id`, `record_type`, `source_system`, `raw_data`, `normalized_data`, `is_valid` | Original ingested record |
| DuplicateReview | `record_a`, `record_b`, `confidence_score`, `explanation`, `status` | Potential duplicate pair and its review decision |
| MergedRecord | `record_type`, `merged_data`, `survivorship_explanation`, `run` | Consolidated entity |
| RecordLineage | `merged_record`, `source_record`, `contribution_details` | Traceability of merged values to source records |

The data model supports customer and product record types. Exact field requirements and validation rules are implemented in the application.

## 6. Matching and Survivorship Assumptions

### Matching

- Records are normalized before comparison.
- Candidate generation reduces the comparison search space.
- Exact and probable duplicate classifications are treated separately.
- Candidate generation is not equivalent to a final merge decision.
- Uncertain candidates are retained for review rather than automatically merged.

### Survivorship

- Only confirmed duplicate reviews are eligible for merging.
- Source records must belong to the same pipeline run and record type.
- Invalid source records are rejected from merging.
- Survivorship selects values according to source-priority logic.
- Original source records are preserved.
- Repeated merge operations are designed to be idempotent.
- Lineage records preserve source-to-merged-record relationships.

## 7. Local Setup Instructions

### Prerequisites

- Python 3.14.7 (or a compatible Python version)
- PostgreSQL 18 (for PostgreSQL configuration)
- Git
- PowerShell or another terminal

### Step 1: Clone the repository

```powershell
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd commerce-clean
```

### Step 2: Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure environment variables

Create a `.env` file in the project root.

Add the required configuration:

```env
DJANGO_SECRET_KEY=replace_with_a_locally_generated_secret
DB_PASSWORD=replace_with_your_local_database_password
```

Configure any additional database settings required by `config/settings.py`.

Never commit `.env` or share actual credentials.

### Step 5: Configure the database

For PostgreSQL:

1. Install and start PostgreSQL.
2. Create a local database for CommerceClean.
3. Configure the database name, username, host, port, and password in the application settings or environment variables.
4. Ensure the PostgreSQL service is running.

SQLite may be used through the provided SQLite settings configuration if supported by the application workflow.

### Step 6: Apply database migrations

```powershell
python manage.py migrate
```

### Step 7: Run Django system checks

```powershell
python manage.py check
```

### Step 8: Start the development server

```powershell
python manage.py runserver
```

Open the application at:

```text
http://127.0.0.1:8000/
```

### Step 9: Run automated tests

```powershell
python manage.py test deduplication.tests
```

The test suite validates the main application workflows, including ingestion, validation, matching, survivorship, merging, review, and lineage.

## 8. Testing and Benchmark Results

The project has a reported passing result of **100 automated test cases**.

The tests cover:

- Data validation and normalization.
- CSV and record ingestion.
- Candidate generation and matching.
- Review workflow.
- Survivorship.
- Merge behavior.
- Lineage creation and validation.
- Idempotency and invalid-operation handling.

### Synthetic 100K benchmark

| Metric | Result |
|---|---:|
| Input records | 100,000 |
| Valid records | 86,000 |
| Rejected records | 14,000 |
| Expected candidate pairs | 20,435 |
| Generated candidates | 20,440 |
| True positives | 20,435 |
| False positives | 5 |
| False negatives | 0 |
| Precision | 99.98% |
| Recall | 100% |
| Candidate generation time | 1.06 seconds |

These metrics are from a generated synthetic benchmark with known expected labels. They should not be interpreted as measured real-world accuracy.

The successful 100K pipeline run produced 20,435 pending review candidates. The benchmark run did not automatically merge those records. Merge and lineage behavior were tested separately using isolated automated test cases.

## 9. Security and Data Handling

- Secrets and database passwords are supplied through environment variables.
- `.env` files are excluded from Git.
- Local database files and environment secrets are excluded from source control. Selected synthetic datasets and reconciliation outputs are intentionally included as assessment evidence.
- Original source records are retained during merge operations.
- Use only synthetic, public, or explicitly authorized datasets.
- Do not upload personal, confidential, or customer information to public repositories.

## 10. Known Limitations

1. **Synthetic benchmark:** Benchmark metrics do not establish performance on real-world customer or product datasets.
2. **Blocking limitations:** Customer candidate generation currently relies heavily on normalized email and phone matching. Duplicates with both values changed or missing may be missed.
3. **Human review:** Probable duplicates require a review decision before merging.
4. **Source quality:** Incorrect or incomplete source data can reduce matching effectiveness.
5. **Scale:** The 100K synthetic benchmark does not establish production readiness at larger volumes or under concurrent workloads.
6. **External integrations:** The core workflow does not require external APIs or paid services.
7. **Operational recovery:** Advanced distributed processing, automated recovery, and large-scale orchestration are not claimed as completed features.

## 11. Possible Next Steps

- Add additional configurable blocking strategies.
- Improve matching for records with missing or changed contact information.
- Add configurable field-level survivorship policies.
- Expand explainability with field-level match evidence.
- Add transaction and rollback tests for bulk merging.
- Improve pipeline retry and recovery support.
- Add larger and more diverse synthetic benchmark datasets.
- Introduce role-based access control and audit logging.
- Add deployment automation and production monitoring.

## 12. Project Structure

```text
commerce-clean/
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── sqlite_settings.py
│
├── deduplication/
│   ├── migrations/
│   ├── services/
│   ├── templates/
│   ├── tests/
│   ├── admin.py
│   ├── models.py
│   └── views.py
│
├── data/
├── docs/
├── scripts/
├── .gitignore
├── manage.py
├── requirements.txt
└── README.md
```

## 13. Project Objective

CommerceClean demonstrates a modular and explainable approach to entity resolution and record deduplication, with particular attention to validation, matching, survivorship, data integrity, and lineage.

The emphasis is on a working, testable end-to-end foundation with clearly documented assumptions and limitations, rather than claiming an unfinished enterprise-scale platform.

## 14. Submission Deliverables

### 14.1 Documentation

The following documentation files describe the expected results, testing evidence, and use of AI assistance during development.

- [Expected Results](docs/expected_results.md)
- [Test Execution Evidence](docs/test_execution_evidence.md)
- [AI Prompt History](docs/ai_prompt_history.md)

### 14.2 Generated Datasets

CommerceClean includes deterministic synthetic customer and product datasets for reproducible testing.

| Dataset | Records |
|---|---:|
| Small | 100 |
| Medium | 10,000 |
| Large | 100,000 |

Dataset generation script:

```powershell
python scripts/generate_dataset.py --size 100000 --seed 42 --output-dir data/generated/large
```

Expected labels are provided as evaluation ground truth and must not be supplied as input to the matching pipeline.

### 14.3 Actual Database Reconciliation Results

The following results were obtained from the application database on October 30, 2026.

| Metric | Result |
|---|---:|
| Pipeline runs | 45 |
| Source records | 364,909 |
| Duplicate reviews | 63,619 |
| Pending reviews | 63,616 |
| Confirmed reviews | 3 |
| Merged records | 2 |
| Customer merged records | 1 |
| Product merged records | 1 |
| Lineage entries | 4 |
| Confirmed reviews without lineage | 1 |

One confirmed review remains unmerged. It is not counted as a completed merge.

### 14.4 Reconciliation Output Files

The following files contain actual database exports:

- [Merged Records CSV](outputs/sample_merged_records.csv)
- [Duplicate Review Queue CSV](outputs/sample_review_queue.csv)
- [Reconciliation Report JSON](outputs/reconciliation_report.json)

### 14.5 Reproducibility Scripts

| Script | Purpose |
|---|---|
| `scripts/generate_dataset.py` | Generate deterministic synthetic datasets |
| `scripts/export_submission.py` | Export merged records and duplicate reviews |
| `scripts/export_report.py` | Generate the reconciliation report |

The export scripts read existing application database records. They do not automatically confirm reviews or merge records.