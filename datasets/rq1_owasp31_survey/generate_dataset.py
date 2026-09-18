"""Build the survey-grounded RQ1 OWASP classification bootstrap dataset.

The output is intentionally deterministic.  Each class has ten scenario groups
with five variants per group.  Groups, rather than individual rows, are assigned
to train/validation/test so close variants cannot cross split boundaries.
"""

from __future__ import annotations

import json
import random
from pathlib import Path


SEED = 20260918
ROWS_PER_LABEL = 50
VARIANTS_PER_GROUP = 5

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
QUESTIONS_PATH = PROJECT_ROOT / "app" / "questions" / "questionsDb.json"
DATASET_PATH = HERE / "owasp31_survey_single_label.jsonl"
CATALOG_PATH = HERE / "label_catalog.json"


def spec(label, name, framework, version, signals):
    return {
        "label": label,
        "name": name,
        "framework": framework,
        "version": version,
        "signals": signals,
    }


# Values below are exact options from questionsDb.json.  LLM entries use the
# 2026 OWASP ordering; the survey predicates in the application still use the
# 2025 ordering, so the mapping here follows category meaning rather than the
# old numeric position.
LABEL_SPECS = [
    spec("LLM01:2026", "Prompt Injection", "owasp_llm", "2026", {
        6: ["File uploads", "Web URLs", "Email or ticket data", "Public repositories"],
        20: ["Yes, through retrieved documents or memory", "Yes, through tool outputs or metadata", "Yes, through prompt templates or variables"],
        30: ["No safeguards", "Basic input filtering only"],
        83: ["Markdown or rich text", "HTML or rendered content", "Documents such as PDF, DOCX, or TXT", "Images or multimodal input", "Audio or transcribed speech"],
        84: ["Yes, parsed with basic validation only", "Yes, parsed and inserted with minimal validation", "No parsing or transformation is performed"],
        90: ["No testing performed", "Basic manual testing only"],
    }),
    spec("LLM02:2026", "Sensitive Information Disclosure", "owasp_llm", "2026", {
        4: ["Yes"],
        24: ["Personally identifiable information (PII)", "API keys or credentials", "Internal operational documents", "Customer support records"],
        32: ["No safeguards", "Basic redaction or masking"],
        47: ["Logs contain full prompts and responses"],
        88: ["Long-term retention without clear deletion controls", "Long-term retention with access controls"],
        46: ["No isolation", "Session-level isolation only"],
    }),
    spec("LLM03:2026", "Excessive Agency", "owasp_llm", "2026", {
        11: ["Framework", "Agent workflow"],
        12: ["Database", "Internal APIs", "Admin tools"],
        15: ["Create or update tickets/records", "Send emails or notifications", "Execute workflows or transactions", "Modify system configurations"],
        16: ["Yes, in low-risk actions only", "Yes, in business-critical actions"],
        39: ["Yes, moderate-impact decisions", "Yes, high-impact or business-critical decisions"],
        44: ["No separation of permissions", "Basic separation (read vs write)"],
        80: ["Basic confirmation only", "No additional controls"],
        91: ["Some state-changing actions may be replayed with safeguards", "State-changing or sensitive actions can be replayed without strong controls"],
    }),
    spec("LLM04:2026", "Supply Chain", "owasp_llm", "2026", {
        17: ["Third-party cloud API", "Hosted by external vendor in private environment", "Hybrid deployment"],
        18: ["Yes, different models for separate tasks", "Yes, fallback or routing between models"],
        35: ["No validation process", "Manual trust in vendor/source"],
        42: ["Administrators via admin panel", "Automated systems or pipelines"],
        71: ["Informally tracked", "Not tracked"],
    }),
    spec("LLM05:2026", "Data and Model Poisoning", "owasp_llm", "2026", {
        6: ["File uploads", "Web URLs", "Public repositories"],
        8: ["Internal knowledge base", "Documentation", "Customer data", "Source code"],
        43: ["Yes, for indexing only", "Yes, for training or fine-tuning", "Yes, both indexing and training"],
        68: ["Yes, with partial isolation", "Yes, shared stores may affect other users"],
        69: ["Partially protected", "No dedicated protection"],
        71: ["Informally tracked", "Not tracked"],
    }),
    spec("LLM06:2026", "Unbounded Consumption", "owasp_llm", "2026", {
        2: ["Anonymous public internet users", "Authenticated public users"],
        34: ["No protections", "Basic request throttling"],
        77: ["Basic global limits only", "Partial or inconsistent limits", "No effective limits"],
        78: ["Yes, partially bounded", "Yes, with weak or unclear limits"],
        86: ["Multiple tenants or customer groups", "Public internet-scale user base"],
    }),
    spec("LLM07:2026", "Misinformation", "owasp_llm", "2026", {
        1: ["Customer support assistant", "Automated data analysis or summarization", "Agent or workflow automation component"],
        22: ["User-facing web interface", "API response consumed by other systems", "Directly used in backend automation"],
        31: ["Not validated", "Manual review only"],
        37: ["Misinformation or unsafe recommendations"],
        39: ["Yes, moderate-impact decisions", "Yes, high-impact or business-critical decisions"],
        87: ["High business, financial, legal, or regulatory impact", "Severe impact such as large-scale data breach, fraud, or critical service disruption"],
    }),
    spec("LLM08:2026", "Hidden Context Exposure", "owasp_llm", "2026", {
        19: ["Hardcoded in application logic", "Stored in configuration files", "Dynamically generated at runtime"],
        20: ["Yes, through retrieved documents or memory", "Yes, through tool outputs or metadata", "Yes, through prompt templates or variables"],
        24: ["API keys or credentials", "Internal operational documents"],
        45: ["Access to limited non-sensitive configuration", "Access to sensitive data such as API keys or credentials"],
        47: ["Logs contain full prompts and responses"],
        76: ["Partial sanitization", "Detailed internal errors may be exposed"],
    }),
    spec("LLM09:2026", "Vector and Embedding Weaknesses", "owasp_llm", "2026", {
        8: ["Internal knowledge base", "Documentation", "Customer data", "Source code"],
        13: ["Vector DB"],
        27: ["Partially enforced", "No filtering applied"],
        36: ["Partially protected", "No dedicated protection"],
        46: ["No isolation", "Session-level isolation only"],
        68: ["Yes, with partial isolation", "Yes, shared stores may affect other users"],
        69: ["Partially protected", "No dedicated protection"],
    }),
    spec("LLM10:2026", "Improper Output Handling", "owasp_llm", "2026", {
        21: ["Markdown or rich text", "Structured JSON", "Code or scripts", "HTML or rendered content"],
        22: ["User-facing web interface", "API response consumed by other systems", "Directly used in backend automation"],
        31: ["Not validated", "Manual review only"],
        64: ["HTML/rich content without reliable sanitization"],
        65: ["Yes, with partial validation", "Yes, directly used with minimal validation"],
        66: ["Partially blocked", "No dedicated controls"],
    }),
    spec("A01:2025", "Broken Access Control", "owasp_web", "2025", {
        26: ["No authorization controls", "Hardcoded application logic"],
        28: ["Partially limited", "No, same behavior for all users"],
        49: ["Partially separated", "No, shared with general application routes"],
        50: ["No, only checked at initial login", "No authentication or session context exists"],
        53: ["Yes, with partial authorization checks", "Yes, without reliable object-level checks"],
        70: ["Yes, with basic controls", "Yes, controls are weak or unclear"],
    }),
    spec("A02:2025", "Security Misconfiguration", "owasp_web", "2025", {
        49: ["Partially separated", "No, shared with general application routes"],
        52: ["Broad but intentional allowlist", "Wildcard or overly permissive CORS"],
        70: ["Yes, with basic controls", "Yes, controls are weak or unclear"],
        72: ["Shared long-lived credentials", "Hardcoded or exposed secrets"],
        76: ["Partial sanitization", "Detailed internal errors may be exposed"],
    }),
    spec("A03:2025", "Software Supply Chain Failures", "owasp_web", "2025", {
        17: ["Third-party cloud API", "Hosted by external vendor in private environment", "Hybrid deployment"],
        18: ["Yes, different models for separate tasks", "Yes, fallback or routing between models"],
        35: ["No validation process", "Manual trust in vendor/source"],
        42: ["Administrators via admin panel", "Automated systems or pipelines"],
        71: ["Informally tracked", "Not tracked"],
        90: ["No testing performed", "Basic manual testing only"],
    }),
    spec("A04:2025", "Cryptographic Failures", "owasp_web", "2025", {
        24: ["Personally identifiable information (PII)", "API keys or credentials", "Customer support records"],
        45: ["Access to sensitive data such as API keys or credentials"],
        72: ["Environment/config secrets with limited scope", "Shared long-lived credentials", "Hardcoded or exposed secrets"],
        73: ["Partially encrypted", "No or unclear encryption between some components"],
        81: ["Browser to web application", "Web application to backend/API", "Backend/API to external providers"],
        82: ["Browser to web application", "Web application to backend/API", "Backend/API to external providers", "Logging or monitoring pipeline"],
    }),
    spec("A05:2025", "Injection", "owasp_web", "2025", {
        21: ["Structured JSON", "Code or scripts", "HTML or rendered content"],
        31: ["Not validated", "Manual review only"],
        64: ["HTML/rich content without reliable sanitization"],
        65: ["Yes, with partial validation", "Yes, directly used with minimal validation"],
        66: ["Partially blocked", "No dedicated controls"],
        83: ["Structured JSON", "XML or YAML", "HTML or rendered content", "Code or scripts"],
        84: ["Yes, parsed and inserted with minimal validation", "No parsing or transformation is performed"],
    }),
    spec("A06:2025", "Insecure Design", "owasp_web", "2025", {
        37: ["Sensitive data extraction", "Unauthorized action triggering", "Misinformation or unsafe recommendations"],
        38: ["Lack of security ownership", "Weak access control hygiene", "No incident response process for LLM misuse"],
        39: ["Yes, moderate-impact decisions", "Yes, high-impact or business-critical decisions"],
        57: ["Partially reviewed", "No formal review"],
        79: ["Refunds or payments", "Account/profile changes", "Approvals or entitlement changes"],
        80: ["Basic confirmation only", "No additional controls"],
        90: ["No testing performed", "Basic manual testing only"],
        91: ["State-changing or sensitive actions can be replayed without strong controls"],
    }),
    spec("A07:2025", "Authentication Failures", "owasp_web", "2025", {
        2: ["Anonymous public internet users", "Authenticated public users"],
        25: ["No authentication required", "Username/password login"],
        41: ["No identity propagation", "Shared system identity only"],
        50: ["No, only checked at initial login", "No authentication or session context exists"],
        56: ["Yes, broad shared service account"],
    }),
    spec("A08:2025", "Software or Data Integrity Failures", "owasp_web", "2025", {
        35: ["No validation process", "Manual trust in vendor/source"],
        42: ["Administrators via admin panel", "Automated systems or pipelines"],
        43: ["Yes, for indexing only", "Yes, for training or fine-tuning", "Yes, both indexing and training"],
        68: ["Yes, with partial isolation", "Yes, shared stores may affect other users"],
        69: ["Partially protected", "No dedicated protection"],
        71: ["Informally tracked", "Not tracked"],
    }),
    spec("A09:2025", "Security Logging and Alerting Failures", "owasp_web", "2025", {
        33: ["No logging or monitoring", "Basic application logs only"],
        38: ["Insufficient monitoring", "No incident response process for LLM misuse"],
        74: ["Logged without alerting", "Basic application logs only", "Not logged"],
        89: ["No defined process", "Informal manual response only", "Documented process but not tested"],
        90: ["No testing performed", "Basic manual testing only"],
    }),
    spec("A10:2025", "Mishandling of Exceptional Conditions", "owasp_web", "2025", {
        31: ["Not validated", "Manual review only"],
        66: ["Partially blocked", "No dedicated controls"],
        75: ["Some non-critical failures may continue safely", "Failures may fall back to less restricted behavior"],
        76: ["Partial sanitization", "Detailed internal errors may be exposed"],
        89: ["No defined process", "Informal manual response only"],
    }),
    spec("API1:2023", "Broken Object Level Authorization", "owasp_api", "2023", {
        26: ["No authorization controls", "Hardcoded application logic"],
        41: ["No identity propagation", "Shared system identity only"],
        50: ["No, only checked at initial login", "No authentication or session context exists"],
        53: ["Yes, with partial authorization checks", "Yes, without reliable object-level checks"],
        56: ["Yes, broad shared service account"],
    }),
    spec("API2:2023", "Broken Authentication", "owasp_api", "2023", {
        2: ["Anonymous public internet users", "Authenticated public users"],
        25: ["No authentication required", "Username/password login", "API keys or tokens"],
        41: ["No identity propagation", "Shared system identity only"],
        50: ["No, only checked at initial login", "No authentication or session context exists"],
        56: ["Yes, broad shared service account"],
    }),
    spec("API3:2023", "Broken Object Property Level Authorization", "owasp_api", "2023", {
        31: ["Not validated", "Manual review only"],
        41: ["No identity propagation", "Shared system identity only"],
        53: ["Yes, with partial authorization checks", "Yes, without reliable object-level checks"],
        54: ["Yes, with partial validation", "Yes, fields can be read or updated without strong controls"],
        65: ["Yes, with partial validation", "Yes, directly used with minimal validation"],
    }),
    spec("API4:2023", "Unrestricted Resource Consumption", "owasp_api", "2023", {
        2: ["Anonymous public internet users", "Authenticated public users"],
        34: ["No protections", "Basic request throttling"],
        77: ["Basic global limits only", "Partial or inconsistent limits", "No effective limits"],
        78: ["Yes, partially bounded", "Yes, with weak or unclear limits"],
        86: ["Multiple tenants or customer groups", "Public internet-scale user base"],
    }),
    spec("API5:2023", "Broken Function Level Authorization", "owasp_api", "2023", {
        26: ["No authorization controls", "Hardcoded application logic"],
        28: ["Partially limited", "No, same behavior for all users"],
        41: ["No identity propagation", "Shared system identity only"],
        44: ["No separation of permissions", "Basic separation (read vs write)"],
        55: ["Yes, through a shared backend service account", "Yes, privileged functions may be reachable without strong checks"],
        56: ["Yes, broad shared service account"],
        57: ["Partially reviewed", "No formal review"],
    }),
    spec("API6:2023", "Unrestricted Access to Sensitive Business Flows", "owasp_api", "2023", {
        15: ["Create or update tickets/records", "Send emails or notifications", "Execute workflows or transactions"],
        16: ["Yes, in low-risk actions only", "Yes, in business-critical actions"],
        39: ["Yes, moderate-impact decisions", "Yes, high-impact or business-critical decisions"],
        79: ["Refunds or payments", "Account/profile changes", "Notifications or external messages", "Approvals or entitlement changes", "Ticket escalation or priority changes"],
        80: ["Basic confirmation only", "No additional controls"],
        91: ["Some state-changing actions may be replayed with safeguards", "State-changing or sensitive actions can be replayed without strong controls"],
    }),
    spec("API7:2023", "Server Side Request Forgery", "owasp_api", "2023", {
        14: ["Directly", "Via backend"],
        62: ["Partially restricted", "Arbitrary URLs or internal addresses may be reachable"],
        63: ["Partially restricted", "No outbound restrictions"],
        60: ["Basic validation only", "Inserted directly into prompt context"],
        57: ["Partially reviewed", "No formal review"],
    }),
    spec("API8:2023", "Security Misconfiguration", "owasp_api", "2023", {
        52: ["Broad but intentional allowlist", "Wildcard or overly permissive CORS"],
        59: ["Possibly, but restricted", "Yes, some non-production or undocumented APIs are reachable"],
        63: ["Partially restricted", "No outbound restrictions"],
        70: ["Yes, with basic controls", "Yes, controls are weak or unclear"],
        72: ["Shared long-lived credentials", "Hardcoded or exposed secrets"],
        76: ["Partial sanitization", "Detailed internal errors may be exposed"],
    }),
    spec("API9:2023", "Improper Inventory Management", "owasp_api", "2023", {
        57: ["Partially reviewed", "No formal review"],
        58: ["Partial inventory", "No reliable inventory"],
        59: ["Possibly, but restricted", "Yes, some non-production or undocumented APIs are reachable"],
        71: ["Informally tracked", "Not tracked"],
        89: ["No defined process", "Informal manual response only"],
    }),
    spec("API10:2023", "Unsafe Consumption of APIs", "owasp_api", "2023", {
        14: ["Directly", "Via backend"],
        60: ["Basic validation only", "Inserted directly into prompt context"],
        61: ["Yes, with basic filtering only", "Yes, inserted without isolation"],
        62: ["Only allowlisted domains are reachable", "Partially restricted", "Arbitrary URLs or internal addresses may be reachable"],
        63: ["Partially restricted", "No outbound restrictions"],
        84: ["Yes, parsed with basic validation only", "Yes, parsed and inserted with minimal validation", "No parsing or transformation is performed"],
    }),
]


