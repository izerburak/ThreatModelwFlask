# THESIS_PROJECT_CONTEXT.md

> Project memory / context document for a **deterministic-first, questionnaire-driven threat
> modeling tool for LLM-enabled applications**, with **optional LLM-assisted architecture
> extraction/enrichment**.
> This is **not** the thesis. It is a reliable, evidence-based knowledge base built by
> reading the repository end to end. Every important statement is tied to a concrete
> file, function, route, schema, or data artifact. Tone is strict and honest.
>
> Repository root: `C:\Users\user\Desktop\ThreatModelwFlask`
> Verified against the codebase on 2026-06-09. Git branch `master`.

> **Implementation status — Phase 1 done (2026-06-11), in `risk_analysis_service.py`:**
> Two earlier limitations are now FIXED and supersede any older wording below.
> 1. **Risk scoring is now answer-aware**, not presence-based. It uses an OWASP-Risk-Rating-style
>    severity matrix (`impact × likelihood`, bands LOW/MED/HIGH) where likelihood is adjusted by the
>    **polarity of the actual answer** (mitigating / neutral / aggravating). Verified: a deliberately
>    safe survey now rates **Medium** and a risky one **Critical** (was "Critical for everything");
>    on real runs Critical items dropped from ~80% to ~12%.
> 2. **Deterministic, OWASP-code-keyed mitigations + quick wins** are now produced for every risk
>    (`OWASP_MITIGATIONS`, `OWASP_QUICK_WINS`). Verified: 386/386 unified risks carry mitigations.
>
> **Phase 2 done (2026-06-11) — local LLM is now wired into the loop (optional, constrained):**
> 3. **LLM call infrastructure** (`ollama_client.chat`): Ollama **structured outputs** (JSON Schema
>    via `response_format`) + `temperature 0` + a 2-attempt retry in `llm_extract_service`, so the
>    extractor is constrained to its schema instead of inventing a questions/answers blob.
> 4. **Constrained LLM risk-reasoning layer** (`llm_risk_review.py`, wired into
>    `pipeline_orchestrator.run_risk_analysis`): the LLM reviews ONLY the deterministic candidate
>    risks — its `code` field is enum-constrained to those codes (closed set, no invented risks) —
>    and returns an advisory `llm_assessment` (applies / assessed_level / rationale / priority) per
>    risk. The deterministic `risk_level` stays the baseline; `risk.html` shows both. Best-effort:
>    if Ollama is unavailable the baseline is returned unchanged (`llm_review.status`).
> Verified by mocked tests + guardrail simulation (out-of-set codes dropped, baseline preserved,
> graceful fallback); all 67 tests pass; templates compile. **Live qwen3:8b behavior not yet
> confirmed on-device** (planned final check).
>
> **Phase 3 done (2026-06-11) — robustness/cleanup:** background pipeline failures are now logged
> (no longer swallowed); `/add-question` writes both `questionsDb.json` copies in sync and wires the
> new question into the QaT flow so it is reachable (verified end-to-end). All 67 tests still pass.
>
> **Phase 4 done (2026-06-13) — risk scoring migrated to DREAD; mitigation is now LLM-first.**
> This SUPERSEDES the "impact × likelihood / OWASP-Risk-Rating" wording in the Phase 1 block and §7,
> and the "mitigations are deterministic-only / the LLM does not write mitigations" wording in §3/§9/
> §13/§15.
> 1. **Risk scoring is now DREAD** (`app/services/dread_scoring.py`, wired into
>    `risk_analysis_service._mapped_question_risks`). Each OWASP risk (LLM/Web/API code) is scored on the
>    five DREAD dimensions (Damage, Reproducibility, Exploitability, Affected users, Discoverability),
>    each 1-3, summed 5-15, banded 14/12/9 → Low/Medium/High/Critical. Scores are DETERMINISTIC from the
>    questionnaire answers (each rule cites its source question → reproducible + auditable):
>    Exploitability/Affected/Discoverability are system-exposure signals (kept independent to avoid
>    correlation inflation); Damage is per-code (data/agency/availability/integrity drivers);
>    Reproducibility is control-consistency. Verified on a 2804-record dataset → Critical 21% / High 36%
>    / Medium 33% / Low 11% with real cross-code and cross-system discrimination. Legacy impact×likelihood
>    figures are retained per risk for reference but no longer drive `risk_level`. `risk.html` shows a
>    "DREAD n/15 — D# R# E# A# Dc#" line. All 67 tests pass after the migration.
> 2. **Methodological basis (citable):** DREAD-for-LLM is anchored to a peer-reviewed paper — Zahid et
>    al., "Securing Educational LLMs: A Generalised Taxonomy of Attacks on LLMs and DREAD Risk
>    Assessment". We ADAPT it (deterministic, questionnaire-grounded, per-OWASP-code) rather than
>    replicate its manual/subjective expert scoring on attack types — and that determinism is the
>    contribution (it fixes the subjectivity the paper itself acknowledges). Frame as adaptation, not
>    replication; do NOT claim their 0–10/average/NIST-band scheme.
> 3. **Mitigation is now LLM-first with a deterministic fallback** (corrects §9/§13/§15). The constrained
>    local-LLM layer `llm_risk_review.py` (already wired into `pipeline_orchestrator.run_risk_analysis`)
>    produces context-specific, answer-grounded mitigations per risk, enum-locked to the deterministic
>    candidate codes (no invented risks). `risk.html` shows the LLM mitigations when available and falls
>    back to the deterministic `OWASP_MITIGATIONS` only when the LLM is unavailable. Mitigations are
>    therefore NO LONGER "deterministic-only"; the OWASP library is the safety-net/fallback. The system
>    still works fully without the LLM (graceful degradation preserved).
> 4. **Fine-tuning dataset (external to repo, experimental):** an SFT dataset was DREAD-relabeled with
>    the SAME deterministic scorer, so the engine, the training labels, and the cited paper are all
>    aligned on DREAD. Distinct sets (varied 2804 + simple 1500 + simple 700) live outside the repo
>    (`Desktop\training\train_dread_{700,1500,2804}.json`) with a DREAD-ready Qwen3-8B LoRA script. Note:
>    an LLM-based relabel of the same data collapsed to ~80% Critical — direct evidence that an
>    uncalibrated LLM cannot discriminate, motivating the deterministic scorer. Still external work, not
>    part of the Flask app.

