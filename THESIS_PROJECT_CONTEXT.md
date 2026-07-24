# THESIS_PROJECT_CONTEXT.md

> Project knowledge base for a **deterministic-first, questionnaire-driven threat-modeling tool for
> generic LLM-enabled applications**, with a **constrained local-LLM layer for threat identification
> and mitigation generation**.
> This is **not** the thesis; it is an evidence-based reference tied to concrete files/functions.
> Tone is strict and honest.
>
> Repository root: `C:\Users\user\Desktop\ThreatModelwFlask` — branch `master`.
> Rewritten clean on **2026-07-03** to reflect the FINAL (V1) pipeline; **updated 2026-07-07** for the
> finalized Chapter 1 / methodology 3.9. **Updated 2026-07-09** for the LLM-centric RQ reframe
> (Main + RQ1–RQ4; sustainability is now RQ4). All earlier layered "Phase 1-4 / LLM-extraction /
> llm_risk_review / MS-TMT-foil / 82-question" wording has been removed as obsolete. Companion files:
> `HANDOFF.md` (start here) and `RQ.txt` (canonical current RQ set; old `RQ Ideas.txt` deleted).
>
> **OFFICIAL thesis title (main.tex):** *Automated Threat Modeling for LLM-Enabled Applications Using
> Local Large Language Models and DREAD Risk Assessment* (TR: *LLM-Destekli Uygulamalar için Yerel
> Büyük Dil Modelleri ve DREAD Risk Değerlendirmesi Kullanarak Otomatik Tehdit Modelleme*).
> Author Burak İzer · MSc Cyber Security · advisor Prof. Süha Orhun Mutluergil · jury F. O. Çetin &
> J. Hernandez-Castro. Fine-tune method = **LoRA** SFT. Full official abstract + committee + thesis
> file structure (`Introduction` → `Chapter2` background → `Metodology` + appendix) in `HANDOFF.md`.

---

## 1. What the project IS / IS NOT

**IS:** a Flask web application that produces a threat model for an LLM-enabled application from a
single adaptive questionnaire, following a deterministic-first pipeline:
**questionnaire → static DFD → deterministic candidate risks → LLM threat identification → grounding
validation → deterministic DREAD scoring → LLM mitigations.** The deterministic layer is the
authoritative core; the local LLM is a constrained, grounded assistant.

**IS NOT:**
- Not an "LLM-generated" threat modeler. The LLM does **not** draw the DFD, does **not** compute
  risk severity, and cannot invent primary risks.
- Not domain-specific. It targets **generic** LLM-enabled apps across the OWASP LLM + Web + API
  surfaces together. **Definition (Chapter 1):** *generic LLM-enabled applications* = systems not
  restricted to a single vertical domain (e.g. healthcare, finance) but sharing common architectural
  features — web/API entry points, LLM orchestration, retrieval/memory components, tool use, external
  services, and logging/monitoring pipelines.
- Not dependent on the LLM: with Ollama unavailable, a deterministic fallback still yields a valid
  `risks.json`.
- Not production-hardened (dev `SECRET_KEY`, `debug=True`, file-based state, no auth).

## 2. Motivation & gap (thesis framing)

Threat modeling is valuable at design time but existing approaches are (a) hard to use (manual DFD
drawing, STRIDE expertise, generic noise) and (b) weak at risk assessment (template threats per
element, no context-aware prioritization). This is worse for LLM-enabled applications, which are
**web + API systems augmented with an LLM layer** and therefore inherit all three attack surfaces at
once.

**Gap (softened, defensible):** *Existing threat-modeling approaches often address Web, API, and LLM
risks through separate taxonomies or workflows, while domain-specific solutions (e.g., healthcare)
do not readily generalize. This thesis addresses this gap by investigating a unified,
questionnaire-driven workflow for modeling the combined attack surface of generic LLM-enabled
applications.* (Do **not** claim "no generic tool exists" — unfalsifiable.)

## 3. Research questions (CURRENT SET — see `RQ.txt`; reframed 2026-07-09, LLM-centric)

> **2026-07-09 reframe:** the RQ set moved from the old "deterministic-first pipeline + what value does
> the LLM add" framing to a **local-LLM-centric** framing. Scheme = **Main + RQ1–RQ4**. The old RQ1
> (unified pipeline) and RQ3 (guardrail effectiveness) are now **contributions**, not research
> questions (intro §1.4). Old deterministic-first RQ text is obsolete — see `git log` for history.

**MAIN:** To what extent can local Large Language Models improve the threat modeling process for
LLM-integrated systems?

