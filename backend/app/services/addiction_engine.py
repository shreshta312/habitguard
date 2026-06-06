class AddictionEngine:
    """
    Computes addiction stock using the formula:

        s(t+1) = rho * (s(t) + x(t))

    where:
    s(t) = current addiction stock
    x(t) = usage at time t
    rho  = habit formation strength
    """

    def __init__(self, rho=0.299):
        self.rho = rho

    def calculate_scores(self, usage_history):
        """
        usage_history: list of daily usage values in minutes

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
        """

        if score < 10:
            return "LOW"
        elif score < 25:
            return "MODERATE"
        elif score < 40:
            return "HIGH"
        else:
            return "SEVERE"