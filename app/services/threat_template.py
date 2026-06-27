"""Generic threat template for template-guided local-LLM threat identification.

This module defines a *fixed, domain-agnostic* catalog of threat patterns the
local LLM is asked to look for. It is deliberately generic: the LLM searches for
these classes of weakness in the supplied evidence (questionnaire answers,
deterministic candidate risks, and the static DFD) instead of free-forming
domain-specific threats. Each pattern lists the OWASP codes it *typically* maps
to - these are advisory hints only. Primary identified threats are still
constrained to the deterministic candidate codes by the validator; the template
never widens the primary code set.
"""

# id, title, description, typical_codes (advisory only - NOT used for scoring)
THREAT_PATTERNS = [
    {
        "id": "prompt_context_manipulation",
        "title": "Prompt / context manipulation",
        "description": (
            "User- or content-controlled text reaches the model context and can override, "
            "leak, or subvert system instructions (direct or indirect prompt injection, "
            "system-prompt leakage)."
        ),
        "typical_codes": ["LLM01", "LLM07"],
    },
    {
        "id": "untrusted_input_crossing_trust_boundary",
        "title": "Untrusted input crossing a trust boundary",
        "description": (
            "Input from a lower-trust zone (public actor, external content, third-party API) "
            "flows across a trust boundary into a higher-trust process with weak validation or "
            "parsing of rich/structured formats."
        ),
        "typical_codes": ["A05:2025", "LLM01", "API10:2023"],
    },
    {
        "id": "rag_or_memory_contamination",
        "title": "RAG or memory contamination",
        "description": (
            "Retrieved documents, indexed content, or conversational memory can be poisoned or "
            "influenced by untrusted sources and later affect other requests or users."
        ),
        "typical_codes": ["LLM04", "LLM08"],
    },
    {
        "id": "sensitive_data_exposure",
        "title": "Sensitive data exposure",
        "description": (
            "Sensitive data (PII, secrets, business data) is reachable by the model, returned in "
            "responses, retained, or written to logs without adequate minimization or access control."
        ),
        "typical_codes": ["LLM02", "A04:2025", "API1:2023"],
    },
    {
        "id": "excessive_tool_or_workflow_agency",
        "title": "Excessive tool or workflow agency",
        "description": (
            "The model can trigger tools, actions, or business workflows (state changes, "
            "transactions) with insufficient scoping, approval, or least-privilege controls."
        ),
        "typical_codes": ["LLM06", "API5:2023", "API6:2023"],
    },
    {
        "id": "weak_authentication_authorization",
        "title": "Weak authentication or authorization",
        "description": (
            "Entry points, objects, or functions lack strong authentication or per-object / "
            "per-function authorization, enabling unauthorized access or privilege escalation."
        ),
        "typical_codes": ["A01:2025", "A07:2025", "API1:2023", "API2:2023"],
    },
    {
        "id": "unsafe_output_handling",
        "title": "Unsafe output handling",
        "description": (
            "Model output is consumed downstream (rendered HTML/markdown, executed, used in "
            "queries or automation) without validation, encoding, or allowlisting."
        ),
        "typical_codes": ["LLM05", "A05:2025"],
    },
    {
        "id": "vector_store_or_embedding_isolation",
        "title": "Vector store or embedding isolation weakness",
        "description": (
            "Vector stores / embeddings lack per-tenant or per-user isolation and access control, "
            "allowing cross-tenant retrieval or inference leakage."
        ),
        "typical_codes": ["LLM08", "A01:2025"],
    },
    {
        "id": "secrets_logging_transport_exposure",
        "title": "Secrets, logging, and transport exposure",
        "description": (
            "Secrets/credentials are reachable at runtime, logs capture sensitive prompt/response "
            "data, or transport is unencrypted/unclear across trust boundaries."
        ),
        "typical_codes": ["LLM07", "A04:2025", "A09:2025"],
    },
    {
        "id": "missing_monitoring_limits_incident_response",
        "title": "Missing monitoring, limits, or incident response",
        "description": (
            "No effective rate/resource limits, no security monitoring/alerting, or no tested "
            "incident-response process for LLM misuse."
        ),
        "typical_codes": ["LLM10", "API4:2023", "A09:2025"],
    },
]


def pattern_ids():
    """Stable list of the generic threat-pattern identifiers."""
    return [pattern["id"] for pattern in THREAT_PATTERNS]


def threat_patterns_prompt_block():
    """Human-readable block describing every pattern, for the prompt file/user payload."""
    lines = []
    for pattern in THREAT_PATTERNS:
        codes = ", ".join(pattern["typical_codes"])
        lines.append(f"- {pattern['id']} ({pattern['title']}): {pattern['description']} [typical: {codes}]")
    return "\n".join(lines)
