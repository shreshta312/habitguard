import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.db.connection import get_db_connection

class OptimizationRepository:
    def record_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO optimization_runs
                       (session_id, user_id, input_snapshot_json, observed_baseline, baseline_source,
                        planned_minutes, necessary_minimum, minutes_used, temptation_estimate,
                        temptation_confidence, optimized_target, recommended_remaining, objective_value,
                        utility_retained, constraints_satisfied, binding_constraints_json, derivation_json,
                        parameter_sources_json, solver_status, configuration_version, tracking_reliability, created_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["session_id"],
                        data["user_id"],
                        json.dumps(data.get("input_snapshot", {})),
                        data["observed_baseline"],
                        data["baseline_source"],
                        data.get("planned_minutes"),
                        data["necessary_minimum"],
                        data["minutes_used"],
                        data["temptation_estimate"],
                        data["temptation_confidence"],
                        data.get("optimized_target"),
                        data.get("recommended_remaining"),
                        data.get("objective_value"),
                        data.get("utility_retained"),
                        1 if data.get("constraints_satisfied", True) else 0,
                        json.dumps(data.get("binding_constraints", [])),
                        json.dumps(data.get("derivation", {})),
                        json.dumps(data.get("parameter_sources", {})),
                        data["solver_status"],
                        data.get("configuration_version", "2.0.0"),
                        data.get("tracking_reliability", 1.0),
                        now_utc
                    )
                )
                run_id = cur.lastrowid
            data["id"] = run_id
            data["created_at_utc"] = now_utc
            return data
        finally:
            conn.close()

    def get_latest_run(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM optimization_runs WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,))
            row = cur.fetchone()
            if not row:
                return None
            run = dict(row)
            run["input_snapshot"] = json.loads(run["input_snapshot_json"]) if run["input_snapshot_json"] else {}
            run["binding_constraints"] = json.loads(run["binding_constraints_json"]) if run["binding_constraints_json"] else []
            run["derivation"] = json.loads(run["derivation_json"]) if run["derivation_json"] else {}
            run["parameter_sources"] = json.loads(run["parameter_sources_json"]) if run["parameter_sources_json"] else {}
            return run
        finally:
            conn.close()

    def get_user_runs(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM optimization_runs WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
            runs = []
            for row in cur.fetchall():
                run = dict(row)
                run["input_snapshot"] = json.loads(run["input_snapshot_json"]) if run["input_snapshot_json"] else {}
                run["binding_constraints"] = json.loads(run["binding_constraints_json"]) if run["binding_constraints_json"] else []
                run["derivation"] = json.loads(run["derivation_json"]) if run["derivation_json"] else {}
                run["parameter_sources"] = json.loads(run["parameter_sources_json"]) if run["parameter_sources_json"] else {}
                runs.append(run)
            return runs
        finally:
            conn.close()
