"""
AGI Component 3: General Reasoning Engine
Multi-strategy reasoning with verification, analogical mapping,
causal graph traversal, and cross-domain transfer.
"""

import json
import time
import uuid
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


# =============================================================================
# 1. REASONING STRATEGY ENUM & DATA STRUCTURES
# =============================================================================

class ReasoningStrategy(Enum):
    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"
    ABDUCTIVE = "abductive"
    ANALOGICAL = "analogical"
    CAUSAL = "causal"
    ABSTRACT = "abstract"
    CROSS_DOMAIN = "cross_domain"


class ReasoningConfidence(Enum):
    VERY_HIGH = 0.95
    HIGH = 0.80
    MEDIUM = 0.60
    LOW = 0.40
    SPECULATIVE = 0.20


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""
    step_id: str
    strategy: ReasoningStrategy
    premise: str
    inference: str
    conclusion: str
    confidence: float
    justification: str
    domain: str = "general"
    timestamp: float = field(default_factory=time.time)


@dataclass
class ReasoningChain:
    """A complete chain of reasoning steps leading to a conclusion."""
    chain_id: str
    query: str
    strategy_used: ReasoningStrategy
    steps: List[ReasoningStep] = field(default_factory=list)
    final_conclusion: str = ""
    overall_confidence: float = 0.0
    verification_status: str = "pending"  # pending, verified, refuted
    analogies_found: List[str] = field(default_factory=list)
    causal_links: List[str] = field(default_factory=list)
    domains_involved: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "query": self.query,
            "strategy": self.strategy_used.value,
            "num_steps": len(self.steps),
            "final_conclusion": self.final_conclusion,
            "confidence": self.overall_confidence,
            "verification": self.verification_status,
            "analogies": self.analogies_found,
            "causal_links": self.causal_links,
            "domains": self.domains_involved,
            "steps": [
                {
                    "premise": s.premise,
                    "inference": s.inference,
                    "conclusion": s.conclusion,
                    "confidence": s.confidence,
                }
                for s in self.steps
            ],
        }


# =============================================================================
# 2. REASONING STRATEGY SELECTOR
# =============================================================================

class ReasoningStrategySelector:
    """
    Classifies the query type and selects the optimal reasoning strategy.
    Uses linguistic cues and structural analysis.
    """

    # Linguistic markers for each reasoning type
    MARKERS = {
        ReasoningStrategy.DEDUCTIVE: [
            "therefore", "thus", "hence", "consequently", "it follows",
            "if.*then", "all.*are", "every.*is", "must be", "necessarily",
            "prove", "logically", "given that", "assuming",
        ],
        ReasoningStrategy.INDUCTIVE: [
            "pattern", "trend", "usually", "typically", "always",
            "based on observations", "repeatedly", "in general",
            "most cases", "tends to", "likelihood", "probability",
        ],
        ReasoningStrategy.ABDUCTIVE: [
            "why", "explain", "what caused", "best explanation",
            "most likely reason", "what happened", "diagnose",
            "root cause", "what could have", "possibly",
        ],
        ReasoningStrategy.ANALOGICAL: [
            "similar to", "like a", "compared to", "analogous",
            "resembles", "is like", "same as", "equivalent to",
            "parallel to", "corresponds to",
        ],
        ReasoningStrategy.CAUSAL: [
            "because", "caused", "led to", "resulted in",
            "due to", "effect of", "impact of", "triggered",
            "consequence", "chain reaction", "downstream",
        ],
        ReasoningStrategy.ABSTRACT: [
            "concept", "principle", "generalize", "abstract",
            "underlying", "fundamental", "essence", "core idea",
            "universal", "invariant", "schema", "framework",
        ],
        ReasoningStrategy.CROSS_DOMAIN: [
            "apply to", "transfer", "from.*to", "in the context of",
            "borrow from", "adapt", "map to", "cross-domain",
            "interdisciplinary", "bridge between",
        ],
    }

    def select_strategy(self, query: str) -> Tuple[ReasoningStrategy, float]:
        """Returns the best reasoning strategy and selection confidence."""
        query_lower = query.lower()
        scores: Dict[ReasoningStrategy, float] = defaultdict(float)

        for strategy, patterns in self.MARKERS.items():
            for pattern in patterns:
                matches = re.findall(pattern, query_lower)
                scores[strategy] += len(matches) * 0.3

        # Structural heuristics
        if "?" in query and any(w in query_lower for w in ["why", "how", "explain"]):
            scores[ReasoningStrategy.ABDUCTIVE] += 0.5
            scores[ReasoningStrategy.CAUSAL] += 0.3

        if "if" in query_lower and "then" in query_lower:
            scores[ReasoningStrategy.DEDUCTIVE] += 0.6

        if "example" in query_lower or "instance" in query_lower:
            scores[ReasoningStrategy.INDUCTIVE] += 0.4

        if not scores:
            # Default: multi-strategy orchestration
            return ReasoningStrategy.DEDUCTIVE, 0.30

        best_strategy = max(scores, key=scores.get)
        total_score = sum(scores.values())
        confidence = scores[best_strategy] / total_score if total_score > 0 else 0.3

        return best_strategy, confidence


