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
REQUEST_TIMEOUT_SECONDS = 300
NUM_CTX = 8192

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
        "TC-LLM01-POS-01", "LLM01:2026", "Prompt Injection", "positive",
        {"Q5": "Retrieved internal documents", "Q6": "Web URLs",
         "Q20": "Yes, through retrieved documents or memory", "Q30": "No safeguards",
         "Q84": "Yes, parsed and inserted with minimal validation"},
        DFD_PROMPT_INJECTION, ["confirmed"], "prompt_context_manipulation",
        ["Q20", "Q30", "Q84"], ["rag_retriever", "llm_gateway"],
    ),
    case(
        "TC-LLM01-CTRL-01", "LLM01:2026", "Prompt Injection", "control",
        {"Q5": "Direct user prompts", "Q6": "User text input only", "Q20": "No",
         "Q30": "Context isolation and instruction hierarchy controls",
         "Q84": "Yes, parsed with strict validation and normalization"},
        DFD_PROMPT_INJECTION, ["not_applicable"], "prompt_context_manipulation",
        ["Q20", "Q30", "Q84"], [],
    ),
    case(
        "TC-LLM01-UNK-01", "LLM01:2026", "Prompt Injection", "unknown",
        {"Q5": "Retrieved internal documents", "Q6": "Web URLs", "Q20": "Unknown",
         "Q30": "Unknown", "Q84": "Unknown"},
        DFD_PROMPT_INJECTION, ["needs_more_info"], "prompt_context_manipulation",
        ["Q20", "Q30", "Q84"], [],
    ),
    case(
        "TC-LLM02-POS-01", "LLM02:2026", "Sensitive Information Disclosure", "positive",
        {"Q24": ["Personally identifiable information (PII)", "API keys or credentials"],
         "Q32": "No safeguards", "Q47": "Logs contain full prompts and responses"},
        DFD_SENSITIVE_DATA, ["confirmed"], "sensitive_data_exposure",
        ["Q24", "Q32", "Q47"], ["llm_gateway", "log_store"],
    ),
    case(
        "TC-LLM02-CTRL-01", "LLM02:2026", "Sensitive Information Disclosure", "control",
        {"Q24": "Personally identifiable information (PII)",
         "Q32": "DLP or content inspection mechanisms",
         "Q47": "Logs contain non-sensitive metadata only"},
        DFD_SENSITIVE_DATA, ["not_applicable", "plausible"], "sensitive_data_exposure",
        ["Q24", "Q32", "Q47"], [],
    ),
    case(
        "TC-LLM02-UNK-01", "LLM02:2026", "Sensitive Information Disclosure", "unknown",
        {"Q24": "Unknown", "Q32": "Unknown", "Q47": "Unknown"},
        DFD_SENSITIVE_DATA, ["needs_more_info"], "sensitive_data_exposure",
        ["Q24", "Q32", "Q47"], [],
    ),
    case(
        "TC-LLM10-POS-01", "LLM10:2026", "Improper Output Handling", "positive",
        {"Q21": ["HTML or rendered content", "Code or scripts"],
         "Q22": "Directly used in backend automation", "Q31": "Not validated",
         "Q64": "HTML/rich content without reliable sanitization",
         "Q65": "Yes, directly used with minimal validation", "Q66": "No dedicated controls"},
        DFD_OUTPUT, ["confirmed"], "unsafe_output_handling",
        ["Q31", "Q64", "Q65", "Q66"], ["llm_gateway", "web_renderer", "backend_automation"],
    ),
    case(
        "TC-LLM10-CTRL-01", "LLM10:2026", "Improper Output Handling", "control",
        {"Q21": "Plain text only", "Q22": "User-facing web interface",
         "Q31": "Rule-based or schema validation", "Q64": "Markdown with sanitization",
         "Q65": "No structured output drives downstream operations",
         "Q66": "Yes, strict blocking or allowlisting"},
        DFD_OUTPUT, ["not_applicable"], "unsafe_output_handling",
        ["Q31", "Q64", "Q65", "Q66"], [],
    ),
    case(
        "TC-LLM10-UNK-01", "LLM10:2026", "Improper Output Handling", "unknown",
        {"Q21": "Structured JSON", "Q22": "Directly used in backend automation",
         "Q31": "Unknown", "Q64": "Unknown", "Q65": "Unknown", "Q66": "Unknown"},
        DFD_OUTPUT, ["needs_more_info", "plausible"], "unsafe_output_handling",
        ["Q31", "Q65", "Q66"], [],
    ),
    case(
        "TC-LLM03-POS-01", "LLM03:2026", "Excessive Agency", "positive",
        {"Q11": "Agent workflow", "Q12": ["Internal APIs", "Admin tools"],
         "Q15": ["Execute workflows or transactions", "Modify system configurations"],
         "Q16": "Yes, in business-critical actions", "Q44": "No separation of permissions"},
        DFD_AGENCY, ["confirmed"], "excessive_tool_or_workflow_agency",
        ["Q12", "Q15", "Q16", "Q44"], ["llm_orchestrator", "tool_runtime", "admin_tool"],
    ),
    case(
        "TC-LLM03-CTRL-01", "LLM03:2026", "Excessive Agency", "control",
        {"Q11": "Basic logic", "Q12": "Search", "Q15": "Generate text responses only",
         "Q16": "No, human approval is always required",
         "Q44": "Granular permissions including admin or destructive actions"},
        DFD_AGENCY, ["not_applicable"], "excessive_tool_or_workflow_agency",
        ["Q15", "Q16", "Q44"], [],
    ),
    case(
        "TC-LLM03-UNK-01", "LLM03:2026", "Excessive Agency", "unknown",
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


def schema_for(target_code: str) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "code": {"type": "string", "enum": [target_code]},
            "name": {"type": "string"},
            "status": {"type": "string", "enum": STATUSES},
            "threat_pattern": {"type": "string", "enum": PATTERNS},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "affected_nodes": {"type": "array", "items": {"type": "string"}},
            "affected_edges": {"type": "array", "items": {"type": "string"}},
            "abuse_path": {"type": "array", "items": {"type": "string"}},
            "control_gap": {"type": "string"},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "missing_information": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "code", "name", "status", "threat_pattern", "evidence",
            "affected_nodes", "affected_edges", "abuse_path", "control_gap",
            "confidence", "missing_information",
        ],
    }


