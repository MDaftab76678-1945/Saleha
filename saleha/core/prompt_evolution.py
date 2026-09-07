"""
Saleha Core: Prompt Evolution (genetic search over real fitness)

Why this exists
---------------
`AgentEvolutionEngine` (`chat-Agent Task Workflow.txt:16473`) has real genetic
machinery -- tournament and roulette selection, elitism, crossover, mutation,
a hall of fame -- attached to this fitness function:

    # Random performance factor (simulates actual execution)
    score += random.uniform(0.1, 0.5)

with the comment *"In production, this would call the actual agent"*. It
evolves against a random number generator: the "fittest" genome is whichever
one drew the luckiest numbers, and running it twice gives different winners.

The machinery was never the problem. This module keeps that shape and replaces
the fitness function with the only thing that means anything here: **run the
candidate prompt on real tasks and count how many actually pass their tests.**

Selection is by execution, never by opinion
-------------------------------------------
The same rule as `parallel_solver.py`: a model rating its own output is the
trust failure this repo keeps finding. A genome's fitness is the fraction of
tasks whose generated code passes a real test suite in the sandbox. No model
is asked whether a prompt is good.

Honest cost
-----------
Fitness is `population x tasks` model calls per generation, each followed by a
sandboxed execution. That is expensive and genuinely slow -- this is an
offline optimiser, not something to run per request. Tasks within a generation
are independent, so they go out concurrently, and identical genomes are cached
by hash so re-evaluating an elite costs nothing.

Honest limits
-------------
- **Small task sets overfit.** With 3 tasks a genome can win by luck. The
  result carries `task_count` so a caller can weigh it, and
  `EvolutionResult.trustworthy` is False below `MIN_TASKS_FOR_TRUST`.
- **Fitness is discrete.** With N tasks there are only N+1 possible scores, so
  ties are common and early generations look flat. That is honest, not broken:
  a prompt that fixes no additional task has not improved.
- Improvement is measured against the seed prompt on the *same* tasks, so a
  reported gain is a real gain on those tasks -- and says nothing about tasks
  outside the set.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# Below this many tasks, a fitness number is not worth trusting.
MIN_TASKS_FOR_TRUST = 5

# Mutation phrasings. Each is a real, testable instruction change -- not
# decoration. They are applied to a prompt, and whether they help is decided
# by execution, not by which sounds better.
_MUTATIONS = [
    "Return only code, with no prose before or after it.",
    "Handle empty and None inputs explicitly.",
    "Add type hints to every function signature.",
    "Prefer the standard library; do not import third-party packages.",
    "Think about edge cases before writing the implementation.",
    "Keep the solution under 30 lines.",
    "Validate arguments and raise ValueError on bad input.",
    "Write the simplest correct implementation, not the cleverest.",
]


@dataclass
class Genome:
    """One candidate prompt plus its sampling parameters."""

    genome_id: str
    system_prompt: str
    temperature: float = 0.2
    directives: List[str] = field(default_factory=list)
    fitness: float = -1.0            # -1 = not yet evaluated
    passed: int = 0
    total: int = 0

    def render(self) -> str:
        if not self.directives:
            return self.system_prompt
        rules = "\n".join(f"- {d}" for d in self.directives)
        return f"{self.system_prompt}\n\nRules:\n{rules}"

    def fingerprint(self) -> str:
        """Identity for caching: same prompt AND same sampling."""
        blob = f"{self.render()}|{self.temperature:.3f}"
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    @property
    def evaluated(self) -> bool:
        return self.fitness >= 0.0


@dataclass
class EvolutionTask:
    """A task with a real pass/fail check."""

    task_id: str
    goal: str
    test_code: str                   # asserts against the generated code


@dataclass
class GenerationRecord:
    generation: int
    best_fitness: float
    mean_fitness: float
    best_genome_id: str


@dataclass
class EvolutionResult:
    best: Optional[Genome]
    seed_fitness: float
    history: List[GenerationRecord] = field(default_factory=list)
    task_count: int = 0
    evaluations: int = 0
    cache_hits: int = 0

    @property
    def improvement(self) -> float:
        if self.best is None:
            return 0.0
        return round(self.best.fitness - self.seed_fitness, 4)

    @property
    def trustworthy(self) -> bool:
        """False when the task set is too small for the number to mean much."""
        return self.task_count >= MIN_TASKS_FOR_TRUST

    def describe(self) -> str:
        if self.best is None:
            return "no genome was successfully evaluated"
        caveat = "" if self.trustworthy else (
            f"  [NOT TRUSTWORTHY: only {self.task_count} tasks, "
            f"need {MIN_TASKS_FOR_TRUST}]")
        return (f"best {self.best.fitness:.3f} "
                f"({self.best.passed}/{self.best.total} tasks) "
                f"vs seed {self.seed_fitness:.3f} "
                f"-> {self.improvement:+.3f}{caveat}")


def extract_code(text: str) -> str:
    """Largest fenced block, else the raw reply."""
    blocks = re.findall(r"```(?:python|py)?\s*(.*?)```", text or "", re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()
    return (text or "").strip()


class PromptEvolver:
    """
    Genetic search over prompts, scored by real execution.

    `verifier(code, task) -> bool` is injected. The default runs the code plus
    the task's tests in the sandboxed executor. Nothing here asks a model
    whether a prompt is good.
    """

    def __init__(self, inference: Optional[Any] = None,
                 model: str = "qwen2.5-coder:3b",
                 population_size: int = 4,
                 elitism: int = 1,
                 mutation_rate: float = 0.5,
                 seed: int = 11,
                 verifier: Optional[Callable[[str, EvolutionTask], bool]] = None):
        self._inference = inference
        self.model = model
        self.population_size = max(2, population_size)
        self.elitism = max(1, min(elitism, self.population_size - 1))
        self.mutation_rate = mutation_rate
        self.verifier = verifier
        # Seeded so a run is reproducible: an evolutionary result nobody can
        # reproduce is indistinguishable from the random-fitness version.
        self.rng = random.Random(seed)
        self._fitness_cache: Dict[str, Tuple[float, int, int]] = {}
        self.evaluations = 0
        self.cache_hits = 0

    def _engine(self):
        if self._inference is None:
            from saleha.core.fast_inference import FastInference
            self._inference = FastInference()
        return self._inference

    # -- fitness -------------------------------------------------------
    def _default_verifier(self, code: str, task: EvolutionTask) -> bool:
        from saleha.core.code_executor import CodeExecutor

        if not code.strip():
            return False
        executor = CodeExecutor(timeout=15)
        result = executor.execute(f"{code}\n\n{task.test_code}")
        return bool(getattr(result, "success", False))

    def evaluate(self, genome: Genome,
                 tasks: Sequence[EvolutionTask]) -> Genome:
        """
        Fitness = fraction of tasks whose generated code really passes.

        Cached by genome fingerprint: re-evaluating an unchanged elite across
        generations would be pure waste.
        """
        if not tasks:
            genome.fitness, genome.passed, genome.total = 0.0, 0, 0
            return genome

        key = genome.fingerprint()
        cached = self._fitness_cache.get(key)
        if cached is not None:
            genome.fitness, genome.passed, genome.total = cached
            self.cache_hits += 1
            return genome

        from saleha.core.fast_inference import InferenceRequest

        requests = [
            InferenceRequest(
                prompt=(f"{genome.render()}\n\nTask: {task.goal}\n\n"
                        "Reply with one ```python code block and nothing else."),
                model=self.model,
                options={"temperature": genome.temperature, "num_predict": 700},
                tag=task.task_id)
            for task in tasks
        ]
        # use_cache=False: two genomes differ precisely in their prompt, and a
        # warm cache keyed on the prompt would still be correct -- but a genome
        # re-tested across generations must re-run, or an unlucky first sample
        # would be frozen in. The fingerprint cache above handles reuse.
        results = {r.tag: r for r in self._engine().run_batch(requests, use_cache=False)}
        verify = self.verifier or self._default_verifier

        passed = 0
        for task in tasks:
            result = results.get(task.task_id)
            if result is None or not result.success:
                continue
            try:
                if verify(extract_code(result.content), task):
                    passed += 1
            except Exception:
                continue        # a crashing verifier fails that task only

        self.evaluations += 1
        genome.passed, genome.total = passed, len(tasks)
        genome.fitness = round(passed / len(tasks), 4)
        self._fitness_cache[key] = (genome.fitness, passed, len(tasks))
        return genome

    # -- genetic operators ---------------------------------------------
    def mutate(self, genome: Genome, generation: int, index: int) -> Genome:
        """Add, drop or swap one directive, and jitter temperature."""
        directives = list(genome.directives)
        roll = self.rng.random()
        if directives and roll < 0.3:
            directives.pop(self.rng.randrange(len(directives)))
        elif directives and roll < 0.5:
            directives[self.rng.randrange(len(directives))] = \
                self.rng.choice(_MUTATIONS)
        else:
            candidate = self.rng.choice(_MUTATIONS)
            if candidate not in directives:
                directives.append(candidate)

        temperature = min(0.9, max(0.0, genome.temperature
                                   + self.rng.uniform(-0.15, 0.15)))
        return Genome(
            genome_id=f"g{generation}_{index}",
            system_prompt=genome.system_prompt,
            temperature=round(temperature, 3),
            directives=directives[:5],
        )

    def crossover(self, a: Genome, b: Genome, generation: int,
                  index: int) -> Genome:
        """Union of two parents' directives, midpoint temperature."""
        merged: List[str] = []
        for directive in a.directives + b.directives:
            if directive not in merged:
                merged.append(directive)
        return Genome(
            genome_id=f"g{generation}_{index}",
            system_prompt=a.system_prompt,
            temperature=round((a.temperature + b.temperature) / 2.0, 3),
            directives=merged[:5],
        )

    def _select(self, population: Sequence[Genome]) -> Genome:
        """
        Tournament selection over 2 contenders.

        Ties break on genome_id so the same population always yields the same
        parent -- a reproducible result matters more here than tie diversity.
        """
        a, b = self.rng.sample(list(population), min(2, len(population))) \
            if len(population) >= 2 else (population[0], population[0])
        if a.fitness != b.fitness:
            return a if a.fitness > b.fitness else b
        return a if a.genome_id <= b.genome_id else b

    # -- the loop ------------------------------------------------------
    def evolve(self, seed_prompt: str, tasks: Sequence[EvolutionTask],
               generations: int = 3) -> EvolutionResult:
        """Evolve `seed_prompt` against real task execution."""
        tasks = list(tasks)
        seed = Genome(genome_id="seed", system_prompt=seed_prompt)
        self.evaluate(seed, tasks)
        seed_fitness = seed.fitness

        population: List[Genome] = [seed]
        for i in range(1, self.population_size):
            population.append(self.mutate(seed, 0, i))
        for genome in population[1:]:
            self.evaluate(genome, tasks)

        history: List[GenerationRecord] = []
        best = max(population, key=lambda g: (g.fitness, -len(g.directives)))

        for generation in range(1, max(1, generations) + 1):
            population.sort(key=lambda g: (-g.fitness, len(g.directives)))
            survivors = population[:self.elitism]

            children: List[Genome] = []
            index = 0
            while len(survivors) + len(children) < self.population_size:
                index += 1
                parent_a = self._select(population)
                parent_b = self._select(population)
                child = (self.crossover(parent_a, parent_b, generation, index)
                         if self.rng.random() > self.mutation_rate
                         else self.mutate(parent_a, generation, index))
                children.append(self.evaluate(child, tasks))

            population = survivors + children
            current_best = max(population,
                               key=lambda g: (g.fitness, -len(g.directives)))
            if current_best.fitness > best.fitness:
                best = current_best

            fitnesses = [g.fitness for g in population]
            history.append(GenerationRecord(
                generation=generation,
                best_fitness=max(fitnesses),
                mean_fitness=round(sum(fitnesses) / len(fitnesses), 4),
                best_genome_id=current_best.genome_id,
            ))

        return EvolutionResult(
            best=best,
            seed_fitness=seed_fitness,
            history=history,
            task_count=len(tasks),
            evaluations=self.evaluations,
            cache_hits=self.cache_hits,
        )
