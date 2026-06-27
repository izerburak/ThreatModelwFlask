"""Deterministic candidate-risk catalog.

The old questionnaire carried per-question ``owasp_llm`` / ``owasp_web`` /
``owasp_api`` arrays and the risk engine discovered candidate risks by reading
them off whichever questions were answered. The new DREAD-oriented
questionnaire drops those arrays, so candidate discovery now lives here:

a fixed catalog of canonical LLM / Web / API risks, each with

  * an ``applies(idx)`` predicate over the *answers* (and therefore the
    architecture they imply) deciding whether the risk is in scope, and
  * the question numbers whose answers act as grounded *evidence* for it.

The OWASP code is kept only as a secondary label/``related_code`` - DREAD
(`dread_scoring`) does the scoring. Because the predicates read answer content
(not per-question metadata), they work identically for legacy Q1-Q82 records
and for the new Q1-Q91 questionnaire.
"""

from app.services.dread_scoring import (
    _has,
    _high_agency,
    _risky_input_formats,
    _secrets_access,
    _sensitive_data,
    index_answers,
)


# --- architecture surface predicates ----------------------------------------

def _web_surface(idx):
    return (
        _has(idx, 3, "web based chat", "rest api")
        or _has(idx, 48, "chat page", "dashboard", "admin", "widget", "iframe", "webhook")
        or _has(idx, 85, "web frontend", "mobile client", "api gateway")
        or _has(idx, 2, "anonymous public", "authenticated public")
    )


def _api_surface(idx):
    return (
        _has(idx, 3, "rest api", "internal service", "third party")
        or _has(idx, 14, "directly", "via backend")
        or _has(idx, 85, "api gateway", "backend api")
        or _has(idx, 12, "internal apis", "database", "search", "admin tools")
        or _has(idx, 9, "backend api", "frontend", "auth service")
    )


def _has_tools(idx):
    return (
        _has(idx, 12, "search", "database", "internal apis", "admin tools")
        or _has(idx, 11, "framework", "agent workflow", "basic logic")
        or _high_agency(idx)
        or (not _has(idx, 15, "generate text responses only") and idx.get(15))
    )


def _rag_enabled(idx):
    q8 = idx.get(8, [])
    return bool(q8) and not _has(idx, 8, "no rag")


def _output_consumed(idx):
    return (
        _has(idx, 21, "json", "code", "html", "markdown", "rich text")
        or _has(idx, 22, "web interface", "admin dashboard", "api response", "messaging", "backend automation")
        or _has(idx, 64, "html", "markdown", "rich content")
        or _has(idx, 65, "yes")
        or _has(idx, 31, "not validated", "manual review only")
    )


def _external_apis(idx):
    return (
        _has(idx, 14, "directly", "via backend")
        or _has(idx, 60, "validated", "basic validation", "inserted directly")
        or _has(idx, 61, "yes")
        or _has(idx, 62, "allowlisted", "partially restricted", "arbitrary urls")
    )


def _always(idx):
    return True


