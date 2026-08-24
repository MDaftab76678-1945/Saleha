"""
Saleha Harness: Multi-Domain Benchmark Dataset Matrix

Standardized benchmark specifications modeled after DeepSeek Harness, HumanEval+, MBPP+,
SWE-Bench, and Math/Reasoning suites.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class BenchmarkTaskSpec:
    id: str
    benchmark: str  # 'humaneval_plus', 'mbpp_plus', 'math_reasoning', 'swe_repo', 'tool_use'
    title: str
    prompt: str
    test_code: str
    difficulty: str = "medium"
    timeout_sec: int = 15


HUMANEVAL_PLUS_DATASET: List[BenchmarkTaskSpec] = [
    BenchmarkTaskSpec(
        id="HE-001-LONGEST-SUBSTR",
        benchmark="humaneval_plus",
        title="Longest Substring Without Repeating Characters",
        prompt="Write a Python function `length_of_longest_substring(s: str) -> int` that finds the length of the longest substring without repeating characters.",
        test_code=(
            "assert length_of_longest_substring('abcabcbb') == 3\n"
            "assert length_of_longest_substring('bbbbb') == 1\n"
            "assert length_of_longest_substring('pwwkew') == 3\n"
            "assert length_of_longest_substring('') == 0\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="medium"
    ),
    BenchmarkTaskSpec(
        id="HE-002-VALID-PARENTHESES",
        benchmark="humaneval_plus",
        title="Valid Parentheses Validation",
        prompt="Write a Python function `is_valid_parentheses(s: str) -> bool` that determines if an input string of brackets '()[]{}' is valid.",
        test_code=(
            "assert is_valid_parentheses('()') == True\n"
            "assert is_valid_parentheses('()[]{}') == True\n"
            "assert is_valid_parentheses('(]') == False\n"
            "assert is_valid_parentheses('([)]') == False\n"
            "assert is_valid_parentheses('{[]}') == True\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="easy"
    ),
    BenchmarkTaskSpec(
        id="HE-003-BINARY-SEARCH",
        benchmark="humaneval_plus",
        title="Binary Search Algorithm",
        prompt="Write a Python function `binary_search(nums: list, target: int) -> int` that returns target index or -1 if not found in sorted array.",
        test_code=(
            "assert binary_search([-1,0,3,5,9,12], 9) == 4\n"
            "assert binary_search([-1,0,3,5,9,12], 2) == -1\n"
            "assert binary_search([5], 5) == 0\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="easy"
    )
]


MBPP_PLUS_DATASET: List[BenchmarkTaskSpec] = [
    BenchmarkTaskSpec(
        id="MBPP-001-WORD-FREQ",
        benchmark="mbpp_plus",
        title="Word Frequency Counter",
        prompt="Write a Python function `word_frequency(text: str) -> dict` that counts word occurrences in a text string case-insensitively.",
        test_code=(
            "res = word_frequency('Hello world hello')\n"
            "assert res.get('hello') == 2\n"
            "assert res.get('world') == 1\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="easy"
    ),
    BenchmarkTaskSpec(
        id="MBPP-002-ANAGRAM-CHECK",
        benchmark="mbpp_plus",
        title="Valid Anagram Checker",
        prompt="Write a Python function `is_anagram(s: str, t: str) -> bool` that returns True if t is an anagram of s.",
        test_code=(
            "assert is_anagram('anagram', 'nagaram') == True\n"
            "assert is_anagram('rat', 'car') == False\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="easy"
    )
]


MATH_REASONING_DATASET: List[BenchmarkTaskSpec] = [
    BenchmarkTaskSpec(
        id="MATH-001-PRIME-FACTORS",
        benchmark="math_reasoning",
        title="Prime Factorization Decomposition",
        prompt="Write a Python function `prime_factors(n: int) -> list` that returns all prime factors of n in ascending order.",
        test_code=(
            "assert prime_factors(24) == [2, 2, 2, 3]\n"
            "assert prime_factors(49) == [7, 7]\n"
            "assert prime_factors(13) == [13]\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="medium"
    ),
    BenchmarkTaskSpec(
        id="MATH-002-COIN-CHANGE",
        benchmark="math_reasoning",
        title="Dynamic Programming Coin Change",
        prompt="Write a Python function `coin_change(coins: list, amount: int) -> int` that returns minimum coins needed to make amount, or -1 if impossible.",
        test_code=(
            "assert coin_change([1, 2, 5], 11) == 3\n"
            "assert coin_change([2], 3) == -1\n"
            "assert coin_change([1], 0) == 0\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="hard"
    )
]


SWE_REPO_DATASET: List[BenchmarkTaskSpec] = [
    BenchmarkTaskSpec(
        id="SWE-001-CONFIG-MERGE",
        benchmark="swe_repo",
        title="Nested Dictionary Deep Merge Bug",
        prompt="Write a Python function `deep_merge_config(base: dict, override: dict) -> dict` that recursively merges two nested config dictionaries without mutating base.",
        test_code=(
            "base = {'db': {'host': 'localhost', 'port': 5432}, 'debug': False}\n"
            "override = {'db': {'port': 5433}, 'debug': True}\n"
            "merged = deep_merge_config(base, override)\n"
            "assert merged['db']['host'] == 'localhost'\n"
            "assert merged['db']['port'] == 5433\n"
            "assert merged['debug'] == True\n"
            "assert base['db']['port'] == 5432\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="medium"
    )
]


TOOL_USE_DATASET: List[BenchmarkTaskSpec] = [
    BenchmarkTaskSpec(
        id="TOOL-001-MCP-PARSE",
        benchmark="tool_use",
        title="JSON-RPC Tool Call Request Parser",
        prompt="Write a Python function `parse_jsonrpc_tool_call(payload: dict) -> tuple` that returns (tool_name, arguments_dict) from a standard MCP 'tools/call' request.",
        test_code=(
            "req = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'sast_scan', 'arguments': {'path': '.'}}}\n"
            "name, args = parse_jsonrpc_tool_call(req)\n"
            "assert name == 'sast_scan'\n"
            "assert args == {'path': '.'}\n"
            "print('HARNESS_TEST_PASSED')"
        ),
        difficulty="easy"
    )
]


class BenchmarkCatalog:
    """Registry providing dataset lookups and filtered task batches."""

    CATALOGS = {
        "humaneval_plus": HUMANEVAL_PLUS_DATASET,
        "mbpp_plus": MBPP_PLUS_DATASET,
        "math_reasoning": MATH_REASONING_DATASET,
        "swe_repo": SWE_REPO_DATASET,
        "tool_use": TOOL_USE_DATASET,
    }

    @classmethod
    def get_benchmarks(cls, name: str = "all") -> List[BenchmarkTaskSpec]:
        clean_name = name.lower().strip()
        if clean_name == "all":
            all_tasks = []
            for tasks in cls.CATALOGS.values():
                all_tasks.extend(tasks)
            return all_tasks
        return cls.CATALOGS.get(clean_name, [])

    @classmethod
    def list_available_benchmarks(cls) -> Dict[str, int]:
        return {k: len(v) for k, v in cls.CATALOGS.items()}

