
import pandas as pd

file_path = "data/raw/Synthetic_patient-HealthCare-Monitoring_dataset.csv"

df = pd.read_csv(file_path)

# 1. Statistical summary
print("\n--- STATISTICAL SUMMARY ---")
print(df.describe())

# 2. Check unique patient identifiers
print("\n--- PATIENT IDENTIFIERS ---")
print("Unique patients:", df["Patient Number"].nunique())
print("Duplicate patient IDs:", df["Patient Number"].duplicated().sum())

# 3. Check categorical values
categorical_columns = [
    "Fall Detection",
    "Predicted Disease",
    "Heart Rate Alert",
    "SpO2 Level Alert",
    "Blood Pressure Alert",
    "Temperature Alert"
]

print("\n--- CATEGORICAL VALUES ---")

for col in categorical_columns:
    print(f"\n{col}:")
    print(df[col].value_counts())

# 4. Check physiological parameter ranges
numeric_columns = [
    "Heart Rate (bpm)",
    "SpO2 Level (%)",
    "Systolic Blood Pressure (mmHg)",
    "Diastolic Blood Pressure (mmHg)",
    "Body Temperature (°C)"
]

print("\n--- PARAMETER RANGES ---")

for col in numeric_columns:
    print(f"\n{col}")
    print("Minimum:", df[col].min())
    print("Maximum:", df[col].max())
    print("Average:", round(df[col].mean(), 2))
