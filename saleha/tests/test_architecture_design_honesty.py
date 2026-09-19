"""Architecture work must not invent a decision, or a model that cannot run.

Two engines, one failure shape each:

`ArchitectureDebater.debate()` fell back to a hardcoded
"## Status: ACCEPTED / Adopt <topic> with monitoring" whenever the model was
unreachable. Probed against a dead port with the topic "Microservices vs
Monolith for a 5-person team": zero model calls, and the ADR still read
ACCEPTED -- advising the reader to "Adopt Microservices vs Monolith", which
is not even a coherent choice.

`NeuralDesigner.design_transformer()` accepted any dimensions at all. The
values land directly in the generated source, so `d_model=512, n_heads=7`
emitted `nn.MultiheadAttention(512, 7)` -- which raises "embed_dim must be
divisible by num_heads" the moment anyone runs it -- after the report had
printed a confident 41,158,656-parameter count for it. `d_model=-512`
reported -24,381,440 parameters.
"""

import unittest

from saleha.core.architecture_debater import ArchitectureDebater
from saleha.core.model_provider import OllamaProvider
from saleha.core.neural_designer import (
    InvalidArchitectureError,
    NeuralArchitectureSpec,
    NeuralDesigner,
)


class _DeadProvider(OllamaProvider):
    """Points at a closed port, so every call fails the way a stopped Ollama
    would."""

    def __init__(self) -> None:
        super().__init__(base_url="http://127.0.0.1:1")


class DebateWithoutAModelTests(unittest.TestCase):

    def setUp(self) -> None:
        self.debater = ArchitectureDebater()
        for agent in (self.debater.advocate_agent,
                      self.debater.skeptic_agent,
                      self.debater.judge_agent):
            agent.inference = None
            agent.provider = _DeadProvider()

    def test_an_unreachable_model_does_not_produce_an_accepted_adr(self) -> None:
        adr = self.debater.debate("Microservices vs Monolith", rounds=1)
        self.assertEqual(adr.status, "UNDECIDED")
        self.assertFalse(adr.model_backed)
        self.assertNotIn("ACCEPTED", adr.markdown_content)

    def test_the_reason_the_debate_failed_is_reported(self) -> None:
        """A blank failure is what made this class of bug survive elsewhere in
        this repo; the caller must be able to say why."""
        adr = self.debater.debate("Event sourcing vs CRUD", rounds=1)
        self.assertTrue(adr.failure_reason)
        self.assertIn("judge", adr.failure_reason)

    def test_the_decision_field_does_not_claim_one_was_reached(self) -> None:
        adr = self.debater.debate("gRPC vs REST", rounds=1)
        self.assertIn("No decision", adr.decision)


class DecisionExtractionTests(unittest.TestCase):
    """`.decision` used to be f"Decision reached for: {topic}" -- the topic
    echoed back, identical whether the ADR concluded for or against."""

    def test_the_decision_is_read_out_of_the_adr_body(self) -> None:
        adr_text = (
            "# ADR: Datastore\n"
            "## Status: ACCEPTED\n"
            "## Decision\n"
            "Stay on PostgreSQL; revisit at 10k writes/sec.\n"
            "## Positive Consequences\n- one\n"
        )
        decision = ArchitectureDebater._extract_decision(adr_text)
        self.assertIn("PostgreSQL", decision)
        self.assertNotIn("Positive Consequences", decision)

    def test_two_opposite_adrs_do_not_yield_the_same_decision(self) -> None:
        base = "## Status: ACCEPTED\n## Decision\n{}\n## Positive Consequences\n- x\n"
        adopt = ArchitectureDebater._extract_decision(
            base.format("Adopt microservices now."))
        reject = ArchitectureDebater._extract_decision(
            base.format("Stay monolithic for this team size."))
        self.assertNotEqual(adopt, reject)

    def test_a_missing_decision_section_says_so(self) -> None:
        decision = ArchitectureDebater._extract_decision("# ADR\n## Status: PROPOSED\n")
        self.assertIn("not found", decision.lower())


class TransformerSpecValidationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.designer = NeuralDesigner()

    def test_a_non_integer_head_dimension_is_refused(self) -> None:
        """512/7 = 73.14. The generated nn.MultiheadAttention(512, 7) cannot
        be constructed, so reporting a parameter count for it is a claim about
        a model that does not exist."""
        spec = NeuralArchitectureSpec(model_name="M", d_model=512, n_heads=7)
        with self.assertRaises(InvalidArchitectureError) as ctx:
            self.designer.design_transformer(spec)
        self.assertIn("divisible", str(ctx.exception))

    def test_zero_and_negative_dimensions_are_refused(self) -> None:
        for field_name, kwargs in (
            ("d_model", dict(d_model=0, n_heads=8)),
            ("d_model", dict(d_model=-512, n_heads=8)),
            ("n_heads", dict(d_model=512, n_heads=0)),
            ("n_layers", dict(d_model=512, n_heads=8, n_layers=0)),
            ("vocab_size", dict(d_model=512, n_heads=8, vocab_size=0)),
        ):
            with self.subTest(**kwargs):
                spec = NeuralArchitectureSpec(model_name="M", **kwargs)
                with self.assertRaises(InvalidArchitectureError) as ctx:
                    self.designer.design_transformer(spec)
                self.assertIn(field_name, str(ctx.exception))

    def test_a_negative_spec_can_no_longer_report_negative_parameters(self) -> None:
        spec = NeuralArchitectureSpec(model_name="M", d_model=-512, n_heads=8)
        with self.assertRaises(InvalidArchitectureError):
            self.designer.design_transformer(spec)

    def test_valid_specs_are_unchanged(self) -> None:
        """The arithmetic was always real; this fix must not move it."""
        spec = NeuralArchitectureSpec(
            model_name="Ok", d_model=512, n_heads=8, n_layers=6)
        report = self.designer.design_transformer(spec)
        self.assertEqual(report.total_parameters, 57_939_968)
        self.assertEqual(spec.head_dim, 64)

    def test_generated_source_embeds_a_head_count_that_divides_the_width(self) -> None:
        spec = NeuralArchitectureSpec(
            model_name="Ok", d_model=512, n_heads=16, n_layers=2)
        report = self.designer.design_transformer(spec)
        self.assertIn("512", report.pytorch_code)
        self.assertEqual(spec.d_model % spec.n_heads, 0)


if __name__ == "__main__":
    unittest.main()
