# NOTE: This module is superseded by the calibration logic inside
# StructuralTimerEngine.get_calibration_status(). It is retained here
# for reference only and is not imported anywhere in the active codebase.


def get_calibration_status(user_usage_history, min_days=10):
    """
    user_usage_history: list of daily usage values
    returns calibration status and baseline info
    """

    days_available = len(user_usage_history)

    if days_available < min_days:
        return {
            "mode": "CALIBRATION",
            "days_available": days_available,
            "days_required": min_days,
            "message": f"Collecting baseline data. {min_days - days_available} more days needed."
        }

    baseline_usage = sum(user_usage_history[:min_days]) / min_days

    return {
        "mode": "ACTIVE",
        "days_available": days_available,
        "days_required": min_days,
        "baseline_usage": baseline_usage,
        "message": "Calibration complete. Timer engine can be activated."
    }