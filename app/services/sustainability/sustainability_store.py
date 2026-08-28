"""Lightweight JSON persistence for Sustainability configuration and scans."""

import json
from pathlib import Path


SCHEMA_VERSION = "sustainability.v1"


class SustainabilityStore:
    def __init__(self, app_root_path=None, storage_path=None):
        if storage_path:
            self.path = Path(storage_path)
        elif app_root_path:
            self.path = Path(app_root_path).parent / "sustainability" / "sustainability.json"
        else:
            raise ValueError("An app root path or storage path is required.")

    def load(self):
        if not self.path.exists():
            return _default_data()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _default_data()
        if not isinstance(payload, dict):
            return _default_data()

        custom = payload.get("custom_keywords")
        custom = custom if isinstance(custom, dict) else {}
        return {
            "schema_version": SCHEMA_VERSION,
            "custom_keywords": {
                "security": _clean_keyword_list(custom.get("security")),
                "llm": _clean_keyword_list(custom.get("llm")),
            },
            "last_scan": payload.get("last_scan") if isinstance(payload.get("last_scan"), dict) else None,
        }

    def save_custom_keywords(self, custom_keywords):
        payload = self.load()
        custom = custom_keywords if isinstance(custom_keywords, dict) else {}
        payload["custom_keywords"] = {
            "security": _clean_keyword_list(custom.get("security")),
            "llm": _clean_keyword_list(custom.get("llm")),
        }
        self._write(payload)
        return payload["custom_keywords"]

    def save_last_scan(self, scan):
        payload = self.load()
        payload["last_scan"] = scan if isinstance(scan, dict) else None
        self._write(payload)

    def _write(self, payload):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)


def _default_data():
    return {
        "schema_version": SCHEMA_VERSION,
        "custom_keywords": {"security": [], "llm": []},
        "last_scan": None,
    }


def _clean_keyword_list(values):
    if not isinstance(values, (list, tuple)):
        return []
    cleaned = []
    seen = set()
    for value in values:
        keyword = " ".join(str(value or "").split())[:80]
        key = keyword.casefold()
        if not keyword or key in seen:
            continue
        seen.add(key)
        cleaned.append(keyword)
    return cleaned
