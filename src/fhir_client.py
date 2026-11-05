
import requests
import json
from pathlib import Path

# HAPI FHIR R4 server
FHIR_SERVER = "https://hapi.fhir.org/baseR4"

BASE_DIR = Path(__file__).resolve().parents[1]

BUNDLE_FILE = (
    BASE_DIR / "output"
    / "device_a_transaction_bundle.json"
)

HEADERS = {
    "Accept": "application/fhir+json",
    "Content-Type": "application/fhir+json"
}


# STEP 1: Check server connection
def check_server_connection():

    url = f"{FHIR_SERVER}/metadata"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        capability = response.json()

        print("HAPI FHIR connection successful!")
        print("FHIR Version:", capability.get("fhirVersion"))
        print(
            "Server Software:",
            capability.get("software", {}).get("name")
        )

        return True

    except requests.exceptions.RequestException as error:
        print("Server connection failed:", error)
        return False


# STEP 2: Upload FHIR transaction Bundle
def upload_bundle():

    print("\nReading FHIR transaction Bundle...")

    with open(BUNDLE_FILE, "r") as file:
        bundle_data = json.load(file)

    print("Resources to upload:", len(bundle_data["entry"]))

    try:
        response = requests.post(
            FHIR_SERVER,
            headers=HEADERS,
            json=bundle_data,
            timeout=120
        )

        response.raise_for_status()

        result = response.json()

        print("\nFHIR Bundle uploaded successfully!")
        print("HTTP Status:", response.status_code)
        print("Response Bundle Type:", result.get("type"))

        # Inspect individual transaction results
        successful = 0
        failed = 0

        for entry in result.get("entry", []):
            status = entry.get("response", {}).get("status", "")

            if status.startswith("2"):
                successful += 1
            else:
                failed += 1
                print("Failed transaction entry:", status)

        print("Successful operations:", successful)
        print("Failed operations:", failed)

        return result if failed == 0 else None

    except requests.exceptions.RequestException as error:
        print("\nFHIR upload failed:", error)

        if getattr(error, "response", None) is not None:
            print("Server response:", error.response.text[:2000])

        return None

    except (ValueError, KeyError) as error:
        print("\nUnexpected server response:", error)
        return None


# STEP 3: Retrieve Patient from HAPI
def verify_upload(patient_id):

    print("\nVerifying uploaded Patient...")

    url = f"{FHIR_SERVER}/Patient/{patient_id}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        patient = response.json()

        print("Patient successfully retrieved!")
        print("Patient ID:", patient.get("id"))
        print("Resource Type:", patient.get("resourceType"))

        # Retrieve observations belonging to this patient
        observation_url = (
            f"{FHIR_SERVER}/Observation"
            f"?subject=Patient/{patient_id}"
        )

        observation_response = requests.get(
            observation_url,
            headers=HEADERS,
            timeout=30
        )

        observation_response.raise_for_status()

        observation_data = observation_response.json()

        print(
            "Associated Observations:",
            observation_data.get("total", 0)
        )

        return True

    except requests.exceptions.RequestException as error:
        print("Verification failed:", error)
        return False


# MAIN EXECUTION
def main():

    print("========== HAPI FHIR CLIENT ==========\n")

    if not check_server_connection():
        return

    # Identify first patient in the Bundle
    with open(BUNDLE_FILE, "r") as file:
        bundle_data = json.load(file)

    first_patient = next(
        entry["resource"]
        for entry in bundle_data["entry"]
        if entry["resource"]["resourceType"] == "Patient"
    )

    patient_id = first_patient["id"]

    # Upload transaction
    upload_result = upload_bundle()

    if upload_result is None:
        print("\nUpload unsuccessful. Verification skipped.")
        return

    # Verify server-side storage
    verify_upload(patient_id)


if __name__ == "__main__":
    main()