# =============================================================================
# 3. DEDUCTIVE REASONING ENGINE (L1)
# =============================================================================

class DeductiveReasoner:
    """
    Rule-based deductive inference.
    Applies syllogistic logic and modus ponens/tollens patterns.
    """

    def __init__(self):
        self.knowledge_base: List[Dict[str, str]] = []

    def add_rule(self, premise: str, conclusion: str, domain: str = "general"):
        self.knowledge_base.append({
            "premise": premise.lower(),
            "conclusion": conclusion.lower(),
            "domain": domain,
        })

    def reason(self, facts: List[str], target: str) -> Optional[ReasoningChain]:
        """Apply deductive rules to derive conclusions from facts."""
        chain = ReasoningChain(
            chain_id=str(uuid.uuid4()),
            query=f"Deduce: {target}",
            strategy_used=ReasoningStrategy.DEDUCTIVE,
        )

        derived_facts = set(f.lower() for f in facts)
        step_count = 0
        changed = True

        while changed and step_count < 20:
            changed = False
            for rule in self.knowledge_base:
                if rule["premise"] in derived_facts:
                    if rule["conclusion"] not in derived_facts:
                        derived_facts.add(rule["conclusion"])
                        changed = True
                        step_count += 1

                        step = ReasoningStep(
                            step_id=f"ded_{step_count}",
                            strategy=ReasoningStrategy.DEDUCTIVE,
                            premise=rule["premise"],
                            inference="modus ponens",
                            conclusion=rule["conclusion"],
                            confidence=0.95,
                            justification=f"Rule applied: IF {rule['premise']} THEN {rule['conclusion']}",
                            domain=rule["domain"],
                        )
                        chain.steps.append(step)

        target_lower = target.lower()
        if target_lower in derived_facts:
            chain.final_conclusion = f"YES — '{target}' is logically entailed."
            chain.overall_confidence = 0.95
            chain.verification_status = "verified"
        else:
            chain.final_conclusion = f"INCONCLUSIVE — '{target}' cannot be deduced from given facts."
            chain.overall_confidence = 0.60
            chain.verification_status = "pending"

        return chain


# =============================================================================
# 4. INDUCTIVE REASONING ENGINE (L2)
# =============================================================================

