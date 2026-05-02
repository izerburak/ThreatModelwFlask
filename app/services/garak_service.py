import json
import re
from importlib import metadata
from pathlib import Path


GARAK_PRESETS = {
    "targets": [
        {"label": "Ollama local model", "target_type": "ollama", "target_name": "qwen3:8b"},
        {"label": "Hugging Face TinyLlama", "target_type": "huggingface", "target_name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0"},
        {"label": "OpenAI compatible", "target_type": "openai", "target_name": "gpt-4o-mini"},
    ],
    "probes": [
        {
            "label": "Prompt Injection",
            "value": "promptinject",
            "description": "General prompt injection robustness probes.",
        },
        {
            "label": "OWASP LLM01",
            "value": "owasp:llm01",
            "mode": "probe_tags",
            "description": "OWASP prompt injection tagged probes.",
        },
        {
            "label": "OWASP LLM02",
            "value": "owasp:llm02",
            "mode": "probe_tags",
            "description": "Sensitive information disclosure tagged probes.",
        },
        {
            "label": "OWASP LLM06",
            "value": "owasp:llm06",
            "mode": "probe_tags",
            "description": "Excessive agency and tool/action related probes.",
        },
        {
            "label": "Jinja Template Injection",
            "value": "exploitation.JinjaTemplatePythonInjection",
            "description": "Focused exploitation probe for template/code execution behavior.",
        },
        {
            "label": "Misleading / False Assertion",
            "value": "misleading.FalseAssertion",
            "description": "Checks whether the target follows false claims.",
        },
    ],
    "detectors": [
        {"label": "Auto", "value": "auto"},
        {"label": "All", "value": "all"},
    ],
}


def garak_status(app_root_path):
    package = _package_status()
    return {
        **package,
        "presets": GARAK_PRESETS,
        "workspace_dirs": _workspace_dirs(app_root_path),
        "reports": list_garak_reports(app_root_path),
    }


def list_garak_reports(app_root_path):
    garak_dir = _garak_dir(app_root_path)
    if not garak_dir.exists():
        return []

    reports = []
    for report_path in garak_dir.rglob("*.html"):
        if not report_path.is_file():
            continue
        relative_path = report_path.relative_to(garak_dir).as_posix()
        reports.append(
            {
                "name": report_path.name,
                "relative_path": relative_path,
                "folder": str(report_path.parent.relative_to(garak_dir)).replace(".", ""),
                "size_kb": round(report_path.stat().st_size / 1024, 1),
                "summary": parse_garak_report(report_path),
            }
        )
    return sorted(reports, key=lambda report: report["relative_path"].lower())


def garak_report_path(app_root_path, relative_path):
    garak_dir = _garak_dir(app_root_path).resolve()
    report_path = (garak_dir / relative_path).resolve()
    if garak_dir not in report_path.parents or report_path.suffix.lower() != ".html":
        raise ValueError("Invalid Garak report path.")
    if not report_path.exists():
        raise FileNotFoundError(relative_path)
    return report_path


def parse_garak_report(report_path):
    try:
        raw = Path(report_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    payload = _extract_embedded_report_payload(raw)
    if not payload:
        return None

    report = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(report, dict):
        return None

    meta = report.get("meta") or {}
    eval_payload = report.get("eval") or {}
    modules = _report_modules(eval_payload)
    worst_defcon = min([module["defcon"] for module in modules if module["defcon"]] or [None])

    return {
        "target_type": meta.get("target_type") or meta.get("model_type"),
        "target_name": meta.get("target_name") or meta.get("model_name"),
        "probe_spec": meta.get("probespec"),
        "garak_version": meta.get("garak_version"),
        "run_uuid": meta.get("run_uuid"),
        "completed_at": meta.get("report_digest_time"),
        "worst_defcon": worst_defcon,
        "modules": modules,
    }


def _extract_embedded_report_payload(raw):
    marker = "const gw=typeof "
    start = raw.find(marker)
    if start == -1:
        return None

    start += len(marker)
    end = raw.find('<"u"?', start)
    if end == -1:
        return None

    json_text = raw[start:end].strip()
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


def _report_modules(eval_payload):
    modules = []
    if not isinstance(eval_payload, dict):
        return modules

    for group_name, group_payload in eval_payload.items():
        if not isinstance(group_payload, dict):
            continue

        group_summary = group_payload.get("_summary") or {}
        for probe_name, probe_payload in group_payload.items():
            if probe_name == "_summary" or not isinstance(probe_payload, dict):
                continue

            probe_summary = probe_payload.get("_summary") or {}
            detectors = []
            for detector_name, detector_payload in probe_payload.items():
                if detector_name == "_summary" or not isinstance(detector_payload, dict):
                    continue
                detectors.append(
                    {
                        "name": detector_payload.get("detector_name") or detector_name,
                        "score": _score_percent(detector_payload.get("absolute_score")),
                        "defcon": detector_payload.get("detector_defcon"),
                        "comment": detector_payload.get("absolute_comment") or detector_payload.get("relative_comment"),
                        "total": detector_payload.get("total_evaluated"),
                        "passed": detector_payload.get("passed"),
                    }
                )

            modules.append(
                {
                    "group": group_name,
                    "group_score": _score_percent(group_summary.get("score")),
                    "group_defcon": group_summary.get("group_defcon"),
                    "probe": probe_summary.get("probe_name") or probe_name,
                    "probe_score": _score_percent(probe_summary.get("probe_score")),
                    "defcon": probe_summary.get("probe_severity") or group_summary.get("group_defcon"),
                    "description": _strip_html(probe_summary.get("probe_descr") or ""),
                    "tags": probe_summary.get("probe_tags") or [],
                    "detectors": detectors,
                }
            )

    return sorted(modules, key=lambda module: (module["defcon"] or 99, module["probe"]))


def _score_percent(value):
    if not isinstance(value, (int, float)):
        return None
    return round(value * 100, 1)


def _strip_html(value):
    return re.sub(r"<[^>]+>", "", str(value)).strip()


def _package_status():
    try:
        version = metadata.version("garak")
    except metadata.PackageNotFoundError:
        return {
            "installed": False,
            "version": None,
            "detail": "garak is not installed in the active Python environment.",
        }

    return {
        "installed": True,
        "version": version,
        "detail": f"garak {version} is installed.",
    }


def _workspace_dirs(app_root_path):
    workspace_root = Path(app_root_path).parent
    return {
        "config": str(workspace_root / ".tmp" / "garak_config"),
        "cache": str(workspace_root / ".tmp" / "garak_cache"),
        "data": str(workspace_root / ".tmp" / "garak_data"),
        "reports": str(_garak_dir(app_root_path)),
    }


def _garak_dir(app_root_path):
    return Path(app_root_path).parent / "Garak"
