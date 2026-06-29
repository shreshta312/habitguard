import logging

logger = logging.getLogger(__name__)


class StructuralTimerEngine:
    """
    User-calibrated timer engine grounded in the Digital Addiction paper
    (Allcott, Gentzkow & Song, 2022).

    Parameter personalization status:
    - rho_user   : estimated from user behavior via lag-1 autocorrelation.
    - xi_user    : derived from user baseline + rho_user.
    - baseline   : computed from the first calibration_days of usage.
    - habit stock: computed from user data using rho_user.
    - eta, zeta, gamma : still paper priors. These require intervention-
                         response data (eta), longer usage history (zeta),
                         and behavioral signals like timer crossings and
                         session restarts (gamma) before they can be
                         personalized. Proxy estimation will be added in
                         a later stage once Chrome extension data is live.

    Unit convention:
    - Input usage_history is in minutes.
    - All structural calculations are done in hours.
    - Output timer is converted back to minutes.

    Timer control rule:
    - recommended_target_usage_minutes is the structural model output.
    - recommended_timer_minutes is the actual intervention timer shown
      to the user. These are kept separate because high habit stock
      should make the timer stricter, not more relaxed.
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

        # rho_paper is a 21-day aggregate from the paper's experiment.
        # Converting to a daily reference for internal comparison only.
        # rho_user replaces this in all actual calculations.
        self.rho_daily_reference = rho_paper ** (1 / paper_period_days)

        # eta, zeta, gamma are paper priors.
        # eta   : marginal utility of usage. Requires intervention-response
        #         data to personalize (how usage changes under timer pressure).
        # zeta  : habit stock influence on current usage. Can be approximated
        #         from longer passive history in a future stage.
        # gamma : temptation / self-control gap. Requires behavioral signals
        #         (timer crossings, session restarts) from Chrome extension.
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
        Estimates user-specific habit persistence via lag-1 autocorrelation.

        Asks: does today's usage predict tomorrow's usage?
        This is a behavioral proxy, not the paper's experimentally
        estimated rho. Clamped to [0.05, 0.95] to keep persistence stable.
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

        rho = max(0.05, min(0.95, rho))

        return rho

    def calculate_habit_stock_history(self, usage_history_hours, rho_user):
        """
        Computes user-calibrated habit stock history.

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
        Baseline is the mean of the first calibration_days of usage.
        """

        calibration_window = usage_history_hours[:self.calibration_days]

        if len(calibration_window) == 0:
            return 0.0

        return sum(calibration_window) / len(calibration_window)

    def calculate_recent_usage(self, usage_history_hours, recent_days=3):
        """
        Recent usage is the mean of the last recent_days of usage.
        Captures current behavior after baseline has been established.
        """

        recent_window = usage_history_hours[-recent_days:]

        if len(recent_window) == 0:
            return 0.0

        return sum(recent_window) / len(recent_window)

    def calculate_xi_user(self, baseline_usage_hours, rho_user):
        """
        Computes user-calibrated xi, the preference parameter from the paper.

        Derived by inverting the paper's steady-state equation at the
        user's observed baseline usage:

            xi_i = p - gamma + x_baseline * (-eta - (zeta * rho) / (1 - rho))

        rho is user-estimated. eta, zeta, gamma remain paper priors.
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
        Model-implied natural (unconstrained) usage given current habit stock.

        x_actual = (zeta * S + xi - p + gamma) / (-eta)

        Includes gamma because this is usage without self-control applied.
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
        Model-implied self-control target usage given current habit stock.

        x_target = (zeta * S + xi - p) / (-eta)

        Excludes gamma because this is usage with self-control applied.
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
        Computes the final intervention timer using a bounded control rule.

        The timer is derived by reducing from baseline proportionally to:
        - overuse_gap         (weight 0.35): how far recent usage exceeds
                               baseline. Largest weight because it is the
                               most direct signal of current over-usage.
        - temptation_gap      (weight 0.15): structural gap between natural
                               and target usage. Reflects paper-implied
                               self-control pressure.
        - habit_stock pressure (weight 0.10): normalized habit stock scaled
                               by baseline. Ensures that high accumulated
                               habit stock tightens the timer rather than
                               relaxing it.

        Result is clamped to [min_timer_minutes, max_timer_minutes].
        """

        overuse_gap = max(0, recent_usage_minutes - baseline_usage_minutes)

        baseline_hours = baseline_usage_minutes / 60

        # Normalize habit stock relative to baseline to make it scale-invariant.
        # Capped at 2.0 to prevent extreme habit stock from dominating.
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

        baseline_usage_hours = self.calculate_baseline_usage(usage_history_hours)
        recent_usage_hours = self.calculate_recent_usage(usage_history_hours)
        rho_user = self.calculate_rho_user(usage_history_hours)

        habit_stock_history = self.calculate_habit_stock_history(
            usage_history_hours,
            rho_user
        )

        current_habit_stock = habit_stock_history[-1]

        xi_user = self.calculate_xi_user(baseline_usage_hours, rho_user)

        predicted_natural_usage_hours_raw = self.predict_natural_usage_hours(
            current_habit_stock,
            xi_user
        )

        recommended_target_usage_hours_raw = self.recommend_target_usage_hours(
            current_habit_stock,
            xi_user
        )

        # Track whether predictions went negative before clamping.
        # Frequent negatives signal the model may be miscalibrated for
        # this user's usage range and should be monitored.
        natural_was_negative = predicted_natural_usage_hours_raw < 0
        target_was_negative = recommended_target_usage_hours_raw < 0

        if natural_was_negative:
            logger.warning(
                "StructuralTimerEngine: predicted_natural_usage went negative "
                "(%.4f hrs) before clamping. rho_user=%.4f, xi_user=%.4f, "
                "habit_stock=%.4f. Timer output may be distorted.",
                predicted_natural_usage_hours_raw,
                rho_user,
                xi_user,
                current_habit_stock
            )

        if target_was_negative:
            logger.warning(
                "StructuralTimerEngine: recommended_target_usage went negative "
                "(%.4f hrs) before clamping. rho_user=%.4f, xi_user=%.4f, "
                "habit_stock=%.4f. Timer output may be distorted.",
                recommended_target_usage_hours_raw,
                rho_user,
                xi_user,
                current_habit_stock
            )

        predicted_natural_usage_hours = max(predicted_natural_usage_hours_raw, 0)
        recommended_target_usage_hours = max(recommended_target_usage_hours_raw, 0)

        predicted_natural_usage_minutes = predicted_natural_usage_hours * 60
        recommended_target_usage_minutes = recommended_target_usage_hours * 60

        temptation_gap_minutes = max(
            0,
            predicted_natural_usage_minutes - recommended_target_usage_minutes
        )

        baseline_usage_minutes = baseline_usage_hours * 60
        recent_usage_minutes = recent_usage_hours * 60

        overuse_gap_minutes = max(0, recent_usage_minutes - baseline_usage_minutes)

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

            "predicted_natural_usage_minutes": round(predicted_natural_usage_minutes, 2),
            "recommended_target_usage_minutes": round(recommended_target_usage_minutes, 2),
            "recommended_timer_minutes": round(recommended_timer_minutes, 2),
            "temptation_gap_minutes": round(temptation_gap_minutes, 2),

            "natural_was_negative": natural_was_negative,
            "target_was_negative": target_was_negative,

            "interpretation": (
                "The first calibration window is used to estimate the user's "
                "baseline. rho_user is estimated from lag-1 autocorrelation of "
                "usage history. xi_user is derived from baseline and rho_user. "
                "eta, zeta, and gamma remain paper priors: eta requires "
                "intervention-response data, zeta can be approximated from longer "
                "passive history, gamma requires Chrome extension behavioral signals "
                "(timer crossings, session restarts). The final timer uses a safe "
                "bounded control rule so that high habit stock tightens the timer "
                "rather than relaxing it."
            )
        }