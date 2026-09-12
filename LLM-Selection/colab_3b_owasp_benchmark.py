"""Standalone Colab benchmark for small local LLM threat identification.

No project repository is required.  The script talks to an Ollama server already
running on http://127.0.0.1:11434, pulls three Q4_K_M instruction models, runs
15 controlled OWASP cases three times, and writes raw JSONL plus a CSV summary.

Run in Colab with:
    !python /content/colab_3b_owasp_benchmark.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OLLAMA_HOST = "http://127.0.0.1:11434"
MODELS = [
    "qwen2.5:3b-instruct-q4_K_M",
    "llama3.2:3b-instruct-q4_K_M",
    "ministral-3:3b-instruct-2512-q4_K_M",
]
RUNS_PER_CASE = 3
REQUEST_TIMEOUT_SECONDS = 120
NUM_CTX = 8192
NUM_PREDICT = 512
SEEDS = [17, 42, 73]

STATUSES = ["confirmed", "plausible", "needs_more_info", "not_applicable"]
PATTERNS = [
    "prompt_context_manipulation",
    "untrusted_input_crossing_trust_boundary",
    "rag_or_memory_contamination",
    "sensitive_data_exposure",
    "excessive_tool_or_workflow_agency",
    "weak_authentication_authorization",
    "unsafe_output_handling",
    "vector_store_or_embedding_isolation",
    "secrets_logging_transport_exposure",
    "missing_monitoring_limits_incident_response",
]

SYSTEM_PROMPT = """You are a constrained security threat-identification component.
You receive exactly one deterministic OWASP candidate, questionnaire evidence,
and a data-flow diagram. Decide whether the candidate is a concrete threat in
this system. Do not create other risk codes. Do not calculate severity or DREAD.
Do not provide mitigations.

Status rules:
- confirmed: strong specific evidence and a clear missing or weak control.
- plausible: supported, but one or more assumptions remain.
- needs_more_info: decisive evidence or control information is unknown/missing.
- not_applicable: the candidate does not manifest because the required capability
  is absent or strong controls make the described path inapplicable.

Threat patterns (use the single pattern that best describes how this candidate
manifests in the supplied system):
- prompt_context_manipulation: untrusted text reaches the model context and can
  override, leak, or subvert system instructions.
- untrusted_input_crossing_trust_boundary: lower-trust input crosses into a
  higher-trust process with weak validation or parsing.
- rag_or_memory_contamination: retrieved, indexed, or memory content can be
  poisoned and affect other requests or users.
- sensitive_data_exposure: sensitive data is reachable, returned, retained, or
  logged without adequate control.
- excessive_tool_or_workflow_agency: the model can trigger tools, actions, or
  workflows with insufficient scoping, approval, or least privilege.
- weak_authentication_authorization: authentication or per-object/per-function
  authorization is insufficient.
- unsafe_output_handling: model output is consumed downstream without validation,
  encoding, or allowlisting.
- vector_store_or_embedding_isolation: vector stores or embeddings lack tenant or
  user isolation and access control.
- secrets_logging_transport_exposure: secrets are reachable, logs capture sensitive
  data, or transport protection across trust boundaries is unclear.
- missing_monitoring_limits_incident_response: effective limits, monitoring,
  alerting, or incident-response processes are missing.

