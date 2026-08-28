"""Deterministic, explainable title keyword matching."""

import unicodedata


SECURITY_KEYWORDS = (
    "attack",
    "attacks",
    "attack surface",
    "vulnerability",
    "vulnerabilities",
    "risk",
    "risks",
    "threat",
    "threats",
    "exploit",
    "exploits",
    "exploitation",
    "injection",
    "jailbreak",
    "poisoning",
    "adversarial",
    "leakage",
    "exfiltration",
    "bypass",
    "hijack",
    "compromise",
    "abuse",
    "security",
)

LLM_KEYWORDS = (
    "llm",
    "large language model",
    "language model",
    "agent",
    "agentic",
    "prompt",
    "rag",
    "retrieval augmented generation",
    "retrieval",
    "memory",
    "tool",
    "tool-use",
    "tool calling",
    "model",
    "ai agent",
)

STATUS_LABELS = {
    "strong_candidate": "Strong Candidate",
    "security_only": "Security Match Only",
    "llm_only": "LLM Match Only",
    "no_match": "No Match",
}

STATUS_ORDER = {
    "strong_candidate": 0,
    "security_only": 1,
    "llm_only": 2,
    "no_match": 3,
}


def active_keywords(custom_keywords=None):
    custom = custom_keywords if isinstance(custom_keywords, dict) else {}
    return {
        "security": _deduplicate_keywords((*SECURITY_KEYWORDS, *custom.get("security", []))),
        "llm": _deduplicate_keywords((*LLM_KEYWORDS, *custom.get("llm", []))),
    }


def match_title(title, security_keywords=None, llm_keywords=None):
    """Return exact active keywords found in a normalized title."""
    security_keywords = security_keywords if security_keywords is not None else SECURITY_KEYWORDS
    llm_keywords = llm_keywords if llm_keywords is not None else LLM_KEYWORDS
    normalized_title = f" {_normalize_for_match(title)} "

    security_matches = [
        keyword for keyword in security_keywords if _keyword_in_title(keyword, normalized_title)
    ]
    llm_matches = [keyword for keyword in llm_keywords if _keyword_in_title(keyword, normalized_title)]
    status = classify_candidate(bool(security_matches), bool(llm_matches))
    return {
        "security_match": bool(security_matches),
        "llm_match": bool(llm_matches),
        "security_matches": security_matches,
        "llm_matches": llm_matches,
        "candidate_status": status,
        "candidate_status_label": STATUS_LABELS[status],
    }


def classify_candidate(security_match, llm_match):
    if security_match and llm_match:
        return "strong_candidate"
    if security_match:
        return "security_only"
    if llm_match:
        return "llm_only"
    return "no_match"


def filter_and_sort_papers(papers, keyword_config):
    filtered = []
    for source_index, paper in enumerate(papers or []):
        result = dict(paper)
        result["source_index"] = source_index
        result.update(
            match_title(
                result.get("title") or "",
                keyword_config.get("security", []),
                keyword_config.get("llm", []),
            )
        )
        filtered.append(result)

    return sorted(
        filtered,
        key=lambda paper: (STATUS_ORDER[paper["candidate_status"]], paper["source_index"]),
    )


def _keyword_in_title(keyword, normalized_title):
    normalized_keyword = _normalize_for_match(keyword)
    return bool(normalized_keyword) and f" {normalized_keyword} " in normalized_title


def _normalize_for_match(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    normalized = "".join(character if character.isalnum() else " " for character in text)
    return " ".join(normalized.split())


def _deduplicate_keywords(values):
    keywords = []
    seen = set()
    for value in values:
        keyword = " ".join(str(value or "").split())
        key = keyword.casefold()
        if not keyword or key in seen:
            continue
        seen.add(key)
        keywords.append(keyword)
    return keywords