- **RQ1 — Threat identification:** to what extent can local LLMs identify threats against
  LLM-integrated systems during the threat modeling process?
- **RQ2 — Effectiveness improvement:** how can the effectiveness of local LLMs in identifying threats
  against LLM-integrated systems be improved? *(Mechanism = supervised fine-tuning / LoRA.)*
- **RQ3 — Mitigation generation:** to what extent can local LLMs generate relevant mitigation
  strategies for threats identified in LLM-integrated systems?
- **RQ4 — Sustainability (experimental):** how can an LLM-assisted threat modeling tool for
  LLM-integrated systems be kept up to date with emerging attack vectors and evolving threat patterns?
  *(Update pipeline: trusted sources → normalized task-specific training data → periodic fine-tune of
  the local model, preserving the same grounding/traceability/reproducibility constraints.)*

RQ1 & RQ3 are load-bearing (implemented, automatically measurable now). RQ2 & RQ4 are the experimental
frontier resting on remote fine-tuning (RQ2 = quality on a fixed knowledge set; RQ4 = fine-tuning as
the delivery vehicle for *newly acquired* threat knowledge); "to what extent / how" absorbs a
partial/inconclusive result.

## 4. Evaluation design (hard constraints)

- **No human evaluation / no external testers.** All metrics are **automatic / structural**. No
  expert-labeled gold, no user study.
- **No external-tool comparison** (MS TMT / STRIDE GPT dropped). The only comparison is **internal**:
  deterministic fallback vs base local LLM vs fine-tuned local LLM (same input, temperature 0, only
  model weights change via `OLLAMA_MODEL`).
- **Reproducibility** claims attach to the **deterministic layer** (DFD + candidate mapping + DREAD
  scoring — same input → identical scores). The LLM threat-identification stage is **stochastic**
  (the selected candidate cluster varies run-to-run); characterize its variance over N runs rather
  than claiming it reproducible.
- **System-specificity AND mitigation actionability are NOT expert-judged semantic quality** — they
  are measured via **structural proxy metrics** (Chapter 1 §1.5): references to concrete DFD
  nodes/components, answer-derived evidence/entities, target components, validation steps, and
  evidence-linked mitigation fields (`maps_to_evidence`), optionally vs a stoplist of generic phrases.
  ⚠️ **Proxy caveat (state in limitations):** these count *presence/linkage*, not quality; a model
  that dumps many node refs could score high without being truly specific (gameable). Define the exact
  computation (ratio? per-risk?) in the eval chapter.
- Fine-tuning is assessed on **structural conformance only** (schema/grounding/actionability/
  specificity); semantic, expert-judged quality is out of scope (no human raters).

## 5. End-to-end pipeline (V1, verified)

Orchestrated by `app/services/pipeline_orchestrator.py::PipelineOrchestrator.run_risk_analysis`:

1. **Static DFD** — `static_dfd_mapper.build_static_dfd_from_answers` builds nodes/edges/trust
   boundaries from answers only. **Deterministic, no LLM.** Written to `dfd_reactflow.json`.
2. **Candidate risks** — `risk_analysis_service.discover_candidate_risks` derives candidate OWASP
   LLM/Web/API codes from answer content via `risk_catalog`. **Deterministic, no LLM.**
3. **LLM threat identification** — `llm_threat_identification.identify_threats` (local Ollama,
   default `qwen3:8b`). Candidates are processed in **chunks** of `LLM_THREAT_ID_CHUNK_SIZE`
   (default 10, because qwen3:8b satisfices at ~10 candidates/call). Primary `code` is enum-locked to
   the deterministic candidates; node/edge ids are enum-locked to the real DFD. It works in two
   stages: guided identification over the candidate set, plus a disciplined, capped search for
   material out-of-set threats surfaced as advisory `suggested_secondary_findings`. Status
   `completed` / `partial` / `unavailable`.
4. **Grounding validation** — `threat_grounding_validator.validate_threats` (pure Python, no LLM):
   strips hallucinated node/edge ids, demotes non-candidate codes to secondary, forbids
   unknown-only "confirmed", downgrades unsupported findings to `needs_more_info`, and backfills
   deterministic candidates the LLM never addressed as `unaddressed_candidates` (reported, not
   scored) so a grounded candidate can never silently vanish.
5. **DREAD scoring** — `score_validated_threats` → `dread_scoring.score_code`. **Fully
   deterministic**; `risk_level` always comes from the DREAD band, never from the LLM.
6. **Mitigations** — `llm_mitigation_service.generate_mitigations` (LLM, **batched** at
   `LLM_MITIGATION_BATCH_SIZE`, default 3; best-effort). `risk_code` is enum-locked. If unavailable,
   deterministic `OWASP_MITIGATIONS` remain as fallback.

