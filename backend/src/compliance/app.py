from compliance.services.site_analysis import summarize_previous_visits
from compliance.services.sites import get_site_history_legacy


def run_pipeline() -> None:
    """Run the local site-history analysis demo pipeline."""
    site_history = get_site_history_legacy(71)
    print(f"site 71: {site_history}")
    if site_history:
        summarize_previous_visits(site_history, ai_model="claude-haiku-4-5-20251001")


if __name__ == "__main__":
    run_pipeline()
