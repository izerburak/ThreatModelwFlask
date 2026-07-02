"""Deterministic grounding validator (stage 5 of the pipeline).

Runs after the local-LLM threat-identification stage and before DREAD scoring. It
is pure, deterministic Python - no LLM - so its behaviour is fully testable. It
enforces that only grounded, supported threats proceed to scoring:

  * Primary threats must use a deterministic candidate code; anything else is
    demoted to ``secondary_findings`` with status ``needs_more_info``.
  * ``affected_nodes`` / ``affected_edges`` that are not real DFD ids are stripped
    (hallucinated architecture never passes).
  * Empty-evidence threats are downgraded to ``needs_more_info``.
  * Unknown-only evidence can never be ``confirmed``.
  * ``confirmed`` requires strong evidence (a real grounded candidate, supporting
    detail, and non-low confidence); otherwise it is downgraded to ``plausible``.

Only ``confirmed`` / ``plausible`` primary threats are returned in
``primary_threats`` (the set that proceeds to DREAD). Everything else is recorded
for transparency but does not get scored or mitigated in V1.
"""

_UNKNOWN_MARKERS = ("unknown", "not sure", "n/a", "not applicable")


def validate_threats(identification, dfd_graph, deterministic_risks):
    """Validate/ground LLM-identified threats against the DFD and deterministic risks."""
    identification = identification if isinstance(identification, dict) else {}
    node_ids = {node.get("id") for node in _nodes(dfd_graph) if node.get("id")}
    edge_ids = {edge.get("id") for edge in _edges(dfd_graph) if edge.get("id")}
    det_by_code = {risk.get("code"): risk for risk in (deterministic_risks or []) if isinstance(risk, dict) and risk.get("code")}
    det_codes = set(det_by_code)

    primary = []
    downgraded = []
    secondary = []
    report = {
        "demoted_non_primary_codes": [],
        "downgraded": [],
        "stripped_node_ids": [],
        "stripped_edge_ids": [],
        "notes": [],
    }

    for raw in identification.get("identified_threats") or []:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or "").strip().upper()

        # Rule: primary threats must reference a deterministic candidate code.
        if code not in det_codes:
            report["demoted_non_primary_codes"].append(code or "(missing)")
            report["notes"].append(f"{code or '(missing)'} is not a deterministic candidate; demoted to secondary_findings.")
            secondary.append(_as_secondary(raw, code, "Code is outside the deterministic candidate set."))
            continue

        threat = _base_threat(raw, code)

        # Rule: reject hallucinated DFD node/edge ids.
        clean_nodes, bad_nodes = _partition(threat["affected_nodes"], node_ids)
        clean_edges, bad_edges = _partition(threat["affected_edges"], edge_ids)
        threat["affected_nodes"] = clean_nodes
        threat["affected_edges"] = clean_edges
        if bad_nodes:
            report["stripped_node_ids"].extend(bad_nodes)
            report["notes"].append(f"{code}: removed unknown affected_nodes {bad_nodes}.")
        if bad_edges:
            report["stripped_edge_ids"].extend(bad_edges)
            report["notes"].append(f"{code}: removed unknown affected_edges {bad_edges}.")

        evidence = [item for item in threat["evidence"] if str(item).strip()]
        threat["evidence"] = evidence
        control_gap = str(threat.get("control_gap") or "").strip()

        candidate = det_by_code[code]
        candidate_evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), list) else []
        unknown_only = _candidate_unknown_only(candidate_evidence)
        has_support = bool(clean_nodes) or bool(control_gap) or bool(evidence)

        status = _normalize_status(threat.get("status"))
        original_status = status

        # Rule: empty evidence (and no control gap) -> needs_more_info.
        if not evidence and not control_gap:
            status = "needs_more_info"
            report["notes"].append(f"{code}: no evidence or control_gap supplied; set to needs_more_info.")

        # Rule: Unknown-only grounding can never be confirmed.
        if unknown_only and status in ("confirmed", "plausible"):
            status = "needs_more_info"
            report["notes"].append(f"{code}: grounding answers are Unknown-only; cannot be confirmed.")

        # Rule: confirmed requires strong evidence.
        if status == "confirmed":
            confidence = str(threat.get("confidence") or "").strip().lower()
            if confidence == "low" or not has_support or not candidate_evidence:
                status = "plausible"
                report["notes"].append(f"{code}: insufficient strength for 'confirmed'; downgraded to plausible.")

        threat["status"] = status
        threat["validated"] = status in ("confirmed", "plausible")
        if status != original_status:
            report["downgraded"].append({"code": code, "from": original_status, "to": status})

        if threat["validated"]:
            primary.append(threat)
        else:
            downgraded.append(threat)

    # LLM-suggested extra findings: always needs_more_info, never scored/mitigated in V1.
    for raw in identification.get("suggested_secondary_findings") or []:
        if isinstance(raw, dict):
            secondary.append(_as_secondary(raw, str(raw.get("code") or "").strip().upper(), raw.get("rationale")))

    identified_codes = {threat["code"] for threat in primary} | {threat["code"] for threat in downgraded}
    unidentified = sorted(det_codes - identified_codes)
    report["unidentified_deterministic_codes"] = unidentified
    report["stripped_node_ids"] = sorted(set(report["stripped_node_ids"]))
    report["stripped_edge_ids"] = sorted(set(report["stripped_edge_ids"]))
    report["demoted_non_primary_codes"] = sorted(set(report["demoted_non_primary_codes"]))

    # Deterministic backfill: a grounded candidate the LLM never addressed must not
    # silently vanish (deterministic-first contract). It is surfaced as needs_more_info
    # for transparency only - never scored or mitigated in V1.
    unaddressed = [_as_unaddressed(det_by_code[code]) for code in unidentified]
    if unaddressed:
        report["notes"].append(
            f"{len(unaddressed)} deterministic candidate(s) not addressed by the model; "
            "surfaced as unaddressed_candidates (needs_more_info), not scored."
        )

    return {
        "primary_threats": primary,
        "downgraded_threats": downgraded,
        "secondary_findings": secondary,
        "unaddressed_candidates": unaddressed,
        "report": report,
    }