FRAMEWORK_CONTEXT = {
    "owasp_llm": {
        1: ["Customer support assistant", "Developer documentation assistant", "Internal productivity assistant", "Automated data analysis or summarization", "Agent or workflow automation component"],
        3: ["Web-based chat interface", "REST API endpoint", "Internal service-to-service calls", "CLI or local scripts", "Third-party integration"],
        40: ["Single-tenant system", "Multi-tenant with strong isolation"],
        85: ["LLM orchestrator", "External model provider API", "Backend API", "Logging or monitoring pipeline"],
        86: ["Small internal group", "Single organization or tenant", "Multiple tenants or customer groups"],
        87: ["Internal inconvenience or low business impact", "Moderate business disruption or customer impact", "High business, financial, legal, or regulatory impact"],
    },
    "owasp_web": {
        1: ["Customer support assistant", "Internal productivity assistant", "Agent or workflow automation component"],
        3: ["Web-based chat interface", "REST API endpoint"],
        40: ["Single-tenant system", "Multi-tenant with strong isolation"],
        48: ["Public chat page", "Authenticated user dashboard", "Admin/operator panel", "Embedded widget or iframe"],
        85: ["Web frontend", "Backend API", "LLM orchestrator", "Logging or monitoring pipeline"],
        86: ["Small internal group", "Single organization or tenant", "Multiple tenants or customer groups"],
        87: ["Internal inconvenience or low business impact", "Moderate business disruption or customer impact", "High business, financial, legal, or regulatory impact"],
    },
    "owasp_api": {
        1: ["Customer support assistant", "Automated data analysis or summarization", "Agent or workflow automation component"],
        3: ["REST API endpoint", "Internal service-to-service calls", "Third-party integration"],
        40: ["Single-tenant system", "Multi-tenant with strong isolation"],
        85: ["API gateway", "Backend API", "LLM orchestrator", "Tool execution runtime", "External model provider API"],
        86: ["Small internal group", "Single organization or tenant", "Multiple tenants or customer groups"],
        87: ["Internal inconvenience or low business impact", "Moderate business disruption or customer impact", "High business, financial, legal, or regulatory impact"],
    },
}


