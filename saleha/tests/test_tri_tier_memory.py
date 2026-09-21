"""Unit tests for the Tri-Tier Persistent Memory System."""

import json
import os
import tempfile
import unittest

from saleha.core.tri_tier_memory import (
    EpisodicMemory,
    SemanticKnowledgeGraph,
    TriTierMemoryEngine,
    WorkingMemory,
)


class WorkingMemoryTests(unittest.TestCase):
    def test_ring_buffer_evicts_oldest_beyond_max_turns(self) -> None:
        wm = WorkingMemory(max_turns=2)
        wm.append("p1", "r1")
        wm.append("p2", "r2")
        wm.append("p3", "r3")
        turns = wm.get_recent_context(limit=5)
        self.assertEqual([t.user_prompt for t in turns], ["p2", "p3"])

    def test_clear_empties_the_ring(self) -> None:
        wm = WorkingMemory()
        wm.append("p", "r")
        wm.clear()
        self.assertEqual(wm.get_recent_context(), [])


class EpisodicMemoryTests(unittest.TestCase):
    def test_record_persists_and_reloads(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "episodic.jsonl")
            mem = EpisodicMemory(path)
            mem.record(agent_id=1, summary="task one", status="done")
            reloaded = EpisodicMemory(path)
            self.assertEqual(len(reloaded.records), 1)
            self.assertEqual(reloaded.records[0].task_summary, "task one")

    def test_record_ids_continue_correctly_across_a_reload(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "episodic.jsonl")
            mem = EpisodicMemory(path)
            mem.record(agent_id=1, summary="a", status="done")
            mem.record(agent_id=1, summary="b", status="done")
            reloaded = EpisodicMemory(path)
            r3 = reloaded.record(agent_id=1, summary="c", status="done")
            self.assertEqual(r3.record_id, 3)

    def test_one_corrupted_line_does_not_lose_later_valid_records(self) -> None:
        """Real bug found auditing this module: _load()'s try/except wrapped
        the entire read loop, so one corrupted line (plausible after a
        crash mid-write) silently discarded every record after it, not
        just that one line. Confirmed by direct probe before fixing: a
        3-line file with a bad middle line loaded only the first record."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "episodic.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "record_id": 1, "agent_id": 1,
                    "task_summary": "ok1", "status": "done",
                }) + "\n")
                f.write("{corrupted json line\n")
                f.write(json.dumps({
                    "record_id": 3, "agent_id": 1,
                    "task_summary": "ok3", "status": "done",
                }) + "\n")
            mem = EpisodicMemory(path)
            self.assertEqual(len(mem.records), 2)
            self.assertEqual(
                {r.task_summary for r in mem.records}, {"ok1", "ok3"})

    def test_search_matches_summary_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            mem = EpisodicMemory(os.path.join(d, "episodic.jsonl"))
            mem.record(agent_id=1, summary="fix the bug", status="done", tags=["bugfix"])
            mem.record(agent_id=1, summary="unrelated task", status="done")
            results = mem.search("bugfix")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].task_summary, "fix the bug")


class SemanticKnowledgeGraphTests(unittest.TestCase):
    def test_insert_and_query_subject(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            g = SemanticKnowledgeGraph(os.path.join(d, "graph.json"))
            g.insert_fact("saleha", "uses", "ollama")
            facts = g.query_subject("saleha")
            self.assertEqual(len(facts), 1)
            self.assertEqual(facts[0].object, "ollama")

    def test_insert_fact_updates_confidence_on_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            g = SemanticKnowledgeGraph(os.path.join(d, "graph.json"))
            g.insert_fact("a", "is", "b", confidence=0.5)
            g.insert_fact("a", "is", "b", confidence=0.9)
            self.assertEqual(len(g.triples), 1)
            self.assertEqual(g.triples[0].confidence, 0.9)

    def test_persists_and_reloads(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "graph.json")
            g = SemanticKnowledgeGraph(path)
            g.insert_fact("a", "is", "b")
            reloaded = SemanticKnowledgeGraph(path)
            self.assertEqual(len(reloaded.triples), 1)

    def test_one_malformed_triple_does_not_lose_the_whole_graph(self) -> None:
        """Same class of bug as EpisodicMemory above: converting every dict
        in one list comprehension meant a single malformed triple (missing
        a required field) raised inside the comprehension and lost the
        whole graph, not just that entry. Confirmed by direct probe: 3
        triples, one missing "object", loaded 0 before this fix."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "graph.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([
                    {"subject": "a", "predicate": "is", "object": "good"},
                    {"subject": "b", "predicate": "is"},
                    {"subject": "c", "predicate": "is", "object": "fine"},
                ], f)
            g = SemanticKnowledgeGraph(path)
            self.assertEqual(len(g.triples), 2)
            self.assertEqual(
                {t.subject for t in g.triples}, {"a", "c"})

    def test_non_list_graph_file_loads_empty_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "graph.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"not": "a list"}, f)
            g = SemanticKnowledgeGraph(path)
            self.assertEqual(g.triples, [])


class TriTierMemoryEngineTests(unittest.TestCase):
    def test_recall_context_combines_all_three_tiers(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            engine = TriTierMemoryEngine(base_dir=d)
            engine.working.append("hello", "world")
            engine.episodic.record(agent_id=1, summary="hello task", status="done")
            engine.semantic.insert_fact("hello", "relates_to", "world")

            result = engine.recall_context("hello")
            self.assertEqual(len(result["working_memory"]), 1)
            self.assertEqual(len(result["episodic_history"]), 1)
            self.assertEqual(len(result["semantic_facts"]), 1)


if __name__ == "__main__":
    unittest.main()
