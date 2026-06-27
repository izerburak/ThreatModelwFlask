"""DREAD signal extraction layer.

Turns raw questionnaire answers into a structured bag of *evidence signals* per
DREAD dimension, plus an impact profile and a scale profile. This sits between
the questionnaire and the scorer: the scorer (`dread_scoring`) consumes the same
answers to produce numbers, while this module produces the human-readable,
auditable "why" behind each dimension and surfaces confidence gaps.

Each signal is grounded in a concrete question/answer and classified as one of:

    "risky"      - the answer increases risk on this dimension
    "mitigating" - the answer is a control that reduces risk
    "safe"       - the answer indicates the dimension is not in play
    "unknown"    - the answer is Unknown / absent (raises uncertainty)

``dread_weights`` from the question catalog (when supplied) are attached as the
signal *importance* - NOT as a severity. Weights never get blindly summed; the
selected answer decides whether a signal is risky/safe/mitigating/unknown.
"""

from app.services.dread_scoring import _norm, index_answers


# Each rule: question number -> (dimensions, polarity classifier, note).
# The classifier returns "risky" | "mitigating" | "safe" | "unknown" | None
# (None => the answer is neutral / not a signal worth recording).
def _classify(markers):
    """Build a classifier from {polarity: (marker, ...)} checked in order."""
    order = ("risky", "mitigating", "safe")

    def classifier(values):
        joined = " ".join(values)
        if not joined.strip():
            return "unknown"
        if any(_norm(m) in joined for m in markers.get("unknown", ())) or joined.strip() == "unknown":
            return "unknown"
        for polarity in order:
            for marker in markers.get(polarity, ()):
                if _norm(marker) in joined:
                    return polarity
        return markers.get("default")

    return classifier


# Ordered so the dominant (worst) phrase wins when several markers match.
_RULES = {
    4: (("damage",), _classify({"risky": ("yes",), "safe": ("no",), "unknown": ("unknown",)}),
        "Processes sensitive or business-critical data."),
    24: (("damage", "affected_users"), _classify({"safe": ("no sensitive data",), "risky": ("personally identifiable", "api keys", "credentials", "customer support records", "internal operational")}),
         "Sensitive data categories reachable by the LLM."),
    15: (("damage", "exploitability"), _classify({"risky": ("execute workflows", "modify system", "send emails", "create or update"), "safe": ("generate text responses only",)}),
         "Actions the LLM can trigger."),
    16: (("damage",), _classify({"risky": ("business critical", "low risk actions only"), "mitigating": ("human approval is always required",), "unknown": ("unknown",)}),
         "Can affect real-world state without human approval."),
    45: (("damage", "exploitability"), _classify({"risky": ("api keys", "credentials"), "safe": ("no access to secrets",)}),
         "Runtime access to secrets / credentials."),
    26: (("reproducibility",), _classify({"risky": ("no authorization",), "mitigating": ("role based", "attribute", "policy")}),
         "Authorization enforcement for LLM access."),
    30: (("exploitability",), _classify({"risky": ("no safeguards", "basic input filtering only"), "mitigating": ("context isolation", "instruction hierarchy", "detection", "scanning")}),
         "Prompt-injection safeguards."),
    2: (("exploitability", "discoverability", "affected_users"), _classify({"risky": ("anonymous public",), "mitigating": ("administrators only", "local system processes", "internal employees only")}),
        "Who can directly reach the system."),
    25: (("exploitability",), _classify({"risky": ("no authentication",), "mitigating": ("single sign on", "api keys or tokens", "username password")}),
         "User authentication before interacting."),
    40: (("affected_users",), _classify({"risky": ("weak or unclear",), "mitigating": ("single tenant", "strong isolation")}),
         "Tenancy / isolation model."),
    46: (("affected_users",), _classify({"risky": ("no isolation", "session level isolation only"), "mitigating": ("user level isolation", "tenant level isolation")}),
         "Conversation/memory isolation."),
    68: (("affected_users",), _classify({"risky": ("shared stores may affect", "may affect other users"), "safe": ("no shared indexing",), "mitigating": ("isolation and review",)}),
         "Shared indexes/caches affecting other users."),
    76: (("discoverability",), _classify({"risky": ("detailed internal errors",), "mitigating": ("sanitized error handling",)}),
         "Error handling / information leakage."),
    59: (("discoverability",), _classify({"risky": ("non production or undocumented", "some non production"), "mitigating": ("only approved production",)}),
         "Reachability of debug/undocumented APIs."),
    33: (("discoverability",), _classify({"risky": ("no logging or monitoring",), "mitigating": ("security monitoring with alerts",)}),
         "Logging / monitoring of interactions."),
    # --- new questions (Q83-Q91) ---
    83: (("exploitability",), _classify({"risky": ("html", "code or scripts", "documents", "images", "audio", "xml", "yaml", "markdown", "rendered content"), "safe": ("plain text prompts only",)}),
         "Input formats accepted (parser/injection surface)."),
    84: (("exploitability", "reproducibility"), _classify({"risky": ("minimal validation", "no parsing or transformation"), "mitigating": ("strict validation and normalization",)}),
         "Parsing/validation of submitted input before the LLM context."),
    86: (("affected_users", "damage"), _classify({"risky": ("multiple tenants", "public internet scale"), "mitigating": ("single user", "local only", "small internal group")}),
         "Approximate user/tenant scale."),
    87: (("damage", "affected_users"), _classify({"risky": ("high business", "financial", "legal", "regulatory", "severe impact", "large scale data breach", "fraud", "critical service disruption", "moderate business disruption"), "mitigating": ("minimal operational impact", "internal inconvenience")}),
         "Maximum business / regulatory impact."),
    88: (("damage", "affected_users"), _classify({"risky": ("without clear deletion controls", "long term retention with access controls"), "mitigating": ("not retained", "session only retention", "automatic deletion")}),
         "Retention of prompts/responses/logs/vector data."),
    89: (("damage", "discoverability"), _classify({"mitigating": ("periodically tested", "automated containment", "kill switch", "documented process"), "risky": ("no defined process", "informal manual response only")}),
         "Incident-response maturity for LLM misuse."),
    90: (("reproducibility", "exploitability", "discoverability"), _classify({"risky": ("no testing performed", "basic manual testing only"), "mitigating": ("formal red team", "continuous adversarial testing", "regression tests", "internal adversarial testing")}),
         "Adversarial / jailbreak / tool-misuse testing."),
    91: (("reproducibility", "exploitability"), _classify({"risky": ("without strong controls", "may be replayed with safeguards"), "mitigating": ("replay is blocked", "fresh authorization", "read only behavior can be replayed")}),
         "Replay / reproducibility of malicious input."),
}