---

## Canonical Thesis Scope After Repository Discovery

> Authoritative scope statement after a full end-to-end repository read and verification against
> all committed pipeline artifacts. This section overrides any looser wording elsewhere in this
> document. It supersedes the earlier "LLM-assisted threat-modeling system" phrasing.

### What the project IS
- A **deterministic-first, questionnaire-driven threat modeling tool for LLM-enabled
  applications**, with **optional LLM-assisted architecture extraction/enrichment**.
- The **core implemented pipeline** is fully deterministic and reproducible:
  1. **Adaptive security questionnaire** — `app/question_flow.py` + `TM-Questions/QaT.txt` +
     82-question DB.
  2. **Deterministic answer normalization** — `static_dfd_mapper.normalize_answers`,
     `risk_analysis_service._answers_by_flow_id`, `save_utils.save_adaptive_llm_sec_answers`
     (canonical `answers_by_flow_id`).
  3. **Deterministic OWASP LLM / Web / API risk mapping** — `app/services/risk_analysis_service.py`.
  4. **Deterministic / static DFD generation** — `app/services/static_dfd_mapper.py`.
  5. **React Flow visualization** with a side panel for node/edge detail — `dfd_mapper_lab.html`
     + `app/static/js/dfd_mapper_lab.js` / `dfd_node.js`.
  6. **Optional local Ollama-based LLM extraction** — `app/services/llm_extract_service.py`
     + `ollama_client.py` + `arch_extract_cleaner.py` (auxiliary, answer-grounded, fails gracefully).

### What the project IS NOT
- **Not** an "LLM-generated threat modeling system." The LLM does not generate the main DFD and
  does not generate the main risk list.
- **Not** an LLM-mitigation generator: mitigations and quick wins are produced **deterministically**
  from an OWASP-code-keyed library (reproducible), not written by the LLM.
- **Not** a fine-tuning / model-training project (no training code or ML dependencies in this repo).
- **Not** production-hardened (dev `SECRET_KEY`, `debug=True`, file-based state, no auth).

### Core components (the thesis contribution)
- `app/question_flow.py` — adaptive questionnaire engine (branching, conditions, path resolution).
- `TM-Questions/QaT.txt` + `app/questions/questionsDb.json` — 82-question adaptive flow + OWASP-tagged DB.
- **`app/services/static_dfd_mapper.py` — the central contribution** (see emphasis below).
- `app/services/risk_analysis_service.py` — deterministic OWASP LLM/Web/API risk scoring.
- `app/services/pipeline_orchestrator.py` — orchestration + per-run manifest/artifacts.
- `app/routes.py`, `app/services/dfd_service.py`, `app/utils/save_utils.py` — controllers + persistence/export.
- Frontend: `dfd_mapper_lab.html`/`.js`, `dfd_node.js`, `home.html` (Chart.js), `risk.html`, `pipeline_*.html`.

> **The static DFD mapper is the most important component — treat it as more central than the
> LLM.** From questionnaire answers alone it deterministically constructs nodes, edges, trust
> boundaries, sensitive-data movement, transport-security metadata (Q73/Q81/Q82, `combined_risk`),
> and rich side-panel detail — while keeping the compact graph clean (empty `display_badges` /
> `visual_badges`, no badges on arrows) and avoiding hallucinated architecture (controls attach to
> existing nodes only).

### Auxiliary components (supporting, optional)
- `app/services/llm_extract_service.py`, `ollama_client.py` (`qwen3:8b`), `arch_extract_cleaner.py`
  — optional architecture **extraction/enrichment** only. Answer-grounded, validated, with a
  graceful fallback. The system runs fully without it.
- `app/services/extract_to_reactflow.py` — converts an LLM extract into a React Flow graph for the
  **lab/manual review path only** (`/api/reactflow/from-extract`, DFD-lab "Extract" tab); **not the
  main pipeline DFD**.
- `LLM-Prompts/Response-Extractor-prompt.txt` — the active (extraction-only) prompt.
- `app/templates/llm.html`, `add_question.html` — developer/utility tools.

### Legacy / out-of-scope components
- **Garak is NOT part of this project and is excluded from scope.** Any Garak-related files,
  routes, or dependencies still physically present in the repository are leftovers to be ignored
  (and ideally removed); do not treat Garak as a feature of this system and do not describe it in
  thesis material.
- **Fine-tuning / training** — **absent from this repository**. Any fine-tuning experiments are
  **external/experimental thesis work**, separate from the Flask application.
- `app/utils/questionnaire_flow.py` (legacy engine, unused), `LLM-Prompts/LLM_Prompt*.txt` (legacy
  PlantUML/STRIDE prompts), `app/templates/form.html` (legacy UI),
  `app/services/llm_generator.py:build_mock_dfd_payload` (mock `TODO`),
  `app/templates/reactflow_test.html` + `reactflow_test.js` + `mock_dfd_inputs.js` (sandbox/fixtures).

### Safe claims
- Deterministic-first, questionnaire-driven threat modeling tool for LLM-enabled applications.
- Adaptive **82-question** questionnaire (verified) with YAML branching + condition operators.
- **Deterministic, reproducible OWASP mapping** across **LLM Top 10 (2025)**, **Web Top 10 (2025)**,
  **API Top 10 (2023)** with **human-readable names**.
- **Deterministic static DFD** from answers (nodes, edges, trust boundaries, sensitive-data
  movement, transport-security metadata, combined-risk flags) with a **stable canonical layout**.
