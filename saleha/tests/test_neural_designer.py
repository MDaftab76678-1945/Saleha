"""Unit tests for Neural Architecture & Transformer Model Designer."""

import unittest
from saleha.core.neural_designer import NeuralDesigner, NeuralArchitectureSpec, NeuralModelReport


class TestNeuralDesigner(unittest.TestCase):
    """Test suite for NeuralDesigner deep learning architecture synthesis."""

    def setUp(self):
        self.designer = NeuralDesigner()

    def test_design_transformer_generates_valid_spec(self):
        spec = NeuralArchitectureSpec(model_name="MiniTransformer", d_model=256, n_heads=4, n_layers=2)
        report = self.designer.design_transformer(spec)
        self.assertIsInstance(report, NeuralModelReport)
        self.assertGreater(report.total_parameters, 10000)
        self.assertIn("class MiniTransformer", report.pytorch_code)
        self.assertIn("RMSNorm", report.pytorch_code)


if __name__ == "__main__":
    unittest.main()
