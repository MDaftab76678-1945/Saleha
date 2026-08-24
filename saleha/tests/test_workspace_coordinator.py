"""Unit tests for Multi-Repo & Monorepo Workspace Coordinator."""

import os
import unittest
from click.testing import CliRunner

from saleha.core.workspace_coordinator import workspace_coordinator
from saleha.cli.commands import cli


class WorkspaceCoordinatorTests(unittest.TestCase):

    def test_discover_current_repo(self):
        repos = workspace_coordinator.discover_repos(".")
        self.assertTrue(len(repos) >= 1)

    def test_get_workspace_status(self):
        statuses = workspace_coordinator.get_workspace_status(".")
        self.assertTrue(len(statuses) >= 1)
        self.assertTrue(isinstance(statuses[0].current_branch, str))
        self.assertTrue(isinstance(statuses[0].is_clean, bool))

    def test_cli_workspace_status_json(self):
        runner = CliRunner()
        res = runner.invoke(cli, ["workspace", "status", "--json"])
        self.assertEqual(res.exit_code, 0)


if __name__ == "__main__":
    unittest.main()

