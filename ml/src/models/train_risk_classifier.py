import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import pickle


INPUT_PATH = Path("data/processed/addiction_ml_features.csv")
MODEL_PATH = Path("ml/saved_models/risk_classifier.pkl")


def train_risk_classifier():
    df = pd.read_csv(INPUT_PATH)

    print("Dataset shape:", df.shape)

    target_column = "addicted_label"

    X = df.drop(columns=[target_column])
    y = df[target_column]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced"
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    print("\nAccuracy:", accuracy_score(y_test, y_pred))

    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(MODEL_PATH, "wb") as file:
        pickle.dump(model, file)

    print("\nModel saved to:", MODEL_PATH)


if __name__ == "__main__":
    train_risk_classifier()