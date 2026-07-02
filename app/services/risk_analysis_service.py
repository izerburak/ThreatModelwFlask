import json
import re
from pathlib import Path

from app.services.dread_scoring import (
    _framework,
    _has,
    _risky_input_formats,
    _weak_parsing,
    index_answers,
    score_code,
)
from app.services.dread_signals import extract_dread_signals, summarize_signals
from app.services.feature_flags import config_int, flag_enabled
from app.services.llm_mitigation_service import generate_mitigations
from app.services.llm_threat_identification import identify_threats
from app.services.risk_catalog import candidate_codes
from app.services.threat_grounding_validator import validate_threats


class ThreatIdentificationUnavailable(RuntimeError):
    """Raised when the local-LLM threat-identification stage cannot run.

    The orchestrator catches this and falls back to the deterministic baseline so a
    valid risks.json is always produced (the feature-flag contract).
    """


OWASP_LLM_2025 = {
    "LLM01": "Prompt Injection",
    "LLM02": "Sensitive Information Disclosure",
    "LLM03": "Supply Chain",
    "LLM04": "Data and Model Poisoning",
    "LLM05": "Improper Output Handling",
    "LLM06": "Excessive Agency",
    "LLM07": "System Prompt Leakage",
    "LLM08": "Vector and Embedding Weaknesses",
    "LLM09": "Misinformation",
    "LLM10": "Unbounded Consumption",
}

OWASP_WEB_2025 = {
    "A01:2025": "Broken Access Control",
    "A02:2025": "Security Misconfiguration",
    "A03:2025": "Software Supply Chain Failures",
    "A04:2025": "Cryptographic Failures",
    "A05:2025": "Injection",
    "A06:2025": "Insecure Design",
    "A07:2025": "Authentication Failures",
    "A08:2025": "Software or Data Integrity Failures",
    "A09:2025": "Security Logging and Alerting Failures",
    "A10:2025": "Mishandling of Exceptional Conditions",
}

OWASP_API_2023 = {
    "API1:2023": "Broken Object Level Authorization",
    "API2:2023": "Broken Authentication",
    "API3:2023": "Broken Object Property Level Authorization",
    "API4:2023": "Unrestricted Resource Consumption",
    "API5:2023": "Broken Function Level Authorization",
    "API6:2023": "Unrestricted Access to Sensitive Business Flows",
    "API7:2023": "Server Side Request Forgery",
    "API8:2023": "Security Misconfiguration",
    "API9:2023": "Improper Inventory Management",
    "API10:2023": "Unsafe Consumption of APIs",
}

# Deterministic, OWASP-code-keyed baseline mitigation guidance. These are the
# reproducible, LLM-independent controls shown for each risk. Context-specific,
# DREAD-aware mitigations are generated on top of these per risk (see
# _dread_aware_mitigations) and listed first.
OWASP_MITIGATIONS = {
    "LLM01": [
        "Separate the system prompt from user input and treat all model input as untrusted.",
        "Constrain model role/format and apply least privilege to any action the model can trigger.",
    ],
    "LLM02": [
        "Minimize and redact sensitive data before it reaches the model, responses, or logs.",
        "Enforce data-access controls so the model only sees data the user is authorized for.",
    ],
    "LLM03": [
        "Pin and verify the provenance of models, libraries, and datasets.",
        "Vet third-party models/plugins and monitor them for known vulnerabilities.",
    ],
    "LLM04": [
        "Validate and quarantine ingested/RAG content before indexing.",
        "Use only reviewed, trusted sources for training and indexing.",
    ],
    "LLM05": [
        "Treat model output as untrusted; validate/encode it before downstream use.",
        "Disable auto-execution and use schema/allowlist validation for structured output.",
    ],
    "LLM06": [
        "Limit tool scope and permissions to the minimum required (least privilege).",
        "Require human approval for state-changing or high-impact actions.",
    ],
    "LLM07": [
        "Keep secrets and authorization server-side; never place them in the system prompt.",
        "Assume the system prompt can leak and design controls accordingly.",
    ],
    "LLM08": [
        "Enforce per-tenant/per-user access control on vector stores and indexes.",
        "Sanitize and isolate documents before embedding.",
    ],
    "LLM09": [
        "Ground responses in retrieved context and show citations.",
        "Add human review and disclaimers for high-stakes outputs.",
    ],
    "LLM10": [
        "Enforce per-user rate limits, quotas, and token/output caps.",
        "Monitor for abusive usage and add circuit breakers.",
    ],
    "A01:2025": [
        "Enforce server-side authorization on every request and object; deny by default.",
        "Apply least privilege across roles and resources.",
    ],
    "A02:2025": [
        "Harden defaults, disable unused features, and remove verbose error output.",
        "Automate configuration and patch management.",
    ],
    "A03:2025": [
        "Maintain an SBOM, pin dependencies, and scan for known CVEs.",
        "Verify the integrity of third-party components.",
    ],
    "A04:2025": [
        "Enforce TLS in transit and strong encryption at rest.",
        "Use vetted algorithms with proper key management.",
    ],
    "A05:2025": [
        "Use parameterized queries and context-aware output encoding.",
        "Validate and sanitize all untrusted input.",
    ],
    "A06:2025": [
        "Apply threat modeling and secure design patterns early.",
        "Define and test security requirements per feature.",
    ],
    "A07:2025": [
        "Enforce MFA, strong session management, and account lockout.",
        "Eliminate weak or default credentials.",
    ],
    "A08:2025": [
        "Verify integrity (signatures) of code, updates, and critical data.",
        "Protect CI/CD pipelines and unsafe deserialization paths.",
    ],
    "A09:2025": [
        "Centralize security logging and alert on anomalies.",
        "Protect logs and keep secrets/PII out of them.",
    ],
    "A10:2025": [
        "Fail securely and handle errors explicitly without leaking internals.",
        "Validate edge cases and enforce resource limits.",
    ],
    "API1:2023": ["Check object-level ownership/authorization on every access (prevent BOLA)."],
    "API2:2023": ["Use strong, standard authentication with token expiry, rotation, and lockout."],
    "API3:2023": ["Validate which properties a user may read/write; prevent mass assignment."],
    "API4:2023": ["Enforce rate limits, quotas, payload-size limits, and timeouts."],
    "API5:2023": ["Enforce function/route-level role checks; deny by default."],
    "API6:2023": ["Add anti-automation (rate/risk checks) to sensitive business flows."],
    "API7:2023": ["Allowlist outbound URLs and block internal address ranges (prevent SSRF)."],
    "API8:2023": ["Harden API configuration, restrict CORS, and disable verbose errors."],
    "API9:2023": ["Maintain an API inventory; retire or secure old and undocumented endpoints."],
    "API10:2023": ["Validate and sanitize data received from third-party APIs (least trust)."],
}

