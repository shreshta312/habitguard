import pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler


INPUT_PATH = Path("data/processed/cleaned_addiction_data.csv")
OUTPUT_PATH = Path("data/processed/addiction_ml_features.csv")


def create_addiction_features():
    df = pd.read_csv(INPUT_PATH)

    print("Input shape:", df.shape)

    # Convert gender into numeric columns
    df = pd.get_dummies(df, columns=["gender"], drop_first=True)

    feature_columns = [
        "age",
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
    ]

    # Add gender columns also
    gender_columns = [col for col in df.columns if col.startswith("gender_")]
    feature_columns.extend(gender_columns)

    target_column = "addicted_label"

    X = df[feature_columns]
    y = df[target_column]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    scaled_df = pd.DataFrame(X_scaled, columns=feature_columns)
    scaled_df[target_column] = y.values

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    scaled_df.to_csv(OUTPUT_PATH, index=False)

    print("Output shape:", scaled_df.shape)
    print("Saved to:", OUTPUT_PATH)
    print("\nColumns:")
    print(scaled_df.columns.tolist())


if __name__ == "__main__":
    create_addiction_features()