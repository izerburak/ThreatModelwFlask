import json
import re
from collections import defaultdict
from pathlib import Path

from app.services.dread_scoring import index_answers, score_code


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

# Deterministic, OWASP-code-keyed mitigation guidance. Kept reproducible and
# LLM-independent so the tool always shows actionable controls for each risk.
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

LEGACY_RISK_CONTEXT_TO_OWASP_LLM = {
    "prompt_injection": ["LLM01"],
    "untrusted_input": ["LLM01"],
    "malicious_content": ["LLM01"],
    "data_leakage": ["LLM02"],
    "data_exposure": ["LLM02"],
    "privacy": ["LLM02"],
    "credential_exposure": ["LLM02"],
    "supply_chain": ["LLM03"],
    "data_poisoning": ["LLM04"],
    "vector_poisoning": ["LLM04", "LLM08"],
    "retrieval_leakage": ["LLM08", "LLM02"],
    "unsafe_output": ["LLM05"],
    "output_injection": ["LLM05"],
    "execution_risk": ["LLM05", "LLM06"],
    "excessive_agency": ["LLM06"],
    "unauthorized_actions": ["LLM06"],
    "privilege_escalation": ["LLM06"],
    "over_permission": ["LLM06"],
    "prompt_leakage": ["LLM07"],
    "misuse": ["LLM09"],
    "overreliance": ["LLM09"],
    "dos": ["LLM10"],
    "abuse": ["LLM10"],
    "attack_surface": ["LLM10"],
}


def build_risk_analysis(app_root_path, response_payload, extract_payload=None):
    questions = _load_questions(app_root_path)
    answers = _answers_by_flow_id(response_payload)
    extract_payload = extract_payload if isinstance(extract_payload, dict) else {}

    mapped_sections = _mapped_question_risks_by_framework(questions, answers)
    mapped_risks = [
        risk
        for framework_key in ("owasp_llm", "owasp_web", "owasp_api")
        for risk in mapped_sections[framework_key]
    ]
    extract_risks = _extract_risks(extract_payload)
    unified_risks = unify_risks(extract_risks, mapped_risks)
    status = _overall_status(extract_payload, unified_risks)

    return {
        "overall_status": status,
        "status_source": "Combined risk model",
        "mapped_risks": mapped_risks,
        "mapped_risks_by_framework": mapped_sections,
        "owasp_llm": mapped_sections["owasp_llm"],
        "owasp_web": mapped_sections["owasp_web"],
        "owasp_api": mapped_sections["owasp_api"],
        "extract_risks": extract_risks,
        "unified_risks": unified_risks,
        "quick_wins": _quick_wins(unified_risks, extract_payload),
        "answers_analyzed": len(answers),
    }


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
        evidence = risk.get("evidence") if isinstance(risk.get("evidence"), list) else []
        bucket["question_evidence"].extend(item for item in evidence if isinstance(item, dict))

    unified = []
    for bucket in merged.values():
        bucket["sources"] = sorted(bucket["sources"])
        bucket["why"] = _unique_strings(bucket["why"])
        bucket["extract_evidence"] = _unique_strings(bucket["extract_evidence"])
        # Any LLM-provided mitigations come first, then deterministic OWASP guidance.
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


def _mapped_question_risks_by_framework(questions, answers):
    return {
        framework_key: _mapped_question_risks(questions, answers, framework_key)
        for framework_key in ("owasp_llm", "owasp_web", "owasp_api")
    }


def _mapped_question_risks(questions, answers, framework_key="owasp_llm"):
    # Code discovery + evidence here; the risk level/score come from the
    # deterministic DREAD scorer (dread_scoring.score_code) applied per code to
    # the questionnaire answers. The legacy impact/likelihood figures are kept on
    # each risk for reference, but DREAD drives risk_level. See dread_scoring.py.
    grouped = defaultdict(lambda: {"impact": 0, "likelihood": 0.0, "evidence": []})

    for flow_id, answer in answers.items():
        question = questions.get(_question_number(flow_id))
        if not question:
            continue

        codes = _question_codes(question, framework_key)
        if not codes:
            continue

        severity = _int_value(question.get("severity_weight"), default=1)
        confidence = _int_value(question.get("confidence_weight"), default=1)
        polarity, factor = _answer_polarity(question, answer)
        likelihood = confidence * factor
        evidence = {
            "question": _question_label(flow_id),
            "text": question.get("text", ""),
            "answer": answer,
            "severity_weight": severity,
            "confidence_weight": confidence,
            "polarity": polarity,
            "likelihood": round(likelihood, 2),
        }
        if question.get("category"):
            evidence["category"] = question.get("category")
        if question.get("scope"):
            evidence["scope"] = _string_list(question.get("scope"))
        if question.get("dfd_impact"):
            evidence["dfd_impact"] = _string_list(question.get("dfd_impact"))
        if question.get("risk_context"):
            evidence["risk_context"] = _string_list(question.get("risk_context"))

        for code in codes:
            code = str(code or "").strip().upper()
            if not code:
                continue
            bucket = grouped[code]
            # Worst-case path drives the rating: strongest impact and the highest
            # (least-mitigated) likelihood among the answers that map to this code.
            bucket["impact"] = max(bucket["impact"], severity)
            bucket["likelihood"] = max(bucket["likelihood"], likelihood)
            bucket["evidence"].append(evidence)

    idx = index_answers(answers)
    risks = []
    for code, bucket in grouped.items():
        dread = score_code(code, idx)
        risks.append(
            {
                "code": code,
                "name": _risk_name(framework_key, code),
                "framework": framework_key,
                "risk_level": dread["band"],
                "score": dread["total"],
                "dread": dread,
                "impact": bucket["impact"],
                "likelihood": round(bucket["likelihood"], 2),
                "evidence": bucket["evidence"],
            }
        )

    return sorted(risks, key=lambda item: (-RISK_RANK.get(item["risk_level"], 0), -item["score"], item["code"]))


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
        "dread": None,
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