# One high-impact, low-effort action per code, used to build the quick-wins list.
OWASP_QUICK_WINS = {
    "LLM01": "Isolate the system prompt from user-supplied content.",
    "LLM02": "Redact PII/secrets from prompts, responses, and logs.",
    "LLM03": "Pin model/dependency versions and verify checksums.",
    "LLM04": "Quarantine and review user-supplied content before indexing.",
    "LLM05": "Validate/encode model output before rendering or executing it.",
    "LLM06": "Require human approval for state-changing actions.",
    "LLM07": "Move secrets and authorization out of the system prompt.",
    "LLM08": "Apply per-user access control to the vector store.",
    "LLM09": "Ground answers in retrieved sources and show citations.",
    "LLM10": "Add per-user rate limits and token/output caps.",
    "A01:2025": "Add server-side authorization checks on every endpoint and object.",
    "A02:2025": "Disable debug/verbose errors and harden default configs.",
    "A03:2025": "Pin and scan dependencies (SBOM/SCA).",
    "A04:2025": "Enforce TLS everywhere and encrypt sensitive data at rest.",
    "A05:2025": "Use parameterized queries and strict input validation.",
    "A06:2025": "Threat model the feature and add security acceptance tests.",
    "A07:2025": "Enable MFA and harden session/credential handling.",
    "A08:2025": "Verify signatures/integrity of updates and critical data.",
    "A09:2025": "Centralize security logging and alert on anomalies.",
    "A10:2025": "Fail closed and stop leaking internal error details.",
    "API1:2023": "Enforce per-object ownership checks (BOLA).",
    "API2:2023": "Harden API authentication (standard tokens, expiry, lockout).",
    "API3:2023": "Whitelist allowed request/response fields (no mass assignment).",
    "API4:2023": "Add rate limits, payload caps, and timeouts.",
    "API5:2023": "Enforce role-based checks on every privileged endpoint.",
    "API6:2023": "Add anti-automation to sensitive business flows.",
    "API7:2023": "Allowlist outbound URLs and block internal ranges (SSRF).",
    "API8:2023": "Lock down CORS and disable verbose API errors.",
    "API9:2023": "Inventory APIs and retire undocumented/old endpoints.",
    "API10:2023": "Validate/sanitize data from upstream third-party APIs.",
}

RISK_RANK = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}

# Multi-select options that are mutually exclusive with concrete choices. When a
# concrete option is selected alongside one of these, the exclusive marker is the
# inconsistency and gets dropped (and recorded as a normalization note).
_EXCLUSIVE_OPTIONS = {
    "none",
    "no rag",
    "no sensitive data",
    "unknown",
    "not applicable",
    "no significant trust boundary",
    "no one (static configuration)",
}