- Clean React Flow visualization: short edge labels, **no badges on arrows**, **detail in a side
  panel**; mapper **avoids hallucinated architecture**.
- The system **works fully without the LLM**; the LLM is **optional, answer-grounded architecture
  extraction/enrichment** with validation + graceful fallback.
- Modular, testable pipeline; questionnaire→static-DFD verified end-to-end with the LLM mocked.

### Claims to avoid
- ❌ "The LLM generates the DFD / generates or explains the risks / proposes mitigations." (Risks,
  scoring, and mitigations are all deterministic; the LLM reasoning layer is Phase 2, not built yet.)
- ❌ "The system fine-tunes or uses a fine-tuned model" (no training code in this repo).
- ❌ "LLM extraction reliably produces structured architecture" (frequent fallbacks with `qwen3:8b`).
- ❌ "Production-ready."

## Recommended Thesis Narrative

Final recommended storyline (deterministic-first, with the LLM as an auxiliary layer):

1. **Problem.** Threat modeling for **LLM-enabled applications** is hard: such systems add LLM/RAG/
   tool-calling/agentic attack surface on top of classic web/API risk, and ad-hoc reviews are
   inconsistent and hard to reproduce.
2. **Why not free-form LLM generation.** Generating threat models directly from an LLM is
   non-reproducible, hard to audit, and prone to **hallucinated** architecture and risks. This
   project deliberately avoids that.
3. **Structured adaptive questionnaire.** Instead, the system elicits architecture and security
   posture through an **adaptive 82-question questionnaire** (`question_flow.py` + `QaT.txt`) that
   only asks context-relevant questions via branching conditions.
4. **Deterministic OWASP mapping.** Questionnaire answers are mapped to **OWASP LLM/Web/API** risks
   with reproducible, weight-based scoring and human-readable names (`risk_analysis_service.py`).
5. **Deterministic DFD from security-relevant signals.** A **static DFD** is constructed from the
   answers (`static_dfd_mapper.py`): actors, entry points, processes, data stores, tools, external
   services, **trust boundaries**, **sensitive-data movement**, and **transport-security** metadata,
   rendered cleanly in React Flow with detail in a side panel.
6. **LLM as optional assistant.** A **local Ollama model** is used **only** as an optional
   **architecture extraction/enrichment** aid, strictly grounded in the questionnaire answers and
   validated with a graceful fallback — never as the source of truth.
7. **Thesis claim.** This **deterministic-first** design improves **reproducibility**,
   **auditability** (every node/edge/risk carries question-level evidence), and **reduces
   hallucination risk**, while still allowing optional LLM enrichment where helpful.

## Open Implementation Decisions Before Thesis Writing

These are real choices that affect what the thesis can claim. Each notes the current code state so
claims stay honest until/unless the code changes.

1. **Put the local LLM in the risk loop — ADDRESSED (Phase 2), differently than originally posed.**
   - The old `top_risks` vs `risk_signals` mismatch is moot: instead of letting the LLM *emit* risks,
     Phase 2 added a **constrained reasoning layer** (`llm_risk_review.py`) that reviews only the
     deterministic candidate codes (enum-constrained — no invented risks) and attaches an advisory
     `llm_assessment` per risk; the deterministic `risk_level` stays the baseline.
   - Thesis framing: the LLM **assesses/prioritizes/explains** the deterministic risk set (grounded,
     auditable), it does **not independently generate** risks. Confirm live qwen3:8b behavior before
     reporting quantitative LLM-vs-baseline results.
2. **Add deterministic mitigation templates? — DONE (Phase 1).**
   - Added `OWASP_MITIGATIONS` and `OWASP_QUICK_WINS` (code-keyed) in `risk_analysis_service.py`;
     `unify_risks` attaches mitigations to every risk and `_quick_wins` builds prioritized quick
     wins. The thesis MAY now claim deterministic, reproducible mitigation/quick-win output.
3. **Remove leftover out-of-scope code from the repository.**
   - *Current:* the repo still physically contains code, routes, files, and a dependency for an
     out-of-scope red-teaming tool that is **not part of this project**.
   - *Decision:* delete/hide those leftovers so the implemented system matches the thesis scope.
     This is a repo-cleanup item only; the excluded tool must not appear in thesis material.
4. **Duplicate `questionsDb.json` + orphaned `/add-question` — ADDRESSED (Phase 3).**
   - `save_utils.append_question_to_catalog` now writes **both** copies in sync, and
     `_append_question_to_flow` re-points the QaT terminal so a new question is **reachable**
     (verified: `Q38 → Q83 → END`, both DBs synced, engine resolves the new question).
   - Residual: the two resolvers still have different precedence; harmless now that writes are
     synced, but a single resolver remains a possible future tidy-up.
5. **Adjust risk scoring so safe answers do not increase risk? — DONE (Phase 1).**
   - Scoring is now answer-aware: OWASP-Risk-Rating severity matrix (`impact × likelihood`) with
     likelihood adjusted by answer polarity (`_answer_polarity`, `_calibrated_level`). Safe answers
     lower the level; e.g., Q4 "No" no longer rates LLM02 Critical. The polarity lexicon is a first
     pass to be refined during the dataset spot-check. The thesis MAY now describe scoring as
     answer-sensitive (impact × likelihood), no longer mere coverage.
6. **Explicitly separate fine-tuning experiments from the web application?**
   - *Current:* no training code or ML dependencies exist in this repo.
   - *Decision:* if the thesis discusses fine-tuning, document it as **external/experimental work**
     in a clearly separate artifact/repository, never as functionality of this Flask app.

---

## 1. Project identity

A **Flask web application** that performs **LLM-assisted threat modeling** of LLM-enabled
systems. A user answers an **adaptive security questionnaire**; the backend deterministically
derives **OWASP-mapped risks** and a **static Data Flow Diagram (DFD)**, and (optionally) calls a
**local Ollama LLM** to extract a structured architecture description. Results are visualized in
the browser with **React Flow** (DFD) and **Chart.js** (risk distribution).