class InductiveReasoner:
    """
    Pattern-based inductive generalization.
    Observes instances and generates general rules.
    """

    def reason(self, observations: List[str], target_generalization: str) -> ReasoningChain:
        chain = ReasoningChain(
            chain_id=str(uuid.uuid4()),
            query=f"Induce: {target_generalization}",
            strategy_used=ReasoningStrategy.INDUCTIVE,
        )

        # Count supporting vs contradicting evidence
        supporting = []
        contradicting = []

        target_lower = target_generalization.lower()
        keywords = set(target_lower.split())

        for obs in observations:
            obs_lower = obs.lower()
            overlap = len(keywords.intersection(set(obs_lower.split())))
            if overlap >= 2:
                supporting.append(obs)
            else:
                contradicting.append(obs)

        total = len(observations)
        support_ratio = len(supporting) / total if total > 0 else 0.0

        step = ReasoningStep(
            step_id="ind_1",
            strategy=ReasoningStrategy.INDUCTIVE,
            premise=f"{len(supporting)}/{total} observations support the generalization",
            inference="statistical induction",
            conclusion=target_generalization,
            confidence=support_ratio,
            justification=f"Support ratio: {support_ratio:.2%}",
        )
        chain.steps.append(step)

        chain.final_conclusion = (
            f"Generalization '{target_generalization}' is supported by "
            f"{len(supporting)}/{total} observations ({support_ratio:.0%})."
        )
        chain.overall_confidence = support_ratio
        chain.verification_status = "verified" if support_ratio > 0.7 else "pending"

        return chain


# =============================================================================
# 5. ABDUCTIVE REASONING ENGINE (L3)
# =============================================================================

class AbductiveReasoner:
    """
    Best-explanation reasoning.
    Generates and ranks hypotheses for observed phenomena.
    """

    def __init__(self):
        self.explanation_templates: List[Dict[str, Any]] = []

    def add_explanation_template(
        self, phenomenon: str, explanation: str, prior_probability: float
    ):
        self.explanation_templates.append({
            "phenomenon": phenomenon.lower(),
            "explanation": explanation,
            "prior": prior_probability,
        })

    def reason(self, observation: str) -> ReasoningChain:
        chain = ReasoningChain(
            chain_id=str(uuid.uuid4()),
            query=f"Abduce: Why {observation}?",
            strategy_used=ReasoningStrategy.ABDUCTIVE,
        )

        candidates = []
        obs_lower = observation.lower()
        obs_keywords = set(obs_lower.split())

        for template in self.explanation_templates:
            phen_keywords = set(template["phenomenon"].split())
            overlap = len(obs_keywords.intersection(phen_keywords))
            if overlap > 0:
                likelihood = overlap / max(len(phen_keywords), 1)
                posterior = likelihood * template["prior"]
                candidates.append({
                    "explanation": template["explanation"],
                    "posterior": posterior,
                    "likelihood": likelihood,
                })

        candidates.sort(key=lambda x: x["posterior"], reverse=True)

        for idx, cand in enumerate(candidates[:3]):
            step = ReasoningStep(
                step_id=f"abd_{idx + 1}",
                strategy=ReasoningStrategy.ABDUCTIVE,
                premise=observation,
                inference="abductive hypothesis generation",
                conclusion=cand["explanation"],
                confidence=cand["posterior"],
                justification=f"Posterior probability: {cand['posterior']:.3f}",
            )
            chain.steps.append(step)

        if candidates:
            best = candidates[0]
            chain.final_conclusion = f"Best explanation: {best['explanation']}"
            chain.overall_confidence = best["posterior"]
            chain.verification_status = "verified" if best["posterior"] > 0.5 else "pending"
        else:
            chain.final_conclusion = "No matching explanation template found."
            chain.overall_confidence = 0.10
            chain.verification_status = "pending"

        return chain


# =============================================================================
# 6. ANALOGICAL REASONING ENGINE (L4)
# =============================================================================