def build_risk_analysis(app_root_path, response_payload, extract_payload=None, dfd_payload=None):
    questions = _load_questions(app_root_path)
    raw_answers = _answers_by_flow_id(response_payload)
    answers, normalization_notes = normalize_answers(raw_answers)
    extract_payload = extract_payload if isinstance(extract_payload, dict) else {}
    dfd_payload = dfd_payload if isinstance(dfd_payload, dict) else None

    dread_signals = extract_dread_signals(answers, questions)
    mapped_sections = _mapped_question_risks_by_framework(questions, answers, dfd_payload)
    mapped_risks = [
        risk
        for framework_key in ("owasp_llm", "owasp_web", "owasp_api")
        for risk in mapped_sections[framework_key]
    ]
    extract_risks = _extract_risks(extract_payload)
    unified_risks = unify_risks(extract_risks, mapped_risks)
    status = _overall_status(extract_payload, unified_risks)
    assumptions, missing_information = _assumptions_and_missing(answers, dread_signals, normalization_notes)

    return {
        "overall_status": status,
        "status_source": "DREAD risk model",
        "risk_summary": _risk_summary(unified_risks),
        "risks": unified_risks,
        "mapped_risks": mapped_risks,
        "mapped_risks_by_framework": mapped_sections,
        "owasp_llm": mapped_sections["owasp_llm"],
        "owasp_web": mapped_sections["owasp_web"],
        "owasp_api": mapped_sections["owasp_api"],
        "extract_risks": extract_risks,
        "unified_risks": unified_risks,
        "quick_wins": _quick_wins(unified_risks, extract_payload),
        "assumptions": assumptions,
        "missing_information": missing_information,
        "extraction_payload": extract_payload,
        "dfd_payload": _dfd_summary(dfd_payload),
        "dread_signal_summary": summarize_signals(dread_signals),
        "answers_analyzed": len(answers),
    }


def normalize_answers(raw_answers):
    """Normalize answers for downstream use.

    - de-duplicates multi-select values (preserving order),
    - resolves mutually-exclusive markers ("None", "No RAG", "Unknown", ...): if a
      concrete option is also selected, the exclusive marker is dropped and the
      inconsistency is recorded as a note.

    Returns ``(normalized_answers, notes)``. Never raises - inconsistent answers
    are normalized + flagged, not rejected.
    """
    normalized = {}
    notes = []
    if not isinstance(raw_answers, dict):
        return normalized, notes

    for flow_id, value in raw_answers.items():
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            deduped = list(dict.fromkeys(value))
            concrete = [item for item in deduped if str(item).strip().lower() not in _EXCLUSIVE_OPTIONS]
            exclusive = [item for item in deduped if str(item).strip().lower() in _EXCLUSIVE_OPTIONS]
            if concrete and exclusive:
                notes.append(
                    f"{flow_id}: dropped mutually-exclusive option(s) {exclusive} because concrete options were also selected."
                )
                deduped = concrete
            normalized[flow_id] = deduped[0] if len(deduped) == 1 else deduped
        else:
            normalized[flow_id] = value
    return normalized, notes


def unify_risks(extract_risks, mapped_risks):
    merged = {}

    for risk in extract_risks or []:
        if not isinstance(risk, dict):
            continue
        code = str(risk.get("code") or "").strip().upper()
        if not code:
            continue
        bucket = merged.setdefault(code, _unified_risk_bucket(code, risk.get("name")))
        _merge_risk_level(bucket, risk.get("risk_level"))
        bucket["sources"].add("LLM extract")
        bucket["why"].append(str(risk.get("why") or "").strip())
        bucket["extract_evidence"].extend(_string_list(risk.get("evidence")))
        if risk.get("mitigation"):
            bucket["mitigations"].append(str(risk.get("mitigation")).strip())

    for risk in mapped_risks or []:
        if not isinstance(risk, dict):
            continue
        code = str(risk.get("code") or "").strip().upper()
        if not code:
            continue
        bucket = merged.setdefault(code, _unified_risk_bucket(code, risk.get("name")))
        _merge_risk_level(bucket, risk.get("risk_level"))
        bucket["sources"].add("Questionnaire")
        if risk.get("score") is not None:
            bucket["score"] = max(bucket.get("score") or 0, risk.get("score") or 0)
        if risk.get("dread"):
            bucket["dread"] = risk["dread"]
            bucket["average"] = risk["dread"].get("average")
            bucket["strongest_dimensions"] = risk["dread"].get("strongest_dimensions") or []
        # DREAD-derived (deterministic baseline) is authoritative for the level.
        bucket["risk_level"] = risk.get("risk_level") or bucket["risk_level"]
        evidence = risk.get("evidence") if isinstance(risk.get("evidence"), list) else []
        bucket["question_evidence"].extend(item for item in evidence if isinstance(item, dict))
        bucket["mitigations"].extend(_string_list(risk.get("mitigations")))
        bucket["related_codes"] = _unique_strings(bucket["related_codes"] + _string_list(risk.get("related_codes")))
        bucket["affected_assets"] = _unique_strings(bucket["affected_assets"] + _string_list(risk.get("affected_assets")))
        bucket["missing_information"] = _unique_strings(bucket["missing_information"] + _string_list(risk.get("missing_information")))

    unified = []
    for bucket in merged.values():
        bucket["sources"] = sorted(bucket["sources"])
        bucket["why"] = _unique_strings(bucket["why"])
        bucket["extract_evidence"] = _unique_strings(bucket["extract_evidence"])
        # Context-specific DREAD-aware mitigations first, then deterministic OWASP guidance.
        bucket["mitigations"] = _unique_strings(
            bucket["mitigations"] + OWASP_MITIGATIONS.get(bucket["code"], [])
        )
        unified.append(bucket)

    return sorted(
        unified,
        key=lambda item: (-RISK_RANK.get(item.get("risk_level"), 0), -(item.get("score") or 0), item.get("code", "")),
    )