- Entry point: `run.py` → `app/__init__.py:create_app()` (Flask app factory, single blueprint
  `main`, dev server `app.run(debug=True)`).
- All routes/controllers live in one file: `app/routes.py` (~1080 lines, blueprint `main`).
- **No database.** All state is JSON files on disk: `responses/` (questionnaire outputs,
  **gitignored**), `pipelines/<id>/` (per-run artifacts), `generated_models/dfd_runs/` (archived
  DFDs), `LLM_Extracts/` (LLM extraction outputs), and the question data files.
- Stack (`requirements.txt`): Flask 3.1.1, Flask-Bootstrap, Flask-WTF/WTForms, Jinja2, PyYAML.
  **No ML/training libraries** (no torch/transformers/peft/datasets/trl). React, ReactDOM, and
  React Flow are loaded from CDN (no npm build). (A leftover out-of-scope dependency may still be
  listed in `requirements.txt` and should be removed — see Open Implementation Decisions.)

## 2. Final thesis scope (what the implemented system actually is)

The system is best described as a **hybrid, deterministic-first threat modeling tool**:

1. **Deterministic adaptive questionnaire** (82 questions, branching graph) → `app/question_flow.py`.
2. **Deterministic OWASP risk analysis** (LLM / Web / API) → `app/services/risk_analysis_service.py`.
3. **Deterministic static DFD generation** from answers only → `app/services/static_dfd_mapper.py`.
4. **Optional LLM architecture extraction** (local Ollama) → `app/services/llm_extract_service.py`
   + `app/services/ollama_client.py`, cleaned by `app/services/arch_extract_cleaner.py`.
5. **Frontend visualization** of risks (tables/cards + chart) and DFD (React Flow with a side
   panel for node/edge detail).

**Verified central fact:** in the current code, the deterministic paths produce the entire
risk list and the entire pipeline DFD. The LLM is **optional and currently peripheral** to the
main outputs (see §9 for evidence). The honest framing is **"LLM-assisted"**, not
"LLM-generated."

## 3. Explicitly OUT OF SCOPE

- **Out-of-scope red-teaming tool — EXCLUDED.** Not part of this project. Any related code, routes,
  files, or dependencies still physically present in the repo are leftovers to be ignored/removed;
  they are detached from the questionnaire→risk→DFD flow and must not be described in thesis
  material.
- **Fine-tuning / training / dataset curation.** **Absent from the codebase.** No training
  scripts, `.jsonl`, `.ipynb`, LoRA/QLoRA/PEFT, optimizers, or ML dependencies. `LLM_Extracts/*`
  are **inference outputs and a few hand-curated example extracts**, not training data.
- **Legacy questionnaire engine** `app/utils/questionnaire_flow.py` (788 lines) — superseded by
  `app/question_flow.py`; **not imported by routes** (referenced only by its own test).
- **Legacy / experimental UI:** `app/templates/form.html` (old layered questionnaire),
  `app/templates/reactflow_test.html` + `app/static/js/reactflow_test.js` (standalone sandbox,
  localStorage only), `app/static/js/mock_dfd_inputs.js` (demo fixtures).
- **Mock DFD generator** `app/services/llm_generator.py:build_mock_dfd_payload` (explicitly marked
  `TODO`, placeholder) — feeds `/api/generate-dfd` → manual editor, not the pipeline.

## 4. Main architecture

```
run.py → app/__init__.py:create_app()  (Flask, blueprint "main")
└── app/routes.py                      (all HTTP routes/controllers)
    ├── app/question_flow.py           (adaptive questionnaire engine)            [CORE]
    ├── app/services/pipeline_orchestrator.py (per-run orchestration + manifest)  [CORE]
    │     ├── static_dfd_mapper.py      (deterministic DFD from answers)          [CORE]
    │     ├── llm_extract_service.py    (Ollama architecture extraction)          [AUX/OPTIONAL]
    │     │     ├── ollama_client.py    (HTTP to local Ollama)                    [AUX]
    │     │     └── arch_extract_cleaner.py (normalize/repair LLM JSON)           [AUX]
    │     └── risk_analysis_service.py  (deterministic OWASP risk mapping)        [CORE]
    ├── extract_to_reactflow.py         (LLM extract → React Flow graph)          [AUXILIARY]
    ├── dfd_service.py                  (persist/list/export DFDs; Mermaid/PlantUML)[CORE util]
    ├── llm_generator.py:build_mock_dfd_payload (mock)                            [EXPERIMENTAL]
    └── app/utils/save_utils.py         (save responses; add question)            [CORE util]
Data: app/questions/questionsDb.json, TM-Questions/questionsDb.json (identical),
      TM-Questions/QaT.txt (flow graph), responses/, pipelines/, generated_models/dfd_runs/
Frontend: app/templates/*.html + app/static/js/*.js (React Flow 11.11.4 + Chart.js via CDN)
```

## 5. Main runtime flow (verified, not assumed)

