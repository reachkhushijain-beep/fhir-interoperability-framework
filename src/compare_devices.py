
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

BATCH_DIR = BASE_DIR / "output" / "batches"


def load_batch(device, batch_number):

    filename = (
        f"device_{device}_batch_{batch_number:04d}.json"
    )

    filepath = BATCH_DIR / filename

    with open(filepath, "r") as file:
        return json.load(file)


def compare_batches(batch_a, batch_b):

    entries_a = batch_a["entry"]
    entries_b = batch_b["entry"]

    if len(entries_a) != len(entries_b):
        return False

    for entry_a, entry_b in zip(entries_a, entries_b):

        resource_a = entry_a["resource"]
        resource_b = entry_b["resource"]

        if resource_a != resource_b:
            return False

        if entry_a["request"] != entry_b["request"]:
            return False

    return True


def main():

    files_a = sorted(
        BATCH_DIR.glob("device_A_batch_*.json")
    )

    files_b = sorted(
        BATCH_DIR.glob("device_B_batch_*.json")
    )

    print("Starting interoperability comparison...\n")

    print("Device A batches:", len(files_a))
    print("Device B batches:", len(files_b))

    if len(files_a) != len(files_b):
        print("Batch count mismatch!")
        return

    matching_batches = 0
    mismatching_batches = 0
    total_resources = 0

    for batch_number in range(1, len(files_a) + 1):

        batch_a = load_batch("A", batch_number)
        batch_b = load_batch("B", batch_number)

        total_resources += len(batch_a["entry"])

        if compare_batches(batch_a, batch_b):
            matching_batches += 1
        else:
            mismatching_batches += 1
            print("Mismatch in batch:", batch_number)

        if batch_number % 50 == 0:
            print(
                f"Compared {batch_number}/{len(files_a)} batches"
            )

    report = {
        "device_a_batches": len(files_a),
        "device_b_batches": len(files_b),
        "matching_batches": matching_batches,
        "mismatching_batches": mismatching_batches,
        "resources_compared": total_resources,
        "interoperability_passed": (
            matching_batches == len(files_a)
            and mismatching_batches == 0
        )
    }

    report_file = (
        BATCH_DIR / "device_interoperability_report.json"
    )

    with open(report_file, "w") as file:
        json.dump(report, file, indent=4)

    print("\n========== COMPARISON SUMMARY ==========")
    print("Matching batches:", matching_batches)
    print("Mismatching batches:", mismatching_batches)
    print("Resources compared:", total_resources)
    print(
        "Interoperability:",
        "PASSED" if report["interoperability_passed"] else "FAILED"
    )
    print("Report saved:", report_file)


if __name__ == "__main__":
    main()