Evidence strings must start with the relevant question id, for example
"Q30: No safeguards". affected_nodes and affected_edges must use only ids from
the supplied DFD. For confirmed/plausible, provide an ordered abuse_path of at
least two steps and a specific control_gap. For needs_more_info/not_applicable,
return abuse_path [] and control_gap "". Return JSON only."""


def node(node_id: str, label: str, node_type: str) -> dict[str, Any]:
    return {"id": node_id, "data": {"label": label, "nodeType": node_type}}


def edge(edge_id: str, source: str, target: str, label: str) -> dict[str, Any]:
    return {"id": edge_id, "source": source, "target": target, "label": label}


DFD_PROMPT_INJECTION = {
    "nodes": [
        node("entry_web", "Web Chat", "interface"),
        node("rag_retriever", "RAG Retriever", "process"),
        node("vector_store", "Vector Store", "data_store"),
        node("llm_gateway", "LLM Gateway", "llm"),
    ],
    "edges": [
        edge("e_web_rag", "entry_web", "rag_retriever", "User query"),
        edge("e_store_rag", "vector_store", "rag_retriever", "Retrieved document"),
        edge("e_rag_llm", "rag_retriever", "llm_gateway", "Prompt plus retrieved context"),
    ],
}

DFD_SENSITIVE_DATA = {
    "nodes": [
        node("customer_store", "Customer Data Store", "data_store"),
        node("llm_gateway", "LLM Gateway", "llm"),
        node("log_store", "Prompt and Response Logs", "data_store"),
    ],
    "edges": [
        edge("e_data_llm", "customer_store", "llm_gateway", "Retrieved customer data"),
        edge("e_llm_logs", "llm_gateway", "log_store", "Prompt and response log"),
    ],
}

DFD_OUTPUT = {
    "nodes": [
        node("llm_gateway", "LLM Gateway", "llm"),
        node("web_renderer", "Web Renderer", "interface"),
        node("backend_automation", "Backend Automation", "process"),
    ],
    "edges": [
        edge("e_llm_web", "llm_gateway", "web_renderer", "Rendered model output"),
        edge("e_llm_backend", "llm_gateway", "backend_automation", "Structured model output"),
    ],
}

DFD_AGENCY = {
    "nodes": [
        node("entry_web", "Web Chat", "interface"),
        node("llm_orchestrator", "LLM Agent Orchestrator", "llm"),
        node("tool_runtime", "Tool Execution Runtime", "process"),
        node("admin_tool", "Administrative Tool", "external"),
    ],
    "edges": [
        edge("e_web_agent", "entry_web", "llm_orchestrator", "User instruction"),
        edge("e_agent_tools", "llm_orchestrator", "tool_runtime", "Tool request"),
        edge("e_tools_admin", "tool_runtime", "admin_tool", "Administrative action"),
    ],
}

DFD_SSRF = {
    "nodes": [
        node("entry_web", "Web Chat", "interface"),
        node("llm_orchestrator", "LLM Orchestrator", "llm"),
        node("fetch_tool", "URL Fetch Tool", "process"),
        node("internal_service", "Internal Service", "external"),
    ],
    "edges": [
        edge("e_web_llm", "entry_web", "llm_orchestrator", "User URL"),
        edge("e_llm_fetch", "llm_orchestrator", "fetch_tool", "Fetch request"),
        edge("e_fetch_internal", "fetch_tool", "internal_service", "Outbound request"),
    ],
}


def case(
    case_id: str,
    target_code: str,
    risk_name: str,
    variant: str,
    answers: dict[str, Any],
    dfd: dict[str, Any],
    expected_statuses: list[str],
    expected_pattern: str,
    expected_evidence: list[str],
    expected_nodes: list[str],
) -> dict[str, Any]:
    return {
        "id": case_id,
        "target_code": target_code,
        "risk_name": risk_name,
        "variant": variant,
        "answers": answers,
        "dfd": dfd,
        "expected_statuses": expected_statuses,
        "expected_pattern": expected_pattern,
        "expected_evidence": expected_evidence,
        "expected_nodes": expected_nodes,
    }


CASES = [
    case(
        "TC-LLM01-POS-01", "LLM01", "Prompt Injection", "positive",
        {"Q5": "Retrieved internal documents", "Q6": "Web URLs",
         "Q20": "Yes, through retrieved documents or memory", "Q30": "No safeguards",
         "Q84": "Yes, parsed and inserted with minimal validation"},
        DFD_PROMPT_INJECTION, ["confirmed"], "prompt_context_manipulation",
        ["Q20", "Q30", "Q84"], ["rag_retriever", "llm_gateway"],
    ),
    case(
        "TC-LLM01-CTRL-01", "LLM01", "Prompt Injection", "control",
        {"Q5": "Direct user prompts", "Q6": "User text input only", "Q20": "No",
         "Q30": "Context isolation and instruction hierarchy controls",
         "Q84": "Yes, parsed with strict validation and normalization"},
        DFD_PROMPT_INJECTION, ["not_applicable"], "prompt_context_manipulation",
        ["Q20", "Q30", "Q84"], [],
    ),
    case(
        "TC-LLM01-UNK-01", "LLM01", "Prompt Injection", "unknown",
        {"Q5": "Retrieved internal documents", "Q6": "Web URLs", "Q20": "Unknown",
         "Q30": "Unknown", "Q84": "Unknown"},
        DFD_PROMPT_INJECTION, ["needs_more_info"], "prompt_context_manipulation",
        ["Q20", "Q30", "Q84"], [],
    ),
    case(
        "TC-LLM02-POS-01", "LLM02", "Sensitive Information Disclosure", "positive",
        {"Q24": ["Personally identifiable information (PII)", "API keys or credentials"],
         "Q32": "No safeguards", "Q47": "Logs contain full prompts and responses"},
        DFD_SENSITIVE_DATA, ["confirmed"], "sensitive_data_exposure",
        ["Q24", "Q32", "Q47"], ["llm_gateway", "log_store"],
    ),
    case(
        "TC-LLM02-CTRL-01", "LLM02", "Sensitive Information Disclosure", "control",
        {"Q24": "Personally identifiable information (PII)",
         "Q32": "DLP or content inspection mechanisms",
         "Q47": "Logs contain non-sensitive metadata only"},
        DFD_SENSITIVE_DATA, ["not_applicable", "plausible"], "sensitive_data_exposure",
        ["Q24", "Q32", "Q47"], [],
    ),
    case(
        "TC-LLM02-UNK-01", "LLM02", "Sensitive Information Disclosure", "unknown",
        {"Q24": "Unknown", "Q32": "Unknown", "Q47": "Unknown"},
        DFD_SENSITIVE_DATA, ["needs_more_info"], "sensitive_data_exposure",
        ["Q24", "Q32", "Q47"], [],
    ),
    case(
        "TC-LLM05-POS-01", "LLM05", "Improper Output Handling", "positive",
        {"Q21": ["HTML or rendered content", "Code or scripts"],
         "Q22": "Directly used in backend automation", "Q31": "Not validated",
         "Q64": "HTML/rich content without reliable sanitization",
         "Q65": "Yes, directly used with minimal validation", "Q66": "No dedicated controls"},
        DFD_OUTPUT, ["confirmed"], "unsafe_output_handling",
        ["Q31", "Q64", "Q65", "Q66"], ["llm_gateway", "web_renderer", "backend_automation"],
    ),
    case(
        "TC-LLM05-CTRL-01", "LLM05", "Improper Output Handling", "control",
        {"Q21": "Plain text only", "Q22": "User-facing web interface",
         "Q31": "Rule-based or schema validation", "Q64": "Markdown with sanitization",
         "Q65": "No structured output drives downstream operations",
         "Q66": "Yes, strict blocking or allowlisting"},
        DFD_OUTPUT, ["not_applicable"], "unsafe_output_handling",
        ["Q31", "Q64", "Q65", "Q66"], [],
    ),
    case(
        "TC-LLM05-UNK-01", "LLM05", "Improper Output Handling", "unknown",
        {"Q21": "Structured JSON", "Q22": "Directly used in backend automation",
         "Q31": "Unknown", "Q64": "Unknown", "Q65": "Unknown", "Q66": "Unknown"},
        DFD_OUTPUT, ["needs_more_info", "plausible"], "unsafe_output_handling",
        ["Q31", "Q65", "Q66"], [],
    ),
    case(
        "TC-LLM06-POS-01", "LLM06", "Excessive Agency", "positive",
        {"Q11": "Agent workflow", "Q12": ["Internal APIs", "Admin tools"],
         "Q15": ["Execute workflows or transactions", "Modify system configurations"],
         "Q16": "Yes, in business-critical actions", "Q44": "No separation of permissions"},
        DFD_AGENCY, ["confirmed"], "excessive_tool_or_workflow_agency",
        ["Q12", "Q15", "Q16", "Q44"], ["llm_orchestrator", "tool_runtime", "admin_tool"],
    ),
    case(
        "TC-LLM06-CTRL-01", "LLM06", "Excessive Agency", "control",
        {"Q11": "Basic logic", "Q12": "Search", "Q15": "Generate text responses only",
         "Q16": "No, human approval is always required",
         "Q44": "Granular permissions including admin or destructive actions"},
        DFD_AGENCY, ["not_applicable"], "excessive_tool_or_workflow_agency",
        ["Q15", "Q16", "Q44"], [],
    ),
    case(
        "TC-LLM06-UNK-01", "LLM06", "Excessive Agency", "unknown",
        {"Q11": "Agent workflow", "Q12": "Internal APIs", "Q16": "Unknown", "Q44": "Unknown"},
        DFD_AGENCY, ["needs_more_info"], "excessive_tool_or_workflow_agency",
        ["Q16", "Q44"], [],
    ),
    case(
        "TC-API7-POS-01", "API7:2023", "Server Side Request Forgery", "positive",
        {"Q62": "Arbitrary URLs or internal addresses may be reachable",
         "Q63": "No outbound restrictions"},
        DFD_SSRF, ["confirmed"], "untrusted_input_crossing_trust_boundary",
        ["Q62", "Q63"], ["llm_orchestrator", "fetch_tool", "internal_service"],
    ),
    case(
        "TC-API7-CTRL-01", "API7:2023", "Server Side Request Forgery", "control",
        {"Q62": "Only allowlisted domains are reachable", "Q63": "Yes, strict egress allowlist"},
        DFD_SSRF, ["not_applicable"], "untrusted_input_crossing_trust_boundary",
        ["Q62", "Q63"], [],
    ),
    case(
        "TC-API7-UNK-01", "API7:2023", "Server Side Request Forgery", "unknown",
        {"Q62": "Partially restricted", "Q63": "Unknown"},
        DFD_SSRF, ["needs_more_info"], "untrusted_input_crossing_trust_boundary",
        ["Q62", "Q63"], [],
    ),
]


def request_json(path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(
        f"{OLLAMA_HOST}{path}", data=data, headers=headers,
        method="POST" if data is not None else "GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def schema_for(test_case: dict[str, Any]) -> dict[str, Any]:
    node_ids = [item["id"] for item in test_case["dfd"]["nodes"]]
    edge_ids = [item["id"] for item in test_case["dfd"]["edges"]]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "code": {"type": "string", "enum": [test_case["target_code"]]},
            "name": {"type": "string", "maxLength": 200},
            "status": {"type": "string", "enum": STATUSES},
            "threat_pattern": {"type": "string", "enum": PATTERNS},
            "evidence": {
                "type": "array", "items": {"type": "string", "maxLength": 300},
                "maxItems": 8,
            },
            "affected_nodes": {
                "type": "array", "items": {"type": "string", "enum": node_ids},
                "uniqueItems": True, "maxItems": len(node_ids),
            },
            "affected_edges": {
                "type": "array", "items": {"type": "string", "enum": edge_ids},
                "uniqueItems": True, "maxItems": len(edge_ids),
            },
            "abuse_path": {
                "type": "array", "items": {"type": "string", "maxLength": 300},
                "maxItems": 8,
            },
            "control_gap": {"type": "string", "maxLength": 500},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "missing_information": {
                "type": "array", "items": {"type": "string", "maxLength": 300},
                "maxItems": 8,
            },
        },
        "required": [
            "code", "name", "status", "threat_pattern", "evidence",
            "affected_nodes", "affected_edges", "abuse_path", "control_gap",
            "confidence", "missing_information",
        ],
    }


def run_case(
    model: str, test_case: dict[str, Any], seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    user_payload = {
        "candidate": {"code": test_case["target_code"], "name": test_case["risk_name"]},
        "questionnaire_answers": test_case["answers"],
        "dfd": test_case["dfd"],
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "stream": False,
        "think": False,
        "format": schema_for(test_case),
        "options": {
            "temperature": 0,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "seed": seed,
        },
        "keep_alive": "5m",
    }
    started = time.perf_counter()
    response = request_json("/api/chat", payload, REQUEST_TIMEOUT_SECONDS)
    wall_seconds = time.perf_counter() - started
    content = (response.get("message") or {}).get("content", "")
    parsed = json.loads(content)
    usage = {
        "wall_seconds": round(wall_seconds, 6),
        "done_reason": response.get("done_reason"),
        "total_duration_ns": response.get("total_duration"),
        "load_duration_ns": response.get("load_duration"),
        "prompt_eval_count": response.get("prompt_eval_count"),
        "prompt_eval_duration_ns": response.get("prompt_eval_duration"),
        "eval_count": response.get("eval_count"),
        "eval_duration_ns": response.get("eval_duration"),
    }
    return parsed, usage


def validate_shape(output: Any, target_code: str) -> bool:
    required = {
        "code", "name", "status", "threat_pattern", "evidence", "affected_nodes",
        "affected_edges", "abuse_path", "control_gap", "confidence", "missing_information",
    }
    if not isinstance(output, dict) or set(output) != required:
        return False
    if output.get("code") != target_code or output.get("status") not in STATUSES:
        return False
    if output.get("threat_pattern") not in PATTERNS or output.get("confidence") not in {"low", "medium", "high"}:
        return False
    return all(isinstance(output.get(key), list) for key in (
        "evidence", "affected_nodes", "affected_edges", "abuse_path", "missing_information"
    )) and isinstance(output.get("control_gap"), str) and isinstance(output.get("name"), str)


def question_refs(evidence: list[Any]) -> set[str]:
    refs: set[str] = set()
    for item in evidence:
        refs.update(re.findall(r"\bQ(?:[1-9]|[1-9][0-9])\b", str(item).upper()))
    return refs


def score_output(test_case: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    node_ids = {item["id"] for item in test_case["dfd"]["nodes"]}
    edge_ids = {item["id"] for item in test_case["dfd"]["edges"]}
    used_nodes = output.get("affected_nodes") if isinstance(output.get("affected_nodes"), list) else []
    used_edges = output.get("affected_edges") if isinstance(output.get("affected_edges"), list) else []
    total_refs = len(used_nodes) + len(used_edges)
    valid_refs = sum(item in node_ids for item in used_nodes) + sum(item in edge_ids for item in used_edges)
    grounding_precision = valid_refs / total_refs if total_refs else 1.0

    expected_evidence = set(test_case["expected_evidence"])
    cited = question_refs(output.get("evidence") or [])
    evidence_coverage = len(expected_evidence & cited) / len(expected_evidence) if expected_evidence else 1.0

    expected_nodes = set(test_case["expected_nodes"])
    node_linkage = 1.0 if not expected_nodes else float(bool(expected_nodes & set(used_nodes)))

    positive_status = output.get("status") in {"confirmed", "plausible"}
    if positive_status:
        actionability = float(len(output.get("abuse_path") or []) >= 2 and bool(str(output.get("control_gap") or "").strip()))
    else:
        actionability = float(not output.get("abuse_path") and not str(output.get("control_gap") or "").strip())

    return {
        "shape_valid": validate_shape(output, test_case["target_code"]),
        "status_match": output.get("status") in test_case["expected_statuses"],
        "pattern_match": output.get("threat_pattern") == test_case["expected_pattern"],
        "grounding_precision": round(grounding_precision, 6),
        "evidence_coverage": round(evidence_coverage, 6),
        "node_linkage": round(node_linkage, 6),
        "actionability": round(actionability, 6),
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def successful_mean(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row["scores"][key]) for row in rows if not row.get("error")]
    return statistics.fmean(values) if values else 0.0


def overall_mean(rows: list[dict[str, Any]], key: str) -> float:
    """Failed calls contribute zero instead of disappearing from the denominator."""
    if not rows:
        return 0.0
    return statistics.fmean(
        float(row.get("scores", {}).get(key, 0.0)) if not row.get("error") else 0.0
        for row in rows
    )


def status_classification_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Use the first expected status as the canonical label for macro metrics."""
    confusion = {
        expected: {predicted: 0 for predicted in [*STATUSES, "failed"]}
        for expected in STATUSES
    }
    for row in rows:
        expected = row["expected_statuses"][0]
        predicted = "failed" if row.get("error") else row["output"].get("status", "failed")
        if predicted not in confusion[expected]:
            predicted = "failed"
        confusion[expected][predicted] += 1

    precisions: list[float] = []
    recalls: list[float] = []
    f1_scores: list[float] = []
    for status in STATUSES:
        tp = confusion[status][status]
        fp = sum(confusion[other][status] for other in STATUSES if other != status)
        fn = sum(confusion[status][other] for other in [*STATUSES, "failed"] if other != status)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1_scores.append(f1)

    return {
        "confusion_matrix": confusion,
        "macro_precision": round(statistics.fmean(precisions), 6),
        "macro_recall": round(statistics.fmean(recalls), 6),
        "macro_f1": round(statistics.fmean(f1_scores), 6),
    }


