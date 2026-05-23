import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.services.dfd_service import archive_dfd_graph, list_response_files, load_response_payload
from app.services.extract_to_reactflow import extract_to_reactflow, has_recognized_dfd_content
from app.services.llm_extract_service import generate_llm_extract, parse_extract_json
from app.services.risk_analysis_service import RISK_RANK, build_risk_analysis


PIPELINE_ARTIFACTS = {
    "manifest.json",
    "response.json",
    "llm_extraction.json",
    "extraction_raw.json",
    "extraction_reviewed.json",
    "dfd_reactflow.json",
    "risks.json",
    "garak_plan.json",
}

PIPELINE_STEPS = {
    "response_saved": "response.json",
    "llm_extraction_generated": "extraction_raw.json",
    "dfd_generated": "dfd_reactflow.json",
    "risk_analysis_completed": "risks.json",
    "garak_plan_created": "garak_plan.json",
}

GARAK_RISK_MAPPING = {
    "LLM01": {
        "risk_name": "Prompt Injection",
        "garak_focus": "Prompt injection, jailbreak, instruction override, and indirect prompt injection probes.",
    },
    "LLM02": {
        "risk_name": "Sensitive Information Disclosure",
        "garak_focus": "Sensitive data leakage, memorization, secret disclosure, and privacy exposure probes.",
    },
    "LLM05": {
        "risk_name": "Improper Output Handling",
        "garak_focus": "Unsafe output, dangerous content, structured output misuse, and downstream handling probes.",
    },
    "LLM06": {
        "risk_name": "Excessive Agency",
        "garak_focus": "Tool misuse, excessive action authority, and autonomous behavior probes.",
    },
    "LLM08": {
        "risk_name": "Vector and Embedding Weaknesses",
        "garak_focus": "RAG, embedding retrieval, context injection, and poisoned knowledge probes.",
    },
    "LLM09": {
        "risk_name": "Misinformation",
        "garak_focus": "Hallucination, factuality, false assertion, and unsupported claim probes.",
    },
    "LLM10": {
        "risk_name": "Unbounded Consumption",
        "garak_focus": "Abuse, resource usage, denial-of-wallet, and repeated workload probes.",
    },
}


