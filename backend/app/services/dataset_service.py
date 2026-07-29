import pandas as pd
from pathlib import Path
from app.core.config import PROJECT_ROOT


class DatasetService:
    """
    Loads cleaned screen-time data and returns usage history
    for selected users and apps.
    """

    def __init__(self, csv_path=None):
        if csv_path is None:
            self.csv_path = PROJECT_ROOT / "data" / "processed" / "cleaned_screen_time.csv"
        else:
            p = Path(csv_path)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            self.csv_path = p

    def load_data(self):
        empty_df = pd.DataFrame(columns=["user_id", "date", "app_name", "screen_time_min"])
        if not self.csv_path.exists():
            return empty_df

        try:
            df = pd.read_csv(self.csv_path)

            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["screen_time_min"] = pd.to_numeric(
                df["screen_time_min"],
                errors="coerce"
            )

            df = df.dropna(
                subset=["user_id", "date", "app_name", "screen_time_min"]
            )

            df["user_id"] = df["user_id"].astype(str)
            df["app_name"] = df["app_name"].astype(str)

            df = df.sort_values(
                by=["user_id", "app_name", "date"]
            )

            return df
        except Exception:
            return empty_df

    def get_user_app_usage(self, df, user_id, app_name):
        """
        Returns usage history for one user and one app, sorted by date.
        """

        user_id = str(user_id)
        app_name = str(app_name).lower()

        filtered_df = df[
            (df["user_id"] == user_id)
            & (df["app_name"].str.lower() == app_name)
        ]

        filtered_df = filtered_df.sort_values("date")

        return filtered_df["screen_time_min"].tolist()

    def get_user_daily_total_usage(self, df, user_id):
        """
        Sums all app usage per day for one user, sorted by date.

        Returns daily totals rather than per-app values because the
        addiction trajectory is better captured at the whole-device level.
        """

        user_id = str(user_id)

        user_df = df[df["user_id"] == user_id]

        daily_usage = (
            user_df
            .groupby("date")["screen_time_min"]
            .sum()
            .reset_index()
            .sort_values("date")
        )

        return daily_usage["screen_time_min"].tolist()

    def get_user_apps(self, df, user_id):
        user_id = str(user_id)

        user_df = df[df["user_id"] == user_id]

        return sorted(user_df["app_name"].dropna().unique().tolist())

    def get_all_users(self, df):
        return sorted(df["user_id"].dropna().unique().tolist())

    def get_all_apps(self, df):
        return sorted(df["app_name"].dropna().unique().tolist())