Output is a single `risks.json` stamped with provenance (`pipeline_mode`, `threat_identification`,
`mitigation` blocks). No separate `threats.json` in V1.

## 6. Fallback (LLM never blocks a valid result)

A five-layer chain guarantees output:
1. `ollama_client` converts connection/timeout/invalid-JSON into `OllamaError`.
2. `identify_threats` catches per-chunk errors; all chunks failing → `status:"unavailable"`.
3. `build_threat_analysis` raises `ThreatIdentificationUnavailable` on `unavailable`.
4. The orchestrator catches that (and any other `Exception`) and calls
   `_deterministic_risk_analysis` (= `build_risk_analysis`, LLM-free).
5. Result is stamped `pipeline_mode=deterministic_fallback` + `pipeline_warning`.

The same feature-flag path is taken when `LLM_THREAT_IDENTIFICATION_ENABLED` is off or no DFD exists.
**DREAD scoring is never LLM-dependent.**

## 7. Questionnaire (91-question DREAD)

- Canonical DB: `app/questions/questionsDb.json` (**91 questions**); `TM-Questions/questionsDb.json`
  kept in sync. Flow graph: `TM-Questions/QaT.txt` (YAML branching with
  `equals/any_of/not_any_of/not_includes` conditions). Engine: `app/question_flow.py`.
- Schema per question: `id`, `text`, `type`, `options[]`, `category`, `scope[]`,
  `dread_dimensions[]`, `dread_weights{damage,reproducibility,exploitability,affected_users,
  discoverability}`. (The old `owasp_*`/`severity_weight`/`confidence_weight` schema is gone.)
- The questionnaire is **fixed at 91 questions**; there is intentionally **no runtime "add question"
  path** (the `/add-question` service was removed 2026-07-03 to keep the question set stable).
- Answers are saved by `save_utils.save_adaptive_llm_sec_answers` to `responses/llmsec_<ts>.json`
  (canonical `answers_by_flow_id`, gitignored).

## 8. Deterministic risk analysis & DREAD scoring

- `risk_analysis_service.py` — candidate discovery (`discover_candidate_risks` via `risk_catalog`),
  the V1 `build_threat_analysis` entry, and the LLM-free `build_risk_analysis` used for fallback.
  OWASP codes are **secondary labels** (`related_codes`); DREAD is the scoring engine.
- `dread_scoring.py` — each code scored on Damage/Reproducibility/Exploitability/Affected/
  Discoverability (each 1–3, summed 5–15). Risk level derives from the **DREAD average**
  (`level_from_average`): **≥2.7 Critical / ≥2.2 High / ≥1.5 Medium / <1.5 Low** (equivalent totals
  14–15 / 11–13 / 8–10 / 5–7). Each rule cites its source question → reproducible + auditable.
  Exploitability/Affected/Discoverability are global system-exposure signals (same across codes),
  so extreme worst-case inputs can legitimately push many codes to the same band — an inherent
  discrimination limit to acknowledge, not a bug.
- `dread_signals.py` — structured DREAD signal extraction (damage/repro/exploit/affected/
  discoverability + impact/scale profiles).
- **Methodological basis (citable):** DREAD-for-LLM is adapted from Zahid et al., "Securing
  Educational LLMs: A Generalised Taxonomy of Attacks on LLMs and DREAD Risk Assessment." We ADAPT
  it (deterministic, questionnaire-grounded, per-code) rather than replicate its manual expert
  scoring; the determinism is the contribution. Frame as adaptation, not replication.

## 9. Static DFD mapper

- `static_dfd_mapper.py` (`build_static_dfd_from_answers`). The pipeline DFD is **100%
  deterministic from answers**; the LLM is not involved.
- Pipeline: `normalize_answers` → `extract_architecture_signals` → `build_nodes` → `build_edges` →
  `prune_edges` → `_enrich_edge_metadata` → `layout_graph` → `_finalize_metadata_controls`.
- Nodes: actors, entry points, preprocessing/orchestrator/tool-layer/API-connector/output-validator,
  RAG orchestrator, LLM gateway (+ self-hosted vs third-party), data stores, tools, business
  actions, external services, logging, trust boundaries. **Q85 is the primary component-inventory
  source**; other questions are inference/fallback.
- **Anti-hallucination by design:** controls (Q25–Q80) attach as metadata to existing nodes and do
  not spawn nodes; missing targets are recorded in `metadata.unresolved_control_targets`.
