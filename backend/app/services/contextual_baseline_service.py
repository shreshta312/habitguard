from typing import Dict, Any, Optional
from app.db.repositories.rollups import DailyUsageRollupsRepository

DEFAULT_DOMAIN_BASELINES = {
    "youtube.com": 45.0,
    "netflix.com": 60.0,
    "instagram.com": 25.0,
    "twitter.com": 20.0,
    "x.com": 20.0,
    "reddit.com": 30.0,
    "github.com": 90.0,
    "stackover flow.com": 45.0,
    "wikipedia.org": 30.0
}

FALLBACK_COLD_START = 30.0

class ContextualBaselineService:
    def __init__(self, rollups_repo: Optional[DailyUsageRollupsRepository] = None):
        self.repo = rollups_repo or DailyUsageRollupsRepository()

    def get_baseline(
        self,
        user_id: str,
        domain: str,
        purpose: Optional[str] = None,
        time_context: Optional[str] = None
    ) -> Dict[str, Any]:
        # Tier 1-3: Search SQLite rollups for historical average
        rollups = self.repo.get_user_rollups(user_id, days=30)
        domain_rollups = [r for r in rollups if r["domain"].lower() == domain.lower()]

        if domain_rollups:
            avg_usage = sum(r["focused_minutes"] for r in domain_rollups) / float(len(domain_rollups))
            sample_count = len(domain_rollups)
            confidence = min(1.0, sample_count / 10.0)
            return {
                "baseline_minutes": round(avg_usage, 2),
                "baseline_source": "DIRECTLY_MEASURED_DOMAIN_HISTORY",
                "sample_count": sample_count,
                "confidence": round(confidence, 2)
            }

        # Tier 4-5: Domain catalog default
        clean_domain = domain.lower().replace("www.", "")
        if clean_domain in DEFAULT_DOMAIN_BASELINES:
            return {
                "baseline_minutes": DEFAULT_DOMAIN_BASELINES[clean_domain],
                "baseline_source": "VERSIONED_DEFAULT_DOMAIN_CATALOG",
                "sample_count": 0,
                "confidence": 0.3
            }

        # Tier 6: Cold start default
        return {
            "baseline_minutes": FALLBACK_COLD_START,
            "baseline_source": "VERSIONED_DEFAULT_COLD_START",
            "sample_count": 0,
            "confidence": 0.1
        }