class PipelineOrchestrator:
    def __init__(self, app_root_path, app_config=None):
        self.app_root_path = Path(app_root_path)
        self.workspace_root = self.app_root_path.parent
        self.pipelines_dir = self.workspace_root / "pipelines"
        self.app_config = app_config

    def create_pipeline(self, response_filename, project_name=None, dfd_name=None, auditor_name=None):
        response_name = Path(str(response_filename or "")).name
        if response_name not in list_response_files(self.app_root_path):
            raise FileNotFoundError(response_filename)

        response_payload = load_response_payload(self.app_root_path, response_name)
        project = _clean_metadata_value(project_name) or Path(response_name).stem
        dfd = _clean_metadata_value(dfd_name) or f"{project} DFD"
        auditor = _clean_metadata_value(auditor_name)
        pipeline_id = self._new_pipeline_id(project)
        pipeline_dir = self._pipeline_dir(pipeline_id, must_exist=False)
        pipeline_dir.mkdir(parents=True, exist_ok=False)

        source_path = self.workspace_root / "responses" / response_name
        shutil.copyfile(source_path, pipeline_dir / "response.json")

        now = _utc_now()
        manifest = {
            "pipeline_id": pipeline_id,
            "project_name": project,
            "dfd_name": dfd,
            "auditor_name": auditor,
            "source_response": response_name,
            "created_at": now,
            "updated_at": now,
            "status": "created",
            "steps": _initial_steps(now),
        }
        self._write_json(pipeline_dir / "manifest.json", manifest)

        # Validate early that the copied response is usable by downstream services.
        if not isinstance(response_payload, dict):
            self._mark_step_error(manifest, "response_saved", "Response payload is not a JSON object.")
            self._save_manifest(manifest)
            raise ValueError("Response payload is not a JSON object.")

        return manifest

    def get_manifest(self, pipeline_id):
        return self._load_manifest(pipeline_id)

    def pipeline_workspace(self, pipeline_id):
        return self._pipeline_dir(pipeline_id)

    def generate_extraction(self, pipeline_id):
        manifest = self._load_manifest(pipeline_id)
        self._mark_running(manifest, "llm_extraction_generated")
        try:
            metadata = {
                "project_name": manifest.get("project_name") or Path(manifest["source_response"]).stem,
                "dfd_name": manifest.get("dfd_name"),
                "auditor_name": manifest.get("auditor_name"),
                "description": "Pipeline-generated LLM extraction.",
            }
            extract = generate_llm_extract(
                self.app_root_path,
                metadata,
                manifest["source_response"],
                self.app_config,
            )
            parsed = extract.get("parsed") if isinstance(extract, dict) else None
            if not isinstance(parsed, dict):
                parsed = parse_extract_json(extract.get("raw")) if isinstance(extract, dict) else None
            if not isinstance(parsed, dict):
                parsed = {}

            self._write_artifact(pipeline_id, "extraction_raw.json", parsed)
            self._mark_step_done(manifest, "llm_extraction_generated")
            return parsed
        except Exception as exc:
            self._mark_step_error(manifest, "llm_extraction_generated", str(exc))
            raise
        finally:
            self._save_manifest(manifest)

    def generate_dfd(self, pipeline_id):
        manifest = self._load_manifest(pipeline_id)
        self._mark_running(manifest, "dfd_generated")
        try:
            extract_payload = self._load_extraction_artifact(pipeline_id)
            response_payload = self._load_artifact(pipeline_id, "response.json")
            answers_by_flow_id = _answers_by_flow_id(response_payload)
            if not has_recognized_dfd_content(extract_payload) and not answers_by_flow_id:
                raise ValueError(
                    "LLM extraction did not contain recognizable DFD architecture fields. "
                    "Expected either `dfd` or `architecture` content."
                )
            graph = extract_to_reactflow(
                extract_payload if isinstance(extract_payload, dict) else {},
                answers_by_flow_id=answers_by_flow_id,
            )
            if len(graph.get("nodes") or []) <= 1:
                raise ValueError("Generated DFD has no architecture nodes; check the extraction artifact.")
            self._write_artifact(pipeline_id, "dfd_reactflow.json", graph)
            archive_path = archive_dfd_graph(
                self.app_root_path,
                graph,
                manifest.get("dfd_name") or manifest.get("source_response"),
                {
                    "pipeline_id": pipeline_id,
                    "display_name": manifest.get("dfd_name") or f"{Path(manifest.get('source_response') or pipeline_id).stem} DFD",
                    "project_name": manifest.get("project_name"),
                    "auditor_name": manifest.get("auditor_name"),
                    "pipeline_workspace": str(self._pipeline_dir(pipeline_id)),
                },
            )
            manifest["dfd_archive"] = archive_path.name
            self._mark_step_done(manifest, "dfd_generated")
            return graph
        except Exception as exc:
            self._mark_step_error(manifest, "dfd_generated", str(exc))
            raise
        finally:
            self._save_manifest(manifest)

    def run_risk_analysis(self, pipeline_id):
        manifest = self._load_manifest(pipeline_id)
        self._mark_running(manifest, "risk_analysis_completed")
        try:
            response_payload = self._load_artifact(pipeline_id, "response.json")
            extract_payload = self._load_extraction_artifact(pipeline_id)

            risks = build_risk_analysis(
                self.app_root_path,
                response_payload if isinstance(response_payload, dict) else {},
                extract_payload if isinstance(extract_payload, dict) else None,
            )
            self._write_artifact(pipeline_id, "risks.json", risks)
            self._mark_step_done(manifest, "risk_analysis_completed")
            return risks
        except Exception as exc:
            self._mark_step_error(manifest, "risk_analysis_completed", str(exc))
            raise
        finally:
            self._save_manifest(manifest)

    def create_garak_plan(self, pipeline_id):
        manifest = self._load_manifest(pipeline_id)
        self._mark_running(manifest, "garak_plan_created")
        try:
            risks_payload = self._load_artifact(pipeline_id, "risks.json")
            selected_risks = _selected_risks(risks_payload)
            recommended_tests = []

            for risk in selected_risks:
                code = str(risk.get("code") or "").upper()
                mapping = GARAK_RISK_MAPPING.get(code)
                if not mapping:
                    continue
                recommended_tests.append(
                    {
                        "owasp_llm": code,
                        "risk_name": risk.get("name") or mapping["risk_name"],
                        "garak_focus": mapping["garak_focus"],
                        "reason": _risk_reason(risk),
                        "status": "planned",
                    }
                )

            plan = {
                "pipeline_id": pipeline_id,
                "created_at": _utc_now(),
                "selected_risks": selected_risks,
                "recommended_tests": recommended_tests,
            }
            self._write_artifact(pipeline_id, "garak_plan.json", plan)
            self._mark_step_done(manifest, "garak_plan_created")
            return plan
        except Exception as exc:
            self._mark_step_error(manifest, "garak_plan_created", str(exc))
            raise
        finally:
            self._save_manifest(manifest)

    def run_until_risk_analysis(self, pipeline_id):
        self.generate_extraction(pipeline_id)
        self.generate_dfd(pipeline_id)
        self.run_risk_analysis(pipeline_id)
        return self.get_manifest(pipeline_id)

    def list_pipelines(self):
        self.pipelines_dir.mkdir(parents=True, exist_ok=True)
        pipelines = []
        for pipeline_dir in self.pipelines_dir.iterdir():
            if not pipeline_dir.is_dir():
                continue
            manifest_path = pipeline_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            pipelines.append(manifest)
        return sorted(pipelines, key=lambda item: item.get("created_at") or "", reverse=True)

    def artifact_exists(self, pipeline_id, artifact_name):
        return self._artifact_path(pipeline_id, artifact_name).exists()

    def load_artifact(self, pipeline_id, artifact_name):
        return self._load_artifact(pipeline_id, artifact_name)

    def _new_pipeline_id(self, name):
        safe_stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(name or "")).strip("-._")
        if not safe_stem:
            safe_stem = "pipeline"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        base_id = f"{timestamp}-{safe_stem}"
        pipeline_id = base_id
        suffix = 2
        while (self.pipelines_dir / pipeline_id).exists():
            pipeline_id = f"{base_id}-{suffix}"
            suffix += 1
        return pipeline_id

    def _pipeline_dir(self, pipeline_id, must_exist=True):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", str(pipeline_id or "")):
            raise ValueError("Invalid pipeline id.")
        candidate = (self.pipelines_dir / str(pipeline_id)).resolve()
        if self.pipelines_dir.resolve() not in candidate.parents:
            raise ValueError("Invalid pipeline id.")
        if must_exist and not candidate.exists():
            raise FileNotFoundError(pipeline_id)
        return candidate

    def _artifact_path(self, pipeline_id, artifact_name):
        artifact = Path(str(artifact_name or "")).name
        if artifact not in PIPELINE_ARTIFACTS:
            raise ValueError("Invalid pipeline artifact.")
        return self._pipeline_dir(pipeline_id) / artifact

    def _load_manifest(self, pipeline_id):
        manifest_path = self._artifact_path(pipeline_id, "manifest.json")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _save_manifest(self, manifest):
        manifest["updated_at"] = _utc_now()
        manifest["status"] = _manifest_status(manifest)
        self._write_artifact(manifest["pipeline_id"], "manifest.json", manifest)

    def _write_artifact(self, pipeline_id, artifact_name, payload):
        self._write_json(self._artifact_path(pipeline_id, artifact_name), payload)

    def _load_artifact(self, pipeline_id, artifact_name):
        artifact_path = self._artifact_path(pipeline_id, artifact_name)
        if not artifact_path.exists():
            raise FileNotFoundError(artifact_name)
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def _load_optional_artifact(self, pipeline_id, artifact_name):
        try:
            return self._load_artifact(pipeline_id, artifact_name)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return None

    def _load_extraction_artifact(self, pipeline_id):
        for artifact_name in ("extraction_raw.json", "llm_extraction.json", "extraction_reviewed.json"):
            payload = self._load_optional_artifact(pipeline_id, artifact_name)
            if isinstance(payload, dict):
                return payload
        return None

    def _write_json(self, path, payload):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _mark_running(self, manifest, step_name):
        step = manifest["steps"][step_name]
        step["error"] = None
        manifest["status"] = f"{step_name}_running"
        manifest["updated_at"] = _utc_now()
        self._write_artifact(manifest["pipeline_id"], "manifest.json", manifest)

    def _mark_step_done(self, manifest, step_name):
        step = manifest["steps"][step_name]
        step["done"] = True
        step["timestamp"] = _utc_now()
        step["error"] = None

    def _mark_step_error(self, manifest, step_name, error):
        step = manifest["steps"][step_name]
        step["done"] = False
        step["timestamp"] = None
        step["error"] = str(error)