- Trust boundaries as nodes with pruned `contains[]`; crossing edges flagged. Transport/sensitive
  data metadata (Q73/Q81/Q82) → `combined_risk` when sensitive data rides unclear transport.
- Deterministic lane-based layout → same answers always produce the same graph. UI hygiene enforced
  in the data layer (`display_badges`/`visual_badges` empty; detail lives in `edge.data` for the
  side panel). **Coupled to exact option strings** — rewording an option can silently break a
  mapping (known limitation).

## 10. LLM role (precise, evidence-based)

- **Where in the pipeline:** two constrained calls — threat identification (§5 step 3) and mitigation
  generation (§5 step 6) — via `ollama_client.chat` to local Ollama (`http://127.0.0.1:11434`,
  default `qwen3:8b`, `think:false`, temperature 0, structured outputs).
- **External prompts:** `LLM-Prompts/Threat-Identification-prompt.txt` and
  `LLM-Prompts/Mitigation-Generation-prompt.txt`.
- **What the LLM does:** identifies grounded, system-specific threats (abuse path, control gap) over
  the deterministic candidate set plus a capped out-of-set search, and proposes context-specific
  mitigations for scored threats.
- **What the LLM does NOT do:** it never generates the DFD, never computes DREAD/severity, and cannot
  emit primary risks outside the candidate enum (the validator demotes any stray code). Every LLM
  output passes the grounding validator.
- **Model-agnostic:** model/host swap via `OLLAMA_MODEL` / `OLLAMA_HOST` (one config change; the
  deterministic guardrails keep swaps safe). qwen3:8b base is a modest model — frame LLM weaknesses
  as **model-specific**, not design flaws.

## 11. Fine-tuning (external / experimental — RQ2 & RQ4)

- **No training code or ML dependencies in this repo.** Fine-tuning runs remotely (VALAR HPC) on an
  external SFT dataset; treat it as experimental thesis work, not app functionality.
- **Current dataset (2026-07-06) = task-split, chat-format**, under `training/`:
  `threatid_{3000,5000}.jsonl` (threat-identification task) + `mitigation_{3000,5000}.jsonl`
  (mitigation task) — both fine-tune-ready (dedup fixed, unique records, 29 codes). ⚠️ The old
  `{input,output}` risk-report set (`train_dread_*.json`) is **obsolete**. Open notes:
  `secondary_findings=0`, Critical-heavy distribution.
- Dataset is grounded on deterministic output (good anti-hallucination design). **Circularity
  caveat:** because labels come from the same deterministic pipeline, fine-tuning is evaluated on
  **structural conformance/grounding + a held-out set disjoint from training**, not "expert-quality
  improvement." Fine-tuning serves **RQ2** (effectiveness on a fixed knowledge set) and **RQ4**
(delivery vehicle for the sustainability update pipeline). See `RQ.txt` and [[project-sft-dataset]] notes.

## 12. Feature flags & configuration

Defined in `app/__init__.py`, env-overridable (resolved via `feature_flags`):
- `LLM_THREAT_IDENTIFICATION_ENABLED` (default True), `LLM_MITIGATION_GENERATION_ENABLED` (True).
- Tunables: `LLM_REQUEST_TIMEOUT` (400s), `LLM_THREAT_ID_CHUNK_SIZE` (10),
  `LLM_MITIGATION_BATCH_SIZE` (3), `OLLAMA_HOST` (127.0.0.1:11434), `OLLAMA_MODEL` (qwen3:8b).
- No `config.py` / `.env.example` (a minor future tidy-up).

## 13. Frontend

- Templates extend `layout.html` (dark Bootstrap navbar: Home / Survey / Pipeline / …).
- Core pages: `home.html` (dashboard + Chart.js), `llm_sec.html` (adaptive questionnaire),
  `pipeline_index.html` + `pipeline_detail.html` (start + live monitor), `dfd_mapper_lab.html`
  (React Flow DFD viewer, side-panel detail, no badges on arrows), `risk.html` (risk + mitigation
  review, with a pipeline status bar coloring each stage LLM/fallback/deterministic and a
  "Suggested Secondary Findings" advisory panel).
- Manual/lab-only extraction path (kept intentionally, **not the pipeline**): `dfd.html` +
  `extract_to_reactflow` + `/api/reactflow/from-extract`.

## 14. Key files

