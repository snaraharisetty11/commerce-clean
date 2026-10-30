
import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path


FIELDS = ["source_record_id", "name", "email", "phone"]


def create_base_customer(index, rng):
    first_names = [
        "Alice", "Bob", "Charlie", "David", "Emily",
        "Frank", "Grace", "Henry", "Ivy", "Jack",
        "Olivia", "Noah", "Sophia", "Liam", "Ava",
    ]

    last_names = [
        "Johnson", "Smith", "Brown", "Wilson", "Davis",
        "Miller", "Taylor", "Clark", "Martin", "Thomas",
    ]

    first = rng.choice(first_names)
    last = rng.choice(last_names)

    return {
        "source_record_id": f"C{index:07d}",
        "name": f"{first} {last}",
        "email": f"{first.lower()}.{last.lower()}.{index}@example.com",
        "phone": f"9{rng.randint(100000000, 999999999)}",
    }


def generate_records(size, seed):
    rng = random.Random(seed)

    # Each category receives a fixed share of the requested dataset.
    counts = {
        "normal": int(size * 0.65),
        "exact_duplicate": int(size * 0.10),
        "near_duplicate": int(size * 0.08),
        "missing_name": int(size * 0.05),
        "missing_email": int(size * 0.05),
        "invalid_email": int(size * 0.04),
        "boundary": 0,
    }

    counts["boundary"] = size - sum(counts.values())

    records = []
    labels = []
    original_customers = []
    next_id = 1

    def add_record(record, scenario, group=None, expected_valid=True):
        records.append(record)
        labels.append({
            "source_record_id": record["source_record_id"],
            "scenario": scenario,
            "expected_valid": expected_valid,
            "duplicate_group": group or "",
        })

    # Normal records
    for _ in range(counts["normal"]):
        customer = create_base_customer(next_id, rng)
        next_id += 1
        original_customers.append(customer.copy())
        add_record(customer, "normal")

    # Exact duplicate business details, but a different source ID
    for _ in range(counts["exact_duplicate"]):
        if not original_customers:
            break

        original = rng.choice(original_customers)
        duplicate = original.copy()
        duplicate["source_record_id"] = f"C{next_id:07d}"
        next_id += 1

        group = original["source_record_id"]
        add_record(duplicate, "exact_duplicate", group)

        for label in labels:
            if label["source_record_id"] == group:
                label["duplicate_group"] = group
                break

    # Near duplicates: a small name variation, same email and phone
    for _ in range(counts["near_duplicate"]):
        if not original_customers:
            break

        original = rng.choice(original_customers)
        near = original.copy()
        near["source_record_id"] = f"C{next_id:07d}"
        next_id += 1
        near["name"] = original["name"] + " Jr"

        group = original["source_record_id"]
        add_record(near, "near_duplicate", group)

        for label in labels:
            if label["source_record_id"] == group:
                label["duplicate_group"] = group
                break

    # Missing required customer name
    for _ in range(counts["missing_name"]):
        customer = create_base_customer(next_id, rng)
        next_id += 1
        customer["name"] = ""
        add_record(customer, "missing_name", expected_valid=False)

    # Missing required customer email
    for _ in range(counts["missing_email"]):
        customer = create_base_customer(next_id, rng)
        next_id += 1
        customer["email"] = ""
        add_record(customer, "missing_email", expected_valid=False)

    # Malformed email addresses
    for _ in range(counts["invalid_email"]):
        customer = create_base_customer(next_id, rng)
        next_id += 1
        customer["email"] = "invalid-email"
        add_record(customer, "invalid_email", expected_valid=False)

    # Boundary-style values that pass the current validation rules:
    # one-character name, minimal valid email, and empty optional phone.
    for _ in range(counts["boundary"]):
        customer = create_base_customer(next_id, rng)
        next_id += 1
        customer["name"] = "A"
        customer["email"] = f"a{next_id}@b.co"
        customer["phone"] = ""
        add_record(customer, "boundary")

    # Deterministic shuffle so scenarios are not grouped together.
    combined = list(zip(records, labels))
    rng.shuffle(combined)

    records = [item[0] for item in combined]
    labels = [item[1] for item in combined]

    return records, labels, counts


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Generate reproducible CommerceClean customer data."
    )
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-dir",
        default="data/generated",
    )
    args = parser.parse_args()

    if args.size < 10:
        parser.error("--size must be at least 10.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records, labels, counts = generate_records(args.size, args.seed)

    input_path = output_dir / "customers.csv"
    labels_path = output_dir / "expected_labels.csv"
    manifest_path = output_dir / "dataset_manifest.json"

    write_csv(input_path, records, FIELDS)
    write_csv(
        labels_path,
        labels,
        [
            "source_record_id",
            "scenario",
            "expected_valid",
            "duplicate_group",
        ],
    )

    manifest = {
        "dataset_type": "CommerceClean customer test data",
        "generator_version": "1.0",
        "record_count": len(records),
        "random_seed": args.seed,
        "category_counts": counts,
        "valid_count": sum(
            label["expected_valid"] for label in labels
        ),
        "invalid_count": sum(
            not label["expected_valid"] for label in labels
        ),
        "input_file": "customers.csv",
        "ground_truth_file": "expected_labels.csv",
        "note": (
            "Expected labels are for evaluation only. "
            "Do not provide them to the reconciliation pipeline."
        ),
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=4),
        encoding="utf-8",
    )

    print("\nDataset generated successfully.")
    print(f"Records: {len(records)}")
    print(f"Seed: {args.seed}")
    print(f"Output folder: {output_dir.resolve()}")
    print(f"Input: {input_path}")
    print(f"Labels: {labels_path}")
    print(f"Manifest: {manifest_path}")
    print("\nScenario counts:")
    for scenario, count in counts.items():
        print(f"  {scenario}: {count}")


if __name__ == "__main__":
    main()