def suggested_extract_filename(response_file):
    stem = Path(str(response_file)).stem
    safe_stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", stem).strip("-._")
    return f"{safe_stem}-extract.json" if safe_stem else ""


def _mapped_question_risks_by_framework(questions, answers, dfd_payload=None):
    sections = {"owasp_llm": [], "owasp_web": [], "owasp_api": []}
    for risk in _build_candidate_risks(questions, answers, dfd_payload):
        sections.setdefault(risk["framework"], []).append(risk)
    for framework_key, risks in sections.items():
        sections[framework_key] = sorted(
            risks, key=lambda item: (-RISK_RANK.get(item["risk_level"], 0), -item["score"], item["code"])
        )
    return sections


def discover_candidate_risks(questions, answers, dfd_payload=None):
    """Discovery-only deterministic candidate risks (no DREAD, no risk_level).

    Returns the candidate risk families implied by the answers, each grounded in the
    questionnaire evidence that triggered it, with affected DFD assets and per-risk
    missing-information notes - but WITHOUT a DREAD block or risk_level. Scoring is a
    separate, later stage (``score_validated_threats`` in the target pipeline, or
    ``_build_candidate_risks`` for the legacy baseline). Every risk still traces to
    answers: a candidate with no grounded evidence is dropped.
    """
    raw_by_number = _raw_by_number(answers)
    risks = []
    for candidate in candidate_codes(answers):
        code = candidate["code"]
        framework = candidate["framework"]
        evidence = _question_evidence(candidate["evidence_questions"], raw_by_number, questions)
        if not evidence:
            continue
        risks.append(
            {
                "code": code,
                "name": _risk_name(framework, code),
                "framework": framework,
                "related_codes": [code],
                "affected_assets": _affected_assets(code, dfd_payload),
                "missing_information": _risk_missing_information(code, raw_by_number),
                "evidence": evidence,
            }
        )
    return risks


def _build_candidate_risks(questions, answers, dfd_payload=None):
    """Deterministic candidate risks WITH DREAD scoring (legacy baseline path).

    Built on top of ``discover_candidate_risks``: discovery decides which families are
    in scope and grounds them in answers; this layer adds the deterministic DREAD
    block, level, and DREAD-aware mitigations for each one.
    """
    idx = index_answers(answers)
    risks = []
    for candidate in discover_candidate_risks(questions, answers, dfd_payload):
        code = candidate["code"]
        dread = score_code(code, idx)
        affected_assets = candidate["affected_assets"]
        risks.append(
            {
                **candidate,
                "risk_level": dread["band"],
                "score": dread["total"],
                "average": dread["average"],
                "dread": dread,
                "strongest_dimensions": dread.get("strongest_dimensions") or [],
                "mitigations": _dread_aware_mitigations(code, dread, idx, affected_assets),
            }
        )
    return risks


def _question_evidence(question_numbers, raw_by_number, questions):
    evidence = []
    for number in question_numbers:
        if number not in raw_by_number:
            continue
        question = questions.get(number) or {}
        evidence.append(
            {
                "question": f"Q{number}",
                "text": question.get("text", ""),
                "answer": raw_by_number[number],
            }
        )
    return evidence


def _raw_by_number(answers):
    raw = {}
    if not isinstance(answers, dict):
        return raw
    for key, value in answers.items():
        match = re.search(r"(\d+)", str(key))
        if not match or value in (None, "", []):
            continue
        raw[int(match.group(1))] = value
    return raw


# Map a code to DFD node selectors (id prefixes / exact ids) that represent the
# assets it threatens, so each risk points at concrete architecture when a DFD is
# available. Falls back to [] when no DFD is supplied.
_CODE_ASSET_SELECTORS = {
    "LLM01": ("entry_", "llm_gateway", "process_preprocessor", "process_orchestrator"),
    "LLM02": ("store_", "llm_gateway", "process_logging_monitoring"),
    "LLM03": ("external_model_provider", "llm_runtime", "llm_gateway"),
    "LLM04": ("store_vector_db", "process_rag_orchestrator", "store_knowledge_base", "store_documentation"),
    "LLM05": ("process_output_validator", "llm_gateway", "entry_"),
    "LLM06": ("process_tool_layer", "tool_", "business_"),
    "LLM07": ("llm_gateway", "process_orchestrator", "process_tool_layer"),
    "LLM08": ("store_vector_db", "process_rag_orchestrator"),
    "LLM09": ("llm_gateway", "entry_", "business_decisioning"),
    "LLM10": ("entry_", "llm_gateway", "process_tool_layer"),
    "A01:2025": ("entry_", "process_tool_layer", "tool_"),
    "A02:2025": ("entry_", "process_api_connector"),
    "A03:2025": ("external_model_provider", "llm_runtime"),
    "A04:2025": ("entry_", "llm_gateway", "external_model_provider", "store_"),
    "A05:2025": ("process_output_validator", "entry_", "process_preprocessor"),
    "A07:2025": ("entry_",),
    "A08:2025": ("store_vector_db", "process_rag_orchestrator"),
    "A09:2025": ("process_logging_monitoring", "store_llm_logs"),
    "A10:2025": ("process_tool_layer", "process_output_validator"),
    "API1:2023": ("tool_database", "tool_internal_api", "process_tool_layer"),
    "API2:2023": ("entry_rest_api", "entry_"),
    "API3:2023": ("tool_database", "tool_internal_api"),
    "API4:2023": ("entry_rest_api", "process_tool_layer"),
    "API5:2023": ("tool_internal_api", "tool_admin", "process_tool_layer"),
    "API6:2023": ("business_", "process_tool_layer"),
    "API7:2023": ("process_api_connector", "external_network", "external_api"),
    "API8:2023": ("entry_", "process_api_connector"),
    "API9:2023": ("tool_internal_api", "process_api_connector"),
    "API10:2023": ("process_api_connector", "external_api", "external_web"),
}


