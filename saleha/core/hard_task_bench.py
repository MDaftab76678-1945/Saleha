"""
Saleha Core: harder task benchmark with a train / held-out split.

`real_task_bench` is too easy to measure improvement on: qwen2.5-coder:3b
already scores 11/12 there, so a model that got better could not show it.
These tasks are chosen to sit in the 3B model's failure range (parsing,
dynamic programming, graphs, stateful classes, edge-heavy string work).

Same rules as real_task_bench, plus one:

- every test must FAIL on a deliberately wrong implementation
  (`verify_tests_can_fail`), and
- every test must PASS on a hand-written reference solution
  (`saleha/tests/test_hard_task_bench.py`) -- a test that no correct code
  can satisfy measures nothing either.

`split` keeps the two halves apart: anything that learns (self-play, LoRA)
may only see TRAIN tasks; improvement is claimed only on HELDOUT tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from saleha.core.real_task_bench import Task

TRAIN = "train"
HELDOUT = "heldout"


@dataclass
class HardTask(Task):
    split: str = TRAIN


def _t(task_id: str, split: str, prompt: str, test: str, wrong: str) -> HardTask:
    return HardTask(task_id, prompt + " Return only the code.", test, wrong, split)


HARD_TASKS: List[HardTask] = [
    _t("edit_distance", TRAIN,
       "Write a Python function `edit_distance(a, b)` returning the Levenshtein distance "
       "(insert, delete, substitute each cost 1) between strings a and b.",
       "assert edit_distance('kitten', 'sitting') == 3\n"
       "assert edit_distance('', 'abc') == 3\n"
       "assert edit_distance('abc', 'abc') == 0\n"
       "assert edit_distance('intention', 'execution') == 5\n"
       "assert edit_distance('ab', 'ba') == 2\n",
       "def edit_distance(a, b):\n    return abs(len(a) - len(b))\n"),

    _t("eval_expr", HELDOUT,
       "Write a Python function `eval_expr(s)` that evaluates an integer arithmetic expression "
       "string with +, -, *, /, parentheses, spaces and unary minus. `/` is integer division "
       "truncating toward zero. Do not use eval or exec.",
       "assert eval_expr('1 + 2 * 3') == 7\n"
       "assert eval_expr('(1 + 2) * 3') == 9\n"
       "assert eval_expr('7 / 2') == 3\n"
       "assert eval_expr('-7 / 2') == -3\n"
       "assert eval_expr('2 * (3 + -4)') == -2\n"
       "assert eval_expr(' 10 - 2 - 3 ') == 5\n"
       "assert eval_expr('-(2 + 3) * 2') == -10\n",
       "def eval_expr(s):\n    total = 0\n    for part in s.replace(' ', '').split('+'):\n"
       "        total += int(part) if part.lstrip('-').isdigit() else 0\n    return total\n"),

    _t("decode_string", TRAIN,
       "Write a Python function `decode_string(s)` that decodes strings like '3[a2[c]]' "
       "into 'accaccacc': k[inner] repeats inner k times, brackets may nest, k may have "
       "several digits.",
       "assert decode_string('3[a]2[bc]') == 'aaabcbc'\n"
       "assert decode_string('3[a2[c]]') == 'accaccacc'\n"
       "assert decode_string('2[abc]3[cd]ef') == 'abcabccdcdcdef'\n"
       "assert decode_string('10[a]') == 'a' * 10\n"
       "assert decode_string('abc') == 'abc'\n",
       "def decode_string(s):\n    out = ''\n    for ch in s:\n        if ch.isalpha():\n"
       "            out += ch\n    return out\n"),

    _t("min_window", HELDOUT,
       "Write a Python function `min_window(s, t)` returning the shortest substring of s "
       "containing every character of t including duplicates; the leftmost one on ties; "
       "'' if none exists.",
       "assert min_window('ADOBECODEBANC', 'ABC') == 'BANC'\n"
       "assert min_window('a', 'a') == 'a'\n"
       "assert min_window('a', 'aa') == ''\n"
       "assert min_window('aa', 'aa') == 'aa'\n"
       "assert min_window('abcabdebac', 'cda') == 'cabd'\n",
       "def min_window(s, t):\n    return s if all(c in s for c in t) else ''\n"),

    _t("regex_match", TRAIN,
       "Write a Python function `regex_match(s, p)` that returns True if pattern p matches "
       "the whole string s, where '.' matches any single character and '*' matches zero or "
       "more of the preceding element. Do not use the re module.",
       "assert regex_match('aa', 'a') is False\n"
       "assert regex_match('aa', 'a*') is True\n"
       "assert regex_match('ab', '.*') is True\n"
       "assert regex_match('aab', 'c*a*b') is True\n"
       "assert regex_match('mississippi', 'mis*is*p*.') is False\n"
       "assert regex_match('', 'a*b*') is True\n",
       "def regex_match(s, p):\n    return len(s) == len(p)\n"),

    _t("wildcard_match", HELDOUT,
       "Write a Python function `wildcard_match(s, p)` returning True if p matches all of s, "
       "where '?' matches one character and '*' matches any sequence (including empty).",
       "assert wildcard_match('aa', 'a') is False\n"
       "assert wildcard_match('aa', '*') is True\n"
       "assert wildcard_match('cb', '?a') is False\n"
       "assert wildcard_match('adceb', '*a*b') is True\n"
       "assert wildcard_match('acdcb', 'a*c?b') is False\n"
       "assert wildcard_match('', '***') is True\n",
       "def wildcard_match(s, p):\n    return p == '*' or s == p\n"),

    _t("topo_sort", TRAIN,
       "Write a Python function `topo_sort(n, edges)` for nodes 0..n-1 and directed edges "
       "(u, v) meaning u before v. Return a list with a valid topological order, or None if "
       "the graph has a cycle.",
       "def _valid(n, edges, order):\n"
       "    if order is None or sorted(order) != list(range(n)):\n        return False\n"
       "    pos = {v: i for i, v in enumerate(order)}\n"
       "    return all(pos[u] < pos[v] for u, v in edges)\n"
       "assert _valid(4, [(0, 1), (1, 2), (0, 3), (3, 2)], topo_sort(4, [(0, 1), (1, 2), (0, 3), (3, 2)]))\n"
       "assert _valid(3, [], topo_sort(3, []))\n"
       "assert topo_sort(3, [(0, 1), (1, 2), (2, 0)]) is None\n"
       "assert topo_sort(2, [(1, 1)]) is None\n",
       "def topo_sort(n, edges):\n    return list(range(n))\n"),

    _t("dijkstra", HELDOUT,
       "Write a Python function `dijkstra(n, edges, src)` for nodes 0..n-1 and weighted "
       "directed edges (u, v, w) with w >= 0. Return a list of shortest distances from src; "
       "unreachable nodes get float('inf').",
       "INF = float('inf')\n"
       "assert dijkstra(4, [(0, 1, 4), (0, 2, 1), (2, 1, 2), (1, 3, 1)], 0) == [0, 3, 1, 4]\n"
       "assert dijkstra(3, [(0, 1, 5)], 0) == [0, 5, INF]\n"
       "assert dijkstra(2, [(0, 1, 0)], 1) == [INF, 0]\n"
       "assert dijkstra(3, [(0, 1, 1), (1, 2, 1), (0, 2, 5)], 0) == [0, 1, 2]\n",
       "def dijkstra(n, edges, src):\n    d = [float('inf')] * n\n    d[src] = 0\n"
       "    for u, v, w in edges:\n        if u == src:\n            d[v] = w\n    return d\n"),

    _t("lis_length", TRAIN,
       "Write a Python function `lis_length(nums)` returning the length of the longest "
       "strictly increasing subsequence of the list nums.",
       "assert lis_length([10, 9, 2, 5, 3, 7, 101, 18]) == 4\n"
       "assert lis_length([0, 1, 0, 3, 2, 3]) == 4\n"
       "assert lis_length([7, 7, 7]) == 1\n"
       "assert lis_length([]) == 0\n"
       "assert lis_length([4, 10, 4, 3, 8, 9]) == 3\n",
       "def lis_length(nums):\n    return len(set(nums))\n"),

    _t("word_break", HELDOUT,
       "Write a Python function `word_break(s, words)` returning True if s can be split into "
       "a sequence of one or more words from the list words (words may be reused).",
       "assert word_break('leetcode', ['leet', 'code']) is True\n"
       "assert word_break('applepenapple', ['apple', 'pen']) is True\n"
       "assert word_break('catsandog', ['cats', 'dog', 'sand', 'and', 'cat']) is False\n"
       "assert word_break('aaaaaaa', ['aaaa', 'aaa']) is True\n"
       "assert word_break('ab', ['a']) is False\n",
       "def word_break(s, words):\n    return any(w in s for w in words)\n"),

    _t("median_finder", TRAIN,
       "Write a Python class `MedianFinder` with `add(num)` and `median()` returning the "
       "median of all numbers added so far as a float (mean of the two middle values when "
       "the count is even).",
       "m = MedianFinder()\nm.add(1)\nassert m.median() == 1.0\n"
       "m.add(2)\nassert m.median() == 1.5\n"
       "m.add(3)\nassert m.median() == 2.0\n"
       "m.add(-10)\nm.add(100)\nassert m.median() == 2.0\n"
       "m.add(4)\nassert m.median() == 2.5\n",
       "class MedianFinder:\n    def __init__(self):\n        self.v = []\n"
       "    def add(self, n):\n        self.v.append(n)\n"
       "    def median(self):\n        return float(self.v[len(self.v) // 2])\n"),

    _t("sliding_max", HELDOUT,
       "Write a Python function `sliding_max(nums, k)` returning the list of maximums of "
       "every contiguous window of size k in nums.",
       "assert sliding_max([1, 3, -1, -3, 5, 3, 6, 7], 3) == [3, 3, 5, 5, 6, 7]\n"
       "assert sliding_max([1], 1) == [1]\n"
       "assert sliding_max([9, 8, 7, 6], 2) == [9, 8, 7]\n"
       "assert sliding_max([1, -1], 1) == [1, -1]\n",
       "def sliding_max(nums, k):\n    return [max(nums)] * (len(nums) - k + 1)\n"),

    _t("int_to_roman", TRAIN,
       "Write a Python function `int_to_roman(n)` converting an integer 1..3999 to a Roman "
       "numeral using subtractive notation (IV, IX, XL, XC, CD, CM).",
       "assert int_to_roman(3) == 'III'\n"
       "assert int_to_roman(58) == 'LVIII'\n"
       "assert int_to_roman(1994) == 'MCMXCIV'\n"
       "assert int_to_roman(3999) == 'MMMCMXCIX'\n"
       "assert int_to_roman(444) == 'CDXLIV'\n",
       "def int_to_roman(n):\n    return 'I' * n\n"),

    _t("num_islands", HELDOUT,
       "Write a Python function `num_islands(grid)` counting islands in a grid (list of "
       "lists of '1' land / '0' water); land connects horizontally and vertically only.",
       "g = [['1','1','0','0','0'],['1','1','0','0','0'],['0','0','1','0','0'],['0','0','0','1','1']]\n"
       "assert num_islands(g) == 3\n"
       "assert num_islands([['1','0','1'],['0','1','0'],['1','0','1']]) == 5\n"
       "assert num_islands([]) == 0\n"
       "assert num_islands([['1','1','1'],['0','1','0'],['1','1','1']]) == 1\n",
       "def num_islands(grid):\n    return sum(row.count('1') for row in grid)\n"),

    _t("coin_change_ways", TRAIN,
       "Write a Python function `coin_change_ways(amount, coins)` returning the number of "
       "combinations (order does not matter) of coins that sum to amount; each coin may be "
       "used any number of times.",
       "assert coin_change_ways(5, [1, 2, 5]) == 4\n"
       "assert coin_change_ways(3, [2]) == 0\n"
       "assert coin_change_ways(10, [10]) == 1\n"
       "assert coin_change_ways(0, [1, 2]) == 1\n"
       "assert coin_change_ways(100, [1, 5, 10, 25]) == 242\n",
       "def coin_change_ways(amount, coins):\n    return sum(1 for c in coins if amount % c == 0)\n"),

    _t("longest_palindrome", HELDOUT,
       "Write a Python function `longest_palindrome(s)` returning the longest palindromic "
       "substring of s; the leftmost one if several have the same length.",
       "assert longest_palindrome('babad') == 'bab'\n"
       "assert longest_palindrome('cbbd') == 'bb'\n"
       "assert longest_palindrome('a') == 'a'\n"
       "assert longest_palindrome('forgeeksskeegfor') == 'geeksskeeg'\n"
       "assert longest_palindrome('abc') == 'a'\n",
       "def longest_palindrome(s):\n    return s[:1]\n"),

    _t("valid_sudoku", TRAIN,
       "Write a Python function `valid_sudoku(board)` for a 9x9 list of lists of '1'-'9' or "
       "'.' returning True if no row, column or 3x3 box repeats a digit (empty cells allowed).",
       "b = [['5','3','.','.','7','.','.','.','.'],['6','.','.','1','9','5','.','.','.'],"
       "['.','9','8','.','.','.','.','6','.'],['8','.','.','.','6','.','.','.','3'],"
       "['4','.','.','8','.','3','.','.','1'],['7','.','.','.','2','.','.','.','6'],"
       "['.','6','.','.','.','.','2','8','.'],['.','.','.','4','1','9','.','.','5'],"
       "['.','.','.','.','8','.','.','7','9']]\n"
       "assert valid_sudoku(b) is True\n"
       "c = [row[:] for row in b]\nc[0][0] = '8'\n"
       "assert valid_sudoku(c) is False\n"
       "d = [row[:] for row in b]\nd[1][1] = '9'\n"
       "assert valid_sudoku(d) is False\n",
       "def valid_sudoku(board):\n    return all(len([c for c in r if c != '.']) == "
       "len(set(c for c in r if c != '.')) for r in board)\n"),

    _t("trie_prefix", HELDOUT,
       "Write a Python class `Trie` with `insert(word)` and `starts_with(prefix)` returning "
       "the sorted list of inserted words that begin with prefix (no duplicates).",
       "t = Trie()\nfor w in ['apple', 'app', 'apply', 'bat', 'app']:\n    t.insert(w)\n"
       "assert t.starts_with('app') == ['app', 'apple', 'apply']\n"
       "assert t.starts_with('b') == ['bat']\n"
       "assert t.starts_with('c') == []\n"
       "assert t.starts_with('') == ['app', 'apple', 'apply', 'bat']\n",
       "class Trie:\n    def __init__(self):\n        self.w = []\n"
       "    def insert(self, word):\n        self.w.append(word)\n"
       "    def starts_with(self, p):\n        return [x for x in self.w if x.startswith(p)]\n"),

    _t("time_map", TRAIN,
       "Write a Python class `TimeMap` with `set(key, value, timestamp)` and "
       "`get(key, timestamp)` returning the value set for key with the largest timestamp "
       "<= the given timestamp, or '' if there is none.",
       "m = TimeMap()\nm.set('foo', 'bar', 1)\n"
       "assert m.get('foo', 1) == 'bar'\nassert m.get('foo', 3) == 'bar'\n"
       "m.set('foo', 'bar2', 4)\n"
       "assert m.get('foo', 4) == 'bar2'\nassert m.get('foo', 5) == 'bar2'\n"
       "assert m.get('foo', 2) == 'bar'\nassert m.get('foo', 0) == ''\n"
       "assert m.get('nope', 9) == ''\n",
       "class TimeMap:\n    def __init__(self):\n        self.d = {}\n"
       "    def set(self, k, v, t):\n        self.d[k] = v\n"
       "    def get(self, k, t):\n        return self.d.get(k, '')\n"),

    _t("min_meeting_rooms", HELDOUT,
       "Write a Python function `min_meeting_rooms(intervals)` returning the minimum number "
       "of rooms needed for meetings given as [start, end) pairs; a meeting ending at t "
       "frees its room for one starting at t.",
       "assert min_meeting_rooms([[0, 30], [5, 10], [15, 20]]) == 2\n"
       "assert min_meeting_rooms([[7, 10], [2, 4]]) == 1\n"
       "assert min_meeting_rooms([]) == 0\n"
       "assert min_meeting_rooms([[1, 5], [5, 10]]) == 1\n"
       "assert min_meeting_rooms([[1, 10], [2, 9], [3, 8], [4, 7]]) == 4\n",
       "def min_meeting_rooms(intervals):\n    return 1 if intervals else 0\n"),

    _t("next_permutation", TRAIN,
       "Write a Python function `next_permutation(nums)` returning a new list with the next "
       "lexicographically greater permutation of nums, or the smallest (sorted ascending) "
       "permutation if nums is already the largest.",
       "assert next_permutation([1, 2, 3]) == [1, 3, 2]\n"
       "assert next_permutation([3, 2, 1]) == [1, 2, 3]\n"
       "assert next_permutation([1, 1, 5]) == [1, 5, 1]\n"
       "assert next_permutation([1, 3, 2]) == [2, 1, 3]\n"
       "assert next_permutation([2, 3, 1]) == [3, 1, 2]\n",
       "def next_permutation(nums):\n    return sorted(nums, reverse=True)\n"),

    _t("simplify_path", HELDOUT,
       "Write a Python function `simplify_path(path)` returning the canonical form of an "
       "absolute Unix path: resolve '.' and '..', collapse repeated slashes, no trailing "
       "slash (except the root '/').",
       "assert simplify_path('/home/') == '/home'\n"
       "assert simplify_path('/../') == '/'\n"
       "assert simplify_path('/home//foo/') == '/home/foo'\n"
       "assert simplify_path('/a/./b/../../c/') == '/c'\n"
       "assert simplify_path('/a/../../b/../c//.//') == '/c'\n"
       "assert simplify_path('/...') == '/...'\n",
       "def simplify_path(path):\n    return path.rstrip('/') or '/'\n"),

    _t("json_get", TRAIN,
       "Write a Python function `json_get(obj, path)` that follows a path like 'a.b[2].c' "
       "through nested dicts and lists and returns the value, or None if any step is "
       "missing or out of range.",
       "d = {'a': {'b': [1, 2, {'c': 'x'}]}, 'k': [[5, 6]]}\n"
       "assert json_get(d, 'a.b[2].c') == 'x'\n"
       "assert json_get(d, 'a.b[0]') == 1\n"
       "assert json_get(d, 'k[0][1]') == 6\n"
       "assert json_get(d, 'a.b[9]') is None\n"
       "assert json_get(d, 'a.z') is None\n"
       "assert json_get(d, 'a') == {'b': [1, 2, {'c': 'x'}]}\n",
       "def json_get(obj, path):\n    return obj.get(path.split('.')[0])\n"),

    _t("merge_k_sorted", HELDOUT,
       "Write a Python function `merge_k_sorted(lists)` merging k sorted lists of numbers "
       "into one sorted list.",
       "assert merge_k_sorted([[1, 4, 5], [1, 3, 4], [2, 6]]) == [1, 1, 2, 3, 4, 4, 5, 6]\n"
       "assert merge_k_sorted([]) == []\n"
       "assert merge_k_sorted([[], [0]]) == [0]\n"
       "assert merge_k_sorted([[-2, 9], [-3], [5, 5]]) == [-3, -2, 5, 5, 9]\n",
       "def merge_k_sorted(lists):\n    out = []\n    for l in lists:\n        out += l\n    return out\n"),
]


def tasks_for(split: str) -> List[HardTask]:
    return [t for t in HARD_TASKS if t.split == split]
