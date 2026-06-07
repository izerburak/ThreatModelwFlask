import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DfdMapperLabUiTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / "app" / "static" / "js" / "dfd_mapper_lab.js").read_text(encoding="utf-8")
        self.template = (ROOT / "app" / "templates" / "dfd_mapper_lab.html").read_text(encoding="utf-8")

    def test_canvas_edges_do_not_render_text_badges(self):
        self.assertIn("display_badges", self.script)
        self.assertIn("visual_badges", self.script)
        self.assertIn("display_badges: []", self.script)
        self.assertIn("visual_badges: []", self.script)
        self.assertNotIn("static-edge-badges", self.script)
        self.assertNotIn("static-edge-badge", self.script)
        self.assertNotIn("static-edge-badges", self.template)
        self.assertNotIn("static-edge-badge", self.template)

    def test_selected_flow_panel_has_trace_and_collapsed_developer_details(self):
        self.assertIn("function flowTrace", self.script)
        self.assertIn("Flow trace", self.script)
        self.assertIn("Flow summary", self.script)
        self.assertIn("Security details", self.script)
        self.assertIn("Security notes", self.script)
        self.assertIn("Developer details", self.script)
        self.assertIn("Data carried", self.script)
        self.assertIn("Transport security", self.script)
        self.assertIn("Required control", self.script)
        self.assertIn('e("details"', self.script)

    def test_raw_graph_json_and_metadata_toggle_are_not_rendered(self):
        self.assertNotIn("Raw Graph JSON", self.script)
        self.assertNotIn("Show Metadata", self.script)
        self.assertNotIn("Generate a static DFD to preview the graph JSON", self.script)


if __name__ == "__main__":
    unittest.main()
