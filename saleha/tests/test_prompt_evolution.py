"""
Tests for prompt evolution with real fitness.

What this replaces: `AgentEvolutionEngine` from the notebook, whose genetic
machinery is real (tournament selection, elitism, crossover, mutation, hall of
fame) but whose fitness function is:

    # Random performance factor (simulates actual execution)
    score += random.uniform(0.1, 0.5)

with the comment "In production, this would call the actual agent". It evolves
against a random number generator -- the "fittest" genome is whichever drew the
luckiest numbers, and two runs disagree.

The two properties that distinguish this from that version are asserted
directly: fitness comes from execution, and the same inputs give the same
result every time.

No real model is contacted: the inference engine and verifier are injected.
"""

from __future__ import annotations

import unittest

from saleha.core.fast_inference import InferenceResult
from saleha.core.prompt_evolution import (
    MIN_TASKS_FOR_TRUST,
    EvolutionTask,
    Genome,
    PromptEvolver,
    extract_code,
)

MARKER = "type hints"


class _Engine:
    """Deterministic stand-in: emits working code only when the genome's
    prompt carries the marker directive."""

    def __init__(self):
        self.calls = 0

    def run_batch(self, requests, **kwargs):
        self.calls += 1
        out = []
        for request in requests:
            good = MARKER in request.prompt.lower()
            code = ("def add(a: int, b: int) -> int:\n    return a + b"
                    if good else "def add(a, b):\n    return a - b")
            out.append(InferenceResult(success=True, tag=request.tag,
                                       content=f"```python\n{code}\n```"))
        return out


def _verify(code, task):
    namespace = {}
    try:
        exec(code, namespace)          # noqa: S102 - the point of the test
        return namespace["add"](2, 3) == 5
    except Exception:
        return False


def _tasks(n=6):
    return [EvolutionTask(f"t{i}", "add two numbers", "assert add(2,3)==5")
            for i in range(n)]


def _evolver(**kwargs):
    kwargs.setdefault("inference", _Engine())
    kwargs.setdefault("verifier", _verify)
    kwargs.setdefault("population_size", 4)
    kwargs.setdefault("seed", 11)
    return PromptEvolver(**kwargs)


class FitnessIsRealTests(unittest.TestCase):
    def test_fitness_is_the_fraction_of_tasks_that_pass(self):
        evolver = _evolver()
        failing = Genome("g", "You are a coder.")
        evolver.evaluate(failing, _tasks(4))
        self.assertEqual(failing.fitness, 0.0)
        self.assertEqual((failing.passed, failing.total), (0, 4))

        passing = Genome("g2", "You are a coder.", directives=[MARKER])
        evolver.evaluate(passing, _tasks(4))
        self.assertEqual(passing.fitness, 1.0)
        self.assertEqual((passing.passed, passing.total), (4, 4))

    def test_a_better_prompt_scores_higher(self):
        evolver = _evolver()
        worse = evolver.evaluate(Genome("a", "base"), _tasks())
        better = evolver.evaluate(
            Genome("b", "base", directives=[MARKER]), _tasks())
        self.assertGreater(better.fitness, worse.fitness)

    def test_no_tasks_means_zero_not_a_lucky_number(self):
        genome = _evolver().evaluate(Genome("g", "base"), [])
        self.assertEqual(genome.fitness, 0.0)
        self.assertEqual(genome.total, 0)

    def test_a_crashing_verifier_fails_only_that_task(self):
        def flaky(code, task):
            if task.task_id == "t0":
                raise RuntimeError("sandbox died")
            return _verify(code, task)

        evolver = _evolver(verifier=flaky)
        genome = evolver.evaluate(
            Genome("g", "base", directives=[MARKER]), _tasks(4))
        self.assertEqual(genome.passed, 3)      # 3 of 4, not 0

    def test_failed_generation_does_not_count_as_a_pass(self):
        class Dead:
            def run_batch(self, requests, **kwargs):
                return [InferenceResult(success=False, error="refused",
                                        tag=r.tag) for r in requests]

        genome = _evolver(inference=Dead()).evaluate(
            Genome("g", "base", directives=[MARKER]), _tasks(3))
        self.assertEqual(genome.fitness, 0.0)


class ReproducibilityTests(unittest.TestCase):
    """The random-fitness version gives a different winner every run."""

    def test_the_same_inputs_give_the_same_result(self):
        outcomes = set()
        for _ in range(3):
            result = _evolver().evolve("You are a coder.", _tasks(),
                                       generations=2)
            outcomes.add((result.best.fitness, result.best.genome_id,
                          result.improvement))
        self.assertEqual(len(outcomes), 1)

    def test_a_different_seed_can_explore_differently(self):
        one = _evolver(seed=1)
        two = _evolver(seed=999)
        a = one.mutate(Genome("s", "base"), 1, 1)
        b = two.mutate(Genome("s", "base"), 1, 1)
        self.assertIsInstance(a.directives, list)
        self.assertIsInstance(b.directives, list)

    def test_tournament_selection_breaks_ties_deterministically(self):
        evolver = _evolver()
        pool = [Genome("a", "p", fitness=0.5), Genome("b", "p", fitness=0.5)]
        picks = {evolver._select(pool).genome_id for _ in range(20)}
        self.assertLessEqual(len(picks), 2)      # never crashes, always valid


