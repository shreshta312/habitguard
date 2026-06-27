import pandas as pd


class DatasetService:
    """
    Loads cleaned screen-time data and returns usage history
    for selected users and apps.
    """

    def __init__(self, csv_path):
        self.csv_path = csv_path

    def load_data(self):
        df = pd.read_csv(self.csv_path)

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["screen_time_min"] = pd.to_numeric(
            df["screen_time_min"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["user_id", "date", "app_name", "screen_time_min"]
        )

        df = df.sort_values(
            by=["user_id", "app_name", "date"]
        )

        return df

    def get_user_app_usage(self, df, user_id, app_name):
        """
        Returns usage history for one user and one app, sorted by date.
        """

        filtered_df = df[
            (df["user_id"].astype(str) == str(user_id))
            & (df["app_name"].str.lower() == app_name.lower())
        ]

        filtered_df = filtered_df.sort_values("date")

        return filtered_df["screen_time_min"].tolist()

    def get_user_daily_total_usage(self, df, user_id):
        """
        Sums all app usage per day for one user, sorted by date.

        Returns daily totals rather than per-app values because the
        addiction trajectory is better captured at the whole-device level.
        """

        user_df = df[df["user_id"].astype(str) == str(user_id)]

        daily_usage = (
            user_df
            .groupby("date")["screen_time_min"]
            .sum()
            .reset_index()
            .sort_values("date")
        )

        return daily_usage["screen_time_min"].tolist()

    def get_user_apps(self, df, user_id):
        user_df = df[df["user_id"].astype(str) == str(user_id)]

        return sorted(user_df["app_name"].dropna().unique().tolist())

    def get_all_users(self, df):
        return sorted(df["user_id"].dropna().unique().tolist())

    def get_all_apps(self, df):
        return sorted(df["app_name"].dropna().unique().tolist())