```
Frontend questionnaire  (GET/POST /llm-sec, app/templates/llm_sec.html)
   ↓   QuestionFlowEngine resolves next question from QaT.txt branching + answers
   ↓   On finish: save_adaptive_llm_sec_answers() → responses/llmsec_<ts>.json
   ↓               schema_version "llmsec.adaptive.v1", canonical "answers_by_flow_id"
   ↓
Pipeline start  (POST /pipeline/start  OR  POST /api/pipeline/start → background daemon Thread)
   ↓   PipelineOrchestrator.create_pipeline(): copies response.json, writes manifest.json
   ↓
PipelineOrchestrator.run_until_risk_analysis()  (pipeline_orchestrator.py:250-254)
   ├─ 1) generate_dfd()        → build_static_dfd_from_answers(answers)  [DETERMINISTIC, no LLM]
   │                             writes dfd_reactflow.json + archives to generated_models/dfd_runs/
   ├─ 2) generate_extraction() → generate_llm_extract() [Ollama]  [OPTIONAL; fails gracefully]
   │                             writes extraction_raw.json (schema llmsec.arch_extract.cleaned.v1)
   └─ 3) run_risk_analysis()   → build_risk_analysis(response, extract)  [DETERMINISTIC]
                                 writes risks.json
   ↓   Each step updates manifest.json steps{done,timestamp,error}; status recomputed
   ↓
Frontend rendering
   ├─ Pipeline monitor: /pipeline/<id> (pipeline_detail.html) polls /api/pipeline/<id>/manifest every 2s
   ├─ Risks: /risk (risk.html) and / (home.html + Chart.js) read risks.json
   └─ DFD: /dfd-mapper-lab?dfd=<archive> (dfd_mapper_lab.html, React Flow) reads the archived graph
```

Note the order: **DFD (static) is generated BEFORE the LLM extraction**, and the static DFD does
not depend on the LLM at all.

## 6. Questionnaire system

- **Active data:** `app/questions/questionsDb.json` **and** `TM-Questions/questionsDb.json` are
  **byte-identical** and each contain **exactly 82 questions** (`"id"` 1–82). **The "82 questions"
  expectation is VERIFIED.**
- **Question schema (per question):** `id`, `text`, `type` (`single`|`multi`), `options[]`,
  `category`, `scope[]` (e.g. `["llm","web","api"]`), `owasp_llm[]`, `owasp_web[]`, `owasp_api[]`,
  `severity_weight` (int), `confidence_weight` (int). All 82 questions carry all of these fields.
  - The legacy fields `risk_context` and `dfd_impact` are **not present** in the current DB; code
    that handles them (`LEGACY_RISK_CONTEXT_TO_OWASP_LLM`, `dfd_impact` evidence) is a
    backward-compatibility fallback that does not fire for the current data.
- **Flow graph:** `TM-Questions/QaT.txt` (YAML, 454 lines). Start `Q1`. Nodes have `next:` and/or
  `conditions:` with `if/then/else` and `next_after`. Conditions support `equals`, `not_equals`,
  `any_of`, `not_any_of`, `not_includes` (`app/question_flow.py:_evaluate_condition`).
- **Engine:** `app/question_flow.py:QuestionFlowEngine` (CORE). Reads QaT.txt (YAML via PyYAML, or
  a hand-rolled parser fallback) + questionsDb.json. Resolves the active path, pending questions,
  branching, duplicate-visit handling, and answer extraction/normalization. Drives `/llm-sec`.
- **Question IDs are used directly in code.** Both the static DFD mapper and the risk engine key
  on specific `Q<n>` ids and on the exact option strings.
- **Dual source-of-truth caveat (latent drift):** the two consumers resolve `questionsDb.json` with
  **different precedence** — `question_flow._resolve_questions_path` prefers
  `TM-Questions/questionsDb.json`; `risk_analysis_service._resolve_questions_path` prefers
  `app/questions/questionsDb.json`. They are identical today, so it works, but edits to only one
  copy would desynchronize the flow from the risk mapping.

### How answers become signals
- **Risk indicators:** `risk_analysis_service.build_risk_analysis` reads each answered `Q<n>`, looks
  up its `owasp_llm/owasp_web/owasp_api` codes, and accumulates score.
- **Architecture / DFD elements:** `static_dfd_mapper.extract_architecture_signals` keyword-matches
  answer **text** to derive actors, entry points, processes, data stores, tools, business actions,
  external services, trust boundaries, controls, transport/sensitivity metadata.

## 7. Risk analysis system

File: `app/services/risk_analysis_service.py` (CORE, deterministic, reproducible).

- **Mechanism:** for every answered question with mapped codes, `score += severity_weight ×
  confidence_weight` is added to **each** code, separately per framework (`owasp_llm`, `owasp_web`,
  `owasp_api`). Evidence (question text, the answer, weights, category, scope) is attached per code.
- **Severity / level:** `_level_from_weights(severity, score)` →
  `Critical` if severity≥5 and score≥100; `High` if severity≥5 or score≥60;
  `Medium` if severity≥3 or score≥25; else `Low`. Overall status = max level present.
- **OWASP names are human-readable**, not raw codes: `OWASP_LLM_2025` (LLM01–LLM10),
  `OWASP_WEB_2025` (A01:2025–A10:2025), `OWASP_API_2023` (API1:2023–API10:2023). `_risk_name()`
  resolves code→name for all three frameworks.
- **Unification:** `unify_risks()` merges `extract_risks` (LLM) and `mapped_risks` (questionnaire)
  by code; tracks `sources` ("Questionnaire" / "LLM extract"); takes the max risk level.
- **Output schema (`risks.json`):** `overall_status`, `status_source`, `mapped_risks`,
  `mapped_risks_by_framework`, `owasp_llm/owasp_web/owasp_api`, `extract_risks`, `unified_risks`,
  `quick_wins`, `answers_analyzed`. Stable across recent runs.

### Important limitations (verified, must be acknowledged)
- **Answer-aware scoring (Phase 1, FIXED).** Scoring is `impact × likelihood` on an OWASP-Risk-Rating
  matrix; likelihood is adjusted by answer polarity, so e.g. `Q4`="No" no longer inflates `LLM02`.
  (Was previously presence-based.) The polarity lexicon is a first pass to refine during spot-check.
- **Deterministic mitigations + quick wins (Phase 1, FIXED).** `OWASP_MITIGATIONS` /
  `OWASP_QUICK_WINS` (code-keyed) populate every risk; mitigations are reproducible, not LLM-written.

## 8. Static DFD mapper

File: `app/services/static_dfd_mapper.py` (1673 lines, CORE). `MAPPER_VERSION = "static-dfd-v2"`.

