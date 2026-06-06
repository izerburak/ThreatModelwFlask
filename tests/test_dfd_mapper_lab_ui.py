import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DfdMapperLabUiTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / "app" / "static" / "js" / "dfd_mapper_lab.js").read_text(encoding="utf-8")

    def test_canvas_badges_use_filtered_display_badges(self):
        self.assertIn("function displayBadges", self.script)
        self.assertIn("display_badges", self.script)
        self.assertIn("visual_badges", self.script)
        self.assertNotIn('"Trust boundary",\n      "Sensitive data"', self.script)

    def test_selected_flow_panel_has_trace_and_collapsed_developer_details(self):
        self.assertIn("function flowTrace", self.script)
        self.assertIn("Flow trace", self.script)
        self.assertIn("Flow summary", self.script)
        self.assertIn("Security details", self.script)
        self.assertIn("Security notes", self.script)
        self.assertIn("Developer details", self.script)
        self.assertIn('e("details"', self.script)


if __name__ == "__main__":
    unittest.main()
