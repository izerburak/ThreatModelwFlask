import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

from jinja2 import FileSystemLoader

from app import create_app
from app.services.sustainability.arxiv_source import fetch_recent_papers, parse_recent_listing
from app.services.sustainability.keyword_filter import (
    active_keywords,
    filter_and_sort_papers,
    match_title,
)
from app.services.sustainability.sustainability_service import SustainabilityService


ROOT = Path(__file__).resolve().parents[1]


def _entry(arxiv_id, title, subjects="Cryptography and Security (cs.CR)", html_link=True):
    html = f'<a href="/html/{arxiv_id}">html</a>' if html_link else ""
    return f"""
        <dt><a href="/abs/{arxiv_id}">arXiv:{arxiv_id}</a>{html}</dt>
        <dd><div class="meta">
            <div class="list-title mathjax"><span class="descriptor">Title:</span> {title}</div>
            <div class="list-subjects"><span class="descriptor">Subjects:</span> {subjects}</div>
        </div></dd>
    """


def _listing(entries):
    return f'<html><body><dl>{"".join(entries)}</dl></body></html>'


def _paper(arxiv_id, title):
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
        "html_url": f"https://arxiv.org/html/{arxiv_id}",
        "subjects": "Cryptography and Security (cs.CR)",
        "categories": ["cs.CR"],
    }


class _FakeResponse:
    def __init__(self, body):
        self._body = body.encode("utf-8")
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class SustainabilityKeywordTests(unittest.TestCase):
    def test_strong_candidate_is_case_insensitive_and_phrase_aware(self):
        result = match_title("InjecMEM: Memory Injection ATTACK on LLM Agent Memory Systems")

        self.assertEqual(result["candidate_status"], "strong_candidate")
        self.assertEqual(result["security_matches"], ["attack", "injection"])
        self.assertEqual(result["llm_matches"], ["llm", "agent", "memory"])

    def test_hyphen_and_whitespace_are_normalized_for_phrase_matching(self):
        result = match_title(
            "Mapping the Attack-Surface of Retrieval   Augmented Generation",
        )

        self.assertIn("attack surface", result["security_matches"])
        self.assertIn("retrieval augmented generation", result["llm_matches"])
        self.assertEqual(result["candidate_status"], "strong_candidate")

    def test_matching_retains_weak_results_and_sorts_strong_first(self):
        papers = [
            _paper("1", "A Study of Quantum Networks"),
            _paper("2", "Security Risks in Distributed Systems"),
            _paper("3", "Language Model Evaluation Methods"),
            _paper("4", "Prompt Injection Attacks on LLM Agents"),
        ]

        results = filter_and_sort_papers(papers, active_keywords())

        self.assertEqual(
            [paper["candidate_status"] for paper in results],
            ["strong_candidate", "security_only", "llm_only", "no_match"],
        )
        self.assertEqual(results[0]["arxiv_id"], "4")


class ArxivSourceTests(unittest.TestCase):
    def test_listing_entries_are_normalized_with_real_ids_and_urls(self):
        html = _listing(
            [
                _entry(
                    "2608.27092",
                    "The Framing Gap: Indirect Prompt-Injection Exfiltration",
                    "Cryptography and Security (cs.CR); Artificial Intelligence (cs.AI)",
                )
            ]
        )

        result = parse_recent_listing(html)
        paper = result["papers"][0]

        self.assertEqual(paper["arxiv_id"], "2608.27092")
        self.assertEqual(paper["categories"], ["cs.CR", "cs.AI"])
        self.assertEqual(paper["paper_url"], "https://arxiv.org/abs/2608.27092")
        self.assertEqual(paper["html_url"], "https://arxiv.org/html/2608.27092")
        self.assertTrue(paper["html_available_on_listing"])

    def test_fetch_uses_listing_pagination_and_never_invents_ids(self):
        first_page = _listing(
            [_entry(f"2608.{number:05d}", f"Paper {number}") for number in range(50)]
        )
        second_page = _listing([_entry("2607.99999", "Older Paper")])
        requested_urls = []

        def fetcher(request, timeout):
            requested_urls.append(request.full_url)
            return _FakeResponse(first_page if len(requested_urls) == 1 else second_page)

        result = fetch_recent_papers(51, fetcher=fetcher)

        self.assertEqual(len(result["papers"]), 51)
        self.assertEqual(result["papers"][-1]["arxiv_id"], "2607.99999")
        self.assertIn("skip=50", requested_urls[1])
        self.assertIn("show=50", requested_urls[1])


class SustainabilityPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app_dir = self.root / "app"
        self.app_dir.mkdir()
        self.storage_path = self.root / "sustainability" / "sustainability.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_custom_keyword_persists_and_can_be_removed(self):
        service = SustainabilityService(self.app_dir, storage_path=self.storage_path)

        self.assertTrue(service.add_keyword("security", "supply chain"))
        reloaded = SustainabilityService(self.app_dir, storage_path=self.storage_path)
        self.assertIn("supply chain", reloaded.view_state()["custom_keywords"]["security"])
        self.assertTrue(reloaded.remove_keyword("security", "SUPPLY CHAIN"))
        self.assertNotIn("supply chain", reloaded.view_state()["keywords"]["security"])

        payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "sustainability.v1")

    def test_scan_result_and_summary_are_persisted(self):
        source = Mock(
            return_value={
                "papers": [
                    _paper("2608.00001", "LLM Agent Prompt Injection Attack"),
                    _paper("2608.00002", "Post-Quantum Signatures"),
                ],
                "warnings": [],
            }
        )
        service = SustainabilityService(self.app_dir, storage_path=self.storage_path, paper_source=source)

        scan = service.run_scan(25)

        source.assert_called_once_with(25)
        self.assertEqual(scan["summary"]["papers_scanned"], 2)
        self.assertEqual(scan["summary"]["strong_candidates"], 1)
        self.assertEqual(scan["papers"][0]["candidate_status"], "strong_candidate")
        self.assertEqual(service.view_state()["last_scan"]["summary"], scan["summary"])


class SustainabilityRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app_dir = self.root / "app"
        self.app_dir.mkdir()
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            SUSTAINABILITY_STORAGE_PATH=str(self.root / "sustainability.json"),
        )
        self.app.root_path = str(self.app_dir)
        self.app.jinja_loader = FileSystemLoader(str(ROOT / "app" / "templates"))
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app.services.sustainability.sustainability_service.fetch_recent_papers")
    def test_page_does_not_scan_on_get_and_post_renders_mocked_results(self, fetch_papers):
        response = self.client.get("/sustainability")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sustainability \xe2\x80\x94 Emerging LLM Security Research", response.data)
        self.assertIn(b"Start Pipeline", response.data)
        fetch_papers.assert_not_called()

        fetch_papers.return_value = {
            "papers": [_paper("2608.00003", "Agent Memory Injection Attack on LLM Systems")],
            "warnings": [],
        }
        response = self.client.post(
            "/sustainability",
            data={"action": "start_pipeline", "papers_to_scan": "25"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Strong Candidate", response.data)
        self.assertIn(b"2608.00003", response.data)
        self.assertIn(b"Why selected", response.data)
        fetch_papers.assert_called_once_with(25)


if __name__ == "__main__":
    unittest.main()