SAFE_SIGNALS = {
    1: ["Developer documentation assistant", "Internal productivity assistant", "Experimental or research feature"],
    2: ["Internal employees only", "Administrators only", "Local system processes only"],
    3: ["Web-based chat interface", "REST API endpoint", "Internal service-to-service calls", "CLI or local scripts"],
    4: ["No"],
    6: ["User text input only"],
    7: ["Input filtering", "Prompt templating"],
    8: ["No RAG"],
    10: ["No", "Session only"],
    11: ["None", "Basic logic"],
    12: ["None"],
    13: ["None"],
    14: ["No"],
    15: ["Generate text responses only"],
    16: ["No, human approval is always required"],
    17: ["Self-hosted on internal infrastructure"],
    18: ["No, a single model is used"],
    19: ["Stored in configuration files", "Managed through database or admin panel"],
    20: ["No"],
    21: ["Plain text only"],
    22: ["User-facing web interface", "Internal admin dashboard"],
    24: ["No sensitive data"],
    25: ["Single sign-on (SSO)", "Internal network authentication"],
    26: ["Role-based access control (RBAC)", "Attribute- or policy-based controls"],
    27: ["Yes, consistently enforced"],
    28: ["Yes, strongly limited"],
    30: ["Context isolation and instruction hierarchy controls", "Prompt injection detection or scanning"],
    31: ["Rule-based or schema validation", "Human-in-the-loop plus technical validation"],
    32: ["Access controls and scoped retrieval", "DLP or content inspection mechanisms"],
    33: ["Security monitoring with alerts"],
    34: ["Rate limits plus abuse/anomaly detection"],
    35: ["Security review and supply chain controls"],
    36: ["Yes, strongly protected", "Not applicable"],
    39: ["No, informational use only"],
    40: ["Single-tenant system", "Multi-tenant with strong isolation"],
    41: ["User identity consistently enforced end-to-end"],
    42: ["No one (static configuration)", "Developers only"],
    43: ["No reuse"],
    44: ["Granular permissions including admin or destructive actions"],
    45: ["No access to secrets or hidden data"],
    46: ["User-level isolation", "Tenant-level isolation"],
    47: ["No logging of LLM data", "Logs contain non-sensitive metadata only"],
    48: ["None"],
    49: ["Yes, clearly separated and protected"],
    50: ["Yes, revalidated on every sensitive request"],
    51: ["Yes, CSRF/origin protections are enforced", "Not applicable"],
    52: ["Strict allowlist with credentials handled safely", "No cross-origin access"],
    53: ["No object identifiers are user-controlled", "Yes, with object-level authorization checks"],
    54: ["No field-level control by the LLM", "Yes, with strict field-level authorization"],
    55: ["No privileged API functions are reachable", "Yes, but permission checks follow the current user"],
    56: ["No, calls use user-scoped identity", "Yes, but permissions are tightly scoped"],
    57: ["Yes, reviewed and minimized"],
    58: ["Yes, complete inventory and classification"],
    59: ["No, only approved production APIs"],
    60: ["Validated, normalized, and treated as untrusted data", "No third-party API data used"],
    61: ["No external API content enters prompt context", "Yes, but instruction/data separation is enforced"],
    62: ["No arbitrary URL fetching is possible", "Only allowlisted domains are reachable"],
    63: ["Yes, strict egress allowlist", "No outbound network access"],
    64: ["Plain text only", "Markdown with sanitization", "HTML/rich content with sanitization"],
    65: ["No structured output drives downstream operations", "Yes, with strict schema and allowlists"],
    66: ["Yes, strict blocking or allowlisting", "Not applicable"],
    67: ["Strict file type, size, malware, and content validation", "No file uploads"],
    68: ["No shared indexing or cache exists", "Yes, with tenant/user isolation and review"],
    69: ["Yes, strong write controls and review", "No RAG sources"],
    70: ["No admin interface exists", "Yes, with strong authentication and authorization"],
    71: ["Yes, versioned with approval and audit trail"],
    72: ["Dedicated secret manager with least privilege"],
    73: ["Yes, encryption is enforced end-to-end where applicable"],
    74: ["Yes, with security alerts and privacy controls"],
    75: ["No, failures are fail-closed"],
    76: ["No, sanitized error handling is enforced"],
    77: ["Yes, per user/tenant/client with anomaly detection"],
    78: ["No expensive operations are user-triggerable", "Yes, but bounded by quotas and timeouts"],
    79: ["No sensitive business flows"],
    80: ["Yes, risk-based approval or step-up controls", "Not applicable"],
    81: ["All sensitive communication is encrypted"],
    82: ["No sensitive data is transmitted"],
    83: ["Plain text prompts only"],
    84: ["Yes, parsed with strict validation and normalization"],
    85: ["Web frontend", "API gateway", "Backend API", "LLM orchestrator", "Logging or monitoring pipeline"],
    86: ["Single user or local-only use", "Small internal group"],
    87: ["Minimal operational impact", "Internal inconvenience or low business impact"],
    88: ["Not retained", "Short-term retention with automatic deletion"],
    89: ["Documented and periodically tested process", "Automated containment, escalation, and kill-switch mechanisms exist"],
    90: ["Formal red-team or security review performed", "Continuous adversarial testing or regression tests are in place"],
    91: ["No, replay is blocked or requires fresh authorization", "Only low-risk read-only behavior can be replayed"],
}