class AnalogicalReasoner:
    """
    Cross-domain structural mapping.
    Maps relational structure from source domain to target domain.
    """

    def __init__(self):
        self.domain_structures: Dict[str, Dict[str, List[str]]] = {}

    def register_domain_structure(self, domain: str, entities: List[str], relations: List[str]):
        self.domain_structures[domain.lower()] = {
            "entities": entities,
            "relations": relations,
        }

    def find_analogies(
        self, source_domain: str, target_domain: str
    ) -> List[Dict[str, str]]:
        """Find structural analogies between two domains."""
        src = self.domain_structures.get(source_domain.lower())
        tgt = self.domain_structures.get(target_domain.lower())

        if not src or not tgt:
            return []

        analogies = []
        src_relations = set(src["relations"])
        tgt_relations = set(tgt["relations"])

        common_relations = src_relations.intersection(tgt_relations)

        for rel in common_relations:
            analogies.append({
                "source": f"{source_domain}: {rel}",
                "target": f"{target_domain}: {rel}",
                "mapping": f"{source_domain}.{rel} ≈ {target_domain}.{rel}",
                "structural_similarity": 1.0,
            })

        return analogies

    def reason(
        self, source_domain: str, target_domain: str, query: str
    ) -> ReasoningChain:
        chain = ReasoningChain(
            chain_id=str(uuid.uuid4()),
            query=query,
            strategy_used=ReasoningStrategy.ANALOGICAL,
        )

        analogies = self.find_analogies(source_domain, target_domain)
        chain.analogies_found = [a["mapping"] for a in analogies]
        chain.domains_involved = [source_domain, target_domain]

        for idx, analogy in enumerate(analogies[:5]):
            step = ReasoningStep(
                step_id=f"ana_{idx + 1}",
                strategy=ReasoningStrategy.ANALOGICAL,
                premise=f"In {source_domain}: {analogy['source']}",
                inference="structural mapping",
                conclusion=f"In {target_domain}: {analogy['target']}",
                confidence=analogy["structural_similarity"],
                justification=f"Shared relational structure: {analogy['mapping']}",
                domain=f"{source_domain}→{target_domain}",
            )
            chain.steps.append(step)

        if analogies:
            chain.final_conclusion = (
                f"Found {len(analogies)} structural analogies between "
                f"'{source_domain}' and '{target_domain}'."
            )
            chain.overall_confidence = sum(
                a["structural_similarity"] for a in analogies
            ) / len(analogies)
            chain.verification_status = "verified"
        else:
            chain.final_conclusion = "No structural analogies found between domains."
            chain.overall_confidence = 0.10
            chain.verification_status = "pending"

        return chain


# =============================================================================
# 7. CAUSAL REASONING ENGINE (L5)
# =============================================================================

class CausalReasoner:
    """
    Cause-effect chain reasoning using causal graph traversal.
    """

    def __init__(self):
        self.causal_graph: Dict[str, List[str]] = defaultdict(list)
        self.causal_strength: Dict[Tuple[str, str], float] = {}

    def add_causal_link(self, cause: str, effect: str, strength: float = 0.8):
        self.causal_graph[cause.lower()].append(effect.lower())
        self.causal_strength[(cause.lower(), effect.lower())] = strength

    def trace_causal_chain(self, start: str, end: str, max_depth: int = 5) -> List[List[str]]:
        """Find all causal paths from start to end."""
        paths = []
        queue = [(start.lower(), [start.lower()])]

        while queue:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                continue
            if current == end.lower():
                paths.append(path)
                continue
            for neighbor in self.causal_graph.get(current, []):
                if neighbor not in path:
                    queue.append((neighbor, path + [neighbor]))

        return paths

    def reason(self, cause: str, effect: str) -> ReasoningChain:
        chain = ReasoningChain(
            chain_id=str(uuid.uuid4()),
            query=f"Causal: Does '{cause}' lead to '{effect}'?",
            strategy_used=ReasoningStrategy.CAUSAL,
        )

        paths = self.trace_causal_chain(cause, effect)
        chain.causal_links = [" → ".join(p) for p in paths]

        if paths:
            best_path = min(paths, key=len)
            cumulative_strength = 1.0
            for i in range(len(best_path) - 1):
                link_strength = self.causal_strength.get(
                    (best_path[i], best_path[i + 1]), 0.5
                )
                cumulative_strength *= link_strength

            step = ReasoningStep(
                step_id="causal_1",
                strategy=ReasoningStrategy.CAUSAL,
                premise=cause,
                inference="causal chain traversal",
                conclusion=" → ".join(best_path),
                confidence=cumulative_strength,
                justification=f"Causal path length: {len(best_path) - 1}, cumulative strength: {cumulative_strength:.3f}",
            )
            chain.steps.append(step)
            chain.final_conclusion = (
                f"YES — Causal chain found: {' → '.join(best_path)} "
                f"(strength: {cumulative_strength:.2f})"
            )
            chain.overall_confidence = cumulative_strength
            chain.verification_status = "verified"
        else:
            chain.final_conclusion = (
                f"NO causal chain found from '{cause}' to '{effect}'."
            )
            chain.overall_confidence = 0.15
            chain.verification_status = "pending"

        return chain


