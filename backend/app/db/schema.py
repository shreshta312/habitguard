# DDL statements for canonical HabitGuard SQLite database

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_goals (
    user_id TEXT PRIMARY KEY,
    selected_domains_json TEXT NOT NULL,
    reduction_intensity TEXT NOT NULL DEFAULT 'moderate', -- gentle, moderate, strong, suggested
    target_reduction_percent REAL NOT NULL DEFAULT 20.0,
    status TEXT NOT NULL DEFAULT 'active',
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intent_episodes (
    episode_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    purpose TEXT NOT NULL, -- work_study, necessary, entertainment, habitual_browsing, unknown
    intended_minutes REAL,
    original_intended_minutes REAL,
    extension_minutes REAL NOT NULL DEFAULT 0.0,
    timer_mode TEXT NOT NULL DEFAULT 'planned', -- planned, no_timer
    remember_today INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active', -- active, expired, completed
    started_at_utc TEXT NOT NULL,
    last_activity_at_utc TEXT,
    last_focused_at_utc TEXT,
    unfocused_at_utc TEXT,
    ended_at_utc TEXT,
    expiry_reason TEXT,
    stop_reminders INTEGER NOT NULL DEFAULT 0,
    version TEXT NOT NULL DEFAULT '2.0.0',
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS technical_sessions (
    session_id TEXT PRIMARY KEY,
    episode_id TEXT,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    ended_at_utc TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    local_timezone TEXT NOT NULL DEFAULT 'UTC',
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES intent_episodes(episode_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS session_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_event_id TEXT UNIQUE NOT NULL,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    event_timestamp_utc TEXT NOT NULL,
    received_at_utc TEXT NOT NULL,
    event_type TEXT NOT NULL, -- focus_start, focus_heartbeat, focus_stop, idle_start, idle_stop
    focused_duration_ms INTEGER,
    tracking_version TEXT NOT NULL DEFAULT '2.0.0',
    FOREIGN KEY (session_id) REFERENCES technical_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    actual_focused_minutes REAL NOT NULL DEFAULT 0.0,
    planned_minutes REAL,
    unplanned_minutes REAL NOT NULL DEFAULT 0.0,
    unknown_minutes REAL NOT NULL DEFAULT 0.0,
    optimized_target REAL,
    user_action TEXT,
    task_completion INTEGER,
    time_sufficient INTEGER,
    intervention_delivered INTEGER NOT NULL DEFAULT 0,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES technical_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS optimization_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    input_snapshot_json TEXT NOT NULL,
    observed_baseline REAL NOT NULL,
    baseline_source TEXT NOT NULL,
    planned_minutes REAL,
    necessary_minimum REAL NOT NULL,
    minutes_used REAL NOT NULL,
    temptation_estimate REAL NOT NULL,
    temptation_confidence REAL NOT NULL,
    optimized_target REAL,
    recommended_remaining REAL,
    objective_value REAL,
    utility_retained REAL,
    constraints_satisfied INTEGER NOT NULL,
    binding_constraints_json TEXT,
    derivation_json TEXT,
    parameter_sources_json TEXT,
    solver_status TEXT NOT NULL,
    configuration_version TEXT NOT NULL,
    tracking_reliability REAL NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES technical_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS personal_parameters (
    user_id TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    context_key TEXT NOT NULL DEFAULT 'global',
    value REAL NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    sample_count INTEGER NOT NULL DEFAULT 1,
    version TEXT NOT NULL DEFAULT '2.0.0',
    updated_at_utc TEXT NOT NULL,
    PRIMARY KEY (user_id, parameter_name, context_key)
);

CREATE TABLE IF NOT EXISTS daily_usage_rollups (
    user_id TEXT NOT NULL,
    local_date TEXT NOT NULL,
    domain TEXT NOT NULL,
    focused_minutes REAL NOT NULL DEFAULT 0.0,
    planned_minutes REAL NOT NULL DEFAULT 0.0,
    unplanned_minutes REAL NOT NULL DEFAULT 0.0,
    unknown_minutes REAL NOT NULL DEFAULT 0.0,
    necessary_minutes REAL NOT NULL DEFAULT 0.0,
    reopen_count INTEGER NOT NULL DEFAULT 0,
    longest_uninterrupted_minutes REAL NOT NULL DEFAULT 0.0,
    cross_domain_switches INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, local_date, domain)
);

CREATE TABLE IF NOT EXISTS feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL, -- finish, extend_5, task_not_finished, dismiss, stop_reminders, change_plan, no_timer
    task_completion INTEGER,
    time_sufficient INTEGER,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES technical_sessions(session_id) ON DELETE CASCADE
);

-- Indexing for high-performance lookup
CREATE INDEX IF NOT EXISTS idx_activities_session ON session_activities(session_id);
CREATE INDEX IF NOT EXISTS idx_activities_user_domain ON session_activities(user_id, domain);
CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON session_activities(event_timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_sessions_user_status ON technical_sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_episodes_user_domain ON intent_episodes(user_id, domain);
CREATE INDEX IF NOT EXISTS idx_rollups_user_date ON daily_usage_rollups(user_id, local_date);
CREATE INDEX IF NOT EXISTS idx_opt_runs_session ON optimization_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_session ON feedback_events(session_id);
CREATE TABLE IF NOT EXISTS delivery_traces (
    trace_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    episode_id TEXT,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'none',
    requested_channel TEXT DEFAULT 'notification',
    fallback_channel TEXT,
    intervention_preserved INTEGER DEFAULT 0,
    should_notify INTEGER NOT NULL DEFAULT 0,
    should_overlay INTEGER NOT NULL DEFAULT 0,
    eligible INTEGER NOT NULL DEFAULT 0,
    attempted_at_utc TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    chrome_notification_id TEXT,
    failure_reason TEXT,
    cooldown_source TEXT DEFAULT 'VERSIONED_DEFAULT',
    next_eligible_at TEXT,
    created_at_utc TEXT NOT NULL
);
"""
