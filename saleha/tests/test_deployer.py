"""Unit tests for 1-Click Multi-Cloud & Kubernetes Deployer."""

import os
import shutil
import tempfile
import unittest
from saleha.core.deployer import cloud_deployer


class DeployerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_deploy_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_package_python_runtime(self):
        pkg = cloud_deployer.generate_package(root_dir=".", app_name="test-api", port=9000)
        self.assertEqual(pkg.app_name, "test-api")
        self.assertEqual(pkg.runtime, "python")
        self.assertEqual(pkg.port, 9000)
        self.assertIn("FROM python:3.11-slim", pkg.dockerfile)
        self.assertIn("kind: Deployment", pkg.k8s_deployment)
        self.assertIn("kind: Service", pkg.k8s_service)

    def test_export_deployment_package(self):
        pkg = cloud_deployer.generate_package(root_dir=".", app_name="test-api", port=9000)
        written = cloud_deployer.export_package(pkg, output_dir=self.temp_dir)
        self.assertEqual(len(written), 5)
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir, "Dockerfile")))
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir, "docker-compose.yml")))
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir, "k8s-deployment.yaml")))


if __name__ == "__main__":
    unittest.main()

