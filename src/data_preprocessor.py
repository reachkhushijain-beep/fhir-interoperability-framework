
import pandas as pd
import json
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parents[1]
RAW_FILE = BASE_DIR / "data" / "raw" / "Synthetic_patient-HealthCare-Monitoring_dataset.csv"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load dataset
df = pd.read_csv(RAW_FILE)

print("Original dataset shape:", df.shape)

# Standardise column names
df = df.rename(columns={
    "Patient Number": "patient_id",
    "Heart Rate (bpm)": "heart_rate",
    "SpO2 Level (%)": "spo2",
    "Systolic Blood Pressure (mmHg)": "systolic_bp",
    "Diastolic Blood Pressure (mmHg)": "diastolic_bp",
    "Body Temperature (°C)": "temperature",
    "Fall Detection": "fall_detection",
    "Predicted Disease": "predicted_disease",
    "Data Accuracy (%)": "data_accuracy",
    "Heart Rate Alert": "heart_rate_alert",
    "SpO2 Level Alert": "spo2_alert",
    "Blood Pressure Alert": "bp_alert",
    "Temperature Alert": "temperature_alert"
})

# Technical plausibility checks (not clinical diagnostic limits)
checks = {
    "heart_rate": (30, 220),
    "spo2": (50, 100),
    "systolic_bp": (50, 260),
    "diastolic_bp": (30, 160),
    "temperature": (30, 43)
}

quality_flags = {}

for column, (minimum, maximum) in checks.items():
    df[column] = pd.to_numeric(df[column], errors="coerce")
    quality_flags[column] = (
        df[column].notna() &
        df[column].between(minimum, maximum)
    )

# Check blood pressure relationship
quality_flags["bp_relationship"] = (
    df["systolic_bp"] > df["diastolic_bp"]
)

# Flag records; do not delete abnormal readings
df["technical_quality_valid"] = pd.DataFrame(
    quality_flags, index=df.index
).all(axis=1)

df["quality_issues"] = ""

for column, valid in quality_flags.items():
    issue = df["quality_issues"].eq("")
    df.loc[~valid & issue, "quality_issues"] = column
    df.loc[~valid & ~issue, "quality_issues"] += ", " + column

# Add standard units for downstream FHIR mapping
df["heart_rate_unit"] = "/min"
df["spo2_unit"] = "%"
df["blood_pressure_unit"] = "mm[Hg]"
df["temperature_unit"] = "Cel"

# Save processed dataset
processed_file = OUTPUT_DIR / "patient_monitoring_processed.csv"
df.to_csv(processed_file, index=False)

# Generate quality report
report = {
    "total_records": int(len(df)),
    "valid_records": int(df["technical_quality_valid"].sum()),
    "flagged_records": int((~df["technical_quality_valid"]).sum()),
    "missing_values_after_conversion": {
        column: int(df[column].isna().sum())
        for column in checks
    },
    "quality_checks": {
        column: int((~valid).sum())
        for column, valid in quality_flags.items()
    },
    "note": "Technical plausibility checks only; not clinical diagnosis."
}

report_file = OUTPUT_DIR / "data_quality_report.json"

with open(report_file, "w") as file:
    json.dump(report, file, indent=4)

print("\nPreprocessing completed!")
print("Processed dataset shape:", df.shape)
print("Valid records:", report["valid_records"])
print("Flagged records:", report["flagged_records"])
print("Processed file:", processed_file)
print("Quality report:", report_file)
