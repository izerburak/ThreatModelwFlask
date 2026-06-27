"""Deterministic DREAD risk scoring for the questionnaire.

Each candidate risk is scored on the five DREAD dimensions
(Damage, Reproducibility, Exploitability, Affected users, Discoverability),
each 1-3, summed to 5-15. The risk level is derived from the DREAD *average*
(total / 5, range 1.0-3.0):

    2.7-3.0 -> Critical    2.2-2.6 -> High    1.5-2.1 -> Medium    1.0-1.4 -> Low

(equivalent total cut-offs: 14-15 Critical, 11-13 High, 8-10 Medium, 5-7 Low.)

Scores are derived ONLY from questionnaire answers, so they are reproducible
and auditable (no analyst judgement, no hand-set per-question weights). OWASP
codes are kept only as secondary labels for each risk - DREAD is the scoring
engine.

Design:
  * Exploitability / Affected users / Discoverability are *system exposure*
    properties (global to the deployment): who can reach the system, how it is
    authenticated, tenancy, web surface, input formats and parsing (Q83/Q84),
    replay (Q91), and adversarial testing maturity (Q90).
  * Damage is *risk specific*: each code has a "driver" (data / agency /
    availability / integrity / access) amplified by the relevant answers
    (sensitive data, agency/actions, resource limits, shared stores) and then
    bounded by the declared business/regulatory impact (Q87), data retention
    (Q88) and incident-response maturity (Q89).
  * Reproducibility reflects control consistency: a code-specific safeguard
    question where one exists, otherwise overall authorization hygiene, plus
    replay (Q91) and adversarial-testing (Q90) signals.
  * Affected users reflects blast radius: tenancy/isolation plus the declared
    user/tenant scale (Q86).

Every rule cites the question number(s) it reads, so each score traces back to
concrete answers. Q83-Q91 are new questions; when they are absent (legacy
Q1-Q82 records) the rules simply fall through to the prior behaviour.
"""
import re

DREAD_DIMENSIONS = ("damage", "reproducibility", "exploitability", "affected_users", "discoverability")