- **The pipeline DFD is 100% static/deterministic, built from answers only.** Entry:
  `build_static_dfd_from_answers(raw_answers)`. The LLM is **not** involved in the pipeline DFD.
- **Pipeline:** `normalize_answers` → `extract_architecture_signals` → `build_nodes` →
  `build_edges` → `prune_edges` → `_enrich_edge_metadata` → `layout_graph` →
  `_finalize_metadata_controls`. Produces React Flow `{nodes, edges, metadata}`.
- **Nodes** (`type:"custom"`, `data.source:"static_mapper"`): actors (Q2/Q3/Q48), entry points
  (Q3/Q48), preprocessing/orchestrator/tool-layer/api-connector/output-validator (Q7/Q11/Q12/Q14/
  Q15/Q31/Q65/Q66/Q79…), RAG orchestrator (Q5/Q7/Q8), LLM gateway + self-hosted runtime vs
  third-party provider (Q17), data stores (Q8/Q10/Q13/Q24/Q43/Q47), tools (Q12), business actions
  (Q15/Q39/Q79), external services (Q5/Q6/Q14/Q62), logging (Q33/Q74), trust boundaries (Q2/Q14/
  Q17/Q23/Q40).
- **Edges** are created by deterministic role-aware rules (`_valid_request_pairs`,
  `_add_*_edges`): actor→entry, entry→first process, preprocessor→orchestrator→RAG→LLM gateway,
  LLM↔provider/runtime, RAG↔stores (retrieval/returned context), tool-layer→tools→stores/business,
  model output→validator→entry→actor responses, logging events. Orphan nodes are anchored sensibly
  (`_add_orphan_node_edges`) instead of left dangling or cross-producted.
- **Trust boundaries** are nodes (`nodeType:"trust_boundary"`) with a `contains[]` list pruned to
  existing nodes (`_clean_boundary_contains`). Edge crossings computed from logical zones
  (`_trust_zone_for_node`); crossing edges get `trust_boundary_crossed=true` + a "Trust boundary"
  badge in `data`.
- **Transport security / sensitive data:** Q73 sets a transport default; Q81 sets
  per-path/global transport state (`enforced/unclear/unknown`); Q82 sets sensitive-data
  classification per path/global. When sensitive data rides an `unclear/unknown` transport edge,
  `data.combined_risk = "sensitive_data_over_unclear_transport"`. `required_control:"TLS"` is added
  where transport matters.
- **Controls (Q25–Q80)** attach as **metadata to existing nodes** (`_attach_controls`); they do
  **not** create new nodes. Missing targets are recorded in `metadata.unresolved_control_targets`.
  This is a deliberate **anti-hallucination** design (e.g., Q30 explicitly does not spawn a node).
- **UI hygiene is enforced at the data layer:** `data.display_badges` and `data.visual_badges` are
  set to **empty arrays** (`static_dfd_mapper.py:989-990`). Rich detail (badges, evidence,
  `source_questions`, `transport_state`, `data_carried`, `flow_type`, `direction`) lives in
  `edge.data` for the **side panel** — the compact graph stays clean, with **no text badges on
  arrows**. Confirmed by `tests/test_dfd_mapper_lab_ui.py` and `tests/test_static_dfd_mapper.py`.
- **Layout** is deterministic lane-based (`LANE_X`/`LANE_START_Y`), so the same answers always
  produce the same graph (one **canonical** graph; no separate compact/detailed graphs).
- **Generic vs overfit:** the mapper is **broadly generic** across the 82-question space (RAG,
  tools, agents, external APIs, self-hosted vs third-party, multi-tenant, file/cloud storage,
  webhooks, logging). However it is **tightly coupled to the exact option strings** of the current
  DB (keyword matching). Changing an option's wording can silently break a mapping.

## 9. LLM role (precise, evidence-based)

- **Where:** `generate_llm_extract()` (`llm_extract_service.py`) via `ollama_client.chat()` →
  local **Ollama** at `http://127.0.0.1:11434`, default model **`qwen3:8b`**
  (`ollama_client.py:8-9`, configurable via `OLLAMA_HOST`/`OLLAMA_MODEL`), `format:"json"`.
- **Active prompt:** `LLM-Prompts/Response-Extractor-prompt.txt` (`PROMPT_FILENAME` in
  `llm_extract_service.py`). It is an **extraction-only** prompt: "Do not create DFD, React Flow,
  PlantUML, Mermaid, STRIDE, or mitigation plans." (The other `LLM-Prompts/LLM_Prompt*.txt` are
  **legacy** PlantUML/STRIDE prompts, not referenced by code.)
- **Input:** questionnaire metadata + `answers_by_flow_id` + compact answer records. **Grounded
  entirely in questionnaire answers** ("Use only the provided answers").
- **Expected output:** JSON `{system_summary, architecture, security_controls, risk_signals}`,
  `schema_version "llmsec.arch_extract.cleaned.v1"`.
- **Validation/robustness:** `parse_extract_json` (direct parse → fenced-block extraction → brace
  scan → JSON repair for smart quotes / trailing commas), `_has_extraction_content` (rejects
  status-only JSON), graceful **fallback** `build_fallback_extract` (builds a minimal extract from
  answers). Output is normalized by `arch_extract_cleaner.clean_arch_extract_v4` (schema merge,
  dedup, reclassification, legacy aliases `dfd`/`architecture_signals`).
- **The system works WITHOUT the LLM.** The static DFD and the risk analysis never call it; the
  test suite mocks `chat()` everywhere.

### Verified reality of the LLM's contribution (critical for honest framing)
- The pipeline DFD uses the **static mapper**, not the LLM extract (`generate_dfd` →
  `build_static_dfd_from_answers`). The LLM extract is consumed only by the **auxiliary**
  `extract_to_reactflow.py` (route `POST /api/reactflow/from-extract`, and the "Extract" panel of
  the DFD lab) — **not** by the main pipeline.