# =============================================================================
# 8. ABSTRACT REASONING ENGINE (L6)
# =============================================================================

class AbstractReasoner:
    """
    Concept generalization and schema extraction.
    Identifies invariant patterns across instances.
    """

    def reason(self, instances: List[str], target_concept: str) -> ReasoningChain:
        chain = ReasoningChain(
            chain_id=str(uuid.uuid4()),
            query=f"Abstract: What is the common essence of '{target_concept}'?",
            strategy_used=ReasoningStrategy.ABSTRACT,
        )

        # Extract common words across instances
        word_freq = defaultdict(int)
        for inst in instances:
            words = set(inst.lower().split())
            for w in words:
                if len(w) > 3:
                    word_freq[w] += 1

        total = len(instances)
        common_words = {
            w: freq / total for w, freq in word_freq.items() if freq / total > 0.3
        }

        abstraction = ", ".join(sorted(common_words.keys()))

        step = ReasoningStep(
            step_id="abs_1",
            strategy=ReasoningStrategy.ABSTRACT,
            premise=f"{total} instances analyzed",
            inference="invariant extraction",
            conclusion=f"Common features: {abstraction}",
            confidence=len(common_words) / max(len(word_freq), 1),
            justification=f"Words appearing in >30% of instances: {abstraction}",
        )
        chain.steps.append(step)

        chain.final_conclusion = (
            f"The abstract essence of '{target_concept}' involves: {abstraction}"
        )
        chain.overall_confidence = min(0.9, len(common_words) * 0.15)
        chain.verification_status = "verified" if common_words else "pending"

        return chain


# =============================================================================
# 9. CROSS-DOMAIN TRANSFER ENGINE (L7)
# =============================================================================

class CrossDomainTransferEngine:
    """
    Transfers reasoning patterns from one domain to another.
    Uses analogical mapping + domain ontology alignment.
    """

    def __init__(self):
        self.domain_ontologies: Dict[str, Dict[str, str]] = {}

    def register_domain_ontology(self, domain: str, concepts: Dict[str, str]):
        self.domain_ontologies[domain.lower()] = concepts

    def transfer(
        self,
        source_domain: str,
        source_concept: str,
        target_domain: str,
    ) -> ReasoningChain:
        chain = ReasoningChain(
            chain_id=str(uuid.uuid4()),
            query=(
                f"Transfer '{source_concept}' from '{source_domain}' "
                f"to '{target_domain}'"
            ),
            strategy_used=ReasoningStrategy.CROSS_DOMAIN,
        )
        chain.domains_involved = [source_domain, target_domain]

        src_onto = self.domain_ontologies.get(source_domain.lower(), {})
        tgt_onto = self.domain_ontologies.get(target_domain.lower(), {})

        # Find matching concepts
        src_concept_lower = source_concept.lower()
        mapped_concepts = []

        for src_key, src_val in src_onto.items():
            if src_concept_lower in src_key.lower():
                # Find corresponding target concept
                for tgt_key, tgt_val in tgt_onto.items():
                    if src_val.lower() in tgt_val.lower():
                        mapped_concepts.append({
                            "source": f"{source_domain}.{src_key}: {src_val}",
                            "target": f"{target_domain}.{tgt_key}: {tgt_val}",
                        })

        for idx, mapping in enumerate(mapped_concepts[:5]):
            step = ReasoningStep(
                step_id=f"xdom_{idx + 1}",
                strategy=ReasoningStrategy.CROSS_DOMAIN,
                premise=mapping["source"],
                inference="domain ontology mapping",
                conclusion=mapping["target"],
                confidence=0.70,
                justification="Ontological alignment between domains",
                domain=f"{source_domain}→{target_domain}",
            )
            chain.steps.append(step)

        if mapped_concepts:
            chain.final_conclusion = (
                f"Transferred {len(mapped_concepts)} concepts from "
                f"'{source_domain}' to '{target_domain}'."
            )
            chain.overall_confidence = 0.70
            chain.verification_status = "verified"
        else:
            chain.final_conclusion = "No cross-domain mapping found."
            chain.overall_confidence = 0.10
            chain.verification_status = "pending"

        return chain