def run_case(model: str, test_case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
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
        "format": schema_for(test_case["target_code"]),
        "options": {"temperature": 0, "num_ctx": NUM_CTX},
        "keep_alive": "5m",
    }
    started = time.perf_counter()
    response = request_json("/api/chat", payload, REQUEST_TIMEOUT_SECONDS)
    wall_seconds = time.perf_counter() - started
    content = (response.get("message") or {}).get("content", "")
    parsed = json.loads(content)
    usage = {
        "wall_seconds": round(wall_seconds, 6),
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


def mean(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row["scores"][key]) for row in rows if not row.get("error")]
    return statistics.fmean(values) if values else 0.0


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
        summary.append({
            "model": model,
            "calls": len(model_rows),
            "successful_calls": len(successful),
            "success_rate": round(len(successful) / len(model_rows), 4) if model_rows else 0.0,
            "shape_valid_rate": round(mean(model_rows, "shape_valid"), 4),
            "status_match_rate": round(mean(model_rows, "status_match"), 4),
            "pattern_match_rate": round(mean(model_rows, "pattern_match"), 4),
            "mean_grounding_precision": round(mean(model_rows, "grounding_precision"), 4),
            "mean_evidence_coverage": round(mean(model_rows, "evidence_coverage"), 4),
            "mean_node_linkage": round(mean(model_rows, "node_linkage"), 4),
            "mean_actionability": round(mean(model_rows, "actionability"), 4),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95_latency_seconds": round(percentile(latencies, 0.95), 3),
            "mean_output_tokens_per_second": round(statistics.fmean(token_rates), 3) if token_rates else 0.0,
        })
    return sorted(
        summary,
        key=lambda row: (
            -row["status_match_rate"], -row["shape_valid_rate"],
            -row["mean_evidence_coverage"], row["median_latency_seconds"],
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
        "options": {"temperature": 0, "num_ctx": NUM_CTX},
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
        help="Run only the three LLM01 cases once with Qwen, to verify the setup.",
    )
    args = parser.parse_args()

    models = MODELS[:1] if args.quick else MODELS
    cases = CASES[:3] if args.quick else CASES
    runs_per_case = 1 if args.quick else RUNS_PER_CASE

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

    metadata_path.write_text(json.dumps({
        "run_id": run_id,
        "models": models,
        "runs_per_case": runs_per_case,
        "num_ctx": NUM_CTX,
        "temperature": 0,
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

        for repeat in range(1, runs_per_case + 1):
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
                    "case_id": test_case["id"],
                    "target_code": test_case["target_code"],
                    "variant": test_case["variant"],
                    "expected_statuses": test_case["expected_statuses"],
                }
                try:
                    output, usage = run_case(model, test_case)
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
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print("\n=== SUMMARY ===")
    for rank, item in enumerate(summary, start=1):
        print(
            f"{rank}. {item['model']} | status={item['status_match_rate']:.3f} | "
            f"schema={item['shape_valid_rate']:.3f} | evidence={item['mean_evidence_coverage']:.3f} | "
            f"median={item['median_latency_seconds']:.2f}s | tok/s={item['mean_output_tokens_per_second']:.2f}"
        )
    print(f"\nRaw results: {raw_path}")
    print(f"Summary CSV: {summary_path}")
    print(f"Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