| File | Responsibility |
|---|---|
| `run.py`, `app/__init__.py` | Flask app factory + dev server + feature flags |
| `app/routes.py` | HTTP routes/controllers |
| `app/question_flow.py` | Adaptive 91-question engine (QaT + DB) |
| `app/services/pipeline_orchestrator.py` | V1 orchestration, fallback, manifest |
| `app/services/static_dfd_mapper.py` | Deterministic DFD from answers |
| `app/services/risk_catalog.py` | Deterministic candidate-risk derivation |
| `app/services/risk_analysis_service.py` | `build_threat_analysis` (V1) + `build_risk_analysis` (fallback) |
| `app/services/dread_scoring.py`, `dread_signals.py` | Deterministic DREAD scoring + signals |
| `app/services/llm_threat_identification.py` | Constrained, chunked LLM threat identification |
| `app/services/threat_grounding_validator.py` | Pure-Python grounding validation + backfill |
| `app/services/llm_mitigation_service.py` | Batched, constrained LLM mitigation generation |
| `app/services/threat_template.py` | Generic threat patterns |
| `app/services/ollama_client.py`, `feature_flags.py` | Local-LLM HTTP client + flag/tunable helpers |
| `app/services/dfd_service.py` | Persist/list/export DFDs (Mermaid/PlantUML) |
| `app/utils/save_utils.py` | Save questionnaire responses |
| `app/questions/questionsDb.json` + `TM-Questions/questionsDb.json` | 91-question DB (synced) |
| `TM-Questions/QaT.txt` | Questionnaire branching graph |
| `LLM-Prompts/Threat-Identification-prompt.txt`, `Mitigation-Generation-prompt.txt` | Active prompts |
| `tests/test_*.py` | Unit/integration tests (LLM mocked), 115 passing |

**Legacy / out-of-scope (present but not in the V1 pipeline):** `llm_extract_service.py`,
`extract_to_reactflow.py`, `arch_extract_cleaner.py`, `Response-Extractor-prompt.txt` (manual/lab
extraction path only); `llm_generator.py:build_mock_dfd_payload` (mock); `questionnaire_flow.py`
(old engine, unused); `form.html`, `reactflow_test.html`, `llm.html` (legacy UI);
`LLM-Prompts/LLM_Prompt*.txt` (legacy STRIDE/PlantUML prompts). **Garak was fully removed.**
**`llm_risk_review.py` (the old single-call review) was fully deleted 2026-07-02.**

## 15. Setup / run / test (new machine)

1. Python 3.12; `python -m venv venv-win` → activate → `pip install -r requirements.txt` (pure
   Flask; no ML libs; React/React Flow from CDN, no npm).
2. Run: `python run.py` → http://127.0.0.1:5000 (Survey `/llm_sec`, Pipeline `/pipeline`, Risk
   `/risk`).
3. LLM (optional): install Ollama, `ollama pull qwen3:8b`, serve on 127.0.0.1:11434. Works fully
   without it (deterministic fallback).
4. Tests (unittest, not pytest; no `__init__.py` in tests/):
   `python -m unittest discover -s tests -q` → **115/115 pass**.
5. State is JSON on disk: `responses/` (gitignored), `pipelines/<id>/`, `generated_models/dfd_runs/`.

## 16. Honest limitations (acknowledge in the thesis)

- LLM threat identification is **stochastic** (candidate cluster varies run-to-run) → report variance
  over multiple runs; only the deterministic layer is reproducible.
- DREAD discrimination is limited on extreme worst-case inputs (global exposure dimensions saturate).
- Static mapper is coupled to exact option strings.
- Fine-tuning evaluation can speak to structural conformance/grounding only (no human raters).
- Not production-hardened; orchestrator catch-all fallback and the JSON-parse-error path have no
  dedicated unit test (behavior is clear in code).

## 17. Thesis-safe claims vs claims to avoid

**Safe:**
- Deterministic-first, questionnaire-driven threat modeling for generic LLM-enabled apps; unified
  OWASP LLM + Web + API in one 91-question adaptive questionnaire.
- Deterministic static DFD from answers (anti-hallucination: controls attach to existing nodes).
- Deterministic, reproducible DREAD scoring; `risk_level` never comes from the LLM.
- The LLM identifies grounded, system-specific threats and proposes mitigations, fully constrained by
  the deterministic candidate set and grounding validation.
- The system works fully without the LLM (deterministic fallback always yields a valid `risks.json`).
- Model-agnostic local LLM (swap via config).

**Avoid:**
- ❌ "The LLM generates the DFD / computes severity / invents risks."
- ❌ "No generic LLM threat-modeling tool exists" (unfalsifiable — use the softened gap wording).
- ❌ "Fine-tuning produces expert-quality / more correct mitigations" (no human evaluation; claim
  structural conformance only).
- ❌ "Reproducible threat identification" (the LLM stage is stochastic; only the deterministic layer
  is reproducible).
- ❌ "Production-ready."