def _affected_assets(code, dfd_payload):
    if not isinstance(dfd_payload, dict):
        return []
    nodes = dfd_payload.get("nodes")
    if not isinstance(nodes, list):
        return []
    selectors = _CODE_ASSET_SELECTORS.get(code.upper(), ())
    if not selectors:
        return []
    labels = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        data = node.get("data") or {}
        if (data.get("nodeType") == "trust_boundary"):
            continue
        if any(node_id == sel or node_id.startswith(sel) for sel in selectors):
            labels.append(data.get("label") or node_id)
    return _unique_strings(labels)[:6]


# Per-code key questions whose Unknown/absence weakens confidence in that risk.
_RISK_KEY_QUESTIONS = {
    "LLM01": (30, 84),
    "LLM02": (24, 32, 88),
    "LLM06": (16, 44, 80),
    "LLM07": (45,),
    "LLM08": (36,),
    "LLM10": (77, 78),
    "A01:2025": (26, 28),
    "A04:2025": (73,),
    "API6:2023": (80,),
    "API7:2023": (63,),
}


def _risk_missing_information(code, raw_by_number):
    notes = []
    for number in _RISK_KEY_QUESTIONS.get(code.upper(), ()):
        value = raw_by_number.get(number)
        if value is None:
            notes.append(f"Q{number} was not provided; risk assessment for {code} is less certain.")
        elif _value_is_unknown(value):
            notes.append(f"Q{number} is Unknown; risk assessment for {code} is less certain.")
    return notes


def _value_is_unknown(value):
    values = value if isinstance(value, list) else [value]
    return bool(values) and all(str(item).strip().lower() == "unknown" for item in values)


def _dread_aware_mitigations(code, dread, idx, affected_assets):
    """Context-specific mitigations driven by which DREAD dimensions are high and
    the answers that drove them (spec: mitigation consumes dimension scores + evidence,
    not just the overall level)."""
    recs = []
    asset_hint = f" (affected: {', '.join(affected_assets[:3])})" if affected_assets else ""

    if dread.get("damage", 0) >= 3:
        if _has(idx, 87, "severe impact", "high business", "financial", "legal", "regulatory"):
            recs.append("Add business-impact-specific controls (approval, segregation of duties, transaction limits) given the high business/regulatory impact (Q87).")
        if _has(idx, 88, "without clear deletion controls"):
            recs.append("Define retention limits and deletion controls for prompts, responses, memory, logs, and vector data (Q88).")
    if dread.get("reproducibility", 0) >= 3:
        if _has(idx, 91, "without strong controls"):
            recs.append("Add replay protection: nonces/idempotency keys and fresh authorization for state-changing or sensitive actions (Q91).")
        if _has(idx, 90, "no testing performed", "basic manual testing only"):
            recs.append("Introduce adversarial-prompt / jailbreak / tool-misuse regression testing (Q90).")
    if dread.get("affected_users", 0) >= 3:
        if _has(idx, 86, "multiple tenants", "public internet scale"):
            recs.append("Enforce tenant isolation and blast-radius reduction (scoped credentials, per-tenant limits) for the multi-tenant/public scale (Q86).")
    if dread.get("exploitability", 0) >= 3:
        if _risky_input_formats(idx) and _weak_parsing(idx):
            recs.append("Use strict parsers, file validation, sandboxing, content normalization, and instruction/data isolation for the risky input formats (Q83/Q84).")
        if _has(idx, 2, "anonymous public") or _has(idx, 25, "no authentication"):
            recs.append("Require authentication and least privilege on the public-facing surface.")
    if dread.get("discoverability", 0) >= 3:
        recs.append(f"Reduce exposure and add authentication, rate limiting, and security monitoring for exposed interfaces{asset_hint}.")

    return recs


def _risk_summary(unified_risks):
    summary = {level: 0 for level in ("Critical", "High", "Medium", "Low")}
    for risk in unified_risks:
        level = str(risk.get("risk_level") or "").strip().title()
        if level in summary:
            summary[level] += 1
    summary["total"] = len([risk for risk in unified_risks if isinstance(risk, dict)])
    return summary