def load_questions():
    raw = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return {int(item["id"]): item for item in raw}


def choose_answer(question, candidates, rng):
    value = rng.choice(candidates)
    if question["type"] == "multi":
        values = [value]
        remaining = [candidate for candidate in candidates if candidate != value]
        if remaining and rng.random() < 0.28:
            values.append(rng.choice(remaining))
        return values
    return value


def split_for_group(group_index):
    if group_index <= 7:
        return "train"
    if group_index == 8:
        return "validation"
    return "test"


def render_input(answers, questions):
    lines = []
    for qid in sorted(answers):
        answer = answers[qid]
        answer_text = "; ".join(answer) if isinstance(answer, list) else answer
        lines.append(f"Q{qid}. {questions[qid]['text']}\nAnswer: {answer_text}")
    return "\n\n".join(lines)


def build_positive_record(label_spec, group_index, variant_index, questions):
    group_rng = random.Random(f"{SEED}:{label_spec['label']}:group:{group_index}")
    variant_rng = random.Random(f"{SEED}:{label_spec['label']}:{group_index}:{variant_index}")

    signal_ids = sorted(label_spec["signals"])
    signal_count = min(len(signal_ids), 4 + (group_index % 3 == 0))
    core_ids = sorted(group_rng.sample(signal_ids, signal_count))

    answers = {
        qid: choose_answer(questions[qid], label_spec["signals"][qid], variant_rng)
        for qid in core_ids
    }

    context = FRAMEWORK_CONTEXT[label_spec["framework"]]
    available_context_ids = [qid for qid in context if qid not in answers]
    # Q3 and Q85 make the application surface explicit.  This is important for
    # semantically overlapping labels such as LLM06 vs API4 resource consumption
    # and Web A02 vs API8 security misconfiguration.
    required_context_ids = [qid for qid in (3, 85) if qid in available_context_ids]
    remaining_context_ids = [qid for qid in available_context_ids if qid not in required_context_ids]
    optional_count = min(1, len(remaining_context_ids))
    context_ids = sorted(required_context_ids + variant_rng.sample(remaining_context_ids, optional_count))
    for qid in context_ids:
        answers[qid] = choose_answer(questions[qid], context[qid], variant_rng)

    return answers, core_ids, context_ids


