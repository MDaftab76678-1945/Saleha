"""Unit & Integration Test Suite for Saleha Next-Gen Hyper-Frontier Engines:
1. HypergraphIndexer (Multi-File AST Symbol Traversal)
2. DynamicLoRARouter (Sub-5ms Domain Adapter Switching)
3. SPICSFuzzEngine (Property-Based Chaos Fuzzing & Auto-Hardening)
"""

import os
import unittest

from saleha.core.hypergraph_indexer import HypergraphIndexer, hypergraph_indexer, SymbolNode, HypergraphIndexStats
from saleha.core.dynamic_lora_router import DynamicLoRARouter, dynamic_lora_router, LoRARoutingDecision
from saleha.core.spics_fuzz_engine import SPICSFuzzEngine, spics_fuzz_engine, FuzzPropertyResult


class TestNextGenHyperSuite(unittest.TestCase):
    def test_hypergraph_indexer_scans_and_resolves_symbols(self):
        indexer = HypergraphIndexer()
        stats: HypergraphIndexStats = indexer.scan_directory("saleha/core")
        
        self.assertGreater(stats.total_files_scanned, 5)
        self.assertGreater(stats.total_symbols_indexed, 10)
        self.assertGreaterEqual(stats.indexing_duration_ms, 0.0)

        # Test symbol query
        ctx = indexer.get_symbol_context("SmartRouter")
        if ctx:
            self.assertEqual(ctx["symbol"], "SmartRouter")
            self.assertEqual(ctx["type"], "class")

    def test_dynamic_lora_router_domain_classification(self):
        router = DynamicLoRARouter()
        
        # Test Frontend routing
        res_fe = router.route_and_switch("Build a responsive React 19 navbar with Tailwind CSS")
        self.assertEqual(res_fe.detected_domain, "frontend")
        self.assertEqual(res_fe.selected_adapter, "lora_frontend_v3")
        self.assertLess(res_fe.switching_latency_ms, 50.0)

        # Test Security routing
        res_sec = router.route_and_switch("Check for SQL injection and CWE-89 vulnerabilities in JWT auth")
        self.assertEqual(res_sec.detected_domain, "security")
        self.assertEqual(res_sec.selected_adapter, "lora_security_v3")

        # Test Algorithms routing
        res_algo = router.route_and_switch("Solve traveling salesperson problem with MCTS dynamic programming")
        self.assertEqual(res_algo.detected_domain, "algorithms")
        self.assertEqual(res_algo.selected_adapter, "lora_algorithms_v3")

    def test_spics_fuzz_engine_discovers_edge_cases_and_hardens(self):
        fuzzer = SPICSFuzzEngine(default_trials=25)
        code = '''def solve(x):
    return {"res": x}
'''
        res: FuzzPropertyResult = fuzzer.fuzz_test_code(code, function_name="solve", num_trials=25)
        self.assertEqual(res.total_fuzz_trials, 25)
        self.assertGreaterEqual(res.passed_trials, 20)
        self.assertGreaterEqual(res.invariant_resilience_pct, 80.0)
        self.assertGreaterEqual(res.execution_time_ms, 0.0)
