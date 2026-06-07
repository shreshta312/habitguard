import pandas as pd
from pathlib import Path
import pickle

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


INPUT_PATH = Path("data/processed/cleaned_screen_time.csv")
MODEL_PATH = Path("ml/saved_models/usage_forecaster.pkl")


def create_daily_user_usage(df):
    """
    Converts app-level records into total daily usage per user.
    """

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    daily_df = (
        df.groupby(["user_id", "date"])
        .agg({
            "screen_time_min": "sum",
            "launches": "sum",
            "interactions": "sum",
            "is_productive": "mean"
        })
        .reset_index()
        .sort_values(["user_id", "date"])
    )

    return daily_df


def create_forecasting_features(df):
    """
    Creates forecasting features using total daily usage per user.
    """

    df = df.copy()

    grouped = df.groupby("user_id")

    df["usage_lag_1"] = grouped["screen_time_min"].shift(1)
    df["usage_lag_2"] = grouped["screen_time_min"].shift(2)
    df["usage_lag_3"] = grouped["screen_time_min"].shift(3)

    df["usage_rolling_mean_3"] = (
        grouped["screen_time_min"]
        .rolling(window=3)
        .mean()
        .reset_index(level=0, drop=True)
    )

    df["launches_lag_1"] = grouped["launches"].shift(1)
    df["interactions_lag_1"] = grouped["interactions"].shift(1)

    df["target_next_usage"] = grouped["screen_time_min"].shift(-1)

    df = df.dropna()

    return df


def train_usage_forecaster():
    df = pd.read_csv(INPUT_PATH)

    print("Original dataset shape:", df.shape)

    daily_df = create_daily_user_usage(df)
    print("Daily user dataset shape:", daily_df.shape)

    forecast_df = create_forecasting_features(daily_df)
    print("Forecasting dataset shape:", forecast_df.shape)

    feature_columns = [
        "usage_lag_1",
        "usage_lag_2",
        "usage_lag_3",
        "usage_rolling_mean_3",
        "launches_lag_1",
        "interactions_lag_1",
        "is_productive"
    ]

    X = forecast_df[feature_columns]
    y = forecast_df["target_next_usage"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42
    )

    model = RandomForestRegressor(
        n_estimators=100,
        random_state=42
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print("\nModel Evaluation:")
    print("MAE:", round(mae, 2))
    print("MSE:", round(mse, 2))
    print("R2 Score:", round(r2, 3))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(MODEL_PATH, "wb") as file:
        pickle.dump(model, file)

    print("\nModel saved to:", MODEL_PATH)


if __name__ == "__main__":
    train_usage_forecaster()