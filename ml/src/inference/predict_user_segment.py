import pickle
import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[3]
MODEL_PATH = BASE_DIR / "ml" / "saved_models" / "user_segmentation.pkl"
FEATURE_PATH = BASE_DIR / "data" / "processed" / "addiction_ml_features.csv"


def get_segment_name(row):
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


def load_model():
    with open(MODEL_PATH, "rb") as file:
        model = pickle.load(file)

    return model


def predict_sample_segment():
    model = load_model()

    df = pd.read_csv(FEATURE_PATH)

    target_column = "addicted_label"

    X = df.drop(columns=[target_column], errors="ignore")

    sample = X.iloc[[0]]

    pipeline = model.get("pipeline", model) if isinstance(model, dict) else model
    cluster = pipeline.predict(sample)[0]

    sample_row = sample.iloc[0]
    segment_name = get_segment_name(sample_row)

    print("Sample Features:")
    print(sample)

    print("\nPredicted Cluster:", cluster)
    print("Segment Name:", segment_name)


if __name__ == "__main__":
    predict_sample_segment()