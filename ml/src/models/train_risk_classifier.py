import json
import pickle
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


INPUT_PATH = Path("data/processed/cleaned_addiction_data.csv")

MODEL_PATH = Path(
    "ml/saved_models/risk_classifier.pkl"
)

METRICS_PATH = Path(
    "ml/saved_models/risk_classifier_metrics.json"
)


FEATURE_COLUMNS = [
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
    "gender_male",
    "gender_other",
]

TARGET_COLUMN = "addicted_label"


def prepare_features(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Convert the cleaned addiction dataset into the exact
    feature structure used by the HabitGuard risk endpoint.
    """

    df = dataframe.copy()

    if "gender" in df.columns:
        df = pd.get_dummies(
            df,
            columns=["gender"],
            prefix="gender",
            drop_first=True,
        )

    # Female acts as the reference category.
    # These columns may not exist if a category is absent
    # from the current training dataset.
    if "gender_male" not in df.columns:
        df["gender_male"] = 0

    if "gender_other" not in df.columns:
        df["gender_other"] = 0

    missing_columns = [
        column
        for column in FEATURE_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Training dataset is missing required columns: "
            + ", ".join(missing_columns)
        )

    if TARGET_COLUMN not in df.columns:
        raise ValueError(
            f"Training dataset is missing target column: "
            f"{TARGET_COLUMN}"
        )

    X = df[FEATURE_COLUMNS].copy()

    for column in FEATURE_COLUMNS:
        X[column] = pd.to_numeric(
            X[column],
            errors="coerce",
        )

        # Protect against a column that contains only
        # missing values.
        if X[column].isna().all():
            X[column] = 0.0

    y = pd.to_numeric(
        df[TARGET_COLUMN],
        errors="coerce",
    )

    valid_target_rows = y.notna()

    X = X.loc[valid_target_rows].reset_index(
        drop=True
    )

    y = (
        y.loc[valid_target_rows]
        .astype(int)
        .reset_index(drop=True)
    )

    return X, y


def build_pipeline() -> Pipeline:
    """
    Save preprocessing and prediction as one object.

    The backend can therefore provide raw questionnaire
    values without manually applying a separate scaler.
    """

    return Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="median",
                    keep_empty_features=True,
                ),
            ),
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=200,
                    random_state=42,
                    class_weight="balanced",
                    n_jobs=-1,
                ),
            ),
        ]
    )


def train_risk_classifier() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Training dataset not found: "
            f"{INPUT_PATH.resolve()}"
        )

    df = pd.read_csv(INPUT_PATH)

    print("Input dataset:", INPUT_PATH)
    print("Dataset shape:", df.shape)

    X, y = prepare_features(df)

    print("Training feature columns:")
    for column in X.columns:
        print(" -", column)

    print("\nTarget distribution:")
    print(y.value_counts().sort_index())

    X_train, X_test, y_train, y_test = (
        train_test_split(
            X,
            y,
            test_size=0.20,
            random_state=42,
            stratify=y,
        )
    )

    pipeline = build_pipeline()

    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)

    accuracy = accuracy_score(
        y_test,
        predictions,
    )

    matrix = confusion_matrix(
        y_test,
        predictions,
    )

    precision, recall, f1, _ = (
        precision_recall_fscore_support(
            y_test,
            predictions,
            average="binary",
            zero_division=0,
        )
    )

    print("\nAccuracy:", round(accuracy, 4))

    print("\nConfusion Matrix:")
    print(matrix)

    print("\nClassification Report:")
    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0,
        )
    )

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(MODEL_PATH, "wb") as file:
        pickle.dump(pipeline, file)

    metrics = {
        "model_type": "Pipeline",
        "classifier": "RandomForestClassifier",
        "features": FEATURE_COLUMNS,
        "training_rows": int(len(X_train)),
        "testing_rows": int(len(X_test)),
        "accuracy": round(
            float(accuracy),
            4,
        ),
        "precision": round(
            float(precision),
            4,
        ),
        "recall": round(
            float(recall),
            4,
        ),
        "f1_score": round(
            float(f1),
            4,
        ),
        "confusion_matrix": matrix.tolist(),
        "class_distribution": {
            str(key): int(value)
            for key, value in (
                y.value_counts()
                .sort_index()
                .items()
            )
        },
    }

    with open(
        METRICS_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metrics,
            file,
            indent=2,
        )

    print("\nPipeline saved to:")
    print(MODEL_PATH)

    print("\nMetrics saved to:")
    print(METRICS_PATH)


if __name__ == "__main__":
    train_risk_classifier()