import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.services.dfd_service import archive_dfd_graph, list_response_files, load_response_payload
from app.services.feature_flags import flag_enabled
from app.services.risk_analysis_service import (
    ThreatIdentificationUnavailable,
    build_risk_analysis,
    build_threat_analysis,
)
from app.services.static_dfd_mapper import build_static_dfd_from_answers


PIPELINE_ARTIFACTS = {
    "manifest.json",
    "response.json",
    "dfd_reactflow.json",
    "risks.json",
}

PIPELINE_STEPS = {
    "response_saved": "response.json",
    "dfd_generated": "dfd_reactflow.json",
    "risk_analysis_completed": "risks.json",
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

    def generate_dfd(self, pipeline_id):
        manifest = self._load_manifest(pipeline_id)
        self._mark_running(manifest, "dfd_generated")
        try:
            response_payload = self._load_artifact(pipeline_id, "response.json")
            answers_by_flow_id = _answers_by_flow_id(response_payload)
            if not answers_by_flow_id:
                raise ValueError("Questionnaire response did not contain answers_by_flow_id for static DFD mapping.")

            graph = build_static_dfd_from_answers({"answers_by_flow_id": answers_by_flow_id})
            graph.setdefault("metadata", {})
            graph["metadata"].update(
                {
                    "pipeline_id": pipeline_id,
                    "pipeline_source": "static_dfd_mapper",
                    "display_name": manifest.get("dfd_name") or f"{Path(manifest.get('source_response') or pipeline_id).stem} DFD",
                    "project_name": manifest.get("project_name"),
                    "auditor_name": manifest.get("auditor_name"),
                    "source_response": manifest.get("source_response"),
                }
            )
            if len(graph.get("nodes") or []) <= 1:
                raise ValueError("Generated DFD has no architecture nodes; check the questionnaire response.")
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
            response_payload = response_payload if isinstance(response_payload, dict) else {}

            # The DFD step normally runs first; load the full graph so the new
            # threat-identification + grounding stages can reference node/edge ids.
            dfd_graph = None
            if self.artifact_exists(pipeline_id, "dfd_reactflow.json"):
                try:
                    dfd_graph = self._load_artifact(pipeline_id, "dfd_reactflow.json")
                except (FileNotFoundError, ValueError, json.JSONDecodeError):
                    dfd_graph = None

            risks = None
            fallback_reason = None
            fallback_detail = None
            # Target-order pipeline (feature-flagged). Requires a DFD for grounding.
            if not flag_enabled(self.app_config, "LLM_THREAT_IDENTIFICATION_ENABLED", True):
                fallback_reason = "flag_disabled"
            elif not isinstance(dfd_graph, dict):
                fallback_reason = "no_dfd"
            else:
                try:
                    risks = build_threat_analysis(self.app_root_path, response_payload, dfd_graph, self.app_config)
                except ThreatIdentificationUnavailable as exc:
                    fallback_reason = "llm_unavailable"
                    fallback_detail = str(exc)
                    print(f"[pipeline] threat identification unavailable; using deterministic baseline: {exc}", file=sys.stderr)
                except Exception as exc:  # never block a valid risks.json (feature-flag contract)
                    fallback_reason = "threat_path_error"
                    fallback_detail = str(exc)
                    print(f"[pipeline] threat-analysis path failed; using deterministic baseline: {exc}", file=sys.stderr)

            if risks is None:
                risks = self._deterministic_risk_analysis(response_payload, dfd_graph, fallback_reason, fallback_detail)

            self._write_artifact(pipeline_id, "risks.json", risks)
            self._mark_step_done(manifest, "risk_analysis_completed")
            return risks
        except Exception as exc:
            self._mark_step_error(manifest, "risk_analysis_completed", str(exc))
            raise
        finally:
            self._save_manifest(manifest)

    def _deterministic_risk_analysis(self, response_payload, dfd_graph, reason=None, detail=None):
        """Deterministic baseline risks.json (no template-guided LLM stages).

        Used when the new pipeline is disabled or the LLM threat-identification stage
        is unavailable, so a valid deterministic risks.json is always produced. The
        result is stamped with provenance (``pipeline_mode`` / ``threat_identification``
        / ``pipeline_warning``) so the artifact is self-describing about which path
        produced it and why.
        """
        risks = build_risk_analysis(
            self.app_root_path,
            response_payload if isinstance(response_payload, dict) else {},
            dfd_payload=dfd_graph,
        )

        used_fallback = reason in ("llm_unavailable", "threat_path_error")
        messages = {
            "flag_disabled": "Template-guided LLM threat identification is disabled; deterministic baseline used.",
            "no_dfd": "No DFD available for grounding; deterministic baseline used.",
            "llm_unavailable": "Local LLM threat identification was unavailable; deterministic baseline used.",
            "threat_path_error": "Template-guided pipeline failed; deterministic baseline used.",
            None: "Deterministic baseline.",
        }
        message = messages.get(reason, messages[None])
        if detail and used_fallback:
            message = f"{message} ({detail})"
        risks["pipeline_mode"] = "deterministic_fallback" if used_fallback else "deterministic_baseline"
        risks["threat_identification"] = {
            "mode": "deterministic_fallback" if used_fallback else "disabled",
            "status": reason or "baseline",
            "message": message,
        }
        if used_fallback:
            risks["pipeline_warning"] = message
        return risks

    def run_until_risk_analysis(self, pipeline_id):
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
    if steps.get("risk_analysis_completed", {}).get("done"):
        return "risk_analysis_completed"
    if steps.get("dfd_generated", {}).get("done"):
        return "dfd_generated"
    return "created"


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
