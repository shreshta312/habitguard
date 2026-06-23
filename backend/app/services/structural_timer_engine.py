class StructuralTimerEngine:
    """
    Research-based timer engine inspired by the Digital Addiction paper.

    Important:
    - Input usage_history is in minutes.
    - Structural calculations are done in hours.
    - Output timer is converted back to minutes.
    """

    def __init__(
        self,
        rho_paper=0.299,
        eta=-2.68,
        zeta=3.08,
        gamma=1.09,
        price=0,
        paper_period_days=21,
        min_timer_minutes=10,
        max_timer_minutes=180
    ):
        self.rho_paper = rho_paper
        self.rho_daily = rho_paper ** (1 / paper_period_days)

        self.eta = eta
        self.zeta = zeta
        self.gamma = gamma
        self.price = price

        self.min_timer_minutes = min_timer_minutes
        self.max_timer_minutes = max_timer_minutes

    def minutes_to_hours(self, usage_history):
        return [usage / 60 for usage in usage_history]

    def calculate_habit_stock_history(self, usage_history_hours):
        """
        Computes habit stock using the paper rho.

        We use rho_paper here because the structural equations are based on
        the paper's model scale, not the daily-decay transformed rho.
        """

        stock = 0.0
        stock_history = []

        for usage in usage_history_hours:
            stock = self.rho_paper * (stock + usage)
            stock_history.append(round(stock, 4))

        return stock_history

    def calculate_baseline_usage(self, usage_history_hours, calibration_days=7):
        if len(usage_history_hours) == 0:
            return 0.0

        calibration_window = usage_history_hours[:calibration_days]

        return sum(calibration_window) / len(calibration_window)

    def calculate_xi_user(self, baseline_usage_hours):
        """
        xi_i = p - gamma + x_i1 * (-eta - (zeta*rho)/(1-rho))

        Uses rho_paper, not rho_daily.
        """

        xi = (
            self.price
            - self.gamma
            + baseline_usage_hours
            * (
                -self.eta
                - ((self.zeta * self.rho_paper) / (1 - self.rho_paper))
            )
        )

        return xi

    def predict_natural_usage_hours(self, habit_stock, xi_user):
        """
        x_actual = (zeta*s + xi - p + gamma) / (-eta)
        """

        x_actual = (
            self.zeta * habit_stock
            + xi_user
            - self.price
            + self.gamma
        ) / (-self.eta)

        return max(x_actual, 0)

    def recommend_target_usage_hours(self, habit_stock, xi_user):
        """
        x_target = (zeta*s + xi - p) / (-eta)
        """

        x_target = (
            self.zeta * habit_stock
            + xi_user
            - self.price
        ) / (-self.eta)

        return max(x_target, 0)

    def clamp_timer_minutes(self, timer_minutes):
        if timer_minutes < self.min_timer_minutes:
            return self.min_timer_minutes

        if timer_minutes > self.max_timer_minutes:
            return self.max_timer_minutes

        return timer_minutes

    def get_structural_timer_summary(self, usage_history_minutes):
        if len(usage_history_minutes) == 0:
            return {
                "error": "No usage history available"
            }

        usage_history_hours = self.minutes_to_hours(usage_history_minutes)

        habit_stock_history = self.calculate_habit_stock_history(
            usage_history_hours
        )

        current_habit_stock = habit_stock_history[-1]

        baseline_usage_hours = self.calculate_baseline_usage(
            usage_history_hours
        )

        xi_user = self.calculate_xi_user(baseline_usage_hours)

        predicted_natural_usage_hours = self.predict_natural_usage_hours(
            current_habit_stock,
            xi_user
        )

        recommended_target_usage_hours = self.recommend_target_usage_hours(
            current_habit_stock,
            xi_user
        )

        predicted_natural_usage_minutes = predicted_natural_usage_hours * 60
        recommended_target_usage_minutes = recommended_target_usage_hours * 60

        recommended_timer_minutes = self.clamp_timer_minutes(
            recommended_target_usage_minutes
        )

        temptation_gap_minutes = (
            predicted_natural_usage_minutes
            - recommended_target_usage_minutes
        )

        return {
            "timer_basis": "structural_model",
            "rho_paper": round(self.rho_paper, 4),
            "rho_daily_reference": round(self.rho_daily, 4),
            "eta": self.eta,
            "zeta": self.zeta,
            "gamma": self.gamma,
            "price": self.price,

            "baseline_usage_hours": round(baseline_usage_hours, 4),
            "baseline_usage_minutes": round(baseline_usage_hours * 60, 2),

            "xi_user": round(xi_user, 4),

            "habit_stock_history": habit_stock_history,
            "current_habit_stock": round(current_habit_stock, 4),

            "predicted_natural_usage_minutes": round(
                predicted_natural_usage_minutes,
                2
            ),
            "recommended_target_usage_minutes": round(
                recommended_target_usage_minutes,
                2
            ),
            "recommended_timer_minutes": round(
                recommended_timer_minutes,
                2
            ),
            "temptation_gap_minutes": round(
                temptation_gap_minutes,
                2
            ),

            "interpretation": (
                "Predicted natural usage includes temptation. "
                "Recommended timer removes the temptation component. "
                "Paper parameters are used as structural priors."
            )
        }