def _norm(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def index_answers(answers):
    """Map {answer-key -> value} to {question_number -> [normalized answer strings]}.

    Accepts both dataset keys ("Q16") and pipeline flow ids; the leading integer
    in the key is the question number.
    """
    indexed = {}
    if not isinstance(answers, dict):
        return indexed
    for key, value in answers.items():
        match = re.search(r"(\d+)", str(key))
        if not match:
            continue
        number = int(match.group(1))
        values = value if isinstance(value, list) else [value]
        indexed[number] = [_norm(v) for v in values if v not in (None, "")]
    return indexed


def _has(idx, number, *markers):
    answers = idx.get(number, [])
    return any(any(_norm(marker) in answer for answer in answers) for marker in markers)


def _clamp(value, low=1, high=3):
    return max(low, min(high, value))


def level_from_average(average):
    """Map a DREAD average (1.0-3.0) to a risk level using the thesis cut-offs."""
    if average >= 2.7:
        return "Critical"
    if average >= 2.2:
        return "High"
    if average >= 1.5:
        return "Medium"
    return "Low"


def _band(total):
    # Risk level from the DREAD average (total / 5). See level_from_average.
    return level_from_average(total / 5.0)


def _framework(code):
    code = code.upper()
    if code.startswith("LLM"):
        return "owasp_llm"
    if code.startswith("API"):
        return "owasp_api"
    return "owasp_web"


# --- answer-derived signals (each cites its source questions) ---------------

def _sensitive_data(idx):
    # Q4: processes sensitive/business-critical data; Q24: sensitive categories accessible.
    if _has(idx, 4, "yes"):
        return True
    q24 = idx.get(24, [])
    return any(answer and "no sensitive data" not in answer for answer in q24)


def _secrets_access(idx):
    # Q45: the LLM can reach secrets/credentials at runtime.
    return _has(idx, 45, "sensitive data such as api keys", "api keys or credentials")


def _high_agency(idx):
    # Q15 actions, Q16 unattended state change, Q39 decision impact, Q79 business flows.
    return (
        _has(idx, 16, "business critical")
        or _has(idx, 15, "execute workflows", "modify system")
        or _has(idx, 39, "high impact")
        or _has(idx, 79, "refunds", "payments", "approvals", "entitlement")
    )


def _low_agency(idx):
    # Strong agency limit: human approval always required AND text-only output.
    return _has(idx, 16, "human approval is always required") and _has(idx, 15, "generate text responses only")


def _availability_exposure(idx):
    # Q77/Q78 resource limits, Q34 abuse protections.
    return (
        _has(idx, 77, "no effective limits", "partial or inconsistent")
        or _has(idx, 78, "weak or unclear", "partially bounded")
        or _has(idx, 34, "no protections")
    )


def _shared_index(idx):
    # Q68: uploaded/retrieved content can affect other users via shared stores.
    return _has(idx, 68, "shared stores may affect", "may affect other users")


# --- new-question signals (Q83-Q91); absent on legacy Q1-Q82 records ---------

# Input formats (Q83) that widen the parser/injection attack surface.
_RISKY_INPUT_FORMATS = (
    "html", "rendered content", "code or scripts", "code", "scripts",
    "documents", "pdf", "docx", "images", "multimodal", "audio",
    "transcribed speech", "xml", "yaml", "structured json", "markdown", "rich text",
)


def _risky_input_formats(idx):
    # Q83: anything beyond plain text broadens parsing / injection surface.
    return _has(idx, 83, *_RISKY_INPUT_FORMATS)


def _weak_parsing(idx):
    # Q84: minimal validation or no parsing means untrusted input reaches the model
    # context with little defence.
    return _has(idx, 84, "minimal validation", "no parsing or transformation")


def _strict_parsing(idx):
    return _has(idx, 84, "strict validation and normalization")


def _replay_open(idx):
    # Q91: state-changing/sensitive actions can be replayed without strong controls.
    return _has(idx, 91, "without strong controls")


def _replay_blocked(idx):
    return _has(idx, 91, "replay is blocked", "fresh authorization")


def _no_adversarial_testing(idx):
    # Q90: never tested against adversarial prompts / jailbreaks / tool misuse.
    return _has(idx, 90, "no testing performed")


def _mature_adversarial_testing(idx):
    return _has(idx, 90, "continuous adversarial testing", "regression tests", "formal red team")


def _mature_incident_response(idx):
    # Q89: tested process or automated containment lowers realised damage.
    return _has(idx, 89, "periodically tested", "automated containment", "kill switch")


def _scale_profile(idx):
    """Affected-users floor from declared user/tenant scale (Q86)."""
    if _has(idx, 86, "public internet scale", "multiple tenants"):
        return 3
    if _has(idx, 86, "single organization", "single tenant"):
        return 2
    if _has(idx, 86, "single user", "local only", "small internal group"):
        return 1
    return None


def _impact_floor(idx):
    """Damage floor from declared business/regulatory impact (Q87) and retention (Q88)."""
    floor = None
    if _has(idx, 87, "severe impact", "large scale data breach", "fraud", "critical service disruption"):
        floor = 3
    elif _has(idx, 87, "high business", "financial", "legal", "regulatory"):
        floor = 2
    elif _has(idx, 87, "moderate business disruption", "customer impact"):
        floor = 2
    # Long-term retention without deletion controls keeps data-exposure damage elevated.
    if _has(idx, 88, "without clear deletion controls"):
        floor = max(floor or 0, 2)
    return floor


def _impact_ceiling(idx):
    """Damage ceiling: a declared-minimal impact or mature response caps damage."""
    if _has(idx, 87, "minimal operational impact", "internal inconvenience", "low business impact"):
        return 2
    return None


# --- Damage (risk specific) -------------------------------------------------

_DAMAGE_DRIVER = {
    # data-exposure risks: damage scales with sensitive data / secrets
    "LLM02": "data", "LLM07": "data", "LLM08": "data",
    "A04:2025": "data", "API1:2023": "data", "API3:2023": "data",
    # agency / action risks: damage scales with what the model can do
    "LLM01": "agency", "LLM05": "agency", "LLM06": "agency",
    "A01:2025": "agency", "A05:2025": "agency",
    "API5:2023": "agency", "API6:2023": "agency", "API7:2023": "agency",
    # availability / resource-consumption risks
    "LLM10": "availability", "API4:2023": "availability",
    # integrity / poisoning risks
    "LLM03": "integrity", "LLM04": "integrity",
    "A03:2025": "integrity", "A08:2025": "integrity", "API10:2023": "integrity",
    # broken-auth (access) risks: damage from sensitive data OR agency
    "A07:2025": "access", "API2:2023": "access",
    # anything else -> generic baseline
}


def _damage(code, idx):
    base = _damage_driver(code, idx)
    # Bound the driver score by declared business/regulatory impact, retention and
    # incident-response maturity (Q87/Q88/Q89). These are new signals; on legacy
    # records the floor/ceiling are None and `base` is returned unchanged.
    floor = _impact_floor(idx)
    ceiling = _impact_ceiling(idx)
    score = base
    # A tested/automated incident-response process (Q89) dampens realised damage...
    if _mature_incident_response(idx) and score > 1:
        score -= 1
    # ...but the declared business/regulatory impact (Q87) / retention (Q88) is a hard
    # floor that response maturity cannot erase, and a declared-minimal impact caps it.
    if floor is not None:
        score = max(score, floor)
    if ceiling is not None:
        score = min(score, ceiling)
    return _clamp(score)


def _damage_driver(code, idx):
    driver = _DAMAGE_DRIVER.get(code.upper(), "generic")
    if driver == "data":
        # 3 only when genuinely sensitive data is in play (not merely "some data").
        if _secrets_access(idx) or (_has(idx, 4, "yes") and _has(idx, 24, "personally identifiable", "api keys", "credentials")):
            return 3
        if _has(idx, 24, "no sensitive data") or _has(idx, 4, "no"):
            return 1
        return 2
    if driver == "agency":
        if _high_agency(idx):
            return 3
        return 1 if _low_agency(idx) else 2
    if driver == "availability":
        if _availability_exposure(idx):
            return 3
        return 1 if _has(idx, 77, "anomaly detection") or _has(idx, 78, "bounded by quotas") else 2
    if driver == "integrity":
        if _shared_index(idx) and _sensitive_data(idx):
            return 3
        return 1 if _has(idx, 68, "no shared indexing") or _has(idx, 8, "no rag") else 2
    if driver == "access":
        if _sensitive_data(idx) and _high_agency(idx):
            return 3
        return 1 if not _sensitive_data(idx) and not _high_agency(idx) else 2
    # generic: misinformation (LLM09) gets worse when responses drive decisions
    if code.upper() == "LLM09":
        if _has(idx, 39, "high impact"):
            return 3
        return 1 if _has(idx, 39, "informational use only") else 2
    return 2


# --- Reproducibility (control consistency) ----------------------------------

# code -> (question, weak_markers, strong_markers)
# "unknown" is intentionally NOT a weak marker: an unknown answer means the
# assessor is unsure, not that the control is absent -> it falls through to 2.
_SAFEGUARD = {
    "LLM01": (30, ("no safeguards",), ("context isolation", "instruction hierarchy", "detection", "scanning")),
    "LLM05": (31, ("not validated",), ("schema validation", "human in the loop", "rule based")),
    "LLM02": (32, ("no safeguards",), ("access controls", "scoped retrieval", "dlp", "content inspection", "redaction", "masking")),
    "LLM07": (45, ("sensitive data such as api keys",), ("no access to secrets",)),
    "LLM08": (36, ("no dedicated protection",), ("strongly protected",)),
    "LLM10": (77, ("no effective limits",), ("anomaly detection",)),
    "LLM04": (69, ("no dedicated protection",), ("strong write controls", "review")),
    "LLM06": (80, ("no additional controls", "basic confirmation"), ("risk based approval", "step up")),
    "API7:2023": (62, ("arbitrary urls", "internal addresses"), ("no arbitrary url", "only allowlisted")),
    "API4:2023": (77, ("no effective limits",), ("anomaly detection",)),
    "A05:2025": (66, ("no dedicated controls",), ("strict blocking", "allowlisting")),
}


def _reproducibility(code, idx):
    spec = _SAFEGUARD.get(code.upper())
    if spec:
        question, weak, strong = spec
        if _has(idx, question, *weak):
            base = 3
        elif _has(idx, question, *strong):
            base = 1
        else:
            base = 2
    # default: overall authorization hygiene (Q26) + fail-open behavior (Q75)
    elif _has(idx, 26, "no authorization") or _has(idx, 75, "fall back to less restricted"):
        base = 3
    elif _has(idx, 26, "role based", "attribute", "policy"):
        base = 1
    else:
        base = 2
    return _clamp(base + _replay_repro_delta(idx))


def _replay_repro_delta(idx):
    # Replay (Q91) and adversarial-testing maturity (Q90) shift how reliably an
    # attack can be re-triggered. New signals; 0 on legacy records.
    delta = 0
    if _replay_open(idx):
        delta += 1
    elif _replay_blocked(idx):
        delta -= 1
    if _mature_adversarial_testing(idx):
        delta -= 1
    elif _no_adversarial_testing(idx):
        delta += 1
    return max(-1, min(1, delta))


# --- Exposure profile (global: Exploitability / Affected / Discoverability) --

# These three are kept deliberately INDEPENDENT (each reads different questions)
# so a single "public" answer cannot spike all three at once.

def _exploitability(idx):
    # Access barrier (Q2 audience, Q25 auth) adjusted by input defenses (Q7, Q30).
    if _has(idx, 2, "administrators only", "local system processes"):
        score = 1
    elif _has(idx, 2, "anonymous public") or _has(idx, 25, "no authentication"):
        score = 3
    elif _has(idx, 25, "single sign on") and _has(idx, 2, "internal employees"):
        score = 1
    else:
        score = 2
    # Strong injection/input defenses make even an exposed surface harder to exploit.
    if score == 3 and _has(idx, 30, "context isolation", "instruction hierarchy", "detection", "scanning"):
        score = 2
    # No defenses at all on an otherwise-guarded surface raises difficulty.
    if score == 2 and _has(idx, 7, "no preprocessing") and _has(idx, 30, "no safeguards"):
        score = 3
    # Risky input formats inserted with weak/no parsing (Q83 + Q84) widen the
    # exploitable surface; strict parsing pulls it back down.
    if _weak_parsing(idx) and _risky_input_formats(idx):
        score += 1
    elif _strict_parsing(idx) and score > 1:
        score -= 1
    return _clamp(score)


def _affected(idx):
    # Blast radius: tenancy (Q40), per-user/session isolation (Q46), shared stores (Q68),
    # plus declared user/tenant scale (Q86).
    if _has(idx, 40, "weak or unclear") or _shared_index(idx) or _has(idx, 46, "no isolation", "session level isolation only"):
        score = 3
    elif (
        _has(idx, 2, "administrators only", "local system processes")
        or _has(idx, 40, "single tenant")
        or _has(idx, 46, "user level isolation", "tenant level isolation")
    ):
        score = 1
    else:
        score = 2
    # The declared scale (Q86) raises a floor: a public/multi-tenant deployment cannot
    # have a tiny blast radius even when isolation looks acceptable.
    scale = _scale_profile(idx)
    if scale is not None:
        score = max(score, scale) if scale == 3 else score
        if scale == 1 and not _shared_index(idx) and not _has(idx, 40, "weak or unclear"):
            score = min(score, 1)
    return _clamp(score)


def _discoverability(idx):
    # How easy to find/probe the weakness: error leakage (Q76) and undocumented/debug
    # APIs (Q59) are the strong signals; sanitized errors + monitoring lower it.
    if _has(idx, 76, "detailed internal errors") or _has(idx, 59, "non production or undocumented", "some non production"):
        score = 3
    elif _has(idx, 76, "sanitized error handling") and _has(idx, 33, "security monitoring"):
        score = 1
    else:
        score = 2
    # A public/anonymous surface is easy to probe; an internal-only one is harder.
    if _has(idx, 2, "anonymous public") and score < 3:
        score += 1
    # Adversarial-testing maturity (Q90) and incident response (Q89) mean weaknesses
    # are likelier to have already been found and closed before an attacker probes.
    if (_mature_adversarial_testing(idx) or _mature_incident_response(idx)) and score > 1:
        score -= 1
    elif _no_adversarial_testing(idx) and score < 3:
        score += 1
    return _clamp(score)


# --- public API -------------------------------------------------------------

def score_code(code, idx):
    """Return the DREAD block for one code given already-indexed answers."""
    damage = _damage(code, idx)
    reproducibility = _reproducibility(code, idx)
    exploitability = _exploitability(idx)
    affected = _affected(idx)
    discoverability = _discoverability(idx)
    total = damage + reproducibility + exploitability + affected + discoverability
    average = round(total / 5.0, 2)
    block = {
        "damage": damage,
        "reproducibility": reproducibility,
        "exploitability": exploitability,
        "affected_users": affected,
        "discoverability": discoverability,
        "total": total,
        "average": average,
        "band": level_from_average(average),
    }
    block["risk_level"] = block["band"]
    block["strongest_dimensions"] = strongest_dimensions(block)
    return block


def strongest_dimensions(block):
    """Names of the DREAD dimensions scoring highest (>=2 and equal to the max)."""
    top = max(block[dim] for dim in DREAD_DIMENSIONS)
    if top < 2:
        return []
    labels = {
        "damage": "Damage",
        "reproducibility": "Reproducibility",
        "exploitability": "Exploitability",
        "affected_users": "Affected users",
        "discoverability": "Discoverability",
    }
    return [labels[dim] for dim in DREAD_DIMENSIONS if block[dim] == top]


def compute_dread(code, answers):
    """Compute the DREAD block for one code from a raw answers dict."""
    return score_code(code, index_answers(answers))


def compute_dread_map(codes, answers):
    """Compute DREAD blocks for many codes from one answers dict (indexed once)."""
    idx = index_answers(answers)
    return {code: score_code(code, idx) for code in codes}


def rationale(block):
    """Short DREAD rationale string for `why`/UI use."""
    labels = {
        "damage": "Damage",
        "reproducibility": "Reproducibility",
        "exploitability": "Exploitability",
        "affected_users": "Affected users",
        "discoverability": "Discoverability",
    }
    highs = [labels[dim] for dim in DREAD_DIMENSIONS if block[dim] == 3]
    text = "DREAD {total}/15 ({band})".format(**block)
    if highs:
        text += " - driven by " + ", ".join(highs)
    return text + "."