def _calibrated_level(impact, likelihood):
    # OWASP Risk Rating style severity matrix: impact and (polarity-adjusted)
    # likelihood are each bucketed into LOW/MED/HIGH bands on the 1-5 scale and
    # combined, so Critical needs high impact AND high likelihood.
    matrix = {
        ("HIGH", "HIGH"): "Critical",
        ("HIGH", "MED"): "High",
        ("MED", "HIGH"): "High",
        ("HIGH", "LOW"): "Medium",
        ("MED", "MED"): "Medium",
        ("LOW", "HIGH"): "Medium",
        ("MED", "LOW"): "Low",
        ("LOW", "MED"): "Low",
        ("LOW", "LOW"): "Low",
    }
    return matrix[(_risk_band(impact), _risk_band(likelihood))]


def _risk_band(value):
    if value >= 3.5:
        return "HIGH"
    if value >= 2.0:
        return "MED"
    return "LOW"


# --- Answer polarity (OWASP-style likelihood adjustment) ---------------------
# Factors multiply the question's confidence_weight to produce a bounded likelihood.
_POLARITY_FACTORS = {"aggravating": 1.0, "neutral": 0.4, "mitigating": 0.2}

# Phrases that signal a control is in place / a safe choice (lower likelihood).
# Checked BEFORE the aggravating list so "No, human approval is always required"
# is read as mitigating rather than matching a bare "no ...".
_MITIGATING_MARKERS = (
    "enforced end to end",
    "encryption is enforced",
    "all sensitive communication is encrypted",
    "strict schema",
    "schema validation",
    "strict blocking",
    "allowlist",
    "allowlisting",
    "human approval is always required",
    "always required",
    "human in the loop",
    "role based access control",
    "rbac",
    "single sign on",
    "multi factor",
    "no rag",
    "no sensitive data",
    "no third party",
    "no external api content",
    "no outbound network",
    "no arbitrary url",
    "internal employees only",
    "administrators only",
    "local system processes only",
    "internal service to service",
    "service to service",
    "self hosted on internal",
    "account based rate",
    "generate text responses only",
    "indexing only",
    "no informational use only",
    "rule based",
    "technical validation",
    "redacted",
    "masked",
    "none",
)
# Phrases that signal a real weakness / increased exposure (raise likelihood).
_AGGRAVATING_MARKERS = (
    "anonymous public",
    "no authentication",
    "arbitrary urls",
    "internal addresses may be reachable",
    "logs contain full prompts",
    "shared service account",
    "unrestricted",
    "unknown",
    "no or unclear",
    "unclear encryption",
    "not logged",
    "no rate limit",
    "no preprocessing",
    "no input filtering",
    "both indexing and training",
    "execute workflows",
    "modify system configurations",
    "refunds or payments",
)
# Per-question disambiguation for short yes/no answers where the generic lexicon
# cannot tell direction. Keyed by question number.
_QUESTION_POLARITY_HINTS = {
    4: {"mitigating": ("no",), "aggravating": ("yes", "unknown")},
    14: {"mitigating": ("via backend", "no"), "aggravating": ("directly", "unknown")},
    16: {"mitigating": ("always required", "human approval"), "aggravating": ("yes",)},
    28: {"mitigating": ("strongly limited", "yes"), "aggravating": ("no",)},
}


def _answer_polarity(question, answer):
    values = answer if isinstance(answer, list) else [answer]
    normalized = [_normalize_polarity_text(value) for value in values if value not in (None, "")]
    if not normalized:
        return "neutral", _POLARITY_FACTORS["neutral"]

    number = _question_number(question.get("id"))
    hints = _QUESTION_POLARITY_HINTS.get(number, {})
    labels = [_classify_polarity_value(text, hints) for text in normalized]

    # Worst case wins: any weak answer dominates a mitigating one (e.g. a multi-select
    # that exposes the system to anonymous users even if employees are also listed).
    if "aggravating" in labels:
        return "aggravating", _POLARITY_FACTORS["aggravating"]
    if "mitigating" in labels:
        return "mitigating", _POLARITY_FACTORS["mitigating"]
    return "neutral", _POLARITY_FACTORS["neutral"]


def _classify_polarity_value(text, hints):
    if _marker_hit(text, hints.get("mitigating", ())):
        return "mitigating"
    if _marker_hit(text, hints.get("aggravating", ())):
        return "aggravating"
    if _marker_hit(text, _MITIGATING_MARKERS):
        return "mitigating"
    if _marker_hit(text, _AGGRAVATING_MARKERS):
        return "aggravating"
    return "neutral"


def _marker_hit(text, markers):
    return any(marker in text for marker in markers)


def _normalize_polarity_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


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


def _question_codes(question, framework_key):
    codes = _string_list(question.get(framework_key))
    if codes or framework_key != "owasp_llm":
        return [str(code).strip().upper() for code in codes if str(code).strip()]

    legacy_codes = []
    for context in _string_list(question.get("risk_context")):
        legacy_codes.extend(LEGACY_RISK_CONTEXT_TO_OWASP_LLM.get(context.strip().lower(), []))
    return _unique_strings(legacy_codes)


def _int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
