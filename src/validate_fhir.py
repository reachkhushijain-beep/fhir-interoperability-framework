
import json
from pathlib import Path

from fhir.resources.patient import Patient
from fhir.resources.observation import Observation
from fhir.resources.bundle import Bundle

BASE_DIR = Path(__file__).resolve().parents[1]

DEVICE_SOURCE = "B"

BATCH_DIR = BASE_DIR / "output" / "batches"

REPORT_FILE = (
    BATCH_DIR / f"device_{DEVICE_SOURCE}_validation_report.json"
)


def main():

    batch_files = sorted(
        BATCH_DIR.glob(
            f"device_{DEVICE_SOURCE}_batch_*.json"
        )
    )

    if not batch_files:
        print("No FHIR batch files found!")
        return

    print("Starting full FHIR R4 validation...")
    print("Total batches found:", len(batch_files))

    total_resources = 0
    valid_count = 0
    invalid_count = 0

    valid_bundles = 0
    invalid_bundles = 0

    resource_counts = {
        "Patient": 0,
        "Observation": 0
    }

    errors = []

    # Process one batch at a time
    for batch_number, batch_file in enumerate(
        batch_files, start=1
    ):

        try:
            with open(batch_file, "r") as file:
                bundle_data = json.load(file)

            entries = bundle_data.get("entry", [])
            total_resources += len(entries)

            # Validate individual resources
            for entry in entries:

                resource = entry.get("resource", {})
                resource_type = resource.get("resourceType")

                try:
                    if resource_type == "Patient":
                        Patient.parse_obj(resource)

                    elif resource_type == "Observation":
                        Observation.parse_obj(resource)

                    else:
                        raise ValueError(
                            f"Unsupported resource: {resource_type}"
                        )

                    valid_count += 1
                    resource_counts[resource_type] += 1

                except Exception as error:

                    invalid_count += 1

                    if len(errors) < 20:
                        errors.append({
                            "batch": batch_file.name,
                            "resource_id": resource.get("id"),
                            "error": str(error)[:500]
                        })

            # Validate complete transaction Bundle
            try:
                if bundle_data.get("type") != "transaction":
                    raise ValueError(
                        "Bundle type is not transaction"
                    )

                Bundle.parse_obj(bundle_data)
                valid_bundles += 1

            except Exception as error:

                invalid_bundles += 1

                if len(errors) < 20:
                    errors.append({
                        "batch": batch_file.name,
                        "bundle_error": str(error)[:500]
                    })

        except Exception as error:

            invalid_bundles += 1

            if len(errors) < 20:
                errors.append({
                    "batch": batch_file.name,
                    "file_error": str(error)[:500]
                })

        # Print progress every 50 batches
        if batch_number % 50 == 0 or batch_number == len(batch_files):
            print(
                f"Processed {batch_number}/{len(batch_files)} batches"
            )

    # Generate validation report
    report = {
        "device_source": DEVICE_SOURCE,
        "total_batches": len(batch_files),
        "valid_bundles": valid_bundles,
        "invalid_bundles": invalid_bundles,
        "total_resources": total_resources,
        "valid_resources": valid_count,
        "invalid_resources": invalid_count,
        "patient_resources": resource_counts["Patient"],
        "observation_resources": resource_counts["Observation"],
        "structural_validation_passed": (
            invalid_count == 0 and invalid_bundles == 0
        ),
        "errors": errors
    }

    with open(REPORT_FILE, "w") as file:
        json.dump(report, file, indent=4)

    # Display results
    print("\n========== VALIDATION SUMMARY ==========")

    print("Total batches:", len(batch_files))
    print("Valid Bundles:", valid_bundles)
    print("Invalid Bundles:", invalid_bundles)

    print("\nTotal resources:", total_resources)
    print("Valid resources:", valid_count)
    print("Invalid resources:", invalid_count)

    print("\nPatient resources:", resource_counts["Patient"])
    print("Observation resources:", resource_counts["Observation"])

    print(
        "\nValidation report saved:",
        REPORT_FILE
    )

    if report["structural_validation_passed"]:
        print("\nFULL FHIR R4 STRUCTURAL VALIDATION SUCCESSFUL!")
    else:
        print("\nVALIDATION NEEDS ATTENTION!")

        for error in errors:
            print(error)


if __name__ == "__main__":
    main()


