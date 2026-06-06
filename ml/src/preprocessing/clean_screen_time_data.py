import pandas as pd
from pathlib import Path


RAW_PATH = Path("data/raw/screen_time_app_usage_dataset.csv")
PROCESSED_PATH = Path("data/processed/cleaned_screen_time.csv")


def clean_screen_time_data():
    df = pd.read_csv(RAW_PATH)

    print("Original shape:", df.shape)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    useful_columns = [
        "user_id",
        "date",
        "app_name",
        "category",
        "screen_time_min",
        "launches",
        "interactions",
        "is_productive",
    ]

    df = df[useful_columns]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    numeric_columns = [
        "screen_time_min",
        "launches",
        "interactions",
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["is_productive"] = (
        df["is_productive"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": 1,
            "false": 0,
            "1": 1,
            "0": 0,
        })
    )

    df = df.dropna(subset=[
        "user_id",
        "date",
        "app_name",
        "screen_time_min",
    ])

    df["category"] = df["category"].fillna("Unknown")
    df["launches"] = df["launches"].fillna(0)
    df["interactions"] = df["interactions"].fillna(0)
    df["is_productive"] = df["is_productive"].fillna(0)

    df = df[df["screen_time_min"] >= 0]
    df = df[df["launches"] >= 0]
    df = df[df["interactions"] >= 0]

    df = df.drop_duplicates()

    df = df.sort_values(
        by=["user_id", "app_name", "date"]
    )

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False)

    print("Cleaned shape:", df.shape)
    print("Saved to:", PROCESSED_PATH)
    print("Users:", df["user_id"].nunique())
    print("Apps:", df["app_name"].nunique())
    print("Missing values:")
    print(df.isnull().sum())


if __name__ == "__main__":
    clean_screen_time_data()