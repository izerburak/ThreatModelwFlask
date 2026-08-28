import unittest
from pathlib import Path

from app.services.risk_analysis_service import build_risk_view_model


ROOT = Path(__file__).resolve().parents[1]


class RiskViewModelTests(unittest.TestCase):
    def test_groups_risks_into_three_categories_and_counts_review_state(self):
        analysis = {
            "quick_wins": ["First", "Second", "Third", "Fourth", "Fifth"],
            "unified_risks": [
                {
                    "code": "LLM01", "name": "Prompt Injection",
                    "framework": "owasp_llm", "risk_level": "Critical",
                    "status": "confirmed", "mitigations": ["Isolate input."],
                },
                {
                    "code": "A01:2025", "name": "Broken Access Control",
                    "framework": "owasp_web", "risk_level": "High",
                    "status": "plausible", "mitigations": ["Deny by default."],
                },
                {
                    "code": "API7:2023", "name": "SSRF",
                    "framework": "owasp_api", "risk_level": "Unscored",
                    "status": "needs_more_info", "mitigations": ["Allowlist URLs."],
                },
            ],
        }

        view = build_risk_view_model(analysis)
        categories = {category["short_key"]: category for category in view["categories"]}

        self.assertEqual(list(categories), ["llm", "web", "api"])
        self.assertEqual([categories[key]["total"] for key in ("llm", "web", "api")], [1, 1, 1])
        self.assertEqual(view["total"], 3)
        self.assertEqual(view["critical_high"], 2)
        self.assertEqual(view["needs_review"], 1)
        self.assertEqual(view["mitigated"], 3)
        self.assertEqual(view["priority_actions"], ["First", "Second", "Third", "Fourth"])
        self.assertEqual(categories["api"]["unscored"], 1)


class RiskUiContractTests(unittest.TestCase):
    def setUp(self):
        self.template = (ROOT / "app" / "templates" / "risk.html").read_text(encoding="utf-8")
        self.script = (ROOT / "app" / "static" / "js" / "risk.js").read_text(encoding="utf-8")

    def test_template_has_category_tabs_compact_rows_and_integrated_mitigations(self):
        self.assertIn('role="tablist"', self.template)
        self.assertIn('data-risk-category="{{ category.short_key }}"', self.template)
        self.assertIn("risk-row-toggle", self.template)
        self.assertIn("Mitigation and validation", self.template)
        self.assertNotIn("<h2>Mitigations</h2>", self.template)

    def test_template_distinguishes_unscored_from_severity(self):
        self.assertIn("Reanalysis required", self.template)
        self.assertIn("Rerun the analysis for DREAD", self.template)

    def test_script_supports_categories_filters_and_expandable_details(self):
        self.assertIn("selectCategory", self.script)
        self.assertIn("applyFilters", self.script)
        self.assertIn('setAttribute("aria-expanded"', self.script)
        self.assertIn('["ArrowLeft", "ArrowRight", "Home", "End"]', self.script)


if __name__ == "__main__":
    unittest.main()