def no_threat_plan():
    """Return 50 hard negatives mirroring all 30 positive label families.

    Interleaving LLM/Web/API labels gives every split examples from all three
    surfaces.  Variable group sizes preserve the 35/5/10 class split while each
    mirrored label remains wholly inside one split.
    """
    interleaved = []
    for offset in range(10):
        interleaved.extend((LABEL_SPECS[offset], LABEL_SPECS[10 + offset], LABEL_SPECS[20 + offset]))

    plan = []
    for position, mirror_spec in enumerate(interleaved, start=1):
        if position <= 21:
            split = "train"
            variant_count = 2 if position <= 14 else 1
        elif position <= 24:
            split = "validation"
            variant_count = 2 if position <= 23 else 1
        else:
            split = "test"
            variant_count = 2 if position <= 28 else 1
        for variant_index in range(1, variant_count + 1):
            plan.append((position, variant_index, split, mirror_spec))
    if len(plan) != ROWS_PER_LABEL:
        raise ValueError(f"Expected {ROWS_PER_LABEL} NO_THREAT rows, got {len(plan)}")
    return plan


def build_safe_record(mirror_spec, group_index, variant_index, questions):
    """Build a hard negative with the mirrored class's question pattern.

    The question presence resembles a positive record, but every answer is a
    strong/neutral control. Questions that offer only weakness choices (for
    example Q38) are excluded because they cannot truthfully form a negative.
    """
    rng = random.Random(f"{SEED}:NO_THREAT:{mirror_spec['label']}:{group_index}:{variant_index}")
    safe_signal_ids = sorted(qid for qid in mirror_spec["signals"] if qid in SAFE_SIGNALS)
    # Include the complete safe counterpart pool for the mirrored class.  With
    # only one or two negatives per positive class, sampling a subset could leave
    # a question globally positive-only and create another presence shortcut.
    core_ids = safe_signal_ids
    answers = {
        qid: choose_answer(questions[qid], SAFE_SIGNALS[qid], rng)
        for qid in core_ids
    }

    context = FRAMEWORK_CONTEXT[mirror_spec["framework"]]
    required_context_ids = [qid for qid in (3, 85) if qid not in answers]
    remaining_context_ids = [
        qid for qid in context
        if qid not in answers and qid not in required_context_ids
    ]
    optional_context_ids = rng.sample(remaining_context_ids, min(1, len(remaining_context_ids)))
    context_ids = sorted(required_context_ids + optional_context_ids)
    for qid in context_ids:
        candidates = SAFE_SIGNALS.get(qid, context[qid])
        answers[qid] = choose_answer(questions[qid], candidates, rng)
    return answers, core_ids, context_ids


