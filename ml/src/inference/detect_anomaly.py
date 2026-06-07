import pickle
import pandas as pd
from pathlib import Path


MODEL_PATH = Path("ml/saved_models/anomaly_detector.pkl")
SCALER_PATH = Path("ml/saved_models/anomaly_scaler.pkl")


def load_model_and_scaler():
    with open(MODEL_PATH, "rb") as file:
        model = pickle.load(file)

    with open(SCALER_PATH, "rb") as file:
        scaler = pickle.load(file)

    return model, scaler


def detect_anomaly(screen_time_min, launches, interactions, is_productive):
    model, scaler = load_model_and_scaler()

    sample = pd.DataFrame([{
        "screen_time_min": screen_time_min,
        "launches": launches,
        "interactions": interactions,
        "is_productive": is_productive
    }])

    sample_scaled = scaler.transform(sample)

    prediction = model.predict(sample_scaled)[0]

    if prediction == -1:
        result = "ANOMALY"
        message = "Unusual usage pattern detected."
    else:
        result = "NORMAL"
        message = "Usage pattern looks normal."

    return {
        "screen_time_min": screen_time_min,
        "launches": launches,
        "interactions": interactions,
        "is_productive": is_productive,
        "result": result,
        "message": message
    }


if __name__ == "__main__":
    normal_test = detect_anomaly(
        screen_time_min=25,
        launches=3,
        interactions=5,
        is_productive=0
    )

    spike_test = detect_anomaly(
        screen_time_min=180,
        launches=1,
        interactions=4,
        is_productive=0
    )

    print("Normal Test:")
    print(normal_test)

    print("\nSpike Test:")
    print(spike_test)