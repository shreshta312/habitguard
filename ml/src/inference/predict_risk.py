import pickle
import pandas as pd
from pathlib import Path


MODEL_PATH = Path("ml/saved_models/risk_classifier.pkl")
FEATURE_PATH = Path("data/processed/addiction_ml_features.csv")


def load_model():
    with open(MODEL_PATH, "rb") as file:
        model = pickle.load(file)
    return model


def predict_sample_user():
    model = load_model()

    df = pd.read_csv(FEATURE_PATH)

    target_column = "addicted_label"

    X = df.drop(columns=[target_column])

    # Pick one sample user from the dataset
    sample = X.iloc[[0]]

    prediction = model.predict(sample)[0]
    probability = model.predict_proba(sample)[0]

    print("Sample Features:")
    print(sample)

    print("\nPrediction:", prediction)

    if prediction == 1:
        print("Risk Result: HIGH ADDICTION RISK")
    else:
        print("Risk Result: LOW ADDICTION RISK")

    print("\nPrediction Probabilities:")
    print("Not Addicted:", round(probability[0] * 100, 2), "%")
    print("Addicted:", round(probability[1] * 100, 2), "%")


if __name__ == "__main__":
    predict_sample_user()