def _pending_step(artifact):
    return {
        "done": False,
        "timestamp": None,
        "artifact": artifact,
        "error": None,
    }


def _initial_steps(timestamp):
    steps = {}
    for step_name, artifact in PIPELINE_STEPS.items():
        if step_name == "response_saved":
            steps[step_name] = {
                "done": True,
                "timestamp": timestamp,
                "artifact": artifact,
            }
        else:
            steps[step_name] = _pending_step(artifact)
    return steps


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_metadata_value(value):
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)[:120]


def _manifest_status(manifest):
    steps = manifest.get("steps") or {}
    if any(isinstance(step, dict) and step.get("error") for step in steps.values()):
        return "failed"
    if steps.get("garak_plan_created", {}).get("done"):
        return "garak_plan_created"
    if steps.get("risk_analysis_completed", {}).get("done"):
        return "risk_analysis_completed"
    if steps.get("dfd_generated", {}).get("done"):
        return "dfd_generated"
    if steps.get("llm_extraction_generated", {}).get("done"):
        return "llm_extraction_generated"
    if steps.get("extraction_reviewed", {}).get("done"):
        return "llm_extraction_generated"
    if steps.get("extraction_generated", {}).get("done"):
        return "llm_extraction_generated"
    return "created"


def _selected_risks(risks_payload):
    if not isinstance(risks_payload, dict):
        return []

    merged = {}
    for source_name in ("extract_risks", "mapped_risks"):
        risk_list = risks_payload.get(source_name)
        if not isinstance(risk_list, list):
            continue
        for risk in risk_list:
            if not isinstance(risk, dict):
                continue
            code = str(risk.get("code") or "").upper()
            if not code:
                continue
            existing = merged.get(code)
            if existing is None or RISK_RANK.get(risk.get("risk_level"), 0) > RISK_RANK.get(existing.get("risk_level"), 0):
                merged[code] = {
                    "code": code,
                    "name": risk.get("name") or code,
                    "risk_level": risk.get("risk_level") or "Medium",
                    "source": source_name,
                    "score": risk.get("score"),
                    "why": risk.get("why") or "",
                }

    return sorted(
        merged.values(),
        key=lambda item: (-RISK_RANK.get(item.get("risk_level"), 0), item.get("code", "")),
    )


def _risk_reason(risk):
    parts = [f"{risk.get('code')} was identified as {risk.get('risk_level', 'Medium')} risk"]
    if risk.get("source") == "extract_risks":
        parts.append("by the LLM extraction")
    elif risk.get("source") == "mapped_risks":
        parts.append("from questionnaire OWASP mappings")
    if risk.get("score") is not None:
        parts.append(f"with questionnaire score {risk.get('score')}")
    if risk.get("why"):
        parts.append(str(risk["why"]))
    return ". ".join(part for part in parts if part) + "."


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
        flow_id = str(answer_record.get("flow_id") or "").strip()
        answer = answer_record.get("answer")
        if flow_id and answer not in (None, "", []):
            normalized[flow_id] = answer
    return normalized