def _assumptions_and_missing(answers, dread_signals, normalization_notes):
    raw_by_number = _raw_by_number(answers)
    assumptions = [
        "Risk levels are computed deterministically from DREAD (Damage, Reproducibility, "
        "Exploitability, Affected users, Discoverability); OWASP codes are secondary labels.",
    ]
    assumptions.extend(normalization_notes)

    missing = []
    # Spec-mandated backward-compatibility messages for the new (Q83-Q91) questions.
    gap_messages = {
        83: "Input format details were not provided.",
        84: "Input parsing/validation behavior was not provided.",
        85: "Authoritative component inventory (Q85) was not provided; the DFD relies on inferred components.",
        86: "User/tenant scale was not provided.",
        87: "Business/regulatory impact was not provided.",
        88: "Data retention behavior was not provided.",
        89: "Incident-response process information was not provided.",
        90: "Adversarial/jailbreak testing information was not provided.",
        91: "Replay/reproducibility behavior was not provided.",
    }
    for number, message in gap_messages.items():
        if number not in raw_by_number:
            missing.append(message)

    missing.extend(dread_signals.get("confidence_notes") or [])
    return _unique_strings(assumptions), _unique_strings(missing)


def _dfd_summary(dfd_payload):
    if not isinstance(dfd_payload, dict):
        return None
    nodes = dfd_payload.get("nodes") if isinstance(dfd_payload.get("nodes"), list) else []
    edges = dfd_payload.get("edges") if isinstance(dfd_payload.get("edges"), list) else []
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": [
            {
                "id": node.get("id"),
                "label": (node.get("data") or {}).get("label") or node.get("id"),
                "nodeType": (node.get("data") or {}).get("nodeType"),
            }
            for node in nodes
            if isinstance(node, dict)
        ],
    }


def _extract_risks(extract_payload):
    top_risks = extract_payload.get("top_risks")
    if not isinstance(top_risks, list):
        return []

    risks = []
    for risk in top_risks:
        if not isinstance(risk, dict):
            continue

        code = str(risk.get("code") or "").strip().upper()
        if code not in OWASP_LLM_2025:
            continue

        risks.append(
            {
                "code": code,
                "name": str(risk.get("name") or OWASP_LLM_2025[code]).strip(),
                "risk_level": _normalize_level(risk.get("risk_level")) or "Medium",
                "why": str(risk.get("why") or "").strip(),
                "evidence": _string_list(risk.get("evidence")),
                "mitigation": str(risk.get("mitigation") or "").strip(),
            }
        )

    return sorted(risks, key=lambda item: (-RISK_RANK.get(item["risk_level"], 0), item["code"]))


def _overall_status(extract_payload, unified_risks):
    levels = [risk.get("risk_level") for risk in unified_risks if isinstance(risk, dict)]
    extract_status = _normalize_level(extract_payload.get("overall_posture"))
    if extract_status:
        levels.append(extract_status)
    ranked = [level for level in levels if level in RISK_RANK]
    if not ranked:
        return "Low"
    return max(ranked, key=lambda level: RISK_RANK[level])


def _unified_risk_bucket(code, name):
    return {
        "code": code,
        "name": str(name or OWASP_LLM_2025.get(code) or code).strip(),
        "risk_level": "Low",
        "score": 0,
        "average": None,
        "dread": None,
        "strongest_dimensions": [],
        "related_codes": [code] if code else [],
        "affected_assets": [],
        "missing_information": [],
        "sources": set(),
        "why": [],
        "extract_evidence": [],
        "question_evidence": [],
        "mitigations": [],
    }


def _merge_risk_level(bucket, level):
    normalized = _normalize_level(level) or "Medium"
    current_rank = RISK_RANK.get(bucket.get("risk_level"), 0)
    if RISK_RANK.get(normalized, 0) > current_rank:
        bucket["risk_level"] = normalized


def _unique_strings(values):
    seen = set()
    result = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _load_questions(app_root_path):
    questions_path = _resolve_questions_path(app_root_path)
    raw_questions = json.loads(questions_path.read_text(encoding="utf-8"))
    questions = raw_questions.get("questions") if isinstance(raw_questions, dict) else raw_questions
    if not isinstance(questions, list):
        return {}
    return {
        int(question["id"]): question
        for question in questions
        if isinstance(question, dict) and str(question.get("id", "")).isdigit()
    }


def _resolve_questions_path(app_root_path):
    app_root_path = Path(app_root_path)
    candidates = [
        app_root_path / "questions" / "questionsDb.json",
        app_root_path.parent / "TM-Questions" / "questionsDb.json",
        app_root_path.parent / "questions" / "questionsDb.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to find questionsDb.json.")


def _answers_by_flow_id(response_payload):
    if not isinstance(response_payload, dict):
        return {}

    compact_answers = response_payload.get("answers_by_flow_id")
    if isinstance(compact_answers, dict):
        return compact_answers

    answers = response_payload.get("answers")
    if not isinstance(answers, list):
        return {}

    normalized = {}
    for answer_record in answers:
        if not isinstance(answer_record, dict):
            continue

        flow_id = answer_record.get("flow_id")
        answer = answer_record.get("answer")
        if isinstance(flow_id, str) and flow_id.strip() and answer not in (None, "", []):
            normalized[flow_id.strip()] = answer

    return normalized