def validate_answer_options(questions, answers):
    for qid, answer in answers.items():
        values = answer if isinstance(answer, list) else [answer]
        invalid = [value for value in values if value not in questions[qid]["options"]]
        if invalid:
            raise ValueError(f"Q{qid} contains invalid values: {invalid}")


def build_dataset():
    questions = load_questions()
    specs = LABEL_SPECS + [spec("NO_THREAT", "No concrete threat", "none", None, {})]
    records = []
    seen_inputs = set()
    global_index = 1

    for label_position, label_spec in enumerate(specs, start=1):
        range_start = global_index
        if label_spec["label"] == "NO_THREAT":
            record_plan = no_threat_plan()
        else:
            record_plan = [
                (group_index, variant_index, split_for_group(group_index), None)
                for group_index in range(1, 11)
                for variant_index in range(1, VARIANTS_PER_GROUP + 1)
            ]

        for group_index, variant_index, split, mirror_spec in record_plan:
            if mirror_spec is not None:
                answers, evidence_ids, context_ids = build_safe_record(
                    mirror_spec, group_index, variant_index, questions
                )
                scenario_group = (
                    f"NO_THREAT-MIRROR-{mirror_spec['label'].replace(':', '_')}-G{group_index:02d}"
                )
            else:
                answers, evidence_ids, context_ids = build_positive_record(
                    label_spec, group_index, variant_index, questions
                )
                scenario_group = f"{label_spec['label'].replace(':', '_')}-G{group_index:02d}"
            validate_answer_options(questions, answers)
            input_text = render_input(answers, questions)
            if input_text in seen_inputs:
                raise ValueError(f"Duplicate model input at row {global_index}")
            seen_inputs.add(input_text)

            answer_map = {f"Q{qid}": answers[qid] for qid in sorted(answers)}
            records.append({
                "id": f"OWASP31-{global_index:04d}",
                "index": global_index,
                "split": split,
                "scenario_group": scenario_group,
                "variant": variant_index,
                "task": "survey_grounded_single_label_classification",
                "input_text": input_text,
                "answers_by_flow_id": answer_map,
                "evidence_question_ids": [f"Q{qid}" for qid in evidence_ids],
                "context_question_ids": [f"Q{qid}" for qid in context_ids],
                "label": label_spec["label"],
                "label_name": label_spec["name"],
                "framework": label_spec["framework"],
                "framework_version": label_spec["version"],
                "hard_negative_for": mirror_spec["label"] if mirror_spec is not None else None,
                "provenance": {
                    "kind": "survey_grounded_synthetic_bootstrap",
                    "survey": "app/questions/questionsDb.json",
                    "generator": "datasets/rq1_owasp31_survey/generate_dataset.py",
                    "human_validated": False,
                },
            })
            global_index += 1

        label_spec["range_start"] = range_start
        label_spec["range_end"] = global_index - 1

    expected = len(specs) * ROWS_PER_LABEL
    if len(records) != expected:
        raise ValueError(f"Expected {expected} records, got {len(records)}")

    DATASET_PATH.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    catalog = []
    for item in specs:
        catalog_item = {key: value for key, value in item.items() if key != "signals"}
        source_ids = sorted(item["signals"]) if item["signals"] else sorted(SAFE_SIGNALS)
        catalog_item["survey_question_ids"] = [f"Q{qid}" for qid in source_ids]
        catalog.append(catalog_item)
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return records


def main():
    records = build_dataset()
    split_counts = {}
    for record in records:
        split_counts[record["split"]] = split_counts.get(record["split"], 0) + 1
    print(f"Wrote {len(records)} records to {DATASET_PATH}")
    print(f"Split counts: {split_counts}")
    print(f"Wrote label catalog to {CATALOG_PATH}")


if __name__ == "__main__":
    main()