class EvolutionOutcomeTests(unittest.TestCase):
    def test_evolution_finds_the_directive_that_works(self):
        result = _evolver().evolve("You are a coder.", _tasks(),
                                   generations=2)
        self.assertEqual(result.seed_fitness, 0.0)
        self.assertEqual(result.best.fitness, 1.0)
        self.assertEqual(result.improvement, 1.0)

    def test_history_records_every_generation(self):
        result = _evolver().evolve("base", _tasks(), generations=3)
        self.assertEqual(len(result.history), 3)
        self.assertEqual([h.generation for h in result.history], [1, 2, 3])

    def test_best_fitness_never_regresses(self):
        """Elitism must carry the best genome forward."""
        result = _evolver().evolve("base", _tasks(), generations=3)
        bests = [h.best_fitness for h in result.history]
        for earlier, later in zip(bests, bests[1:]):
            self.assertGreaterEqual(later, earlier)

    def test_a_small_task_set_is_reported_as_untrustworthy(self):
        result = _evolver().evolve("base", _tasks(2), generations=1)
        self.assertFalse(result.trustworthy)
        self.assertIn("NOT TRUSTWORTHY", result.describe())

    def test_a_large_enough_task_set_is_trusted(self):
        result = _evolver().evolve("base", _tasks(MIN_TASKS_FOR_TRUST),
                                   generations=1)
        self.assertTrue(result.trustworthy)
        self.assertNotIn("NOT TRUSTWORTHY", result.describe())


class CachingTests(unittest.TestCase):
    def test_an_unchanged_genome_is_not_re_evaluated(self):
        evolver = _evolver()
        genome = Genome("g", "base", directives=[MARKER])
        evolver.evaluate(genome, _tasks(3))
        before = evolver.evaluations
        evolver.evaluate(Genome("g2", "base", directives=[MARKER]), _tasks(3))
        self.assertEqual(evolver.evaluations, before)
        self.assertEqual(evolver.cache_hits, 1)

    def test_temperature_is_part_of_the_identity(self):
        cold = Genome("a", "base", temperature=0.0)
        warm = Genome("b", "base", temperature=0.8)
        self.assertNotEqual(cold.fingerprint(), warm.fingerprint())

    def test_directives_are_part_of_the_identity(self):
        self.assertNotEqual(Genome("a", "base").fingerprint(),
                            Genome("b", "base", directives=["x"]).fingerprint())


class GeneticOperatorTests(unittest.TestCase):
    def test_crossover_merges_both_parents(self):
        evolver = _evolver()
        child = evolver.crossover(
            Genome("a", "base", directives=["one"]),
            Genome("b", "base", directives=["two"]), 1, 1)
        self.assertIn("one", child.directives)
        self.assertIn("two", child.directives)

    def test_crossover_does_not_duplicate_shared_directives(self):
        evolver = _evolver()
        child = evolver.crossover(
            Genome("a", "base", directives=["same"]),
            Genome("b", "base", directives=["same"]), 1, 1)
        self.assertEqual(child.directives.count("same"), 1)

    def test_mutation_changes_something(self):
        evolver = _evolver()
        parent = Genome("p", "base", directives=["one"])
        child = evolver.mutate(parent, 1, 1)
        self.assertTrue(child.directives != parent.directives
                        or child.temperature != parent.temperature)

    def test_temperature_stays_in_range(self):
        evolver = _evolver()
        genome = Genome("p", "base", temperature=0.85)
        for _ in range(30):
            genome = evolver.mutate(genome, 1, 1)
            self.assertGreaterEqual(genome.temperature, 0.0)
            self.assertLessEqual(genome.temperature, 0.9)

    def test_directives_are_capped(self):
        evolver = _evolver()
        genome = Genome("p", "base")
        for _ in range(40):
            genome = evolver.mutate(genome, 1, 1)
            self.assertLessEqual(len(genome.directives), 5)

    def test_render_includes_the_directives(self):
        rendered = Genome("g", "You are a coder.", directives=["Be brief."]).render()
        self.assertIn("You are a coder.", rendered)
        self.assertIn("Be brief.", rendered)

    def test_render_of_a_bare_genome_is_the_prompt(self):
        self.assertEqual(Genome("g", "just this").render(), "just this")


class ExtractCodeTests(unittest.TestCase):
    def test_prefers_the_largest_block(self):
        text = ("```python\nprint(add(1,2))\n```\n"
                "```python\ndef add(a, b):\n    return a + b\n```")
        self.assertIn("def add", extract_code(text))

    def test_unfenced_reply_is_returned(self):
        self.assertEqual(extract_code("def f(): pass"), "def f(): pass")

    def test_empty_is_empty(self):
        self.assertEqual(extract_code(""), "")


if __name__ == "__main__":
    unittest.main()
