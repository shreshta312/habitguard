class DynamicLimitEngine:
    """
    Calculates adaptive daily limits based on addiction score.

    Higher addiction score = stricter recommended limit.

    base_limit_minutes=120 is a reasonable starting point for general
    screen-time guidance (2 hours/day). It is user-configurable at
    init time so the Chrome extension can pass a personalized value
    once user preferences are collected.

    Friction thresholds (70%, 85%, 100%, 115%, 130%) define a
    graduated escalation ladder from passive awareness to active
    cooldown, matching the intervention intensity levels expected
    by the Chrome extension.
    """

    def __init__(self, base_limit_minutes=120, minimum_limit_minutes=20):
        self.base_limit_minutes = base_limit_minutes
        self.minimum_limit_minutes = minimum_limit_minutes

    def recommend_limit(self, addiction_score):
        """
        Returns recommended daily limit in minutes.

        Reduction factors by score band:
        < 10  : no reduction (baseline)
        10-25 : 15% reduction
        25-40 : 30% reduction
        40-60 : 40% reduction
        60+   : 50% reduction
        """

        if addiction_score < 10:
            limit = self.base_limit_minutes

        elif addiction_score < 25:
            limit = self.base_limit_minutes * 0.85

        elif addiction_score < 40:
            limit = self.base_limit_minutes * 0.70

        elif addiction_score < 60:
            limit = self.base_limit_minutes * 0.60

        else:
            limit = self.base_limit_minutes * 0.50

        return max(int(limit), self.minimum_limit_minutes)

    def friction_action(self, usage_today, recommended_limit):
        """
        Decides what action the Chrome extension should show.
        """

        if recommended_limit <= 0:
            raise ValueError("Recommended limit must be positive")

        usage_percent = (usage_today / recommended_limit) * 100

        if usage_percent < 70:
            return {
                "level": "NONE",
                "message": "Usage is within safe range.",
                "cooldown_seconds": 0
            }

        elif usage_percent < 85:
            return {
                "level": "SOFT_WARNING",
                "message": "You are approaching today's recommended limit.",
                "cooldown_seconds": 0
            }

        elif usage_percent < 100:
            return {
                "level": "WARNING",
                "message": "You are very close to today's recommended limit.",
                "cooldown_seconds": 0
            }

        elif usage_percent < 115:
            return {
                "level": "LIGHT_COOLDOWN",
                "message": "You crossed today's recommended limit. Take a short pause.",
                "cooldown_seconds": 5
            }

        elif usage_percent < 130:
            return {
                "level": "MEDIUM_COOLDOWN",
                "message": "Usage is significantly above today's recommended limit.",
                "cooldown_seconds": 15
            }

        else:
            return {
                "level": "STRONG_COOLDOWN",
                "message": "Heavy usage detected. Pause before continuing.",
                "cooldown_seconds": 30
            }