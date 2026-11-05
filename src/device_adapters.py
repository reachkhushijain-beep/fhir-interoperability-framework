
import argparse
import copy
import json
import math
from pathlib import Path

import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR / "data" / "processed"
    / "patient_monitoring_processed.csv"
)

OUTPUT_DIR = BASE_DIR / "data" / "adapters"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEVICE_A_OUTPUT = OUTPUT_DIR / "device_a_standardised.json"
DEVICE_B_OUTPUT = OUTPUT_DIR / "device_b_standardised.json"


# ============================================================
# CUSTOM ERROR
# ============================================================

class AdapterError(Exception):
    """Raised when incoming device data is invalid."""
    pass


# ============================================================
# COMMON VALIDATION FUNCTIONS
# ============================================================

def require_field(data, field):
    if not isinstance(data, dict):
        raise AdapterError("Device payload must be a dictionary.")

    if field not in data:
        raise AdapterError(f"Missing required field: {field}")

    value = data[field]

    if value is None or pd.isna(value):
        raise AdapterError(f"Missing or invalid value: {field}")

    return value


def require_number(data, field):
    value = require_field(data, field)

    if isinstance(value, bool):
        raise AdapterError(f"{field} must be numeric.")

    try:
        value = float(value)
    except (TypeError, ValueError):
        raise AdapterError(f"{field} must be numeric.")

    if not math.isfinite(value):
        raise AdapterError(f"{field} must be finite.")

    return value


def require_patient_id(data, field):
    value = require_field(data, field)

    if isinstance(value, str) and not value.strip():
        raise AdapterError("Patient ID cannot be empty.")

    return value


def require_quality_metadata(data):

    valid = require_field(data, "technical_quality_valid")

    if isinstance(valid, str):
        normalised = valid.strip().lower()

        if normalised not in ("true", "false"):
            raise AdapterError(
                "technical_quality_valid must be Boolean."
            )

        valid = normalised == "true"

    elif valid in (True, False, 0, 1):
        valid = bool(valid)

    else:
        raise AdapterError(
            "technical_quality_valid must be Boolean."
        )

    if "quality_issues" not in data:
        raise AdapterError("Missing required field: quality_issues")

    issues = data["quality_issues"]

    # Empty quality issues are acceptable.
    if issues is None or pd.isna(issues):
        issues = ""
    else:
        issues = str(issues)

    return {
        "technical_quality_valid": valid,
        "quality_issues": issues
    }


# ============================================================
# TEMPERATURE UNIT CONVERSION
# ============================================================

def convert_temperature_to_celsius(value, unit):

    if unit == "Cel":
        result = value

    elif unit == "[degF]":
        result = (value - 32) * 5 / 9

    else:
        raise AdapterError(
            f"Unsupported temperature unit: {unit}"
        )

    if not math.isfinite(result):
        raise AdapterError("Invalid converted temperature.")

    return round(result, 6)


# ============================================================
# CANONICAL DATA MODEL
# ============================================================

def create_canonical_record(
    patient_id,
    heart_rate,
    spo2,
    systolic_bp,
    diastolic_bp,
    temperature,
    temperature_unit,
    quality_metadata
):

    temperature_celsius = convert_temperature_to_celsius(
        temperature,
        temperature_unit
    )

    return {
        "patient_id": patient_id,
        "heart_rate": heart_rate,
        "spo2": spo2,
        "systolic_bp": systolic_bp,
        "diastolic_bp": diastolic_bp,
        "temperature": temperature_celsius,
        "technical_quality_valid":
            quality_metadata["technical_quality_valid"],
        "quality_issues":
            quality_metadata["quality_issues"]
    }


# ============================================================
# DEVICE A: NESTED JSON-STYLE INPUT
# Temperature unit: Celsius (Cel)
# ============================================================

