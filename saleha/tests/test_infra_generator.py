"""Unit tests for Full-Stack Docker, K8s & Terraform IaC Generator."""

import unittest
from saleha.core.infra_generator import InfraGenerator, InfrastructureBundle


class TestInfraGenerator(unittest.TestCase):
    """Test suite for InfraGenerator Docker, K8s, and Terraform synthesis."""

    def setUp(self):
        self.generator = InfraGenerator()

    def test_generate_infrastructure_bundle(self):
        bundle = self.generator.generate_infrastructure("user-service", port=8080)
        self.assertIsInstance(bundle, InfrastructureBundle)
        self.assertIn("Dockerfile", bundle.files)
        self.assertIn("docker-compose.yml", bundle.files)
        self.assertIn("k8s_deployment.yaml", bundle.files)
        self.assertIn("main.tf", bundle.files)

        self.assertIn("8080", bundle.dockerfile)
        self.assertIn("user-service", bundle.k8s_deployment)


if __name__ == "__main__":
    unittest.main()
