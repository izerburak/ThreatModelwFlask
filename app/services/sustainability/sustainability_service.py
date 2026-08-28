"""Orchestrate the isolated Sustainability research scan."""

from datetime import datetime, timezone

from .arxiv_source import ARXIV_RECENT_URL, fetch_recent_papers
from .keyword_filter import active_keywords, filter_and_sort_papers
from .sustainability_store import SustainabilityStore


PAPER_COUNT_OPTIONS = (25, 50, 100, 200)


class SustainabilityService:
    def __init__(self, app_root_path, storage_path=None, paper_source=None):
        self.store = SustainabilityStore(app_root_path, storage_path)
        self.paper_source = paper_source or fetch_recent_papers

    def view_state(self):
        stored = self.store.load()
        return {
            "source_name": "ArXiv — cs.CR Recent",
            "source_url": ARXIV_RECENT_URL,
            "paper_count_options": PAPER_COUNT_OPTIONS,
            "custom_keywords": stored["custom_keywords"],
            "keywords": active_keywords(stored["custom_keywords"]),
            "last_scan": stored["last_scan"],
        }

    def add_keyword(self, group, keyword):
        group = _validate_group(group)
        keyword = " ".join(str(keyword or "").split())
        if not keyword:
            raise ValueError("Enter a keyword to add.")
        if len(keyword) > 80:
            raise ValueError("Keywords must be 80 characters or fewer.")

        stored = self.store.load()
        all_active = active_keywords(stored["custom_keywords"])[group]
        if keyword.casefold() in {value.casefold() for value in all_active}:
            return False
        stored["custom_keywords"][group].append(keyword)
        self.store.save_custom_keywords(stored["custom_keywords"])
        return True

    def remove_keyword(self, group, keyword):
        group = _validate_group(group)
        target = " ".join(str(keyword or "").split()).casefold()
        stored = self.store.load()
        original = stored["custom_keywords"][group]
        updated = [value for value in original if value.casefold() != target]
        if len(updated) == len(original):
            return False
        stored["custom_keywords"][group] = updated
        self.store.save_custom_keywords(stored["custom_keywords"])
        return True

    def run_scan(self, paper_count):
        try:
            requested = int(paper_count)
        except (TypeError, ValueError) as exc:
            raise ValueError("Choose a valid number of papers to scan.") from exc
        if requested not in PAPER_COUNT_OPTIONS:
            raise ValueError("Choose one of the available paper-count options.")

        stored = self.store.load()
        keywords = active_keywords(stored["custom_keywords"])
        source_result = self.paper_source(requested)
        papers = filter_and_sort_papers(source_result.get("papers", []), keywords)
        if not papers:
            raise ValueError("ArXiv returned no papers to scan.")

        summary = {
            "papers_scanned": len(papers),
            "security_matches": sum(1 for paper in papers if paper["security_match"]),
            "llm_matches": sum(1 for paper in papers if paper["llm_match"]),
            "strong_candidates": sum(
                1 for paper in papers if paper["candidate_status"] == "strong_candidate"
            ),
            "no_keyword_match": sum(1 for paper in papers if paper["candidate_status"] == "no_match"),
        }
        scan = {
            "schema_version": "sustainability.scan.v1",
            "source_name": "ArXiv — cs.CR Recent",
            "source_url": ARXIV_RECENT_URL,
            "requested_count": requested,
            "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "keywords": keywords,
            "summary": summary,
            "warnings": list(source_result.get("warnings") or []),
            "papers": papers,
        }
        self.store.save_last_scan(scan)
        return scan


def _validate_group(group):
    normalized = str(group or "").strip().lower()
    if normalized not in {"security", "llm"}:
        raise ValueError("Choose Security or LLM / AI System for the keyword group.")
    return normalized