def _question_number(flow_id):
    match = re.search(r"(\d+)", str(flow_id))
    return int(match.group(1)) if match else None


def _question_label(flow_id):
    number = _question_number(flow_id)
    return f"Q{number}" if number is not None else str(flow_id)


def _normalize_level(value):
    text = str(value or "").strip().lower()
    levels = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "med": "Medium",
        "low": "Low",
    }
    return levels.get(text)


def _string_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _quick_wins(unified_risks, extract_payload):
    # Keep any LLM-provided quick wins first, then add deterministic, code-keyed
    # quick wins for the highest-priority risks so the list is never empty.
    wins = list(_string_list(extract_payload.get("quick_wins")))
    prioritized = [
        risk for risk in unified_risks
        if isinstance(risk, dict) and risk.get("risk_level") in ("Critical", "High")
    ]
    if not prioritized:
        prioritized = [risk for risk in unified_risks if isinstance(risk, dict)][:3]
    for risk in prioritized:
        win = OWASP_QUICK_WINS.get(str(risk.get("code") or "").strip().upper())
        if win:
            wins.append(win)
    return _unique_strings(wins)[:8]


def _risk_name(framework_key, code):
    if framework_key == "owasp_llm":
        return OWASP_LLM_2025.get(code, code)
    if framework_key == "owasp_web":
        return OWASP_WEB_2025.get(code, code)
    if framework_key == "owasp_api":
        return OWASP_API_2023.get(code, code)
    return code


# --- target-order pipeline (template-guided LLM threat identification) -------


def score_validated_threats(validated_primary, answers, deterministic_by_code):
    """Static DREAD scoring for validated primary threats (stage 6).

    DREAD is computed deterministically via ``score_code`` (the LLM never scores).
    Each validated threat is turned into a unified-risk-compatible dict: it keeps the
    grounded questionnaire evidence and deterministic mitigations of its candidate,
    and gains the threat-identification fields (status, threat_pattern, affected
    nodes/edges, abuse_path, control_gap, confidence). risk_level always comes from
    the DREAD band - never from the LLM.
    """
    idx = index_answers(answers)
    deterministic_by_code = deterministic_by_code or {}
    scored = []
    for threat in validated_primary or []:
        if not isinstance(threat, dict):
            continue
        code = str(threat.get("code") or "").strip().upper()
        if not code:
            continue
        dread = score_code(code, idx)
        candidate = deterministic_by_code.get(code, {})
        framework = candidate.get("framework") or _framework(code)
        affected_assets = candidate.get("affected_assets") or []
        evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), list) else []
        scored.append(
            {
                "code": code,
                "name": threat.get("name") or candidate.get("name") or _risk_name(framework, code),
                "framework": framework,
                "risk_level": dread["band"],
                "score": dread["total"],
                "average": dread["average"],
                "dread": dread,
                "strongest_dimensions": dread.get("strongest_dimensions") or [],
                "related_codes": [code],
                "affected_assets": affected_assets,
                "missing_information": _unique_strings(
                    (candidate.get("missing_information") or []) + (threat.get("missing_information") or [])
                ),
                "evidence": evidence,
                "question_evidence": evidence,
                "sources": ["Questionnaire", "LLM threat identification"],
                "mitigations": _unique_strings(
                    _dread_aware_mitigations(code, dread, idx, affected_assets) + OWASP_MITIGATIONS.get(code, [])
                ),
                # threat-identification fields (the LLM's semantic contribution)
                "status": threat.get("status"),
                "threat_pattern": threat.get("threat_pattern"),
                "affected_nodes": threat.get("affected_nodes") or [],
                "affected_edges": threat.get("affected_edges") or [],
                "abuse_path": threat.get("abuse_path") or [],
                "control_gap": threat.get("control_gap") or "",
                "confidence": threat.get("confidence"),
                "llm_evidence": threat.get("evidence") or [],
            }
        )
    return sorted(
        scored,
        key=lambda item: (-RISK_RANK.get(item.get("risk_level"), 0), -(item.get("score") or 0), item.get("code", "")),
    )


