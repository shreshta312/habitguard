import pandas as pd
from pathlib import Path


RAW_PATH = Path("data/raw/Smartphone_Usage_And_Addiction_Analysis_7500_Rows.csv")
PROCESSED_PATH = Path("data/processed/cleaned_addiction_data.csv")


def clean_addiction_data():
    df = pd.read_csv(RAW_PATH)

    print("Original shape:", df.shape)

    # Standardize column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    useful_columns = [
        "user_id",
        "age",
        "gender",
        "daily_screen_time_hours",
        "social_media_hours",
        "gaming_hours",
        "work_study_hours",
        "sleep_hours",
        "notifications_per_day",
        "app_opens_per_day",
        "weekend_screen_time",
        "stress_level",
        "academic_work_impact",
        "addiction_level",
        "addicted_label",
    ]

    existing_columns = [col for col in useful_columns if col in df.columns]
    df = df[existing_columns]

    # Numeric columns
    numeric_columns = [
        "age",
        "daily_screen_time_hours",
        "social_media_hours",
        "gaming_hours",
        "work_study_hours",
        "sleep_hours",
        "notifications_per_day",
        "app_opens_per_day",
        "weekend_screen_time",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].fillna(df[col].median())

    # Clean gender
    if "gender" in df.columns:
        df["gender"] = (
            df["gender"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

    # Encode stress level
    if "stress_level" in df.columns:
        df["stress_level"] = (
            df["stress_level"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({
                "low": 0,
                "medium": 1,
                "moderate": 1,
                "high": 2,
                "very high": 3,
            })
        )

        df["stress_level"] = df["stress_level"].fillna(0)

    # Encode academic/work impact
    if "academic_work_impact" in df.columns:
        df["academic_work_impact"] = (
            df["academic_work_impact"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({
                "yes": 1,
                "no": 0,
                "true": 1,
                "false": 0,
                "1": 1,
                "0": 0,
                "none": 0,
                "low": 1,
                "mild": 1,
                "moderate": 2,
                "medium": 2,
                "high": 3,
                "severe": 4,
            })
        )

        df["academic_work_impact"] = df["academic_work_impact"].fillna(0)

    # Encode addiction level
    if "addiction_level" in df.columns:
        df["addiction_level"] = (
            df["addiction_level"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({
                "none": 0,
                "low": 1,
                "mild": 1,
                "moderate": 2,
                "medium": 2,
                "high": 3,
                "severe": 4,
            })
        )

        df["addiction_level"] = df["addiction_level"].fillna(0)

    # Encode addicted label
    if "addicted_label" in df.columns:
        df["addicted_label"] = (
            df["addicted_label"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({
                "yes": 1,
                "no": 0,
                "addicted": 1,
                "not addicted": 0,
                "true": 1,
                "false": 0,
                "1": 1,
                "0": 0,
            })
        )

    # Remove rows where target is missing
    df = df.dropna(subset=["addicted_label"])

    # Remove duplicate rows
    df = df.drop_duplicates()

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False)

    print("Cleaned shape:", df.shape)
    print("Saved to:", PROCESSED_PATH)

    print("\nMissing values:")
    print(df.isnull().sum())

    print("\nLabel distribution:")
    print(df["addicted_label"].value_counts())


if __name__ == "__main__":
    clean_addiction_data()