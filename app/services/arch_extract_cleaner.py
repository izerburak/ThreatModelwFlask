import json
import re
from copy import deepcopy
from typing import Any


CLEAN_SCHEMA_VERSION = "llmsec.arch_extract.cleaned.v1"

SYSTEM_SUMMARY_KEYS = ("purpose", "llm_role", "deployment", "exposure", "confidence")
ARCHITECTURE_KEYS = (
    "actors",
    "entry_points",
    "components",
    "data_stores",
    "external_services",
    "trust_boundaries",
    "data_flows",
)
SECURITY_CONTROL_KEYS = (
    "authentication",
    "authorization",
    "input_validation",
    "output_validation",
    "logging_monitoring",
    "rate_limiting",
    "secrets_management",
    "encryption",
)
RISK_SIGNAL_KEYS = ("misuse_scenarios", "operational_weaknesses", "owasp_llm_candidates")

RISK_LIKE_PHRASES = (
    "prompt injection",
    "sensitive data extraction",
    "unauthorized action",
    "misinformation",
    "unsafe recommendation",
    "denial of service",
    "excessive usage",
    "data leakage",
    "prompt leakage",
    "jailbreak",
    "poisoning",
    "abuse",
    "weakness",
    "insufficient monitoring",
    "weak access control",
    "poor prompt/change management",
    "no incident response",
)

CONTROL_LIKE_PHRASES = (
    "rbac",
    "role-based access control",
    "scoped retrieval",
    "input filtering",
    "schema validation",
    "prompt/response logging",
    "monitoring",
    "alerts",
    "rate limiting",
    "version pinning",
    "secret manager",
    "encryption",
    "redaction",
    "dlp",
    "approval",
    "human review",
)

NON_STORAGE_PHRASES = (
    "internal api",
    "model service",
    "cross-tenant boundary",
    "cross tenant boundary",
    "api gateway",
    "backend api",
    "orchestrator",
)
STORAGE_PHRASES = (
    "database",
    "db",
    "store",
    "storage",
    "log",
    "vector",
    "embedding",
    "file",
    "knowledge base",
    "conversation history",
    "repository",
)


def clean_arch_extract_v4(raw_extract: dict) -> dict:
    raw = raw_extract if isinstance(raw_extract, dict) else {}
    cleaned = _empty_clean_extract()

    cleaned["system_summary"].update(_clean_system_summary(raw))
    _merge_architecture(cleaned, raw)
    _merge_security_controls(cleaned, raw)
    _merge_risk_signals(cleaned, raw)
    _apply_classification_guards(cleaned)
    _dedupe_cleaned(cleaned)

    for optional_key in ("llm_parse_error", "response_file", "metadata", "dfd_notes", "missing_information"):
        value = _remove_empty(raw.get(optional_key))
        if value not in (None, "", [], {}):
            cleaned[optional_key] = value

    _add_compatibility_aliases(cleaned)
    return cleaned


def _empty_clean_extract() -> dict:
    return {
        "schema_version": CLEAN_SCHEMA_VERSION,
        "system_summary": {key: "" for key in SYSTEM_SUMMARY_KEYS},
        "architecture": {key: [] for key in ARCHITECTURE_KEYS},
        "security_controls": {key: [] for key in SECURITY_CONTROL_KEYS},
        "risk_signals": {key: [] for key in RISK_SIGNAL_KEYS},
    }


def _clean_system_summary(raw: dict) -> dict:
    summary = _as_dict(raw.get("system_summary"))
    legacy_system = _as_dict(raw.get("system"))
    return {
        "purpose": _string(summary.get("purpose") or legacy_system.get("purpose") or legacy_system.get("description")),
        "llm_role": _string(summary.get("llm_role") or summary.get("role")),
        "deployment": _string(summary.get("deployment") or raw.get("deployment")),
        "exposure": _string(summary.get("exposure")),
        "confidence": _normalize_confidence(summary.get("confidence") or summary.get("overall_dfd_confidence")),
    }


