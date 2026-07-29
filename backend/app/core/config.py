import os
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
env_db = os.environ.get("HABITGUARD_DB_PATH")
DB_PATH = Path(env_db) if env_db else (DATA_DIR / "habitguard.db")

# Data Provenance Sources
SOURCE_USER_SELECTED = "USER_SELECTED"
SOURCE_DIRECTLY_MEASURED = "DIRECTLY_MEASURED"
SOURCE_PERSONALLY_LEARNED = "PERSONALLY_LEARNED"
SOURCE_VERSIONED_DEFAULT = "VERSIONED_DEFAULT"
SOURCE_SAFETY_BOUND = "SAFETY_BOUND"
SOURCE_PAPER_EQUATION = "PAPER_EQUATION"
SOURCE_PAPER_POPULATION_DEFAULT = "PAPER_POPULATION_DEFAULT"
SOURCE_HABITGUARD_PROPOSED = "HABITGUARD_PROPOSED"

# Centralized Timing & Resumption Constants
SESSION_RESUME_GAP_MINUTES = 5.0
INTENT_RESUME_GAP_MINUTES = 5.0
DEFAULT_NOTIFICATION_COOLDOWN_MINUTES = 15.0
DEFAULT_OVERLAY_COOLDOWN_MINUTES = 20.0

# Configuration Version
CONFIG_VERSION = "2.0.0"

# Centralized Parameters with Provenance
SYSTEM_PARAMETERS: Dict[str, Dict[str, Any]] = {
    "session_resume_gap_minutes": {
        "value": 5.0,
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Centralized threshold for session pause, resumption and expiry across domain switches"
    },
    "session_grace_period_minutes": {
        "value": 5.0,
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Initial grace period before overrun is counted as unplanned"
    },
    "idle_detection_interval_seconds": {
        "value": 60.0,
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Chrome idle state detection interval"
    },
    # Temptation Weights: w1*O + w2*R + w3*L + w4*H + w5*K + w6*W + w7*Q
    "temptation_weights": {
        "value": {
            "w1_overrun": 0.25,
            "w2_reopen": 0.15,
            "w3_uninterrupted": 0.15,
            "w4_habitual": 0.20,
            "w5_context": 0.10,
            "w6_switching": 0.10,
            "w7_historical_overrun": 0.05
        },
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Weights for temptation component estimation"
    },
    "utility_parameters": {
        "value": {
            "necessity_weight": 0.4,
            "completion_weight": 0.4,
            "under_allocation_penalty": 0.2,
            "minimum_required_utility": 0.35,
            "typical_sufficient_duration_default": 25.0
        },
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Parameters for task completion utility estimation"
    },
    "optimization_coefficients": {
        "value": {
            "alpha_usage_cost": 0.25,
            "beta_temptation_cost": 0.30,
            "lambda_plan_deviation": 0.20,
            "kappa_intervention_burden": 0.10,
            "gamma_reduction_goal": 0.15,
            "session_scale_minutes": 60.0,
            "grid_search_step_minutes": 1.0,
            "safe_session_maximum_minutes": 180.0
        },
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Weights and bounds for session optimization objective function"
    },
    "learning_rates": {
        "value": {
            "default_learning_rate": 0.15,
            "min_sample_count_for_learned": 5
        },
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Learning rates for exponential moving average personal adaptation"
    },
    "decision_cooldown_minutes": {
        "value": 15.0,
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Minimum cooldown between interventions"
    },
    "cross_domain_parameters": {
        "value": {
            "meaningful_change_minutes": 10.0,
            "substitution_offset_threshold": 0.50,
            "min_days_for_detection": 7,
            "cold_start_allowance_minutes": 120.0,
            "safety_floor_minutes": 15.0,
            "default_reduction_percent": 20.0,
            "min_samples_for_learned": 5
        },
        "source": SOURCE_VERSIONED_DEFAULT,
        "description": "Thresholds for cross-domain allowance calculation and site-substitution detection"
    }
}
