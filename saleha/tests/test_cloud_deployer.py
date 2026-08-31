"""Unit tests for CloudDeployer deployment asset generator."""

import os
import tempfile
import unittest

from saleha.core.cloud_deployer import CloudDeployer, DeploymentPlan


class CloudDeployerTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.deployer = CloudDeployer(root_dir=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_python_stack(self):
        with open(os.path.join(self.root, "requirements.txt"), "w") as f:
            f.write("pytest\nfastapi\n")
        stack = self.deployer.detect_stack()
        self.assertEqual(stack, "python")

    def test_plan_and_apply_deployment(self):
        with open(os.path.join(self.root, "pyproject.toml"), "w") as f:
            f.write("[project]\nname='app'\n")

        plan = self.deployer.plan_deployment()
        self.assertEqual(plan.stack_detected, "python")
        self.assertEqual(len(plan.assets), 3)

        written = self.deployer.apply_plan(plan)
        self.assertIn("Dockerfile", written)
        self.assertIn("docker-compose.yml", written)
        self.assertIn(".github/workflows/ci.yml", written)

        self.assertTrue(os.path.isfile(os.path.join(self.root, "Dockerfile")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".github", "workflows", "ci.yml")))


if __name__ == "__main__":
    unittest.main()
