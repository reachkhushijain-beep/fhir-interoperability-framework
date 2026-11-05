import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fhir_mapper


SAMPLE_RECORD = {
    "patient_id": 1,
    "heart_rate": 98.0,
    "spo2": 96.0,
    "systolic_bp": 120.0,
    "diastolic_bp": 86.0,
    "temperature": 37.0,
    "technical_quality_valid": True,
    "quality_issues": ""
}


def test_patient_bundle_contains_five_resources():
    resources = fhir_mapper.create_patient_bundle(SAMPLE_RECORD)
    assert len(resources) == 5
    assert resources[0]["resourceType"] == "Patient"
    assert all(r["resourceType"] == "Observation" for r in resources[1:])


def test_fhir_resource_ids_are_deterministic():
    resources = fhir_mapper.create_patient_bundle(SAMPLE_RECORD)
    assert [r["id"] for r in resources] == [
        "patient-1", "hr-1", "spo2-1", "bp-1", "temp-1"
    ]


def test_all_observations_reference_correct_patient():
    resources = fhir_mapper.create_patient_bundle(SAMPLE_RECORD)
    for observation in resources[1:]:
        assert observation["subject"]["reference"] == "Patient/patient-1"


def test_observations_have_expected_loinc_codes():
    resources = fhir_mapper.create_patient_bundle(SAMPLE_RECORD)
    codes = [r["code"]["coding"][0]["code"] for r in resources[1:]]
    assert codes == ["8867-4", "59408-5", "85354-9", "8310-5"]


def test_heart_rate_and_spo2_values_are_mapped():
    resources = fhir_mapper.create_patient_bundle(SAMPLE_RECORD)
    assert resources[1]["valueQuantity"]["value"] == 98
    assert resources[2]["valueQuantity"]["value"] == 96


def test_blood_pressure_has_two_components():
    resources = fhir_mapper.create_patient_bundle(SAMPLE_RECORD)
    bp = resources[3]
    assert len(bp["component"]) == 2
    assert bp["component"][0]["code"]["coding"][0]["code"] == "8480-6"
    assert bp["component"][1]["code"]["coding"][0]["code"] == "8462-4"


def test_temperature_is_mapped_with_ucum_code():
    resources = fhir_mapper.create_patient_bundle(SAMPLE_RECORD)
    temperature = resources[4]["valueQuantity"]
    assert temperature["value"] == 37.0
    assert temperature["code"] == "Cel"
    assert temperature["system"] == "http://unitsofmeasure.org"


def test_quality_metadata_is_preserved():
    record = SAMPLE_RECORD.copy()
    record["technical_quality_valid"] = False
    record["quality_issues"] = "Technical quality check failed"

    patient = fhir_mapper.create_patient_bundle(record)[0]
    extensions = patient["extension"]

    assert extensions[0]["valueBoolean"] is False
    assert extensions[1]["valueString"] == "Technical quality check failed"


def test_batch_generation_preserves_all_records():
    records = list(range(250))
    batches = list(fhir_mapper.generate_batches(records, 100))
    assert len(batches) == 3
    assert [len(batch) for batch in batches] == [100, 100, 50]


def test_safe_id_removes_invalid_characters():
    assert fhir_mapper.safe_id("patient 1/test") == "patient-1-test"
