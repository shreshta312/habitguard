import pandas as pd
from pathlib import Path
import pickle

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


INPUT_PATH = Path("data/processed/addiction_ml_features.csv")
MODEL_PATH = Path("ml/saved_models/user_segmentation.pkl")
OUTPUT_PATH = Path("data/processed/user_segments.csv")


def get_segment_name(row):
    """
    Assign readable segment names based on user behavior.
    These names are rule-based after KMeans clustering.
    """

    if row["daily_screen_time_hours"] > 0.8 and row["social_media_hours"] > 0.8:
        return "Heavy Social User"

    elif row["gaming_hours"] > 0.8:
        return "Gaming Heavy User"

    elif row["work_study_hours"] > 0.8 and row["daily_screen_time_hours"] < 0.5:
        return "Productivity Focused User"

    elif row["sleep_hours"] < -0.8 and row["daily_screen_time_hours"] > 0.5:
        return "Late Night / High Usage User"

    else:
        return "Balanced User"


def train_user_segmentation():
    df = pd.read_csv(INPUT_PATH)

    print("Dataset shape:", df.shape)

    target_column = "addicted_label"

    X = df.drop(columns=[target_column])

    kmeans = KMeans(
        n_clusters=5,
        random_state=42,
        n_init=10
    )

    clusters = kmeans.fit_predict(X)

    df["cluster"] = clusters

    score = silhouette_score(X, clusters)

    print("\nSilhouette Score:", round(score, 3))

    print("\nCluster counts:")
    print(df["cluster"].value_counts())

    df["segment_name"] = df.apply(get_segment_name, axis=1)

    print("\nSegment counts:")
    print(df["segment_name"].value_counts())

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(MODEL_PATH, "wb") as file:
        pickle.dump(kmeans, file)

    df.to_csv(OUTPUT_PATH, index=False)

    print("\nModel saved to:", MODEL_PATH)
    print("Segmented data saved to:", OUTPUT_PATH)


if __name__ == "__main__":
    train_user_segmentation()