def device_a_adapter(payload):

    patient_id = require_patient_id(payload, "patient")

    vitals = require_field(payload, "vitals")

    if not isinstance(vitals, dict):
        raise AdapterError("Device A vitals must be a dictionary.")

    blood_pressure = require_field(vitals, "bp")

    if not isinstance(blood_pressure, dict):
        raise AdapterError(
            "Device A blood pressure must be a dictionary."
        )

    temperature = require_field(vitals, "temp")

    if not isinstance(temperature, dict):
        raise AdapterError(
            "Device A temperature must contain value and unit."
        )

    temperature_value = require_number(
        temperature, "value"
    )

    temperature_unit = require_field(
        temperature, "unit"
    )

    quality = require_quality_metadata(payload)

    return create_canonical_record(
        patient_id=patient_id,
        heart_rate=require_number(vitals, "hr"),
        spo2=require_number(vitals, "oxygen"),
        systolic_bp=require_number(blood_pressure, "sys"),
        diastolic_bp=require_number(blood_pressure, "dia"),
        temperature=temperature_value,
        temperature_unit=temperature_unit,
        quality_metadata=quality
    )


# ============================================================
# DEVICE B: FLAT CSV-STYLE INPUT
# Temperature unit: Fahrenheit ([degF])
# ============================================================

def device_b_adapter(payload):

    patient_id = require_patient_id(payload, "subject_id")

    temperature_value = require_number(
        payload, "body_temp_value"
    )

    temperature_unit = require_field(
        payload, "body_temp_unit"
    )

    quality = require_quality_metadata(payload)

    return create_canonical_record(
        patient_id=patient_id,
        heart_rate=require_number(
            payload, "pulse_rate_bpm"
        ),
        spo2=require_number(
            payload, "spo2_percent"
        ),
        systolic_bp=require_number(
            payload, "systolic_pressure_mmhg"
        ),
        diastolic_bp=require_number(
            payload, "diastolic_pressure_mmhg"
        ),
        temperature=temperature_value,
        temperature_unit=temperature_unit,
        quality_metadata=quality
    )


# ============================================================
# CONVERT PROCESSED DATA INTO DEVICE-SPECIFIC PAYLOADS
# ============================================================

def build_device_a_payload(row):

    return {
        "patient": row["patient_id"],
        "vitals": {
            "hr": row["heart_rate"],
            "oxygen": row["spo2"],
            "bp": {
                "sys": row["systolic_bp"],
                "dia": row["diastolic_bp"]
            },
            "temp": {
                "value": row["temperature"],
                "unit": "Cel"
            }
        },
        "technical_quality_valid":
            row["technical_quality_valid"],
        "quality_issues": row["quality_issues"]
    }


def build_device_b_payload(row):

    temperature_fahrenheit = (
        float(row["temperature"]) * 9 / 5 + 32
    )

    return {
        "subject_id": row["patient_id"],
        "pulse_rate_bpm": row["heart_rate"],
        "spo2_percent": row["spo2"],
        "systolic_pressure_mmhg": row["systolic_bp"],
        "diastolic_pressure_mmhg": row["diastolic_bp"],
        "body_temp_value": temperature_fahrenheit,
        "body_temp_unit": "[degF]",
        "technical_quality_valid":
            row["technical_quality_valid"],
        "quality_issues": row["quality_issues"]
    }


# ============================================================
# EQUIVALENCE VERIFICATION
# ============================================================

def records_equivalent(record_a, record_b):

    if record_a.keys() != record_b.keys():
        return False

    numeric_fields = [
        "heart_rate",
        "spo2",
        "systolic_bp",
        "diastolic_bp",
        "temperature"
    ]

    for field in numeric_fields:
        if not math.isclose(
            record_a[field],
            record_b[field],
            rel_tol=0,
            abs_tol=0.000001
        ):
            return False

    exact_fields = [
        "patient_id",
        "technical_quality_valid",
        "quality_issues"
    ]

    return all(
        record_a[field] == record_b[field]
        for field in exact_fields
    )


# ============================================================
# TESTING INVALID INPUTS
# ============================================================

def test_invalid_inputs(valid_payload):

    tests = []

    # Test 1: Missing required field
    missing_field = copy.deepcopy(valid_payload)
    missing_field.pop("pulse_rate_bpm")

    # Test 2: Non-numeric measurement
    invalid_number = copy.deepcopy(valid_payload)
    invalid_number["pulse_rate_bpm"] = "invalid"

    # Test 3: Unsupported temperature unit
    invalid_unit = copy.deepcopy(valid_payload)
    invalid_unit["body_temp_unit"] = "Rankine"

    for payload in (
        missing_field,
        invalid_number,
        invalid_unit
    ):
        try:
            device_b_adapter(payload)
            tests.append(False)

        except AdapterError:
            tests.append(True)

    return tests