- The LLM extract does **not** feed the risk list. `build_risk_analysis` reads `extract_payload
  ["top_risks"]`, but the active extractor emits `risk_signals.owasp_llm_candidates` — a **schema
  mismatch**, so the LLM's risk signals are effectively unused.
- **Evidence across all committed pipeline runs:** every run from `20260519` onward has
  `extract_risks = 0`, `unified_risks` = the 30 questionnaire-mapped risks, **0 mitigations, 0
  quick wins**; several runs show `llm_parse_error` ("LLM returned … unrecognized fields") with
  fallback. Only the single oldest run (`20260516…`, legacy prompt) had `extract_risks = 6` and
  `quick_wins = 4`.
- **Conclusion:** today the LLM is an **optional architecture-extraction aid** for the lab/manual
  review. It does **not** currently drive the main risk or DFD outputs, and with `qwen3:8b` it
  frequently fails to produce usable structured fields (handled by fallback).

## 10. Frontend visualization

- Templates extend `app/templates/layout.html` (dark theme, Bootstrap 5.3 CDN navbar).
- **Core pages:** `home.html` (dashboard + Chart.js risk doughnut), `llm_sec.html` (adaptive
  questionnaire), `pipeline_index.html` (start pipeline; polls `/api/llm/status`),
  `pipeline_detail.html` (live monitor; polls `/api/pipeline/<id>/manifest` every 2s),
  `dfd_mapper_lab.html` (primary DFD viewer), `risk.html` (risk + mitigation review),
  `dfd.html` (LLM extract generator).
- **DFD viewer (`dfd_mapper_lab.html` + `app/static/js/dfd_mapper_lab.js`):** React Flow 11.11.4 +
  React 18 (CDN). Three columns: tabs (Response/DFD/Extract), canvas, **right-hand side panel** for
  the selected node/edge (role, kind, metadata, evidence, security details, collapsed developer
  details). Edge labels are short; **no text badges on arrows** (matches the data-layer hygiene in
  §8). `dfd_node.js` renders role-styled nodes; `dfd_mapper.js` is a client-side graph builder.
- **Manual editor (`dfd_editor.html` + `dfd_editor.js`):** React Flow editor with JSON/Mermaid/
  PlantUML export (`/api/export/...`, backed by `dfd_service.export_diagram_as_*`).
- **Risk rendering (`risk.html`):** per risk shows `code`, human-readable `name`, `risk_level`
  pill, `sources`, `why`, `question_evidence` (question/answer pairs), `mitigations`. Because the
  current pipeline yields no mitigations/quick wins, those UI sections are typically empty.
- **Schema alignment:** frontend field names match backend output (`unified_risks`, `nodes/edges`
  with `data.label/role/nodeType`, manifest `steps`). OWASP **names** come from the backend.
- **Experimental/legacy UI:** `reactflow_test.html`/`.js` (sandbox, not in nav), `form.html`
  (legacy questionnaire), `llm.html` + `add_question.html` (auxiliary tools).

## 11. Training / fine-tuning experiments

**No training code or ML dependencies in the repository.** However, an **external SFT dataset
exists on the author's machine** (`C:\Users\user\Desktop\llm_sft_1000.jsonl`, 1000 examples, JSONL
with `{"input","output"}`), used to **fine-tune a model remotely** so it returns graded risks. It
is **outside this repo**, and the **Flask app does not consume the fine-tuned model's risk output**
(integration gap below). Treat fine-tuning as **external/experimental thesis work**, not a function
of the Flask application. `LLM_Extracts/*` remain inference outputs / hand-curated examples.

- **Dataset input** keys: `project_metadata`, `questionnaire_answers`, `deterministic_risks`,
  `extraction_payload`, `dfd_payload` — i.e. the model is **grounded on the deterministic output**
  (good anti-hallucination design).
- **Dataset output:** `overall_status`, `risk_summary`, `risks[]` (each `code`, `name`,
  `risk_level`, `why`, `evidence`, `affected_assets`, `related_codes`, `mitigations[]` of
  `{title,priority,action,owner_hint,verification}`), `quick_wins`, `assumptions`,
  `missing_information`. Codes span **LLM (~1647), API (~292), Web (~74)**.
- **Integration gap (why fine-tuned LLM risks never reach the UI) — all in the Flask app, not the
  dataset:**
  1. **Prompt skew** — the app sends `LLM-Prompts/Response-Extractor-prompt.txt` (architecture
     extraction), not a risk-report prompt matching the dataset's task.
  2. **Input skew** — the app sends `{metadata, response_file, answers_by_flow_id, answers}`, not
     the trained `{project_metadata, questionnaire_answers, deterministic_risks, extraction_payload,
     dfd_payload}`.
  3. **Output-key mismatch** — `risk_analysis_service._extract_risks` reads `top_risks`; the model
     emits `risks`. It also expects `mitigation` (string) vs the dataset's `mitigations` (object
     list), and **drops non-LLM codes** (Web/API).
  4. **Content gate** — `llm_extract_service._has_extraction_content` only accepts
     `system_summary`/`architecture`/`dfd`/`llm_components`/`applicable_owasp_llm_risks`, so a
     risk-report output is rejected → `build_fallback_extract` (the fallback the author observes).

## 12. Key files and responsibilities