def build_diagnostics(rows: list[dict[str, Any]], models: list[str]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    for model in models:
        model_rows = [row for row in rows if row["model"] == model]
        by_scenario: dict[str, Any] = {}
        for variant in ("positive", "control", "unknown"):
            subset = [row for row in model_rows if row["variant"] == variant]
            successful = [row for row in subset if not row.get("error")]
            by_scenario[variant] = {
                "calls": len(subset),
                "completed": len(successful),
                "completion_rate": round(len(successful) / len(subset), 6) if subset else 0.0,
                "overall_status_match_rate": round(overall_mean(subset, "status_match"), 6),
                "conditional_status_match_rate": round(successful_mean(subset, "status_match"), 6),
            }

        stability: dict[str, Any] = {}
        for case_id in sorted({row["case_id"] for row in model_rows}):
            subset = [row for row in model_rows if row["case_id"] == case_id]
            successful = [row for row in subset if not row.get("error")]
            statuses = [row["output"]["status"] for row in successful]
            patterns = [row["output"]["threat_pattern"] for row in successful]
            stability[case_id] = {
                "completed_repeats": len(successful),
                "expected_repeats": len(subset),
                "status_stable": len(successful) == len(subset) and len(set(statuses)) == 1,
                "pattern_stable": len(successful) == len(subset) and len(set(patterns)) == 1,
                "statuses": statuses,
                "patterns": patterns,
            }

        diagnostics[model] = {
            **status_classification_metrics(model_rows),
            "by_scenario": by_scenario,
            "repeat_stability": stability,
        }
    return diagnostics


def summarize(rows: list[dict[str, Any]], models: list[str]) -> list[dict[str, Any]]:
    summary = []
    for model in models:
        model_rows = [row for row in rows if row["model"] == model]
        successful = [row for row in model_rows if not row.get("error")]
        latencies = [float(row["usage"]["wall_seconds"]) for row in successful]
        token_rates = []
        for row in successful:
            count = row["usage"].get("eval_count")
            duration = row["usage"].get("eval_duration_ns")
            if count and duration:
                token_rates.append(float(count) / (float(duration) / 1_000_000_000))
        classification = status_classification_metrics(model_rows)
        completion_rate = len(successful) / len(model_rows) if model_rows else 0.0
        schema_success = overall_mean(model_rows, "shape_valid")
        summary.append({
            "model": model,
            "calls": len(model_rows),
            "successful_calls": len(successful),
            "completion_rate": round(completion_rate, 4),
            "overall_schema_success_rate": round(schema_success, 4),
            "overall_status_match_rate": round(overall_mean(model_rows, "status_match"), 4),
            "conditional_status_match_rate": round(successful_mean(model_rows, "status_match"), 4),
            "status_macro_precision": round(classification["macro_precision"], 4),
            "status_macro_recall": round(classification["macro_recall"], 4),
            "status_macro_f1": round(classification["macro_f1"], 4),
            "overall_pattern_match_rate": round(overall_mean(model_rows, "pattern_match"), 4),
            "conditional_pattern_match_rate": round(successful_mean(model_rows, "pattern_match"), 4),
            "mean_grounding_precision": round(successful_mean(model_rows, "grounding_precision"), 4),
            "mean_evidence_coverage": round(successful_mean(model_rows, "evidence_coverage"), 4),
            "mean_node_linkage": round(successful_mean(model_rows, "node_linkage"), 4),
            "mean_actionability": round(successful_mean(model_rows, "actionability"), 4),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95_latency_seconds": round(percentile(latencies, 0.95), 3),
            "mean_output_tokens_per_second": round(statistics.fmean(token_rates), 3) if token_rates else 0.0,
            "passes_reliability_gate": completion_rate >= 0.95 and schema_success >= 0.95,
        })
    return sorted(
        summary,
        key=lambda row: (
            -int(row["passes_reliability_gate"]), -row["status_macro_f1"],
            -row["mean_evidence_coverage"], -row["mean_actionability"],
            row["p95_latency_seconds"],
        ),
    )


def pull_model(model: str) -> None:
    print(f"\nPulling {model} ...", flush=True)
    subprocess.run(["ollama", "pull", model], check=True)


def warm_up(model: str) -> None:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": 'Return JSON only: {"ready":true}'}],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0, "num_ctx": NUM_CTX, "num_predict": 32, "seed": SEEDS[0],
        },
        "keep_alive": "5m",
    }
    request_json("/api/chat", payload, REQUEST_TIMEOUT_SECONDS)