# ============================================================
# FIVE-RECORD TEST MODE
# ============================================================

def run_tests(df):

    print("\n========== ADAPTER TESTING ==========")

    sample = df.head(5)

    device_a_records = []
    device_b_records = []

    for _, row in sample.iterrows():

        payload_a = build_device_a_payload(row)
        payload_b = build_device_b_payload(row)

        record_a = device_a_adapter(payload_a)
        record_b = device_b_adapter(payload_b)

        device_a_records.append(record_a)
        device_b_records.append(record_b)

    equivalent = all(
        records_equivalent(a, b)
        for a, b in zip(device_a_records, device_b_records)
    )

    print("Sample records processed:", len(sample))
    print("Device A and B equivalent:", equivalent)

    conversion_test = convert_temperature_to_celsius(
        98.6, "[degF]"
    )

    print("98.6 Fahrenheit converted to:", conversion_test)

    invalid_results = test_invalid_inputs(
        build_device_b_payload(sample.iloc[0])
    )

    print("Invalid input tests passed:", sum(invalid_results))
    print("Invalid input tests total:", len(invalid_results))

    if (
        equivalent
        and math.isclose(
            conversion_test, 37.0, abs_tol=0.000001
        )
        and all(invalid_results)
    ):
        print("\nADAPTER TESTING PASSED!")
        print("Existing output files were not modified.")

    else:
        print("\nADAPTER TESTING FAILED!")
        print("Review the errors before full processing.")


# ============================================================
# FULL DATASET PROCESSING
# ============================================================

def run_full_processing(df):

    print("\n========== FULL DATASET PROCESSING ==========")

    device_a_records = []
    device_b_records = []

    for index, (_, row) in enumerate(df.iterrows(), start=1):

        payload_a = build_device_a_payload(row)
        payload_b = build_device_b_payload(row)

        record_a = device_a_adapter(payload_a)
        record_b = device_b_adapter(payload_b)

        device_a_records.append(record_a)
        device_b_records.append(record_b)

        if index % 10000 == 0:
            print(f"Processed {index}/{len(df)} records")

    equivalent = all(
        records_equivalent(a, b)
        for a, b in zip(device_a_records, device_b_records)
    )

    if not equivalent:
        raise AdapterError(
            "Device A and Device B outputs are not equivalent."
        )

    valid_count = sum(
        record["technical_quality_valid"]
        for record in device_a_records
    )

    flagged_count = len(device_a_records) - valid_count

    # Save only after successful processing and comparison.
    for output_file, records in (
        (DEVICE_A_OUTPUT, device_a_records),
        (DEVICE_B_OUTPUT, device_b_records)
    ):

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(
                records,
                file,
                indent=2,
                allow_nan=False
            )

    print("\n========== ADAPTER SUMMARY ==========")
    print("Device A records:", len(device_a_records))
    print("Device B records:", len(device_b_records))
    print("Valid records:", valid_count)
    print("Flagged records:", flagged_count)
    print("Equivalent canonical outputs:", equivalent)

    print("\nDevice A output:", DEVICE_A_OUTPUT)
    print("Device B output:", DEVICE_B_OUTPUT)

    print("\nFULL DATASET ADAPTER PROCESSING SUCCESSFUL!")


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Patient monitoring device adapter framework"
    )

    mode = parser.add_mutually_exclusive_group(required=True)

    mode.add_argument(
        "--test",
        action="store_true",
        help="Run five-record and invalid-input tests."
    )

    mode.add_argument(
        "--full",
        action="store_true",
        help="Process the complete dataset."
    )

    args = parser.parse_args()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Processed dataset not found: {INPUT_FILE}"
        )

    print("Loading processed dataset...")

    df = pd.read_csv(INPUT_FILE)

    required_columns = [
        "patient_id",
        "heart_rate",
        "spo2",
        "systolic_bp",
        "diastolic_bp",
        "temperature",
        "technical_quality_valid",
        "quality_issues"
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise AdapterError(
            f"Processed dataset missing columns: {missing_columns}"
        )

    print("Total input records:", len(df))

    if args.test:
        run_tests(df)

    elif args.full:
        run_full_processing(df)


if __name__ == "__main__":
    main()


