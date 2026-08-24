import unittest
from saleha.cli.tui_canvas import build_tui_layout, build_file_tree


class TUICanvasTests(unittest.TestCase):
    def test_build_file_tree(self):
        tree = build_file_tree(".", max_depth=1)
        self.assertIsNotNone(tree)
        self.assertTrue(len(tree.children) > 0)

    def test_build_tui_layout_structure(self):
        layout = build_tui_layout(
            active_profile="agent_sde",
            chat_messages=[{"role": "user", "text": "Build auth"}, {"role": "assistant", "text": "Starting swarm"}],
            sec_issues_count=0,
            dag_tasks_count=4
        )
        self.assertIsNotNone(layout)
        self.assertIsNotNone(layout["header"])
        self.assertIsNotNone(layout["body"])
        self.assertIsNotNone(layout["footer"])
        self.assertIsNotNone(layout["left"])
        self.assertIsNotNone(layout["center"])
        self.assertIsNotNone(layout["right"])


if __name__ == "__main__":
    unittest.main()
