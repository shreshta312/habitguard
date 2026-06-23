class StructuralTimerEngine:
    """
    User-calibrated timer engine inspired by the Digital Addiction paper.

    Important:
    - Input usage_history is in minutes.
    - Structural calculations are done in hours.
    - Output timer is converted back to minutes.
    - First calibration_days are used only to build user baseline.
    """

    def __init__(
        self,
        rho_paper=0.299,
        eta=-2.68,
        zeta=3.08,
        gamma=1.09,
        price=0,
        paper_period_days=21,
        calibration_days=10,
        min_timer_minutes=10,
        max_timer_minutes=180
    ):
        self.rho_paper = rho_paper
        self.rho_daily_reference = rho_paper ** (1 / paper_period_days)

        self.eta = eta
        self.zeta = zeta
        self.gamma = gamma
        self.price = price

        self.calibration_days = calibration_days
        self.min_timer_minutes = min_timer_minutes
        self.max_timer_minutes = max_timer_minutes

    def minutes_to_hours(self, usage_history_minutes):
        return [usage / 60 for usage in usage_history_minutes]

    def calculate_rho_user(self, usage_history_hours):
        """
        Estimate user-specific persistence using lag-1 autocorrelation.

        This is a behavioral persistence proxy, not the paper's exact
        experimentally estimated rho.
        """

        if len(usage_history_hours) < 3:
            return self.rho_daily_reference

        x = usage_history_hours[:-1]
        y = usage_history_hours[1:]

        mean_x = sum(x) / len(x)
        mean_y = sum(y) / len(y)

        numerator = sum(
            (x[i] - mean_x) * (y[i] - mean_y)
            for i in range(len(x))
        )

        denominator_x = sum((value - mean_x) ** 2 for value in x)
        denominator_y = sum((value - mean_y) ** 2 for value in y)

        if denominator_x == 0 or denominator_y == 0:
            return self.rho_daily_reference

        rho = numerator / ((denominator_x * denominator_y) ** 0.5)

        # Keep habit persistence stable.
        rho = max(0.05, min(0.95, rho))

        return rho

    def calculate_habit_stock_history(self, usage_history_hours, rho_user):
        """
        Computes user-calibrated habit stock.

        S_t = rho_user * (S_{t-1} + x_{t-1})
        """

        stock = 0.0
        stock_history = []

        for usage in usage_history_hours:
            stock = rho_user * (stock + usage)
            stock_history.append(round(stock, 4))

        return stock_history

    def calculate_baseline_usage(self, usage_history_hours):
        """
        Baseline is calculated from the first calibration_days.
        """

        calibration_window = usage_history_hours[:self.calibration_days]

        if len(calibration_window) == 0:
            return 0.0

        return sum(calibration_window) / len(calibration_window)

    def calculate_recent_usage(self, usage_history_hours, recent_days=3):
        """
        Recent usage captures current behavior after baseline.
        """

        recent_window = usage_history_hours[-recent_days:]

        if len(recent_window) == 0:
            return 0.0

        return sum(recent_window) / len(recent_window)

    def calculate_xi_user(self, baseline_usage_hours, rho_user):
        """
        Adapted xi calibration:

        xi_i = p - gamma + x_baseline * (-eta - (zeta*rho)/(1-rho))

        Here rho is user-calibrated persistence.
        Eta, zeta, and gamma are still paper priors for now.
        """

        denominator_adjustment = (
            -self.eta
            - ((self.zeta * rho_user) / (1 - rho_user))
        )

        xi = (
            self.price
            - self.gamma
            + baseline_usage_hours * denominator_adjustment
        )

        return xi

    def predict_natural_usage_hours(self, habit_stock, xi_user):
        """
        Model-implied natural usage:

        x_actual = (zeta*S + xi - p + gamma) / (-eta)
        """

        x_actual = (
            self.zeta * habit_stock
            + xi_user
            - self.price
            + self.gamma
        ) / (-self.eta)

        return x_actual

    def recommend_target_usage_hours(self, habit_stock, xi_user):
        """
        Model-implied self-control target usage:

        x_target = (zeta*S + xi - p) / (-eta)
        """

        x_target = (
            self.zeta * habit_stock
            + xi_user
            - self.price
        ) / (-self.eta)

        return x_target

    def clamp_timer_minutes(self, timer_minutes):
        if timer_minutes < self.min_timer_minutes:
            return self.min_timer_minutes

        if timer_minutes > self.max_timer_minutes:
            return self.max_timer_minutes

        return timer_minutes

    def calculate_safe_timer_minutes(
        self,
        baseline_usage_minutes,
        recent_usage_minutes,
        habit_stock,
        temptation_gap_minutes
    ):
        """
        Safe timer control rule.

        Important distinction:
        - recommended_target_usage_minutes is the structural model output.
        - recommended_timer_minutes is the actual intervention timer.

        The timer should not become more relaxed simply because habit stock is high.
        High habit stock should make the intervention stricter, not looser.
        """

        overuse_gap = max(0, recent_usage_minutes - baseline_usage_minutes)

        baseline_hours = baseline_usage_minutes / 60

        normalized_habit_pressure = habit_stock / (baseline_hours + 1)
        normalized_habit_pressure = min(normalized_habit_pressure, 2.0)

        reduction = (
            0.35 * overuse_gap
            + 0.15 * temptation_gap_minutes
            + 0.10 * normalized_habit_pressure * baseline_usage_minutes
        )

        safe_timer = baseline_usage_minutes - reduction

        return self.clamp_timer_minutes(safe_timer)

    def get_calibration_status(self, usage_history_minutes):
        days_available = len(usage_history_minutes)

        if days_available < self.calibration_days:
            return {
                "mode": "CALIBRATION",
                "days_available": days_available,
                "days_required": self.calibration_days,
                "days_remaining": self.calibration_days - days_available,
                "timer_active": False,
                "message": (
                    f"Collecting baseline data. "
                    f"{self.calibration_days - days_available} more days needed."
                )
            }

        return {
            "mode": "ACTIVE",
            "days_available": days_available,
            "days_required": self.calibration_days,
            "timer_active": True,
            "message": "Calibration complete. Timer engine is active."
        }

    def get_structural_timer_summary(self, usage_history_minutes):
        if len(usage_history_minutes) == 0:
            return {
                "error": "No usage history available"
            }

        calibration_status = self.get_calibration_status(usage_history_minutes)

        if calibration_status["mode"] == "CALIBRATION":
            return {
                "timer_basis": "user_calibration",
                **calibration_status
            }

        usage_history_hours = self.minutes_to_hours(usage_history_minutes)

        baseline_usage_hours = self.calculate_baseline_usage(
            usage_history_hours
        )

        recent_usage_hours = self.calculate_recent_usage(
            usage_history_hours
        )

        rho_user = self.calculate_rho_user(usage_history_hours)

        habit_stock_history = self.calculate_habit_stock_history(
            usage_history_hours,
            rho_user
        )

        current_habit_stock = habit_stock_history[-1]

        xi_user = self.calculate_xi_user(
            baseline_usage_hours,
            rho_user
        )

        predicted_natural_usage_hours_raw = self.predict_natural_usage_hours(
            current_habit_stock,
            xi_user
        )

        recommended_target_usage_hours_raw = self.recommend_target_usage_hours(
            current_habit_stock,
            xi_user
        )

        natural_was_negative = predicted_natural_usage_hours_raw < 0
        target_was_negative = recommended_target_usage_hours_raw < 0

        predicted_natural_usage_hours = max(
            predicted_natural_usage_hours_raw,
            0
        )

        recommended_target_usage_hours = max(
            recommended_target_usage_hours_raw,
            0
        )

        predicted_natural_usage_minutes = predicted_natural_usage_hours * 60
        recommended_target_usage_minutes = recommended_target_usage_hours * 60

        temptation_gap_minutes = max(
            0,
            predicted_natural_usage_minutes - recommended_target_usage_minutes
        )

        baseline_usage_minutes = baseline_usage_hours * 60
        recent_usage_minutes = recent_usage_hours * 60

        overuse_gap_minutes = max(
            0,
            recent_usage_minutes - baseline_usage_minutes
        )

        recommended_timer_minutes = self.calculate_safe_timer_minutes(
            baseline_usage_minutes=baseline_usage_minutes,
            recent_usage_minutes=recent_usage_minutes,
            habit_stock=current_habit_stock,
            temptation_gap_minutes=temptation_gap_minutes
        )

        return {
            "timer_basis": "user_calibrated_structural_model",
            **calibration_status,

            "rho_paper_reference": round(self.rho_paper, 4),
            "rho_daily_reference": round(self.rho_daily_reference, 4),
            "rho_user": round(rho_user, 4),

            "eta_prior": self.eta,
            "zeta_prior": self.zeta,
            "gamma_prior": self.gamma,
            "price": self.price,

            "baseline_usage_hours": round(baseline_usage_hours, 4),
            "baseline_usage_minutes": round(baseline_usage_minutes, 2),

            "recent_usage_minutes": round(recent_usage_minutes, 2),
            "overuse_gap_minutes": round(overuse_gap_minutes, 2),

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

            "natural_was_negative": natural_was_negative,
            "target_was_negative": target_was_negative,

            "interpretation": (
                "The first calibration window is used to estimate the user's "
                "baseline. User-specific rho is estimated from usage persistence. "
                "The structural model produces natural usage and target usage. "
                "The final recommended timer uses a safe bounded control rule so "
                "that high habit stock makes the timer stricter, not more relaxed. "
                "Eta, zeta, and gamma are still priors until intention and "
                "intervention-response data are collected."
            )
        }