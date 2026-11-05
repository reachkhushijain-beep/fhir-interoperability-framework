
import pandas as pd
import os

data_folder = "data/raw"

files = [f for f in os.listdir(data_folder) if f.endswith(".csv")]

print("CSV files found:", files)

for file in files:
    path = os.path.join(data_folder, file)
    df = pd.read_csv(path)

    print("\n" + "=" * 50)
    print("FILE:", file)
    print("=" * 50)

    print("Dataset shape:", df.shape)

    print("\nColumn names:")
    print(df.columns.tolist())

    print("\nFirst 5 records:")
    print(df.head())

    print("\nData types:")
    print(df.dtypes)

    print("\nMissing values:")
    print(df.isnull().sum())
