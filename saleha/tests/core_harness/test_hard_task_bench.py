"""The hard benchmark's tests must fail on wrong code AND pass on correct code.

verify_tests_can_fail covers the first half. The references below cover the
second: a test no correct solution can satisfy would score every model 0 and
look like a hard task.
"""

import unittest

from saleha.core.harness.hard_task_bench import HARD_TASKS, HELDOUT, TRAIN, tasks_for
from saleha.core.harness.real_task_bench import run_in_subprocess, verify_tests_can_fail

REFERENCES = {
    "edit_distance": '''
def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
''',
    "eval_expr": '''
def eval_expr(s):
    toks = [c for c in s if c != " "]
    pos = 0
    def peek():
        return toks[pos] if pos < len(toks) else None
    def take():
        nonlocal pos
        pos += 1
        return toks[pos - 1]
    def expr():
        v = term()
        while peek() in ("+", "-"):
            v = v + term() if take() == "+" else v - term()
        return v
    def term():
        v = factor()
        while peek() in ("*", "/"):
            if take() == "*":
                v *= factor()
            else:
                d = factor()
                v = int(v / d)
        return v
    def factor():
        if peek() == "-":
            take()
            return -factor()
        if peek() == "(":
            take()
            v = expr()
            take()
            return v
        n = 0
        while peek() is not None and peek().isdigit():
            n = n * 10 + int(take())
        return n
    return expr()
''',
    "decode_string": '''
def decode_string(s):
    stack, cur, k = [], "", 0
    for ch in s:
        if ch.isdigit():
            k = k * 10 + int(ch)
        elif ch == "[":
            stack.append((cur, k))
            cur, k = "", 0
        elif ch == "]":
            prev, n = stack.pop()
            cur = prev + cur * n
        else:
            cur += ch
    return cur
''',
    "min_window": '''
from collections import Counter
def min_window(s, t):
    need, missing = Counter(t), len(t)
    best, left = (0, 0), 0
    for right, ch in enumerate(s, 1):
        if need[ch] > 0:
            missing -= 1
        need[ch] -= 1
        if missing == 0:
            while need[s[left]] < 0:
                need[s[left]] += 1
                left += 1
            if best == (0, 0) or right - left < best[1] - best[0]:
                best = (left, right)
            need[s[left]] += 1
            missing += 1
            left += 1
    return s[best[0]:best[1]]
''',
    "regex_match": '''
from functools import lru_cache
def regex_match(s, p):
    @lru_cache(None)
    def m(i, j):
        if j == len(p):
            return i == len(s)
        first = i < len(s) and p[j] in (s[i], ".")
        if j + 1 < len(p) and p[j + 1] == "*":
            return m(i, j + 2) or (first and m(i + 1, j))
        return first and m(i + 1, j + 1)
    return m(0, 0)
''',
    "wildcard_match": '''
from functools import lru_cache
def wildcard_match(s, p):
    @lru_cache(None)
    def m(i, j):
        if j == len(p):
            return i == len(s)
        if p[j] == "*":
            return m(i, j + 1) or (i < len(s) and m(i + 1, j))
        return i < len(s) and p[j] in (s[i], "?") and m(i + 1, j + 1)
    return m(0, 0)
''',
    "topo_sort": '''
def topo_sort(n, edges):
    indeg = [0] * n
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        indeg[v] += 1
    queue = [v for v in range(n) if indeg[v] == 0]
    order = []
    while queue:
        u = queue.pop()
        order.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    return order if len(order) == n else None
''',
    "dijkstra": '''
import heapq
def dijkstra(n, edges, src):
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w))
    dist = [float("inf")] * n
    dist[src] = 0
    heap = [(0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            if d + w < dist[v]:
                dist[v] = d + w
                heapq.heappush(heap, (dist[v], v))
    return dist
''',
    "lis_length": '''
import bisect
def lis_length(nums):
    tails = []
    for x in nums:
        i = bisect.bisect_left(tails, x)
        tails[i:i + 1] = [x]
    return len(tails)
''',
    "word_break": '''
def word_break(s, words):
    ok = [True] + [False] * len(s)
    for i in range(1, len(s) + 1):
        ok[i] = any(ok[i - len(w)] and s[i - len(w):i] == w for w in words if len(w) <= i)
    return ok[-1]
''',
    "median_finder": '''
import heapq
class MedianFinder:
    def __init__(self):
        self.lo, self.hi = [], []
    def add(self, num):
        heapq.heappush(self.lo, -num)
        heapq.heappush(self.hi, -heapq.heappop(self.lo))
        if len(self.hi) > len(self.lo):
            heapq.heappush(self.lo, -heapq.heappop(self.hi))
    def median(self):
        if len(self.lo) > len(self.hi):
            return float(-self.lo[0])
        return (-self.lo[0] + self.hi[0]) / 2
''',
    "sliding_max": '''
from collections import deque
def sliding_max(nums, k):
    dq, out = deque(), []
    for i, x in enumerate(nums):
        while dq and nums[dq[-1]] <= x:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - k:
            dq.popleft()
        if i >= k - 1:
            out.append(nums[dq[0]])
    return out
''',
    "int_to_roman": '''
def int_to_roman(n):
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
             (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, sym in table:
        while n >= v:
            out += sym
            n -= v
    return out
''',
    "num_islands": '''
def num_islands(grid):
    seen, count = set(), 0
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == "1" and (r, c) not in seen:
                count += 1
                stack = [(r, c)]
                while stack:
                    y, x = stack.pop()
                    if (y, x) in seen or not (0 <= y < len(grid) and 0 <= x < len(grid[0])) or grid[y][x] != "1":
                        continue
                    seen.add((y, x))
                    stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return count
''',
    "coin_change_ways": '''
def coin_change_ways(amount, coins):
    ways = [1] + [0] * amount
    for c in coins:
        for a in range(c, amount + 1):
            ways[a] += ways[a - c]
    return ways[amount]
''',
    "longest_palindrome": '''
def longest_palindrome(s):
    best = s[:1]
    for center in range(2 * len(s) - 1):
        l, r = center // 2, center // 2 + center % 2
        while l >= 0 and r < len(s) and s[l] == s[r]:
            l, r = l - 1, r + 1
        if r - l - 1 > len(best):
            best = s[l + 1:r]
    return best
''',
    "valid_sudoku": '''
def valid_sudoku(board):
    seen = set()
    for r in range(9):
        for c in range(9):
            v = board[r][c]
            if v == ".":
                continue
            keys = [("r", r, v), ("c", c, v), ("b", r // 3, c // 3, v)]
            if any(k in seen for k in keys):
                return False
            seen.update(keys)
    return True
''',
    "trie_prefix": '''
class Trie:
    def __init__(self):
        self.words = set()
    def insert(self, word):
        self.words.add(word)
    def starts_with(self, prefix):
        return sorted(w for w in self.words if w.startswith(prefix))
''',
    "time_map": '''
import bisect
class TimeMap:
    def __init__(self):
        self.d = {}
    def set(self, key, value, timestamp):
        self.d.setdefault(key, []).append((timestamp, value))
    def get(self, key, timestamp):
        items = self.d.get(key, [])
        i = bisect.bisect_right(items, (timestamp, chr(0x10FFFF)))
        return items[i - 1][1] if i else ""
''',
    "min_meeting_rooms": '''
def min_meeting_rooms(intervals):
    events = sorted([(s, 1) for s, _ in intervals] + [(e, -1) for _, e in intervals])
    cur = best = 0
    for _, d in events:
        cur += d
        best = max(best, cur)
    return best
''',
    "next_permutation": '''
def next_permutation(nums):
    a = list(nums)
    i = len(a) - 2
    while i >= 0 and a[i] >= a[i + 1]:
        i -= 1
    if i < 0:
        return sorted(a)
    j = len(a) - 1
    while a[j] <= a[i]:
        j -= 1
    a[i], a[j] = a[j], a[i]
    a[i + 1:] = reversed(a[i + 1:])
    return a
''',
    "simplify_path": '''
def simplify_path(path):
    parts = []
    for p in path.split("/"):
        if p == "..":
            if parts:
                parts.pop()
        elif p and p != ".":
            parts.append(p)
    return "/" + "/".join(parts)
''',
    "json_get": '''
import re
def json_get(obj, path):
    cur = obj
    for key, idx in re.findall(r"([^.\\[\\]]+)|\\[(\\d+)\\]", path):
        try:
            cur = cur[int(idx)] if idx else cur[key]
        except (KeyError, IndexError, TypeError):
            return None
    return cur
''',
    "merge_k_sorted": '''
import heapq
def merge_k_sorted(lists):
    return list(heapq.merge(*lists))
''',
}


class HardTaskBenchTests(unittest.TestCase):
    def test_every_test_fails_on_its_wrong_implementation(self) -> None:
        self.assertEqual(verify_tests_can_fail(list(HARD_TASKS)), [])

    def test_every_test_passes_on_a_correct_reference(self) -> None:
        for task in HARD_TASKS:
            with self.subTest(task=task.task_id):
                ok, err = run_in_subprocess(REFERENCES[task.task_id], task.test)
                self.assertTrue(ok, err)

    def test_split_is_balanced_and_disjoint(self) -> None:
        train, heldout = tasks_for(TRAIN), tasks_for(HELDOUT)
        self.assertEqual(len(train), len(heldout))
        self.assertFalse({t.task_id for t in train} & {t.task_id for t in heldout})
        self.assertEqual(set(REFERENCES), {t.task_id for t in HARD_TASKS})


if __name__ == "__main__":
    unittest.main()