def _merge_architecture(cleaned: dict, raw: dict) -> None:
    architecture = _as_dict(raw.get("architecture"))
    signals = _as_dict(raw.get("architecture_signals"))
    dfd = _as_dict(raw.get("dfd"))

    _extend(cleaned["architecture"]["actors"], architecture.get("actors"))
    _extend(cleaned["architecture"]["actors"], signals.get("actors"))
    _extend(cleaned["architecture"]["actors"], dfd.get("actors"))

    _extend(cleaned["architecture"]["entry_points"], architecture.get("entry_points"))
    _extend(cleaned["architecture"]["entry_points"], architecture.get("interfaces"))
    _extend(cleaned["architecture"]["entry_points"], signals.get("entry_points"))
    _extend(cleaned["architecture"]["entry_points"], dfd.get("interfaces"))

    _extend(cleaned["architecture"]["components"], architecture.get("components"))
    _extend(cleaned["architecture"]["components"], architecture.get("tools"))
    _extend(cleaned["architecture"]["components"], signals.get("runtime_components"))
    _extend(cleaned["architecture"]["components"], signals.get("tools_actions"))
    _extend(cleaned["architecture"]["components"], dfd.get("processes"))
    _extend(cleaned["architecture"]["components"], dfd.get("tools"))
    _extend(cleaned["architecture"]["components"], _legacy_llm_components(raw))

    _extend(cleaned["architecture"]["data_stores"], architecture.get("data_stores"))
    _extend(cleaned["architecture"]["data_stores"], architecture.get("data_sources"))
    _extend(cleaned["architecture"]["data_stores"], architecture.get("storage"))
    _extend(cleaned["architecture"]["data_stores"], signals.get("data_stores"))
    _extend(cleaned["architecture"]["data_stores"], dfd.get("data_stores"))

    _extend(cleaned["architecture"]["external_services"], architecture.get("external_services"))
    _extend(cleaned["architecture"]["external_services"], signals.get("external_systems"))
    _extend(cleaned["architecture"]["external_services"], dfd.get("external_systems"))

    _extend(cleaned["architecture"]["trust_boundaries"], architecture.get("trust_boundaries"))
    _extend(cleaned["architecture"]["trust_boundaries"], signals.get("trust_boundary_hints"))
    _extend(cleaned["architecture"]["trust_boundaries"], dfd.get("trust_boundaries"))
    _extend(cleaned["architecture"]["trust_boundaries"], _as_dict(raw.get("system_summary")).get("trust_boundaries"))

    _extend(cleaned["architecture"]["data_flows"], architecture.get("data_flows"))
    _extend(cleaned["architecture"]["data_flows"], signals.get("data_movement_hints"))
    _extend(cleaned["architecture"]["data_flows"], dfd.get("data_flows"))


def _merge_security_controls(cleaned: dict, raw: dict) -> None:
    controls = _as_dict(raw.get("security_controls"))
    for key in SECURITY_CONTROL_KEYS:
        _extend(cleaned["security_controls"][key], controls.get(key))

    system_security = _as_dict(_as_dict(raw.get("system")).get("security"))
    if system_security.get("access_control"):
        _extend(cleaned["security_controls"]["authorization"], [system_security.get("access_control")])
    if system_security.get("audit_logs"):
        _extend(cleaned["security_controls"]["logging_monitoring"], [system_security.get("audit_logs")])
    if system_security.get("data_encryption"):
        _extend(cleaned["security_controls"]["encryption"], [system_security.get("data_encryption")])


def _merge_risk_signals(cleaned: dict, raw: dict) -> None:
    risks = _as_dict(raw.get("risk_signals"))
    for key in RISK_SIGNAL_KEYS:
        _extend(cleaned["risk_signals"][key], risks.get(key))

    _extend(cleaned["risk_signals"]["owasp_llm_candidates"], raw.get("applicable_owasp_llm_risks"))
    _extend(cleaned["risk_signals"]["owasp_llm_candidates"], raw.get("top_risks"))
    _extend(cleaned["risk_signals"]["owasp_llm_candidates"], raw.get("extract_risks"))


def _apply_classification_guards(cleaned: dict) -> None:
    purpose = _normalize(cleaned["system_summary"].get("purpose"))
    if purpose:
        cleaned["architecture"]["actors"] = [
            item for item in cleaned["architecture"]["actors"] if _normalize(_item_name(item)) != purpose
        ]

    moved_risks = []
    for key in SECURITY_CONTROL_KEYS:
        retained = []
        for item in cleaned["security_controls"][key]:
            if _is_risk_like(item) and not _is_control_like(item):
                moved_risks.append(item)
            else:
                retained.append(item)
        cleaned["security_controls"][key] = retained
    cleaned["risk_signals"]["misuse_scenarios"].extend(moved_risks)

    retained_stores = []
    moved_components = []
    for item in cleaned["architecture"]["data_stores"]:
        if _looks_like_non_storage(item) and not _has_storage_evidence(item):
            moved_components.append(item)
        else:
            retained_stores.append(item)
    cleaned["architecture"]["data_stores"] = retained_stores
    cleaned["architecture"]["components"].extend(moved_components)

    cleaned["architecture"]["data_flows"] = [_normalize_data_flow(item) for item in cleaned["architecture"]["data_flows"]]


