import itertools
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


INPUT_PATH = Path(
    "data/processed/cleaned_addiction_data.csv"
)

MODEL_PATH = Path(
    "ml/saved_models/user_segmentation.pkl"
)

METRICS_PATH = Path(
    "ml/saved_models/user_segmentation_metrics.json"
)

OUTPUT_PATH = Path(
    "data/processed/user_segments.csv"
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


SEGMENT_NAMES = [
    "Heavy Social User",
    "Gaming Heavy User",
    "Productivity Focused User",
    "Late Night / High Usage User",
    "Balanced User",
]


def prepare_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepare the exact raw feature structure accepted by
    the HabitGuard segmentation endpoint.
    """

    df = dataframe.copy()

    if "gender" in df.columns:
        df["gender"] = (
            df["gender"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        gender_columns = pd.get_dummies(
            df["gender"],
            prefix="gender",
            dtype=int,
        )

        df = pd.concat(
            [df.drop(columns=["gender"]), gender_columns],
            axis=1,
        )

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
            "Dataset is missing required columns: "
            + ", ".join(missing_columns)
        )

    X = df[FEATURE_COLUMNS].copy()

    for column in FEATURE_COLUMNS:
        X[column] = pd.to_numeric(
            X[column],
            errors="coerce",
        )

        if X[column].isna().all():
            X[column] = 0.0

    return X


def build_pipeline() -> Pipeline:
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
                "kmeans",
                KMeans(
                    n_clusters=5,
                    random_state=42,
                    n_init=20,
                ),
            ),
        ]
    )


def build_cluster_name_map(
    standardized_centers: np.ndarray,
) -> dict[int, str]:
    """
    Assign one meaningful name to each fitted cluster.

    The assignment is based on the actual KMeans cluster
    centres rather than separate thresholds applied during
    prediction.
    """

    feature_index = {
        name: FEATURE_COLUMNS.index(name)
        for name in FEATURE_COLUMNS
    }

    daily = standardized_centers[
        :,
        feature_index["daily_screen_time_hours"],
    ]

    social = standardized_centers[
        :,
        feature_index["social_media_hours"],
    ]

    gaming = standardized_centers[
        :,
        feature_index["gaming_hours"],
    ]

    work_study = standardized_centers[
        :,
        feature_index["work_study_hours"],
    ]

    sleep = standardized_centers[
        :,
        feature_index["sleep_hours"],
    ]

    weekend = standardized_centers[
        :,
        feature_index["weekend_screen_time"],
    ]

    stress = standardized_centers[
        :,
        feature_index["stress_level"],
    ]

    impact = standardized_centers[
        :,
        feature_index["academic_work_impact"],
    ]

    # One score row for each possible segment name.
    scores = np.vstack(
        [
            social + (0.35 * daily),
            gaming + (0.15 * daily),
            work_study - (0.25 * daily),
            (
                daily
                + (0.35 * weekend)
                + (0.25 * stress)
                + (0.25 * impact)
                - (0.60 * sleep)
            ),
            -np.mean(
                np.abs(
                    np.column_stack(
                        [
                            daily,
                            social,
                            gaming,
                            work_study,
                            sleep,
                            weekend,
                            stress,
                            impact,
                        ]
                    )
                ),
                axis=1,
            ),
        ]
    )

    cluster_ids = range(
        standardized_centers.shape[0]
    )

    # Try all assignments. With five clusters there are
    # only 120 possibilities.
    best_assignment = max(
        itertools.permutations(cluster_ids),
        key=lambda assignment: sum(
            scores[segment_index, cluster_id]
            for segment_index, cluster_id
            in enumerate(assignment)
        ),
    )

    return {
        int(cluster_id): SEGMENT_NAMES[segment_index]
        for segment_index, cluster_id
        in enumerate(best_assignment)
    }


def train_user_segmentation() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {INPUT_PATH.resolve()}"
        )

    dataframe = pd.read_csv(INPUT_PATH)

    print("Input dataset:", INPUT_PATH)
    print("Dataset shape:", dataframe.shape)

    X = prepare_features(dataframe)

    pipeline = build_pipeline()
    pipeline.fit(X)

    clusters = pipeline.predict(X)

    transformed_features = (
        pipeline[:-1].transform(X)
    )

    score = silhouette_score(
        transformed_features,
        clusters,
    )

    scaler = pipeline.named_steps["scaler"]
    kmeans = pipeline.named_steps["kmeans"]

    standardized_centers = (
        kmeans.cluster_centers_
    )

    raw_centers = scaler.inverse_transform(
        standardized_centers
    )

    cluster_names = build_cluster_name_map(
        standardized_centers
    )

    center_dataframe = pd.DataFrame(
        raw_centers,
        columns=FEATURE_COLUMNS,
    )

    result_dataframe = X.copy()
    result_dataframe["cluster"] = clusters

    result_dataframe["segment_name"] = [
        cluster_names[int(cluster)]
        for cluster in clusters
    ]

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact = {
        "artifact_version": 2,
        "pipeline": pipeline,
        "feature_columns": FEATURE_COLUMNS,
        "cluster_names": cluster_names,
        "cluster_centers_raw": (
            center_dataframe
            .round(4)
            .to_dict(orient="index")
        ),
        "silhouette_score": float(score),
    }

    with open(MODEL_PATH, "wb") as file:
        pickle.dump(artifact, file)

    result_dataframe.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    cluster_counts = (
        result_dataframe["cluster"]
        .value_counts()
        .sort_index()
    )

    metrics = {
        "model_type": "KMeans Pipeline",
        "number_of_clusters": 5,
        "training_rows": int(len(X)),
        "silhouette_score": round(
            float(score),
            4,
        ),
        "cluster_names": {
            str(key): value
            for key, value
            in cluster_names.items()
        },
        "cluster_counts": {
            str(key): int(value)
            for key, value
            in cluster_counts.items()
        },
        "cluster_centers_raw": {
            str(key): value
            for key, value
            in (
                center_dataframe
                .round(4)
                .to_dict(orient="index")
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

    print(
        "\nSilhouette Score:",
        round(score, 4),
    )

    print("\nCluster names:")

    for cluster_id in sorted(cluster_names):
        print(
            f"Cluster {cluster_id}: "
            f"{cluster_names[cluster_id]}"
        )

    print("\nCluster counts:")
    print(cluster_counts)

    print("\nModel saved to:")
    print(MODEL_PATH)

    print("\nMetrics saved to:")
    print(METRICS_PATH)

    print("\nSegmented data saved to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    train_user_segmentation()