def _as_unaddressed(candidate):
    """A grounded deterministic candidate the LLM did not address - transparency only."""
    return {
        "code": candidate.get("code"),
        "name": candidate.get("name") or candidate.get("code"),
        "framework": candidate.get("framework"),
        "status": "needs_more_info",
        "evidence": candidate.get("evidence") if isinstance(candidate.get("evidence"), list) else [],
        "missing_information": list(candidate.get("missing_information") or []),
        "rationale": "Deterministic candidate not addressed by the threat-identification model.",
        "classification": "unaddressed_candidate",
        "validated": False,
    }


def _base_threat(raw, code):
    return {
        "code": code,
        "name": str(raw.get("name") or code).strip(),
        "status": _normalize_status(raw.get("status")),
        "threat_pattern": str(raw.get("threat_pattern") or "").strip(),
        "evidence": list(raw.get("evidence") or []) if isinstance(raw.get("evidence"), list) else [],
        "affected_nodes": list(raw.get("affected_nodes") or []) if isinstance(raw.get("affected_nodes"), list) else [],
        "affected_edges": list(raw.get("affected_edges") or []) if isinstance(raw.get("affected_edges"), list) else [],
        "abuse_path": list(raw.get("abuse_path") or []) if isinstance(raw.get("abuse_path"), list) else [],
        "control_gap": str(raw.get("control_gap") or "").strip(),
        "confidence": str(raw.get("confidence") or "").strip().lower() or None,
        "missing_information": list(raw.get("missing_information") or []) if isinstance(raw.get("missing_information"), list) else [],
        "classification": "primary",
    }


def _as_secondary(raw, code, rationale):
    return {
        "code": code or None,
        "name": str(raw.get("name") or code or "Suggested finding").strip(),
        "status": "needs_more_info",
        "threat_pattern": str(raw.get("threat_pattern") or "").strip(),
        "evidence": list(raw.get("evidence") or []) if isinstance(raw.get("evidence"), list) else [],
        "rationale": str(rationale or raw.get("rationale") or "").strip(),
        "missing_information": list(raw.get("missing_information") or []) if isinstance(raw.get("missing_information"), list) else [],
        "classification": "secondary_candidate",
        "validated": False,
    }


def _partition(values, allowed):
    keep = []
    bad = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if text in allowed:
            keep.append(text)
        else:
            bad.append(text)
    return keep, bad


def _candidate_unknown_only(candidate_evidence):
    answers = []
    for entry in candidate_evidence:
        if isinstance(entry, dict) and "answer" in entry:
            answers.append(entry.get("answer"))
    if not answers:
        return False
    return all(_value_is_unknown(answer) for answer in answers)


def _value_is_unknown(value):
    values = value if isinstance(value, list) else [value]
    cleaned = [str(item).strip().lower() for item in values if str(item).strip()]
    if not cleaned:
        return True
    return all(any(marker in item for marker in _UNKNOWN_MARKERS) for item in cleaned)


def _normalize_status(value):
    text = str(value or "").strip().lower()
    if text in ("confirmed", "plausible", "needs_more_info", "not_applicable"):
        return text
    return "needs_more_info"


def _nodes(dfd_graph):
    nodes = (dfd_graph or {}).get("nodes") if isinstance(dfd_graph, dict) else None
    return [node for node in (nodes or []) if isinstance(node, dict)]


def _edges(dfd_graph):
    edges = (dfd_graph or {}).get("edges") if isinstance(dfd_graph, dict) else None
    return [edge for edge in (edges or []) if isinstance(edge, dict)]