| File | Responsibility | Status |
|---|---|---|
| `run.py`, `app/__init__.py` | Flask app factory + dev server | core |
| `app/routes.py` | All HTTP routes/controllers; orchestration glue | core |
| `app/question_flow.py` | Adaptive questionnaire engine (QaT + DB) | core |
| `app/services/pipeline_orchestrator.py` | Per-run orchestration, manifest, steps | core |
| `app/services/static_dfd_mapper.py` | Deterministic DFD from answers | core |
| `app/services/risk_analysis_service.py` | Deterministic OWASP risk mapping | core |
| `app/services/llm_extract_service.py` | Ollama architecture extraction + parsing/fallback | auxiliary (optional) |
| `app/services/ollama_client.py` | HTTP client to local Ollama (`qwen3:8b`) | auxiliary |
| `app/services/arch_extract_cleaner.py` | Normalize/repair/dedup LLM extract JSON | auxiliary |
| `app/services/extract_to_reactflow.py` | LLM extract → React Flow graph (lab/API only) | auxiliary |
| `app/services/dfd_service.py` | Persist/list/load DFDs; Mermaid/PlantUML export | core util |
| `app/utils/save_utils.py` | Save questionnaire responses; add question to DB | core util |
| `app/services/llm_generator.py` | `build_mock_dfd_payload` (mock, TODO) | experimental |
| `app/utils/questionnaire_flow.py` | Old questionnaire engine | legacy (unused) |
| `app/questions/questionsDb.json` + `TM-Questions/questionsDb.json` | 82-question DB (identical) | core data |
| `TM-Questions/QaT.txt` | Questionnaire branching graph | core data |
| `LLM-Prompts/Response-Extractor-prompt.txt` | Active extraction prompt | core data |
| `LLM-Prompts/LLM_Prompt*.txt` | Legacy PlantUML/STRIDE prompts | legacy |
| `pipelines/<id>/{manifest,response,extraction_raw,dfd_reactflow,risks}.json` | Run artifacts | data |
| `generated_models/dfd_runs/*.json` | Archived DFDs | data |
| `tests/test_*.py` | Unit/integration tests (LLM mocked) | core (quality) |

## 13. Current limitations

1. ~~LLM risk signals disconnected~~ **ADDRESSED (Phase 2):** a constrained LLM **review** layer
   (`llm_risk_review.py`) now assesses the deterministic candidate risks (closed-set, advisory);
   the LLM no longer needs to emit risks via the old `top_risks` path. (Live behavior unverified.)
2. ~~No mitigation generation~~ **FIXED (Phase 1):** deterministic OWASP-code-keyed mitigations +
   quick wins now populate every risk (`OWASP_MITIGATIONS`/`OWASP_QUICK_WINS`).
3. ~~Risk scoring is presence-based~~ **FIXED (Phase 1):** scoring is now answer-aware
   (OWASP-Risk-Rating `impact × likelihood` matrix + answer polarity).
4. **LLM extraction quality** with `qwen3:8b` was unreliable; **mitigated (Phase 2)** via Ollama
   structured outputs + retry, but **not yet confirmed live on-device**.
5. **Static mapper is coupled to exact option strings** — wording changes can silently break it.
6. ~~Dual `questionsDb.json`~~ **FIXED (Phase 3):** `/add-question` now writes both copies in sync.
7. ~~`/add-question` produces unreachable questions~~ **FIXED (Phase 3):** the new question is wired
   into the QaT flow (reachable). Polarity/weights of an auto-added question are still defaults.
8. **Schema drift across runs** (`extraction_generated` vs `llm_extraction_generated`; legacy
   `top_risks` extract in the oldest run; `extraction_reviewed.json` abandoned). Handled by
   backward-compat fallbacks.
9. **Not production-hardened:** hardcoded dev `SECRET_KEY`, `debug=True`, single-process; pipeline
   automation runs in a daemon `Thread` (background failures are now logged — Phase 3 — instead of
   silently swallowed).
10. **Test gaps:** `risk_analysis_service` (only name mapping tested), `dfd_service`,
    `llm_generator`, legacy `questionnaire_flow` are untested; frontend tests are
    string-presence only.

## 14. Thesis-safe claims (supported by code)

- The system is a **hybrid, deterministic-first LLM-assisted threat modeling tool** built on Flask.
- It uses an **adaptive 82-question questionnaire** (verified) with a YAML branching graph and
  `equals/any_of/not_any_of/not_includes` conditions.
- It performs **deterministic, reproducible OWASP risk mapping** across **OWASP LLM Top 10 (2025),
  OWASP Web Top 10 (2025), and OWASP API Top 10 (2023)**, with **human-readable risk names**.
- It generates a **deterministic static DFD** from answers (nodes, edges, trust boundaries, control
  metadata, transport/sensitive-data edge metadata, combined-risk flags) with a **stable, canonical
  layout**.
- The DFD UI keeps the **compact graph clean** (short edge labels, no badges on arrows) and shows
  **detail in a side panel** on selection — enforced both in the data layer and the frontend.
- The DFD mapper **avoids hallucinated architecture** (controls attach to existing nodes; missing
  targets are recorded, not invented).
- The system **works fully without the LLM**; the LLM (local Ollama, `qwen3:8b`) provides an
  **optional architecture extraction** that is **grounded in answers** and **validated with a
  graceful fallback**.
- The pipeline is **modular and testable**: orchestrator steps are independent, the LLM is mocked
  in tests, and the questionnaire→static-DFD path is verified end-to-end without a live model.

## 15. Claims that must NOT be made

- ❌ "The LLM generates the DFD." (Pipeline DFD is the static mapper; LLM extract feeds only the
  auxiliary lab path.)
- ❌ "The LLM generates/explains the risks or proposes mitigations." (Risks, scoring, and
  mitigations are all deterministic; the local-LLM reasoning layer is Phase 2, not built yet.)
- ❌ "The system fine-tunes / trains a model" or "uses a fine-tuned domain model." (No training
  code or dependencies exist; future work only.)
- ✅ Now SAFE to claim (Phase 1): "Risk severity is answer-sensitive (OWASP-style impact ×
  likelihood)" and "the tool produces deterministic, code-keyed mitigations and quick wins."
- ❌ "The LLM extraction reliably produces structured architecture." (It frequently falls back with
  `qwen3:8b`.)
- ❌ "It is production-ready." (Dev secret key, debug mode, file-based state, no auth.)
```
