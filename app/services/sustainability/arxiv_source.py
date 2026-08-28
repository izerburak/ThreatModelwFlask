"""Retrieve and normalize recent arXiv cs.CR listing entries."""

import re
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ARXIV_BASE_URL = "https://arxiv.org"
ARXIV_RECENT_URL = f"{ARXIV_BASE_URL}/list/cs.CR/recent"
PAGE_SIZE = 50


class ArxivSourceError(RuntimeError):
    """A user-displayable failure while retrieving or parsing arXiv."""


class _RecentListingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.papers = []
        self.warnings = []
        self._entry = None
        self._capture = None
        self._capture_depth = 0
        self._capture_parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "dt":
            self._finish_entry()
            self._entry = {"arxiv_id": "", "title": "", "subjects": "", "html_available": False}

        if self._entry is None:
            return

        if tag == "a":
            href = attributes.get("href") or ""
            if href.startswith("/abs/") and not self._entry["arxiv_id"]:
                self._entry["arxiv_id"] = _normalize_arxiv_id(href)
            elif href.startswith("/html/"):
                self._entry["html_available"] = True

        if tag == "div" and "list-title" in classes:
            self._capture = "title"
            self._capture_depth = 1
            self._capture_parts = []
        elif tag == "div" and "list-subjects" in classes:
            self._capture = "subjects"
            self._capture_depth = 1
            self._capture_parts = []
        elif self._capture and tag == "div":
            self._capture_depth += 1

    def handle_data(self, data):
        if self._capture:
            self._capture_parts.append(data)

    def handle_endtag(self, tag):
        if self._capture and tag == "div":
            self._capture_depth -= 1
            if self._capture_depth == 0:
                value = _normalize_space(" ".join(self._capture_parts))
                value = re.sub(rf"^{self._capture}:\s*", "", value, flags=re.IGNORECASE)
                self._entry[self._capture] = value
                self._capture = None
                self._capture_parts = []

        if tag == "dd":
            self._finish_entry()

    def close(self):
        super().close()
        self._finish_entry()

    def _finish_entry(self):
        if self._entry is None:
            return

        arxiv_id = self._entry.get("arxiv_id") or ""
        title = self._entry.get("title") or ""
        if arxiv_id and title:
            subjects = self._entry.get("subjects") or ""
            self.papers.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "paper_url": f"{ARXIV_BASE_URL}/abs/{arxiv_id}",
                    "html_url": f"{ARXIV_BASE_URL}/html/{arxiv_id}",
                    "html_available_on_listing": bool(self._entry.get("html_available")),
                    "subjects": subjects,
                    "categories": re.findall(r"\(([a-z-]+\.[A-Z]{2})\)", subjects),
                }
            )
        elif arxiv_id or title:
            self.warnings.append("Skipped one malformed arXiv listing entry.")

        self._entry = None
        self._capture = None
        self._capture_depth = 0
        self._capture_parts = []


def parse_recent_listing(html):
    """Parse normalized papers and non-fatal warnings from an arXiv listing."""
    if not isinstance(html, str) or not html.strip():
        raise ArxivSourceError("ArXiv returned an empty response.")
    if "list-title" not in html or "/abs/" not in html:
        raise ArxivSourceError("ArXiv returned an unexpected listing format.")

    parser = _RecentListingParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:
        raise ArxivSourceError("The ArXiv listing could not be parsed.") from exc

    if not parser.papers:
        raise ArxivSourceError("No papers were found in the ArXiv listing.")
    return {"papers": parser.papers, "warnings": parser.warnings}


def fetch_recent_papers(limit, fetcher=None, timeout=20):
    """Fetch up to ``limit`` actual cs.CR entries, following listing pages."""
    try:
        requested = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("Paper count must be a number.") from exc
    if requested <= 0:
        raise ValueError("Paper count must be greater than zero.")

    fetcher = fetcher or urlopen
    papers = []
    warnings = []
    seen_ids = set()
    skip = 0

    while len(papers) < requested:
        page_url = ARXIV_RECENT_URL if skip == 0 else f"{ARXIV_RECENT_URL}?skip={skip}&show={PAGE_SIZE}"
        request = Request(
            page_url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "LLM-Sentinel-Sustainability/1.0 (research discovery)",
            },
        )
        try:
            with fetcher(request, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                if content_type and "html" not in content_type.lower():
                    raise ArxivSourceError("ArXiv returned an unexpected response type.")
                charset = response.headers.get_content_charset() or "utf-8"
                html = response.read().decode(charset, errors="replace")
        except ArxivSourceError:
            raise
        except HTTPError as exc:
            raise ArxivSourceError(f"ArXiv could not be reached (HTTP {exc.code}).") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ArxivSourceError("ArXiv is currently unavailable. Please try again later.") from exc

        parsed = parse_recent_listing(html)
        new_papers = []
        for paper in parsed["papers"]:
            if paper["arxiv_id"] in seen_ids:
                continue
            seen_ids.add(paper["arxiv_id"])
            new_papers.append(paper)
        papers.extend(new_papers)
        warnings.extend(parsed["warnings"])

        if len(parsed["papers"]) < PAGE_SIZE or not new_papers:
            break
        skip += PAGE_SIZE

    if not papers:
        raise ArxivSourceError("No papers were returned by ArXiv.")
    if len(papers) < requested:
        warnings.append(f"ArXiv returned {len(papers)} of the {requested} requested papers.")
    return {"papers": papers[:requested], "warnings": _deduplicate(warnings)}


def _normalize_arxiv_id(value):
    text = str(value or "").strip().lstrip("/")
    text = re.sub(r"^https?://(?:www\.)?arxiv\.org/", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:abs/|arxiv:\s*)", "", text, flags=re.IGNORECASE)
    return text.strip("/ ")


def _normalize_space(value):
    return " ".join(str(value or "").split())


def _deduplicate(values):
    return list(dict.fromkeys(values))