# --- catalog ----------------------------------------------------------------
# (code, framework, applies, evidence_question_numbers)
_CATALOG = [
    ("LLM01", "owasp_llm", _always, [5, 6, 20, 30, 83, 84, 2, 48]),
    ("LLM02", "owasp_llm", lambda idx: _sensitive_data(idx) or _has(idx, 47, "full prompts") or _has(idx, 88, "without clear deletion"), [4, 24, 32, 47, 88]),
    ("LLM03", "owasp_llm", lambda idx: _has(idx, 17, "third party", "external vendor", "hybrid") or _has(idx, 18, "different models", "fallback", "routing") or _has(idx, 35, "no validation", "manual trust"), [17, 18, 35]),
    ("LLM04", "owasp_llm", lambda idx: _rag_enabled(idx) or _has(idx, 6, "file uploads", "web urls", "public repositories") or _has(idx, 43, "training", "both indexing") or _has(idx, 68, "may affect") or _has(idx, 69, "no dedicated"), [6, 8, 43, 68, 69]),
    ("LLM05", "owasp_llm", _output_consumed, [21, 22, 31, 64, 65, 66]),
    ("LLM06", "owasp_llm", _has_tools, [11, 12, 14, 15, 16, 39, 44, 79, 80, 91]),
    ("LLM07", "owasp_llm", lambda idx: _secrets_access(idx) or _has(idx, 19, "hardcoded", "configuration files", "dynamically generated") or _has(idx, 20, "yes"), [19, 20, 45]),
    ("LLM08", "owasp_llm", lambda idx: _has(idx, 13, "vector db") or _rag_enabled(idx) or _has(idx, 36, "no dedicated", "partially") or _has(idx, 68, "may affect"), [8, 13, 36, 68]),
    ("LLM09", "owasp_llm", lambda idx: _has(idx, 39, "decisions", "low impact", "moderate", "high impact") or _has(idx, 22, "web interface", "backend automation") or not idx.get(39), [1, 39, 31, 22]),
    ("LLM10", "owasp_llm", lambda idx: _has(idx, 34, "no protections", "basic request") or _has(idx, 77, "no effective", "partial", "inconsistent") or _has(idx, 78, "weak", "partially") or _has(idx, 2, "anonymous public"), [34, 77, 78, 2]),

    ("A01:2025", "owasp_web", lambda idx: _web_surface(idx) or _has(idx, 26, "no authorization") or _has(idx, 28, "no, same behavior"), [26, 28, 49, 50, 53]),
    ("A02:2025", "owasp_web", lambda idx: _has(idx, 52, "wildcard", "broad", "overly permissive") or _has(idx, 76, "detailed internal errors") or _web_surface(idx), [52, 76, 49]),
    ("A03:2025", "owasp_web", lambda idx: _has(idx, 17, "third party", "external vendor", "hybrid") or _has(idx, 35, "no validation", "manual trust"), [17, 35]),
    ("A04:2025", "owasp_web", lambda idx: _has(idx, 73, "no or unclear", "partially encrypted", "unclear") or (idx.get(81) and not _has(idx, 81, "all sensitive communication is encrypted")) or _has(idx, 82, "browser to web", "web application to backend", "backend api to"), [73, 81, 82]),
    ("A05:2025", "owasp_web", lambda idx: _has(idx, 64, "html", "rich content") or _has(idx, 65, "yes") or _has(idx, 66, "no dedicated", "partially") or _risky_input_formats(idx), [64, 65, 66, 83]),
    ("A07:2025", "owasp_web", lambda idx: _has(idx, 25, "no authentication", "username password") or _has(idx, 50, "only checked at initial login", "no authentication"), [25, 50]),
    ("A08:2025", "owasp_web", lambda idx: _has(idx, 68, "may affect") or _has(idx, 69, "no dedicated", "partially") or _has(idx, 71, "not tracked", "informally"), [68, 69, 71]),
    ("A09:2025", "owasp_web", lambda idx: _has(idx, 33, "no logging", "basic application") or _has(idx, 74, "not logged", "basic application") or _has(idx, 89, "no defined process", "informal"), [33, 74, 89]),
    ("A10:2025", "owasp_web", lambda idx: _has(idx, 75, "fall back", "some non critical") or _has(idx, 76, "detailed internal errors"), [75, 76]),

    ("API1:2023", "owasp_api", lambda idx: _has(idx, 53, "user controlled", "without reliable", "partial authorization") or _has_tools(idx), [53, 54]),
    ("API2:2023", "owasp_api", lambda idx: _api_surface(idx) or _has(idx, 25, "no authentication") or _has(idx, 56, "shared service account"), [25, 50, 56]),
    ("API3:2023", "owasp_api", lambda idx: _has(idx, 54, "without strong controls", "partial validation") or _has_tools(idx), [54, 53]),
    ("API4:2023", "owasp_api", lambda idx: _has(idx, 77, "no effective", "partial", "inconsistent") or _has(idx, 78, "weak", "partially"), [77, 78]),
    ("API5:2023", "owasp_api", lambda idx: _has(idx, 55, "without strong checks", "shared backend service") or _has(idx, 9, "backend api", "auth service") or _has_tools(idx), [55, 57, 9]),
    ("API6:2023", "owasp_api", lambda idx: (idx.get(79) and not _has(idx, 79, "no sensitive business flows")) or _has(idx, 15, "execute workflows", "create or update"), [79, 80]),
    ("API7:2023", "owasp_api", lambda idx: _has(idx, 62, "arbitrary urls", "allowlisted", "partially restricted") or _has(idx, 63, "no outbound restrictions", "partially"), [62, 63]),
    ("API8:2023", "owasp_api", lambda idx: _has(idx, 52, "wildcard", "broad") or _has(idx, 76, "detailed internal errors"), [52, 76]),
    ("API9:2023", "owasp_api", lambda idx: _has(idx, 58, "partial inventory", "no reliable") or _has(idx, 59, "non production", "some non production"), [58, 59]),
    ("API10:2023", "owasp_api", _external_apis, [60, 61, 14]),
]


def candidate_codes(answers):
    """Return the catalog entries whose ``applies`` predicate fires for these answers.

    Each entry is ``{"code", "framework", "evidence_questions"}``. ``evidence_questions``
    is filtered to the questions actually present in the answer set, so a risk never
    cites a question that was not asked (important for legacy Q1-Q82 records).
    """
    idx = index_answers(answers)
    present = set(idx.keys())
    candidates = []
    for code, framework, applies, evidence in _CATALOG:
        try:
            fired = bool(applies(idx))
        except Exception:
            fired = False
        if not fired:
            continue
        cited = [number for number in evidence if number in present]
        candidates.append(
            {
                "code": code,
                "framework": framework,
                "evidence_questions": cited,
            }
        )
    return candidates


def all_catalog_codes():
    """All canonical codes in the catalog (for tests / documentation)."""
    return [code for code, _framework, _applies, _evidence in _CATALOG]