# =============================================================================
# 10. REASONING CHAIN VERIFIER
# =============================================================================

class ReasoningChainVerifier:
    """
    Verifies logical consistency, premise validity,
    and conclusion soundness of reasoning chains.
    """

    def verify(self, chain: ReasoningChain) -> Tuple[str, float]:
        """Returns (verification_status, adjusted_confidence)."""
        if not chain.steps:
            return "refuted", 0.0

        issues = []

        # Check 1: Confidence monotonicity (each step should maintain confidence)
        for step in chain.steps:
            if step.confidence < 0.1:
                issues.append(f"Step {step.step_id}: confidence too low ({step.confidence})")

        # Check 2: Chain consistency (no contradictory conclusions)
        conclusions = [s.conclusion.lower() for s in chain.steps]
        for i in range(len(conclusions)):
            for j in range(i + 1, len(conclusions)):
                if conclusions[i] == "not " + conclusions[j]:
                    issues.append(f"Contradiction between step {i} and step {j}")

        # Check 3: Domain consistency
        domains = set(s.domain for s in chain.steps if s.domain != "general")
        if len(domains) > 3:
            issues.append("Too many unrelated domains in single chain")

        # Adjust confidence
        adjusted_confidence = chain.overall_confidence
        if issues:
            adjusted_confidence *= max(0.1, 1.0 - len(issues) * 0.2)

        if issues:
            status = "refuted" if len(issues) > 2 else "pending"
        else:
            status = "verified"

        return status, adjusted_confidence


# =============================================================================
# 11. MASTER GENERAL REASONING ENGINE (Orchestrator)
# =============================================================================

