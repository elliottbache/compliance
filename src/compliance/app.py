from compliance.db.query_history import get_site_history
from compliance.llm.anthropic_api import summarize_previous_visits


def run_pipeline() -> None:
    site_history = get_site_history(71)
    print(f"site 71: {site_history}")
    if site_history:
        summarize_previous_visits(site_history, ai_model="claude-haiku-4-5-20251001")


if __name__ == "__main__":
    run_pipeline()
