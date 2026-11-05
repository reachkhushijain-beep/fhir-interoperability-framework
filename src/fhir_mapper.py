
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

# Select input device: "A" or "B"
DEVICE_SOURCE = "B"

INPUT_FILES = {
    "A": BASE_DIR / "data" / "adapters" / "device_a_standardised.json",
    "B": BASE_DIR / "data" / "adapters" / "device_b_standardised.json"
}

BATCH_SIZE = 100

OUTPUT_DIR = BASE_DIR / "output" / "batches"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def safe_id(value):
    """Generate a FHIR-compatible resource ID."""
    value = re.sub(r"[^A-Za-z0-9.-]", "-", str(value))
    return value[:64]


def create_observation(
    obs_id, patient_id, code, display, value, unit, ucum
):
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": code,
                    "display": display
                }
            ],
            "text": display
        },
        "subject": {
            "reference": f"Patient/{patient_id}"
        },
        "valueQuantity": {
            "value": value,
            "unit": unit,
            "system": "http://unitsofmeasure.org",
            "code": ucum
        }
    }


def create_patient_bundle(record):

    patient_number = safe_id(record["patient_id"])
    patient_id = f"patient-{patient_number}"

    # Preserve technical data-quality information
    patient_extensions = [
        {
            "url": "https://example.org/fhir/StructureDefinition/technical-quality-valid",
            "valueBoolean": bool(record["technical_quality_valid"])
        },
        {
            "url": "https://example.org/fhir/StructureDefinition/quality-issues",
            "valueString": str(record["quality_issues"])
        }
    ]

    patient = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [
            {
                "system": "https://example.org/fhir/NamingSystem/synthetic-patient-id",
                "value": str(record["patient_id"])
            }
        ],
        "active": True,
        "extension": patient_extensions
    }

    observations = [
        create_observation(
            f"hr-{patient_number}",
            patient_id,
            "8867-4",
            "Heart rate",
            int(record["heart_rate"]),
            "beats/minute",
            "/min"
        ),

        create_observation(
            f"spo2-{patient_number}",
            patient_id,
            "59408-5",
            "Oxygen saturation",
            int(record["spo2"]),
            "%",
            "%"
        ),

        {
            "resourceType": "Observation",
            "id": f"bp-{patient_number}",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs",
                            "display": "Vital Signs"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "85354-9",
                        "display": "Blood pressure panel"
                    }
                ],
                "text": "Blood pressure panel"
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "component": [
                {
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "8480-6",
                                "display": "Systolic blood pressure"
                            }
                        ]
                    },
                    "valueQuantity": {
                        "value": int(record["systolic_bp"]),
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]"
                    }
                },
                {
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "8462-4",
                                "display": "Diastolic blood pressure"
                            }
                        ]
                    },
                    "valueQuantity": {
                        "value": int(record["diastolic_bp"]),
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]"
                    }
                }
            ]
        },

        create_observation(
            f"temp-{patient_number}",
            patient_id,
            "8310-5",
            "Body temperature",
            float(record["temperature"]),
            "°C",
            "Cel"
        )
    ]

    return [patient] + observations


def generate_batches(records, batch_size):
    """Yield smaller groups of patient records."""
    for start in range(0, len(records), batch_size):
        yield records[start:start + batch_size]


def main():

    input_file = INPUT_FILES[DEVICE_SOURCE]

    print("Starting batch-based FHIR mapping...")
    print("Selected device:", DEVICE_SOURCE)

    with open(input_file, "r") as file:
        records = json.load(file)

    print("Total input records:", len(records))

    total_resources = 0
    total_batches = 0
    total_flagged = 0

    for batch_number, batch_records in enumerate(
        generate_batches(records, BATCH_SIZE), start=1
    ):

        entries = []

        for record in batch_records:

            resources = create_patient_bundle(record)

            for resource in resources:

                resource_type = resource["resourceType"]
                resource_id = resource["id"]

                entries.append({
                    "resource": resource,
                    "request": {
                        "method": "PUT",
                        "url": f"{resource_type}/{resource_id}"
                    }
                })

            if not record["technical_quality_valid"]:
                total_flagged += 1

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": entries
        }

        output_file = (
            OUTPUT_DIR /
            f"device_{DEVICE_SOURCE}_batch_{batch_number:04d}.json"
        )

        with open(output_file, "w") as file:
            json.dump(bundle, file, separators=(",", ":"))

        total_batches += 1
        total_resources += len(entries)

        print(
            f"Batch {batch_number}: "
            f"{len(batch_records)} patients, "
            f"{len(entries)} resources"
        )

    # Save mapping summary
    summary = {
        "device_source": DEVICE_SOURCE,
        "total_patients": len(records),
        "batch_size": BATCH_SIZE,
        "total_batches": total_batches,
        "total_fhir_resources": total_resources,
        "flagged_patients": total_flagged,
        "resources_per_patient": 5
    }

    summary_file = OUTPUT_DIR / f"device_{DEVICE_SOURCE}_summary.json"

    with open(summary_file, "w") as file:
        json.dump(summary, file, indent=4)

    print("\n========== MAPPING SUMMARY ==========")
    print("Patients processed:", len(records))
    print("Total batches:", total_batches)
    print("Total FHIR resources:", total_resources)
    print("Flagged patients preserved:", total_flagged)
    print("Output directory:", OUTPUT_DIR)
    print("Summary file:", summary_file)

    if total_resources == len(records) * 5:
        print("\nBATCH FHIR MAPPING SUCCESSFUL!")
    else:
        print("\nMAPPING NEEDS ATTENTION!")


if __name__ == "__main__":
    main()


