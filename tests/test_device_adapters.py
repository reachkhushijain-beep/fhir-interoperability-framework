import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import device_adapters as adapters


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


def test_device_a_and_b_produce_equivalent_records():
    payload_a = adapters.build_device_a_payload(SAMPLE_RECORD)
    payload_b = adapters.build_device_b_payload(SAMPLE_RECORD)

    result_a = adapters.device_a_adapter(payload_a)
    result_b = adapters.device_b_adapter(payload_b)

    assert adapters.records_equivalent(result_a, result_b)


def test_device_a_temperature_remains_in_celsius():
    payload = adapters.build_device_a_payload(SAMPLE_RECORD)
    result = adapters.device_a_adapter(payload)

    assert result["temperature"] == 37.0


def test_device_b_fahrenheit_converts_to_celsius():
    payload = adapters.build_device_b_payload(SAMPLE_RECORD)
    result = adapters.device_b_adapter(payload)

    assert result["temperature"] == pytest.approx(37.0)


@pytest.mark.parametrize(
    "temperature, unit, expected",
    [
        (37.0, "Cel", 37.0),
        (98.6, "[degF]", 37.0),
        (32.0, "[degF]", 0.0),
        (212.0, "[degF]", 100.0),
    ]
)
def test_temperature_conversion(temperature, unit, expected):
    result = adapters.convert_temperature_to_celsius(
        temperature, unit
    )
    assert result == pytest.approx(expected)


def test_unsupported_temperature_unit_is_rejected():
    with pytest.raises(adapters.AdapterError):
        adapters.convert_temperature_to_celsius(37, "Rankine")


@pytest.mark.parametrize(
    "field, value",
    [
        ("pulse_rate_bpm", "invalid"),
        ("pulse_rate_bpm", float("inf")),
        ("pulse_rate_bpm", True),
        ("body_temp_unit", "Rankine"),
    ]
)
def test_invalid_device_b_measurements_are_rejected(field, value):
    payload = adapters.build_device_b_payload(SAMPLE_RECORD)
    payload[field] = value

    with pytest.raises(adapters.AdapterError):
        adapters.device_b_adapter(payload)


def test_missing_device_b_field_is_rejected():
    payload = adapters.build_device_b_payload(SAMPLE_RECORD)
    del payload["pulse_rate_bpm"]

    with pytest.raises(adapters.AdapterError):
        adapters.device_b_adapter(payload)


def test_missing_device_a_nested_field_is_rejected():
    payload = adapters.build_device_a_payload(SAMPLE_RECORD)
    del payload["vitals"]["hr"]

    with pytest.raises(adapters.AdapterError):
        adapters.device_a_adapter(payload)


def test_flagged_quality_metadata_is_preserved():
    record = SAMPLE_RECORD.copy()
    record["technical_quality_valid"] = False
    record["quality_issues"] = "Heart rate outside technical range"

    payload = adapters.build_device_b_payload(record)
    result = adapters.device_b_adapter(payload)

    assert result["technical_quality_valid"] is False
    assert result["quality_issues"] == record["quality_issues"]


def test_records_with_different_values_are_not_equivalent():
    record_a = SAMPLE_RECORD.copy()
    record_b = SAMPLE_RECORD.copy()
    record_b["heart_rate"] = 100.0

    assert not adapters.records_equivalent(record_a, record_b)