def build_threat_analysis(app_root_path, response_payload, dfd_graph, app_config=None):
    """Target-order risk analysis with template-guided local-LLM threat identification.

    Order: deterministic discovery -> LLM threat identification -> deterministic
    grounding validation -> deterministic DREAD scoring of validated primary threats
    -> LLM mitigation generation. Returns a risks.json-shaped dict that preserves the
    backward-compatible ``unified_risks`` structure. Raises
    ``ThreatIdentificationUnavailable`` when the LLM identification stage is
    unavailable, so the caller can fall back to the deterministic baseline.
    """
    questions = _load_questions(app_root_path)
    raw_answers = _answers_by_flow_id(response_payload)
    answers, normalization_notes = normalize_answers(raw_answers)
    dfd_graph = dfd_graph if isinstance(dfd_graph, dict) else {}

    dread_signals = extract_dread_signals(answers, questions)
    deterministic_risks = discover_candidate_risks(questions, answers, dfd_graph)
    assumptions, missing_information = _assumptions_and_missing(answers, dread_signals, normalization_notes)

    # Local-LLM request timeout (per chat call). qwen3:8b "thinks" before emitting
    # JSON, so the heavier mitigation call can exceed a short timeout; make it
    # configurable (env/app config) with a generous default for slower models.
    llm_timeout = config_int(app_config, "LLM_REQUEST_TIMEOUT", 400)
    identification = identify_threats(app_root_path, raw_answers, deterministic_risks, {}, dfd_graph, app_config, timeout=llm_timeout)
    if identification.get("status") == "unavailable":
        raise ThreatIdentificationUnavailable(identification.get("error") or "Threat identification unavailable.")

    validation = validate_threats(identification, dfd_graph, deterministic_risks)
    deterministic_by_code = {risk["code"]: risk for risk in deterministic_risks}
    unified_risks = score_validated_threats(validation["primary_threats"], answers, deterministic_by_code)

    # Mitigation generation runs only on validated, scored threats; best-effort.
    if flag_enabled(app_config, "LLM_MITIGATION_GENERATION_ENABLED", True) and unified_risks:
        mitigation_result = generate_mitigations(app_root_path, unified_risks, raw_answers, dfd_graph, app_config, timeout=llm_timeout)
    else:
        mitigation_result = {
            "status": "disabled" if unified_risks else "skipped",
            "mitigations": [],
            "quick_wins": [],
            "assumptions": [],
            "missing_information": [],
        }

    structured_mitigations = mitigation_result.get("mitigations") or []
    _attach_mitigation_actions(unified_risks, structured_mitigations)

    sections = _grouped_by_framework(unified_risks)
    quick_wins = _quick_wins(unified_risks, {"quick_wins": mitigation_result.get("quick_wins")})
    assumptions = _unique_strings(assumptions + _string_list(mitigation_result.get("assumptions")))
    missing_information = _unique_strings(missing_information + _string_list(mitigation_result.get("missing_information")))

    return {
        "overall_status": _overall_status({}, unified_risks),
        "status_source": "Template-guided LLM threat identification + deterministic DREAD",
        "pipeline_mode": "llm_threat_identification_v1",
        "risk_summary": _risk_summary(unified_risks),
        "risks": unified_risks,
        "mapped_risks": unified_risks,
        "mapped_risks_by_framework": sections,
        "owasp_llm": sections["owasp_llm"],
        "owasp_web": sections["owasp_web"],
        "owasp_api": sections["owasp_api"],
        "extract_risks": [],
        "unified_risks": unified_risks,
        "deterministic_risks": deterministic_risks,
        "identified_threats": validation["primary_threats"] + validation["downgraded_threats"],
        "suggested_secondary_findings": validation["secondary_findings"],
        "unaddressed_candidates": validation.get("unaddressed_candidates", []),
        "threat_validation_report": validation["report"],
        "mitigations": structured_mitigations,
        "mitigation_meta": {
            "status": mitigation_result.get("status"),
            "model": mitigation_result.get("model"),
            "error": mitigation_result.get("error"),
        },
        "quick_wins": quick_wins,
        "assumptions": assumptions,
        "missing_information": missing_information,
        "extraction_payload": {},
        "dfd_payload": _dfd_summary(dfd_graph),
        "dread_signal_summary": summarize_signals(dread_signals),
        "answers_analyzed": len(answers),
        "threat_identification": {
            "mode": "template_guided_llm",
            "status": identification.get("status"),
            "model": identification.get("model"),
            "chunks_total": identification.get("chunks_total"),
            "chunks_succeeded": identification.get("chunks_succeeded"),
            "message": (
                f"{len(validation['primary_threats'])} validated primary, "
                f"{len(validation['downgraded_threats'])} downgraded, "
                f"{len(validation['secondary_findings'])} secondary findings, "
                f"{len(validation.get('unaddressed_candidates', []))} unaddressed candidates."
            ),
            "primary_count": len(validation["primary_threats"]),
            "downgraded_count": len(validation["downgraded_threats"]),
            "secondary_count": len(validation["secondary_findings"]),
            "unaddressed_count": len(validation.get("unaddressed_candidates", [])),
        },
    }


def _grouped_by_framework(risks):
    sections = {"owasp_llm": [], "owasp_web": [], "owasp_api": []}
    for risk in risks:
        framework = risk.get("framework") or _framework(str(risk.get("code") or ""))
        sections.setdefault(framework, []).append(risk)
    return sections


def _attach_mitigation_actions(risks, structured_mitigations):
    by_code = {}
    for mitigation in structured_mitigations or []:
        code = str(mitigation.get("risk_code") or "").strip().upper()
        if code:
            by_code.setdefault(code, []).append(mitigation)
    for risk in risks:
        actions = by_code.get(str(risk.get("code") or "").strip().upper())
        if actions:
            risk["mitigation_actions"] = actions
