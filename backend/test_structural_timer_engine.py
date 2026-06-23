from app.services.structural_timer_engine import StructuralTimerEngine


def print_summary(title, summary):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

    for key, value in summary.items():
        if key == "habit_stock_history":
            print(f"{key}: {value[-5:] if value else []}  # last 5 values")
        else:
            print(f"{key}: {value}")


def test_calibration_mode():
    engine = StructuralTimerEngine()

    short_history = [30, 40, 35, 50, 45]

    summary = engine.get_structural_timer_summary(short_history)

    assert summary["mode"] == "CALIBRATION"
    assert summary["timer_active"] is False
    assert summary["days_available"] == 5
    assert summary["days_required"] == 10
    assert summary["days_remaining"] == 5
    assert "recommended_timer_minutes" not in summary

    print_summary("TEST 1: CALIBRATION MODE", summary)


def test_active_mode_normal_usage():
    engine = StructuralTimerEngine()

    normal_history = [
        30, 35, 40, 32, 38,
        41, 36, 39, 42, 37,
        45, 48
    ]

    summary = engine.get_structural_timer_summary(normal_history)

    assert summary["mode"] == "ACTIVE"
    assert summary["timer_active"] is True
    assert summary["days_available"] == 12
    assert "rho_user" in summary
    assert "baseline_usage_minutes" in summary
    assert "recommended_timer_minutes" in summary
    assert summary["recommended_timer_minutes"] >= engine.min_timer_minutes
    assert summary["recommended_timer_minutes"] <= engine.max_timer_minutes

    print_summary("TEST 2: ACTIVE MODE - NORMAL USAGE", summary)


def test_active_mode_heavy_usage():
    engine = StructuralTimerEngine()

    heavy_history = [
        30, 35, 40, 32, 38,
        41, 36, 39, 42, 37,
        70, 85, 95
    ]

    summary = engine.get_structural_timer_summary(heavy_history)

    assert summary["mode"] == "ACTIVE"
    assert summary["timer_active"] is True
    assert summary["days_available"] == 13
    assert "overuse_gap_minutes" in summary
    assert summary["overuse_gap_minutes"] > 0
    assert "recommended_timer_minutes" in summary
    assert summary["recommended_timer_minutes"] >= engine.min_timer_minutes
    assert summary["recommended_timer_minutes"] <= engine.max_timer_minutes

    print_summary("TEST 3: ACTIVE MODE - HEAVY RECENT USAGE", summary)


def test_heavy_usage_timer_not_higher_than_normal():
    engine = StructuralTimerEngine()

    normal_history = [
        30, 35, 40, 32, 38,
        41, 36, 39, 42, 37,
        45, 48
    ]

    heavy_history = [
        30, 35, 40, 32, 38,
        41, 36, 39, 42, 37,
        70, 85, 95
    ]

    normal_summary = engine.get_structural_timer_summary(normal_history)
    heavy_summary = engine.get_structural_timer_summary(heavy_history)

    assert heavy_summary["recommended_timer_minutes"] <= normal_summary["recommended_timer_minutes"]

    print("\n" + "=" * 60)
    print("TEST 4: TIMER COMPARISON")
    print("=" * 60)
    print(f"Normal timer: {normal_summary['recommended_timer_minutes']} minutes")
    print(f"Heavy usage timer: {heavy_summary['recommended_timer_minutes']} minutes")


if __name__ == "__main__":
    test_calibration_mode()
    test_active_mode_normal_usage()
    test_active_mode_heavy_usage()
    test_heavy_usage_timer_not_higher_than_normal()

    print("\nAll structural timer engine tests passed.")