def unload(model: str) -> None:
    try:
        request_json("/api/generate", {"model": model, "keep_alive": 0}, 30)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the standalone 3B OWASP threat-identification benchmark.")
    parser.add_argument(
        "--quick", action="store_true",
        help="Run the three LLM01 cases once with every model to verify the setup.",
    )
    args = parser.parse_args()

    models = MODELS
    cases = CASES[:3] if args.quick else CASES
    runs_per_case = 1 if args.quick else RUNS_PER_CASE
    seeds = SEEDS[:runs_per_case]

    try:
        request_json("/api/tags", timeout=5)
    except Exception as exc:
        raise SystemExit(
            "Ollama is not reachable at 127.0.0.1:11434. Start `ollama serve` "
            "in the background before running this file."
        ) from exc

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path("/content") if Path("/content").exists() else Path.cwd()
    raw_path = output_dir / f"owasp_3b_benchmark_{run_id}.jsonl"
    summary_path = output_dir / f"owasp_3b_benchmark_summary_{run_id}.csv"
    metadata_path = output_dir / f"owasp_3b_benchmark_metadata_{run_id}.json"
    diagnostics_path = output_dir / f"owasp_3b_benchmark_diagnostics_{run_id}.json"

    metadata_path.write_text(json.dumps({
        "run_id": run_id,
        "models": models,
        "runs_per_case": runs_per_case,
        "num_ctx": NUM_CTX,
        "num_predict": NUM_PREDICT,
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "temperature": 0,
        "seeds": seeds,
        "case_count": len(cases),
        "ollama_version": subprocess.run(
            ["ollama", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip(),
    }, indent=2), encoding="utf-8")

    rows: list[dict[str, Any]] = []
    total = len(models) * len(cases) * runs_per_case
    completed = 0

    for model in models:
        pull_model(model)
        print(f"Warming up {model} ...", flush=True)
        warm_up(model)

        for repeat, seed in enumerate(seeds, start=1):
            for test_case in cases:
                completed += 1
                print(
                    f"[{completed}/{total}] {model} | repeat={repeat} | {test_case['id']}",
                    flush=True,
                )
                row: dict[str, Any] = {
                    "run_id": run_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "model": model,
                    "repeat": repeat,
                    "seed": seed,
                    "case_id": test_case["id"],
                    "target_code": test_case["target_code"],
                    "variant": test_case["variant"],
                    "expected_statuses": test_case["expected_statuses"],
                }
                try:
                    output, usage = run_case(model, test_case, seed)
                    row["output"] = output
                    row["usage"] = usage
                    row["scores"] = score_output(test_case, output)
                    row["error"] = None
                except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                    row["output"] = None
                    row["usage"] = {}
                    row["scores"] = {}
                    row["error"] = f"{type(exc).__name__}: {exc}"
                except Exception as exc:
                    row["output"] = None
                    row["usage"] = {}
                    row["scores"] = {}
                    row["error"] = f"{type(exc).__name__}: {exc}"

                rows.append(row)
                with raw_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        unload(model)

    summary = summarize(rows, models)
    diagnostics_path.write_text(
        json.dumps(build_diagnostics(rows, models), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print("\n=== SUMMARY ===")
    for rank, item in enumerate(summary, start=1):
        print(
            f"{rank}. {item['model']} | complete={item['completion_rate']:.3f} | "
            f"macro_f1={item['status_macro_f1']:.3f} | "
            f"status_overall={item['overall_status_match_rate']:.3f} | "
            f"schema_overall={item['overall_schema_success_rate']:.3f} | "
            f"evidence={item['mean_evidence_coverage']:.3f} | "
            f"median={item['median_latency_seconds']:.2f}s | tok/s={item['mean_output_tokens_per_second']:.2f}"
        )
    print(f"\nRaw results: {raw_path}")
    print(f"Summary CSV: {summary_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Diagnostics: {diagnostics_path}")


if __name__ == "__main__":
    main()