_DIMENSION_KEYS = {
    "damage": "damage_signals",
    "reproducibility": "reproducibility_signals",
    "exploitability": "exploitability_signals",
    "affected_users": "affected_users_signals",
    "discoverability": "discoverability_signals",
}

# Questions important enough that an Unknown/absent answer should lower confidence.
_IMPORTANT_FOR_CONFIDENCE = {
    16: "authority over business-critical actions",
    26: "authorization enforcement",
    24: "sensitive data exposure",
    40: "tenant isolation",
    44: "tool permission separation",
    86: "user/tenant scale",
    87: "business/regulatory impact",
    91: "replay / reproducibility behaviour",
}


def extract_dread_signals(answers, questions=None):
    """Build the structured DREAD signal object from raw questionnaire answers."""
    idx = index_answers(answers)
    raw = _raw_answer_map(answers)
    questions = questions if isinstance(questions, dict) else {}

    result = {key: [] for key in _DIMENSION_KEYS.values()}
    result["impact_profile"] = {}
    result["scale_profile"] = {}
    result["confidence_notes"] = []

    for number, (dimensions, classifier, note) in _RULES.items():
        values = idx.get(number)
        present = number in raw
        polarity = classifier(values) if values else ("unknown" if present else "absent")
        if polarity in (None, "absent"):
            continue
        weights = (questions.get(number) or {}).get("dread_weights") if questions else None
        for dimension in dimensions:
            signal = {
                "question": f"Q{number}",
                "answer": raw.get(number),
                "note": note,
                "polarity": polarity,
            }
            if isinstance(weights, dict) and dimension in weights:
                signal["importance"] = weights.get(dimension)
            result[_DIMENSION_KEYS[dimension]].append(signal)

    result["impact_profile"] = _impact_profile(idx, raw)
    result["scale_profile"] = _scale_profile(idx, raw)
    result["confidence_notes"] = _confidence_notes(idx, raw)
    return result


def summarize_signals(signals):
    """Compact counts per dimension for the report header."""
    summary = {}
    for dimension, key in _DIMENSION_KEYS.items():
        entries = signals.get(key) or []
        summary[dimension] = {
            "risky": sum(1 for s in entries if s.get("polarity") == "risky"),
            "mitigating": sum(1 for s in entries if s.get("polarity") == "mitigating"),
            "unknown": sum(1 for s in entries if s.get("polarity") == "unknown"),
            "total": len(entries),
        }
    summary["impact_profile"] = signals.get("impact_profile") or {}
    summary["scale_profile"] = signals.get("scale_profile") or {}
    summary["confidence_notes"] = signals.get("confidence_notes") or []
    return summary


def _impact_profile(idx, raw):
    profile = {}
    if 87 in raw:
        profile["business_impact"] = raw.get(87)
    if 4 in raw:
        profile["sensitive_data"] = raw.get(4)
    if 88 in raw:
        profile["retention"] = raw.get(88)
    if 24 in raw:
        profile["data_categories"] = raw.get(24)
    return profile


def _scale_profile(idx, raw):
    profile = {}
    if 86 in raw:
        profile["user_tenant_scale"] = raw.get(86)
    if 40 in raw:
        profile["tenancy"] = raw.get(40)
    if 2 in raw:
        profile["reachable_by"] = raw.get(2)
    return profile


def _confidence_notes(idx, raw):
    notes = []
    for number, label in _IMPORTANT_FOR_CONFIDENCE.items():
        values = idx.get(number)
        if number not in raw:
            notes.append(f"Q{number} ({label}) was not answered; risk for related dimensions is uncertain.")
        elif values and all("unknown" in value for value in values):
            notes.append(f"Q{number} ({label}) is Unknown; risk for related dimensions is uncertain.")
    return notes


def _raw_answer_map(answers):
    """Map question number -> original (un-normalized) answer value."""
    import re

    raw = {}
    if not isinstance(answers, dict):
        return raw
    for key, value in answers.items():
        match = re.search(r"(\d+)", str(key))
        if not match:
            continue
        if value in (None, "", []):
            continue
        raw[int(match.group(1))] = value
    return raw
