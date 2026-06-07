import pandas as pd
from pathlib import Path
import pickle

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


INPUT_PATH = Path("data/processed/cleaned_screen_time.csv")
MODEL_PATH = Path("ml/saved_models/anomaly_detector.pkl")
SCALER_PATH = Path("ml/saved_models/anomaly_scaler.pkl")


def train_anomaly_detector():
    df = pd.read_csv(INPUT_PATH)

    print("Dataset shape:", df.shape)

    feature_columns = [
        "screen_time_min",
        "launches",
        "interactions",
        "is_productive"
    ]

    X = df[feature_columns]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=100,
        contamination=0.05,
        random_state=42
    )

    model.fit(X_scaled)

    predictions = model.predict(X_scaled)

    # Isolation Forest gives:
    #  1  = normal
    # -1  = anomaly
    df["anomaly_label"] = predictions
    df["is_anomaly"] = df["anomaly_label"].map({
        1: 0,
        -1: 1
    })

    print("\nAnomaly counts:")
    print(df["is_anomaly"].value_counts())

    print("\nSample anomalies:")
    print(
        df[df["is_anomaly"] == 1][
            ["user_id", "date", "app_name", "screen_time_min", "launches", "interactions"]
        ].head(10)
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(MODEL_PATH, "wb") as file:
        pickle.dump(model, file)

    with open(SCALER_PATH, "wb") as file:
        pickle.dump(scaler, file)

    print("\nModel saved to:", MODEL_PATH)
    print("Scaler saved to:", SCALER_PATH)


if __name__ == "__main__":
    train_anomaly_detector()