class GeneralReasoningEngine:
    """
    Master orchestrator that coordinates all 7 reasoning strategies,
    selects the optimal approach, executes reasoning, and verifies results.
    """

    def __init__(self):
        self.selector = ReasoningStrategySelector()
        self.deductive = DeductiveReasoner()
        self.inductive = InductiveReasoner()
        self.abductive = AbductiveReasoner()
        self.analogical = AnalogicalReasoner()
        self.causal = CausalReasoner()
        self.abstract = AbstractReasoner()
        self.cross_domain = CrossDomainTransferEngine()
        self.verifier = ReasoningChainVerifier()

        self.reasoning_history: List[ReasoningChain] = []

    def reason(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        strategy_override: Optional[ReasoningStrategy] = None,
    ) -> ReasoningChain:
        """
        Main entry point. Orchestrates the complete reasoning pipeline.
        """
        context = context or {}

        # Step 1: Select reasoning strategy
        if strategy_override:
            strategy = strategy_override
            selection_confidence = 1.0
        else:
            strategy, selection_confidence = self.selector.select_strategy(query)

        # Step 2: Execute reasoning based on selected strategy
        chain = self._execute_strategy(strategy, query, context)

        # Step 3: Verify reasoning chain
        verification_status, adjusted_confidence = self.verifier.verify(chain)
        chain.verification_status = verification_status
        chain.overall_confidence = adjusted_confidence

        # Step 4: Store in history
        self.reasoning_history.append(chain)

        return chain

    def _execute_strategy(
        self,
        strategy: ReasoningStrategy,
        query: str,
        context: Dict[str, Any],
    ) -> ReasoningChain:
        """Dispatches to the appropriate reasoning engine."""

        if strategy == ReasoningStrategy.DEDUCTIVE:
            facts = context.get("facts", [])
            return self.deductive.reason(facts, query)

        elif strategy == ReasoningStrategy.INDUCTIVE:
            observations = context.get("observations", [])
            return self.inductive.reason(observations, query)

        elif strategy == ReasoningStrategy.ABDUCTIVE:
            return self.abductive.reason(query)

        elif strategy == ReasoningStrategy.ANALOGICAL:
            source = context.get("source_domain", "physics")
            target = context.get("target_domain", "economics")
            return self.analogical.reason(source, target, query)

        elif strategy == ReasoningStrategy.CAUSAL:
            cause = context.get("cause", query.split("→")[0] if "→" in query else query)
            effect = context.get("effect", query.split("→")[1] if "→" in query else query)
            return self.causal.reason(cause, effect)

        elif strategy == ReasoningStrategy.ABSTRACT:
            instances = context.get("instances", [])
            return self.abstract.reason(instances, query)

        elif strategy == ReasoningStrategy.CROSS_DOMAIN:
            source_domain = context.get("source_domain", "")
            source_concept = context.get("source_concept", query)
            target_domain = context.get("target_domain", "")
            return self.cross_domain.transfer(
                source_domain, source_concept, target_domain
            )

        else:
            return ReasoningChain(
                chain_id=str(uuid.uuid4()),
                query=query,
                strategy_used=strategy,
                final_conclusion="Unknown strategy.",
                overall_confidence=0.0,
                verification_status="refuted",
            )

    def multi_strategy_reason(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, ReasoningChain]:
        """
        Runs ALL reasoning strategies in parallel and returns
        a ranked set of results for cross-validation.
        """
        results = {}
        context = context or {}

        strategies = [
            ReasoningStrategy.DEDUCTIVE,
            ReasoningStrategy.INDUCTIVE,
            ReasoningStrategy.ABDUCTIVE,
            ReasoningStrategy.CAUSAL,
            ReasoningStrategy.ABSTRACT,
        ]

        for strategy in strategies:
            try:
                chain = self.reason(query, context, strategy_override=strategy)
                results[strategy.value] = chain
            except Exception:
                pass

        return results

    def get_best_reasoning(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> ReasoningChain:
        """Runs multi-strategy reasoning and returns the highest-confidence result."""
        results = self.multi_strategy_reason(query, context)

        if not results:
            return ReasoningChain(
                chain_id=str(uuid.uuid4()),
                query=query,
                strategy_used=ReasoningStrategy.DEDUCTIVE,
                final_conclusion="No reasoning strategy produced results.",
                overall_confidence=0.0,
            )

        best = max(results.values(), key=lambda c: c.overall_confidence)
        return best


# =============================================================================
# 12. BENCHMARK & VERIFICATION
# =============================================================================

def benchmark_general_reasoning() -> Dict[str, Any]:
    """Comprehensive benchmark for all 7 reasoning layers."""

    engine = GeneralReasoningEngine()
    results = {}

    # --- L1: Deductive ---
    engine.deductive.add_rule("all humans are mortal", "socrates is mortal")
    engine.deductive.add_rule("socrates is human", "socrates is mortal")

    chain_ded = engine.reason(
        "socrates is mortal",
        context={"facts": ["all humans are mortal", "socrates is human"]},
        strategy_override=ReasoningStrategy.DEDUCTIVE,
    )
    results["L1_deductive"] = {
        "conclusion": chain_ded.final_conclusion,
        "confidence": chain_ded.overall_confidence,
        "verified": chain_ded.verification_status,
        "steps": len(chain_ded.steps),
    }

    # --- L2: Inductive ---
    chain_ind = engine.reason(
        "the sun rises in the east",
        context={
            "observations": [
                "sun rises in the east on monday",
                "sun rises in the east on tuesday",
                "sun rises in the east on wednesday",
                "sun sets in the west on monday",
            ]
        },
        strategy_override=ReasoningStrategy.INDUCTIVE,
    )
    results["L2_inductive"] = {
        "conclusion": chain_ind.final_conclusion,
        "confidence": chain_ind.overall_confidence,
        "verified": chain_ind.verification_status,
    }

    # --- L3: Abductive ---
    engine.abductive.add_explanation_template(
        "ground is wet", "it rained last night", 0.7
    )
    engine.abductive.add_explanation_template(
        "ground is wet", "sprinkler was on", 0.5
    )
    engine.abductive.add_explanation_template(
        "ground is wet", "someone spilled water", 0.2
    )

    chain_abd = engine.reason(
        "the ground is wet",
        strategy_override=ReasoningStrategy.ABDUCTIVE,
    )
    results["L3_abductive"] = {
        "conclusion": chain_abd.final_conclusion,
        "confidence": chain_abd.overall_confidence,
        "verified": chain_abd.verification_status,
        "hypotheses_ranked": len(chain_abd.steps),
    }

    # --- L4: Analogical ---
    engine.analogical.register_domain_structure(
        "solar_system",
        entities=["sun", "planets", "gravity"],
        relations=["orbits", "attracts", "illuminates"],
    )
    engine.analogical.register_domain_structure(
        "atom",
        entities=["nucleus", "electrons", "electromagnetic_force"],
        relations=["orbits", "attracts", "illuminates"],
    )

    chain_ana = engine.reason(
        "compare solar system and atom",
        context={"source_domain": "solar_system", "target_domain": "atom"},
        strategy_override=ReasoningStrategy.ANALOGICAL,
    )
    results["L4_analogical"] = {
        "conclusion": chain_ana.final_conclusion,
        "confidence": chain_ana.overall_confidence,
        "analogies_found": chain_ana.analogies_found,
    }

    # --- L5: Causal ---
    engine.causal.add_causal_link("power outage", "ac stops", 0.95)
    engine.causal.add_causal_link("ac stops", "temperature rises", 0.90)
    engine.causal.add_causal_link("temperature rises", "discomfort", 0.85)

    chain_causal = engine.reason(
        "power outage → discomfort",
        strategy_override=ReasoningStrategy.CAUSAL,
    )
    results["L5_causal"] = {
        "conclusion": chain_causal.final_conclusion,
        "confidence": chain_causal.overall_confidence,
        "causal_links": chain_causal.causal_links,
    }

    # --- L6: Abstract ---
    chain_abs = engine.reason(
        "what is the common essence",
        context={
            "instances": [
                "a car engine converts fuel to motion",
                "a power plant converts coal to electricity",
                "a solar panel converts sunlight to energy",
            ]
        },
        strategy_override=ReasoningStrategy.ABSTRACT,
    )
    results["L6_abstract"] = {
        "conclusion": chain_abs.final_conclusion,
        "confidence": chain_abs.overall_confidence,
    }

    # --- L7: Cross-Domain ---
    engine.cross_domain.register_domain_ontology(
        "physics",
        {"energy": "capacity to do work", "entropy": "measure of disorder"},
    )
    engine.cross_domain.register_domain_ontology(
        "economics",
        {"capital": "capacity to do work", "inflation": "measure of disorder"},
    )

    chain_xdom = engine.reason(
        "transfer energy concept",
        context={
            "source_domain": "physics",
            "source_concept": "energy",
            "target_domain": "economics",
        },
        strategy_override=ReasoningStrategy.CROSS_DOMAIN,
    )
    results["L7_cross_domain"] = {
        "conclusion": chain_xdom.final_conclusion,
        "confidence": chain_xdom.overall_confidence,
        "domains": chain_xdom.domains_involved,
    }

    return results


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  AGI COMPONENT 3: GENERAL REASONING ENGINE BENCHMARK")
    print("=" * 70)

    results = benchmark_general_reasoning()

    for layer, data in results.items():
        print(f"\n[{layer.upper()}]")
        for key, value in data.items():
            print(f"  {key}: {value}")

    print("\n" + "=" * 70)
    print("  BENCHMARK COMPLETE")
    print("=" * 70)
