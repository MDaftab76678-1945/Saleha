import unittest
from click.testing import CliRunner
from unittest.mock import patch

from saleha.cli.dashboard import build_dashboard_layout, render_dashboard, run_live_dashboard
from saleha.cli.commands import cli


class DashboardTests(unittest.TestCase):
    def test_build_dashboard_layout(self):
        layout = build_dashboard_layout()
        self.assertIsNotNone(layout)
        self.assertIsNotNone(layout["header"])
        self.assertIsNotNone(layout["main"])
        self.assertIsNotNone(layout["footer"])

    def test_render_dashboard(self):
        with patch("saleha.cli.dashboard.console.print") as mock_print:
            render_dashboard()
            mock_print.assert_called_once()

    def test_cli_dashboard_invocation(self):
        with patch("saleha.cli.commands.render_dashboard") as mock_render:
            res = CliRunner().invoke(cli, ["dashboard"])
            self.assertEqual(res.exit_code, 0)
            mock_render.assert_called_once()

    def test_cli_ui_alias(self):
        with patch("saleha.cli.commands.render_dashboard") as mock_render:
            res = CliRunner().invoke(cli, ["ui"])
            self.assertEqual(res.exit_code, 0)
            mock_render.assert_called_once()


if __name__ == "__main__":
    unittest.main()