def _dedupe_cleaned(cleaned: dict) -> None:
    for key in ARCHITECTURE_KEYS:
        cleaned["architecture"][key] = _dedupe_list(cleaned["architecture"][key])
    for key in SECURITY_CONTROL_KEYS:
        cleaned["security_controls"][key] = _dedupe_list(cleaned["security_controls"][key])
    for key in RISK_SIGNAL_KEYS:
        cleaned["risk_signals"][key] = _dedupe_list(cleaned["risk_signals"][key])


def _add_compatibility_aliases(cleaned: dict) -> None:
    architecture = cleaned["architecture"]
    dfd_flows = []
    for flow in architecture["data_flows"]:
        if isinstance(flow, dict):
            dfd_flow = deepcopy(flow)
            if "target" not in dfd_flow and "destination" in dfd_flow:
                dfd_flow["target"] = dfd_flow["destination"]
            dfd_flows.append(dfd_flow)
        else:
            dfd_flows.append(deepcopy(flow))
    cleaned["dfd"] = {
        "actors": deepcopy(architecture["actors"]),
        "interfaces": deepcopy(architecture["entry_points"]),
        "processes": deepcopy(architecture["components"]),
        "data_stores": deepcopy(architecture["data_stores"]),
        "external_systems": deepcopy(architecture["external_services"]),
        "tools": [],
        "trust_boundaries": deepcopy(architecture["trust_boundaries"]),
        "data_flows": dfd_flows,
    }
    cleaned["architecture_signals"] = {
        "actors": deepcopy(architecture["actors"]),
        "entry_points": deepcopy(architecture["entry_points"]),
        "runtime_components": deepcopy(architecture["components"]),
        "data_stores": deepcopy(architecture["data_stores"]),
        "external_systems": deepcopy(architecture["external_services"]),
        "tools_actions": [],
        "trust_boundary_hints": deepcopy(architecture["trust_boundaries"]),
        "data_movement_hints": deepcopy(architecture["data_flows"]),
    }


def _legacy_llm_components(raw: dict) -> list:
    components = []
    for key, value in _as_dict(raw.get("llm_components")).items():
        if value not in (None, "", [], {}):
            components.append({"name": _title(key), "description": value})
    return components


def _normalize_data_flow(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    normalized = _clean_item(item)
    if "destination" not in normalized and "target" in normalized:
        normalized["destination"] = normalized.pop("target")
    if "destination" not in normalized and "target_name" in normalized:
        normalized["destination"] = normalized["target_name"]
    if "source" not in normalized and "source_name" in normalized:
        normalized["source"] = normalized["source_name"]
    normalized.setdefault("exposure", "")
    normalized.setdefault("trust_zone", "")
    return normalized


def _extend(target: list, value: Any) -> None:
    for item in _as_list(value):
        cleaned = _clean_item(item)
        if cleaned not in (None, "", [], {}):
            target.append(cleaned)


def _clean_item(item: Any) -> Any:
    if isinstance(item, dict):
        return {
            key: cleaned_value
            for key, value in item.items()
            if (cleaned_value := _remove_empty(value)) not in (None, "", [], {})
        }
    return _remove_empty(item)


def _remove_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _remove_empty(item)) not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _remove_empty(item)) not in (None, "", [], {})]
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def _dedupe_list(items: list) -> list:
    deduped = []
    seen = set()
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)
        normalized_key = _normalize(key)
        if not normalized_key or normalized_key in seen:
            continue
        seen.add(normalized_key)
        deduped.append(item)
    return deduped


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def _string(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _string(value).lower()).strip()


def _normalize_confidence(value: Any) -> str:
    normalized = _normalize(value)
    if normalized in {"high", "medium", "low"}:
        return normalized
    return _string(value)


def _item_name(item: Any) -> str:
    if isinstance(item, dict):
        return _string(item.get("name") or item.get("label") or item.get("title"))
    return _string(item)


def _item_text(item: Any) -> str:
    if isinstance(item, dict):
        return " ".join(_string(value) for value in item.values())
    return _string(item)


def _is_risk_like(item: Any) -> bool:
    text = _normalize(_item_text(item))
    return any(_normalize(phrase) in text for phrase in RISK_LIKE_PHRASES)


def _is_control_like(item: Any) -> bool:
    text = _normalize(_item_text(item))
    return any(_normalize(phrase) in text for phrase in CONTROL_LIKE_PHRASES)


def _looks_like_non_storage(item: Any) -> bool:
    text = _normalize(_item_name(item) or _item_text(item))
    return any(_normalize(phrase) in text for phrase in NON_STORAGE_PHRASES)


def _has_storage_evidence(item: Any) -> bool:
    text = _normalize(_item_text(item))
    return any(_normalize(phrase) in text for phrase in STORAGE_PHRASES)


def _title(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", " ", str(value or "")).strip().title()
