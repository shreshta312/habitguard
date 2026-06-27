class AddictionEngine:
    """
    Computes addiction stock using the formula:

        s(t+1) = rho * (s(t) + x(t))

    where:
    s(t) = current addiction stock
    x(t) = usage at time t (in minutes)
    rho  = habit formation strength

    Note on rho:
    The paper reports rho = 0.299 over a 21-day experimental period.
    This engine receives daily usage values, so rho here is used as a
    heuristic signal for friction and limit decisions — not as a
    structurally grounded daily estimate. For structurally grounded
    daily habit stock, see StructuralTimerEngine which converts rho
    to a daily reference and further personalizes it per user.

    Score level thresholds (LOW / MODERATE / HIGH / SEVERE) are
    calibrated against observed score distributions on the Kaggle
    screen-time dataset used in this project. They are not derived
    from the paper.
    """

    def __init__(self, rho=0.299):
        self.rho = rho

    def calculate_scores(self, usage_history):
        """
        usage_history: list of daily usage values in minutes.

        Example:
        [45, 52, 48, 61, 70]
        """

        scores = []
        stock = 0.0

        for usage in usage_history:
            if usage < 0:
                raise ValueError("Usage cannot be negative")

            stock = self.rho * (stock + usage)
            scores.append(round(stock, 2))

        return scores

    def current_score(self, usage_history):
        """
        Returns the latest addiction score.
        """

        if len(usage_history) == 0:
            return 0.0

        scores = self.calculate_scores(usage_history)
        return scores[-1]

    def score_level(self, score):
        """
        Converts numerical addiction score into readable level.

        Thresholds calibrated against score distributions observed
        on the project dataset. Not derived from paper parameters.
        """

        if score < 10:
            return "LOW"
        elif score < 25:
            return "MODERATE"
        elif score < 40:
            return "HIGH"
        else:
            return "SEVERE"