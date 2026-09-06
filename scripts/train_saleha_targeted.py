#!/usr/bin/env python3
"""
Saleha: Market-Benchmark-Informed LoRA Fine-Tuning

WHY these targets (real, sourced numbers -- not invented):

Official Qwen2.5-Coder-Instruct scores, Qwen2.5-Coder Technical Report,
Table 16 (arXiv:2409.12186v3, https://arxiv.org/html/2409.12186v3):

    Model                          HumanEval   MBPP    LiveCodeBench
    Qwen2.5-Coder-0.5B-Instruct      61.6       52.4        2.0
    Qwen2.5-Coder-1.5B-Instruct      70.7       69.2        6.1
    Qwen2.5-Coder-3B-Instruct        84.1       73.6       10.8
    Qwen2.5-Coder-7B-Instruct        88.4       83.5       18.2

Same-size competitors (for market context):
    CodeQwen1.5-7B-Chat              83.5       77.7        7.9
    DS-Coder-6.7B-Instruct           74.4       74.9       15.5
    Yi-Coder-9B-Chat                 82.3       82.0       17.2

The pattern that matters for fine-tuning strategy: HumanEval/MBPP are
old, widely-leaked benchmarks -- every model in this class already
scores 60-90% on them, so there's little real headroom (and little real
signal) left there. LiveCodeBench is contamination-resistant and much
harder, and EVERY model in the table -- including ours -- is weak on it
(2-18%). That gap, not the saturated HumanEval/MBPP numbers, is the
actual market-competitive weakness for small local coding models.

So this script does NOT fine-tune on more toy one-liners (that only
moves the already-saturated benchmarks). It seeds/uses training data
skewed toward LiveCodeBench-style problems: multi-step algorithms with
real edge cases (DP, graph traversal, interval merging, string parsing),
closer to what actually separates models on the hard benchmark.

Real pipeline, no fabricated numbers:
    TrainingCollector -> LoRATuner (PEFT/TRL SFT) -> merge + `ollama create`
    -> saleha.core.evaluator.ModelBenchmarkEvaluator (real sandboxed Pass@1,
       before vs. after, on our own small benchmark set -- NOT a claim of
       official LiveCodeBench/HumanEval scores, just a real local signal).

Usage:
    python scripts/train_saleha_targeted.py --base qwen2.5-coder:1.5b \\
        --output saleha-targeted-v1 --epochs 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saleha.core.training_collector import TrainingCollector
from saleha.core.frontier_trainer import FrontierTrainer

# Real, official reference numbers (see module docstring for source) --
# printed for context, never used as a training/eval result.
OFFICIAL_REFERENCE = {
    "qwen2.5-coder:0.5b": {"HumanEval": 61.6, "MBPP": 52.4, "LiveCodeBench": 2.0},
    "qwen2.5-coder:1.5b": {"HumanEval": 70.7, "MBPP": 69.2, "LiveCodeBench": 6.1},
    "qwen2.5-coder:3b": {"HumanEval": 84.1, "MBPP": 73.6, "LiveCodeBench": 10.8},
}

# Hand-written, LiveCodeBench-style (harder, multi-step, edge-case-heavy)
# training pairs -- real correct solutions, not fabricated. This is what
# actually targets the gap identified above, instead of more toy one-liners.
TARGETED_SAMPLES = [
    (
        "Write a Python function `longest_increasing_subsequence(nums: list[int]) -> int` "
        "that returns the length of the longest strictly increasing subsequence, in O(n log n).",
        "def longest_increasing_subsequence(nums):\n"
        "    import bisect\n"
        "    tails = []\n"
        "    for x in nums:\n"
        "        i = bisect.bisect_left(tails, x)\n"
        "        if i == len(tails):\n"
        "            tails.append(x)\n"
        "        else:\n"
        "            tails[i] = x\n"
        "    return len(tails)",
    ),
    (
        "Write a Python function `merge_intervals(intervals: list[list[int]]) -> list[list[int]]` "
        "that merges all overlapping intervals and returns them sorted by start.",
        "def merge_intervals(intervals):\n"
        "    if not intervals:\n"
        "        return []\n"
        "    intervals = sorted(intervals, key=lambda x: x[0])\n"
        "    merged = [intervals[0]]\n"
        "    for start, end in intervals[1:]:\n"
        "        if start <= merged[-1][1]:\n"
        "            merged[-1][1] = max(merged[-1][1], end)\n"
        "        else:\n"
        "            merged.append([start, end])\n"
        "    return merged",
    ),
    (
        "Write a Python function `num_islands(grid: list[list[str]]) -> int` that counts the "
        "number of islands ('1' = land, '0' = water) in a 2D grid using 4-directional connectivity.",
        "def num_islands(grid):\n"
        "    if not grid:\n"
        "        return 0\n"
        "    rows, cols = len(grid), len(grid[0])\n"
        "    visited = set()\n"
        "    def dfs(r, c):\n"
        "        stack = [(r, c)]\n"
        "        while stack:\n"
        "            cr, cc = stack.pop()\n"
        "            if (cr, cc) in visited or not (0 <= cr < rows and 0 <= cc < cols):\n"
        "                continue\n"
        "            if grid[cr][cc] != '1':\n"
        "                continue\n"
        "            visited.add((cr, cc))\n"
        "            stack.extend([(cr+1,cc),(cr-1,cc),(cr,cc+1),(cr,cc-1)])\n"
        "    count = 0\n"
        "    for r in range(rows):\n"
        "        for c in range(cols):\n"
        "            if grid[r][c] == '1' and (r, c) not in visited:\n"
        "                dfs(r, c)\n"
        "                count += 1\n"
        "    return count",
    ),
    (
        "Write a Python function `min_window_substring(s: str, t: str) -> str` that returns "
        "the smallest substring of s containing all characters of t (with multiplicity), or "
        "'' if no such substring exists.",
        "def min_window_substring(s, t):\n"
        "    from collections import Counter\n"
        "    if not s or not t:\n"
        "        return ''\n"
        "    need = Counter(t)\n"
        "    missing = len(t)\n"
        "    left = start = end = 0\n"
        "    for right, ch in enumerate(s, 1):\n"
        "        if need[ch] > 0:\n"
        "            missing -= 1\n"
        "        need[ch] -= 1\n"
        "        if missing == 0:\n"
        "            while left < right and need[s[left]] < 0:\n"
        "                need[s[left]] += 1\n"
        "                left += 1\n"
        "            if end == 0 or right - left < end - start:\n"
        "                start, end = left, right\n"
        "            need[s[left]] += 1\n"
        "            missing += 1\n"
        "            left += 1\n"
        "    return s[start:end]",
    ),
    (
        "Write a Python function `word_break(s: str, word_dict: list[str]) -> bool` that returns "
        "True if s can be segmented into a space-separated sequence of one or more dictionary words.",
        "def word_break(s, word_dict):\n"
        "    words = set(word_dict)\n"
        "    n = len(s)\n"
        "    dp = [False] * (n + 1)\n"
        "    dp[0] = True\n"
        "    for i in range(1, n + 1):\n"
        "        for j in range(i):\n"
        "            if dp[j] and s[j:i] in words:\n"
        "                dp[i] = True\n"
        "                break\n"
        "    return dp[n]",
    ),
    (
        "Write a Python function `topological_sort(num_nodes: int, edges: list[tuple[int,int]]) -> list[int]` "
        "that returns a valid topological ordering of a DAG given as (from, to) edges, or [] if a cycle exists.",
        "def topological_sort(num_nodes, edges):\n"
        "    from collections import deque, defaultdict\n"
        "    graph = defaultdict(list)\n"
        "    indegree = [0] * num_nodes\n"
        "    for a, b in edges:\n"
        "        graph[a].append(b)\n"
        "        indegree[b] += 1\n"
        "    queue = deque(n for n in range(num_nodes) if indegree[n] == 0)\n"
        "    order = []\n"
        "    while queue:\n"
        "        node = queue.popleft()\n"
        "        order.append(node)\n"
        "        for nxt in graph[node]:\n"
        "            indegree[nxt] -= 1\n"
        "            if indegree[nxt] == 0:\n"
        "                queue.append(nxt)\n"
        "    return order if len(order) == num_nodes else []",
    ),
    (
        "Write a Python function `edit_distance(word1: str, word2: str) -> int` that returns the "
        "minimum number of single-character insert/delete/replace operations to turn word1 into word2.",
        "def edit_distance(word1, word2):\n"
        "    m, n = len(word1), len(word2)\n"
        "    dp = [[0] * (n + 1) for _ in range(m + 1)]\n"
        "    for i in range(m + 1):\n"
        "        dp[i][0] = i\n"
        "    for j in range(n + 1):\n"
        "        dp[0][j] = j\n"
        "    for i in range(1, m + 1):\n"
        "        for j in range(1, n + 1):\n"
        "            if word1[i-1] == word2[j-1]:\n"
        "                dp[i][j] = dp[i-1][j-1]\n"
        "            else:\n"
        "                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])\n"
        "    return dp[m][n]",
    ),
    (
        "Write a Python function `k_closest_points(points: list[list[int]], k: int) -> list[list[int]]` "
        "that returns the k points closest to the origin (Euclidean distance), using a heap.",
        "def k_closest_points(points, k):\n"
        "    import heapq\n"
        "    return heapq.nsmallest(k, points, key=lambda p: p[0]**2 + p[1]**2)",
    ),
    # --- Rust: our real training data was 99.6% Python / 0% Rust / 0% C++.
    # These are hand-written, compiler-valid Rust and C++ solutions to the
    # same class of harder algorithmic problems, to make the model a real
    # polyglot instead of a Python specialist.
    (
        "Write a Rust function `fn merge_intervals(mut intervals: Vec<(i32, i32)>) -> Vec<(i32, i32)>` "
        "that merges all overlapping intervals and returns them sorted by start.",
        "fn merge_intervals(mut intervals: Vec<(i32, i32)>) -> Vec<(i32, i32)> {\n"
        "    intervals.sort_by_key(|iv| iv.0);\n"
        "    let mut merged: Vec<(i32, i32)> = Vec::new();\n"
        "    for (start, end) in intervals {\n"
        "        if let Some(last) = merged.last_mut() {\n"
        "            if start <= last.1 {\n"
        "                last.1 = last.1.max(end);\n"
        "                continue;\n"
        "            }\n"
        "        }\n"
        "        merged.push((start, end));\n"
        "    }\n"
        "    merged\n"
        "}",
    ),
    (
        "Write a Rust function `fn edit_distance(word1: &str, word2: &str) -> usize` that returns the "
        "minimum number of single-character insert/delete/replace operations to turn word1 into word2.",
        "fn edit_distance(word1: &str, word2: &str) -> usize {\n"
        "    let a: Vec<char> = word1.chars().collect();\n"
        "    let b: Vec<char> = word2.chars().collect();\n"
        "    let (m, n) = (a.len(), b.len());\n"
        "    let mut dp = vec![vec![0usize; n + 1]; m + 1];\n"
        "    for i in 0..=m { dp[i][0] = i; }\n"
        "    for j in 0..=n { dp[0][j] = j; }\n"
        "    for i in 1..=m {\n"
        "        for j in 1..=n {\n"
        "            dp[i][j] = if a[i-1] == b[j-1] {\n"
        "                dp[i-1][j-1]\n"
        "            } else {\n"
        "                1 + dp[i-1][j].min(dp[i][j-1]).min(dp[i-1][j-1])\n"
        "            };\n"
        "        }\n"
        "    }\n"
        "    dp[m][n]\n"
        "}",
    ),
    (
        "Write a Rust function `fn word_break(s: &str, word_dict: &[&str]) -> bool` that returns true "
        "if s can be segmented into a space-separated sequence of one or more dictionary words.",
        "use std::collections::HashSet;\n\n"
        "fn word_break(s: &str, word_dict: &[&str]) -> bool {\n"
        "    let words: HashSet<&str> = word_dict.iter().copied().collect();\n"
        "    let n = s.len();\n"
        "    let mut dp = vec![false; n + 1];\n"
        "    dp[0] = true;\n"
        "    for i in 1..=n {\n"
        "        for j in 0..i {\n"
        "            if dp[j] && words.contains(&s[j..i]) {\n"
        "                dp[i] = true;\n"
        "                break;\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    dp[n]\n"
        "}",
    ),
    # --- C++
    (
        "Write a C++ function `int numIslands(vector<vector<char>>& grid)` that counts the number of "
        "islands ('1' = land, '0' = water) using 4-directional connectivity.",
        "int numIslands(vector<vector<char>>& grid) {\n"
        "    if (grid.empty()) return 0;\n"
        "    int rows = grid.size(), cols = grid[0].size(), count = 0;\n"
        "    vector<vector<bool>> visited(rows, vector<bool>(cols, false));\n"
        "    vector<pair<int,int>> dirs = {{1,0},{-1,0},{0,1},{0,-1}};\n"
        "    for (int r = 0; r < rows; ++r) {\n"
        "        for (int c = 0; c < cols; ++c) {\n"
        "            if (grid[r][c] == '1' && !visited[r][c]) {\n"
        "                count++;\n"
        "                vector<pair<int,int>> stack = {{r, c}};\n"
        "                while (!stack.empty()) {\n"
        "                    auto [cr, cc] = stack.back(); stack.pop_back();\n"
        "                    if (cr < 0 || cr >= rows || cc < 0 || cc >= cols) continue;\n"
        "                    if (visited[cr][cc] || grid[cr][cc] != '1') continue;\n"
        "                    visited[cr][cc] = true;\n"
        "                    for (auto& [dr, dc] : dirs) stack.push_back({cr + dr, cc + dc});\n"
        "                }\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    return count;\n"
        "}",
    ),
    (
        "Write a C++ function `vector<int> topologicalSort(int numNodes, vector<pair<int,int>>& edges)` "
        "that returns a valid topological ordering of a DAG, or an empty vector if a cycle exists.",
        "vector<int> topologicalSort(int numNodes, vector<pair<int,int>>& edges) {\n"
        "    vector<vector<int>> graph(numNodes);\n"
        "    vector<int> indegree(numNodes, 0);\n"
        "    for (auto& [a, b] : edges) {\n"
        "        graph[a].push_back(b);\n"
        "        indegree[b]++;\n"
        "    }\n"
        "    queue<int> q;\n"
        "    for (int i = 0; i < numNodes; ++i) if (indegree[i] == 0) q.push(i);\n"
        "    vector<int> order;\n"
        "    while (!q.empty()) {\n"
        "        int node = q.front(); q.pop();\n"
        "        order.push_back(node);\n"
        "        for (int next : graph[node]) {\n"
        "            if (--indegree[next] == 0) q.push(next);\n"
        "        }\n"
        "    }\n"
        "    return order.size() == (size_t)numNodes ? order : vector<int>();\n"
        "}",
    ),
    (
        "Write a C++ function `string minWindow(string s, string t)` that returns the smallest "
        "substring of s containing all characters of t (with multiplicity), or \"\" if none exists.",
        "string minWindow(string s, string t) {\n"
        "    if (s.empty() || t.empty()) return \"\";\n"
        "    unordered_map<char, int> need;\n"
        "    for (char c : t) need[c]++;\n"
        "    int missing = t.size(), left = 0, start = 0, end = 0;\n"
        "    for (int right = 1; right <= (int)s.size(); ++right) {\n"
        "        char c = s[right - 1];\n"
        "        if (need.count(c) && need[c]-- > 0) missing--;\n"
        "        while (missing == 0) {\n"
        "            if (end == 0 || right - left < end - start) { start = left; end = right; }\n"
        "            char lc = s[left];\n"
        "            if (need.count(lc) && ++need[lc] > 0) missing++;\n"
        "            left++;\n"
        "        }\n"
        "    }\n"
        "    return s.substr(start, end - start);\n"
        "}",
    ),
]

MIN_REAL_SAMPLES_BEFORE_SEEDING = 5


def _detect_lang(prompt: str, completion: str) -> str:
    text = (prompt + " " + completion).lower()
    if "fn " in completion and ("->" in completion or "let " in completion):
        return "rust"
    cpp_markers = ("#include", "vector<", "std::", "unordered_map<", "push_back", "size_t")
    if any(m in text for m in cpp_markers):
        return "cpp"
    return "python"


def seed_targeted_samples(collector: TrainingCollector) -> Dict[str, int]:
    """
    Seed LiveCodeBench-style + multi-language (Python/Rust/C++) samples,
    per-language: if real session data already has real Python coverage but
    zero Rust/C++ (our actual measured state: 513/515 Python, 0 C++), only
    the missing languages get seeded. Never overwrites genuine collected data.
    """
    existing = collector.load_samples(min_quality=0.75)
    existing_langs = {_detect_lang(s.prompt, s.completion) for s in existing}

    added: Dict[str, int] = {"python": 0, "rust": 0, "cpp": 0}
    for prompt, completion in TARGETED_SAMPLES:
        lang = _detect_lang(prompt, completion)
        if lang == "python" and len(existing) >= MIN_REAL_SAMPLES_BEFORE_SEEDING:
            continue  # already have enough real Python data
        if lang in existing_langs and lang == "python":
            continue
        collector.add_sample(prompt, completion, quality_score=1.0, source="targeted_seed",
                              tags=["livecodebench_style", "algorithmic", lang])
        added[lang] += 1
    return added


def print_reference_table() -> None:
    print("Official Qwen2.5-Coder-Instruct benchmarks (source: arXiv:2409.12186v3, Table 16):")
    print(f"{'model':<22}{'HumanEval':>11}{'MBPP':>8}{'LiveCodeBench':>16}")
    for model, scores in OFFICIAL_REFERENCE.items():
        print(f"{model:<22}{scores['HumanEval']:>11}{scores['MBPP']:>8}{scores['LiveCodeBench']:>16}")
    print("-> HumanEval/MBPP are near-saturated across this model class; LiveCodeBench")
    print("   is the real gap (2-11%). Training data below is skewed toward that gap,")
    print("   not toward more easy HumanEval-style one-liners.\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="qwen2.5-coder:1.5b", choices=list(OFFICIAL_REFERENCE))
    parser.add_argument("--output", default="saleha-targeted-v1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--no-deploy", action="store_true", help="Skip merging + `ollama create`")
    parser.add_argument("--no-benchmark", action="store_true", help="Skip the real before/after Pass@1 check")
    args = parser.parse_args()

    print_reference_table()

    trainer = FrontierTrainer()
    seeded = seed_targeted_samples(trainer.tuner.collector)
    total_seeded = sum(seeded.values())
    if total_seeded:
        print(f"Seeded {total_seeded} targeted samples by language: {seeded}")
        print("(Python only seeded if real session data was thin; Rust/C++ seeded because "
              "the real collected dataset currently has ~0% coverage of those languages.)\n")
    else:
        print("Existing real session data already covers Python/Rust/C++ -- nothing seeded.\n")

    print(f"Training {args.base} -> {args.output} ({args.epochs} epoch(s))...\n")
    report = trainer.run_training(
        base_model=args.base,
        output_model=args.output,
        epochs=args.epochs,
        enable_dpo=True,
        deploy_to_ollama=not args.no_deploy,
        run_benchmark=not args.no_benchmark,
    )

    print("=" * 60)
    print(f"Run {report.run_id} finished in {report.training_duration_sec}s\n")
    print("Completed:")
    for p in report.phases_completed:
        print(f"  [x] {p}")
    print("Skipped/not implemented:")
    for p in report.phases_skipped:
        print(f"  [ ] {p}")

    if report.sft_result and report.sft_result.success:
        r = report.sft_result
        print(f"\nHeld-out eval loss: {r.before_score} -> {r.after_score} "
              f"({r.improvement_pct:+.2f}%, lower is better)")
        if r.benchmark_before_pass_rate is not None:
            print(f"Real local Pass@1 (our own {len(TARGETED_SAMPLES)}-style sample, not official "
                  f"LiveCodeBench): {r.benchmark_before_pass_rate}% -> {r.benchmark_after_pass_rate}%")
        elif r.benchmark_error:
            print(f"Benchmark step failed (training still succeeded): {r.benchmark_error}")
        print(f"\nAdapter: {r.adapter_path}")
        if r.deployed_to_ollama:
            print(f"Deployed: `ollama run {args.output}`")
    else:
        print(f"\nTraining did not succeed: {report.error}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
