"""Extract structured OWASP LLM 2026 training-source records from the official PDF.

This script does not invent or paraphrase source material. It extracts the
Description, Common Examples of Risk, Prevention and Mitigation Strategies, and
Example Attack Scenarios sections into auditable JSON/JSONL files.

Usage:
    python extract_official_training_sources.py path/to/OWASP-GenAI-LLM-Top-10-2026-v1.0.pdf
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader


OUTPUT_DIR = Path(__file__).resolve().parent
SOURCE_URL = "https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/"
LICENSE = "CC BY-SA 4.0"

CATEGORIES = [
    ("LLM01:2026", "Prompt Injection", 10, 17),
    ("LLM02:2026", "Sensitive Information Disclosure", 18, 22),
    ("LLM03:2026", "Excessive Agency", 23, 26),
    ("LLM04:2026", "Supply Chain", 27, 32),
    ("LLM05:2026", "Data and Model Poisoning", 33, 37),
    ("LLM06:2026", "Unbounded Consumption", 38, 42),
    ("LLM07:2026", "Misinformation", 43, 45),
    ("LLM08:2026", "Hidden Context Exposure", 46, 49),
    ("LLM09:2026", "Vector and Embedding Weaknesses", 50, 54),
    ("LLM10:2026", "Improper Output Handling", 55, 57),
]

SECTION_HEADINGS = (
    "Description",
    "Common Examples of Risk",
    "Prevention and Mitigation Strategies",
    "Example Attack Scenarios",
    "References",
)


def clean_page_text(text: str) -> str:
    lines = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if line == "genai.owasp.org" or re.fullmatch(r"Page\s+\d+", line):
            continue
        lines.append(line)
    return "\n".join(lines)


def compact(text: str) -> str:
    text = re.sub(r"\s*-\s*\n\s*", "", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def section(text: str, heading: str, next_heading: str | None) -> str:
    start_match = re.search(rf"(?m)^\s*{re.escape(heading)}\s*$", text)
    if not start_match:
        raise ValueError(f"Missing section heading: {heading}")
    start = start_match.end()
    if next_heading is None:
        return text[start:].strip()
    end_match = re.search(rf"(?m)^\s*{re.escape(next_heading)}\s*$", text[start:])
    if not end_match:
        raise ValueError(f"Missing next section heading: {next_heading}")
    return text[start:start + end_match.start()].strip()


def split_numbered_items(text: str) -> tuple[str, list[dict]]:
    """Parse numbered items while preserving optional Tier headings."""
    intro_lines = []
    items = []
    current = None
    current_tier = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tier_match = re.match(r"^Tier\s+(\d+)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if tier_match:
            current_tier = f"Tier {tier_match.group(1)}: {tier_match.group(2).strip()}"
            if current is not None:
                items.append(current)
                current = None
            continue
        item_match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if item_match:
            if current is not None:
                items.append(current)
            current = {
                "source_number": int(item_match.group(1)),
                "tier": current_tier,
                "text_parts": [item_match.group(2)],
            }
        elif current is None:
            intro_lines.append(line)
        else:
            current["text_parts"].append(line)
    if current is not None:
        items.append(current)

    normalized = []
    for position, item in enumerate(items, start=1):
        normalized.append({
            "position": position,
            "source_number": item["source_number"],
            "tier": item["tier"],
            "text": compact("\n".join(item["text_parts"])),
        })
    return compact("\n".join(intro_lines)), normalized


def split_scenarios(text: str) -> list[dict]:
    pattern = re.compile(r"(?m)^\s*Scenario\s+#(\d+)(?::\s*([^\n]+))?\s*$")
    matches = list(pattern.finditer(text))
    scenarios = []
    for position, match in enumerate(matches, start=1):
        body_start = match.end()
        body_end = matches[position].start() if position < len(matches) else len(text)
        scenarios.append({
            "position": position,
            "source_number": int(match.group(1)),
            "title": compact(match.group(2) or ""),
            "text": compact(text[body_start:body_end]),
        })
    return scenarios


def category_text(reader: PdfReader, start_page: int, end_page: int) -> str:
    pages = []
    for page_number in range(start_page, end_page + 1):
        pages.append(clean_page_text(reader.pages[page_number - 1].extract_text() or ""))
    return "\n".join(pages)


def parse_category(reader: PdfReader, code: str, name: str, start_page: int, end_page: int) -> dict:
    text = category_text(reader, start_page, end_page)
    description = section(text, "Description", "Common Examples of Risk")
    examples_text = section(text, "Common Examples of Risk", "Prevention and Mitigation Strategies")
    mitigations_text = section(text, "Prevention and Mitigation Strategies", "Example Attack Scenarios")

    scenarios_start = re.search(r"(?m)^\s*Example Attack Scenarios\s*$", text)
    if not scenarios_start:
        raise ValueError(f"Missing scenario section for {code}")
    scenario_tail = text[scenarios_start.end():]
    references = re.search(r"(?m)^\s*References\s*$", scenario_tail)
    scenarios_text = scenario_tail[:references.start()] if references else scenario_tail

    examples_intro, examples = split_numbered_items(examples_text)
    mitigation_intro, mitigations = split_numbered_items(mitigations_text)
    scenarios = split_scenarios(scenarios_text)

    return {
        "code": code,
        "name": name,
        "framework": "owasp_llm",
        "version": "2026",
        "source_pages": list(range(start_page, end_page + 1)),
        "description": compact(description),
        "common_examples_intro": examples_intro,
        "common_examples": examples,
        "mitigation_intro": mitigation_intro,
        "mitigations": mitigations,
        "attack_scenarios": scenarios,
        "source": {
            "title": "OWASP Top 10 for LLM Applications 2026",
            "url": SOURCE_URL,
            "license": LICENSE,
        },
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def build_outputs(pdf_path: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    if len(reader.pages) < 58:
        raise ValueError(f"Unexpected PDF length: {len(reader.pages)} pages")

    catalog = [parse_category(reader, *entry) for entry in CATEGORIES]
    scenarios = []
    mitigations = []
    risk_examples = []

    for category in catalog:
        shared = {
            "label": category["code"],
            "label_name": category["name"],
            "framework": category["framework"],
            "framework_version": category["version"],
            "source_pages": category["source_pages"],
            "source_url": SOURCE_URL,
            "license": LICENSE,
        }
        for item in category["attack_scenarios"]:
            scenarios.append({
                "id": f"{category['code']}-SC{item['position']:02d}",
                "task": "threat_classification_source",
                "input": item["text"],
                "scenario_title": item["title"],
                **shared,
            })
        for item in category["mitigations"]:
            mitigations.append({
                "id": f"{category['code']}-MIT{item['position']:02d}",
                "task": "mitigation_generation_source",
                "mitigation": item["text"],
                "tier": item["tier"],
                **shared,
            })
        for item in category["common_examples"]:
            risk_examples.append({
                "id": f"{category['code']}-EX{item['position']:02d}",
                "task": "threat_classification_source",
                "input": item["text"],
                **shared,
            })

    (OUTPUT_DIR / "official_llm2026_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_jsonl(OUTPUT_DIR / "official_attack_scenarios.jsonl", scenarios)
    write_jsonl(OUTPUT_DIR / "official_mitigations.jsonl", mitigations)
    write_jsonl(OUTPUT_DIR / "official_common_risk_examples.jsonl", risk_examples)

    manifest = {
        "source_pdf": pdf_path.name,
        "source_url": SOURCE_URL,
        "license": LICENSE,
        "categories": len(catalog),
        "attack_scenarios": len(scenarios),
        "mitigations": len(mitigations),
        "common_risk_examples": len(risk_examples),
        "per_category": [
            {
                "code": category["code"],
                "name": category["name"],
                "source_pages": category["source_pages"],
                "attack_scenarios": len(category["attack_scenarios"]),
                "mitigations": len(category["mitigations"]),
                "common_risk_examples": len(category["common_examples"]),
            }
            for category in catalog
        ],
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path, help="Path to OWASP GenAI LLM Top 10 2026 v1.0 PDF")
    args = parser.parse_args()
    manifest = build_outputs(args.pdf.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
