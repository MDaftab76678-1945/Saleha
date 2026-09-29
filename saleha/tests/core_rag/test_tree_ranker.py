"""Tree-sitter context ranker tests (real + fake extractor paths)."""
import os
import tempfile
import unittest
from typing import Any

from saleha.core.rag.repo_context_packer import RepoContextPacker

try:
    from saleha.core.rag.tree_context_ranker import TreeContextRanker
    _HAS_TS = TreeContextRanker().available
except Exception:
    _HAS_TS = False


class FakeRanker:
    """Deterministic stub: 'hub.js' ko fixed boost deta hai."""

    def __init__(self) -> None:
        self.indexed = []

    @property
    def available(self) -> Any:
        return True

    def supported(self, ext: Any) -> Any:
        return ext in (".js", ".py")

    def reset(self) -> None:
        pass

    def index_file(self, rel: Any, _code: Any) -> Any:
        self.indexed.append(rel)
        facts = type("F", (), {"defines": {"sharedThing"}, "references": set()})()
        return facts

    def extract_symbols(self, _rel: Any, _code: Any) -> Any:
        return [(1, "function sharedThing")]

    def popularity_boost(self) -> Any:
        return {"src/hub.js": 10.0}


class PackerRankerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "src"))
        with open(os.path.join(self.root, "src", "plain.py"), "w") as f:
            f.write("value = 1\n")
        with open(os.path.join(self.root, "src", "hub.js"), "w") as f:
            f.write("export function sharedThing() {}\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _first_listed(self, task: str) -> str:
        packer = RepoContextPacker(root_dir=self.root, symbol_ranker=FakeRanker())
        ctx = packer.pack(task, budget_chars=3000)
        sym_lines = [ln for ln in ctx.splitlines() if ln.startswith("- src/") and "::" in ln]
        self.assertTrue(sym_lines, ctx)
        return sym_lines[0]

    def test_fake_ranker_boost_reorders_matched_files(self) -> None:
        # Both files match "plain thing"; plain.py scores higher on
        # keywords, and hub.js's popularity boost lifts it above.
        self.assertIn("hub.js", self._first_listed("plain thing"))

    def test_boost_cannot_lift_a_file_the_task_does_not_match(self) -> None:
        # hub.js shares no word with "plain value". The old uncapped boost put
        # it first anyway -- which is how minified .next bundles out-ranked
        # every real source file.
        self.assertIn("plain.py", self._first_listed("plain value"))

    def test_ranker_receives_indexed_files(self) -> None:
        fake = FakeRanker()
        RepoContextPacker(root_dir=self.root,
                          symbol_ranker=fake).pack("anything")
        self.assertTrue(fake.indexed)  # files index hui


@unittest.skipIf(not _HAS_TS, "tree-sitter grammars not installed")
class RealTreeSitterTests(unittest.TestCase):
    def test_python_symbols_with_lines(self) -> None:
        r = TreeContextRanker()
        syms = r.extract_symbols("m.py", "import os\n\nclass Alpha:\n    def beta(self):\n        pass\n")
        labels = [s[1] for s in syms]
        self.assertIn("class Alpha", labels)
        self.assertIn("def beta", labels)
        alpha = next(s for s in syms if s[1] == "class Alpha")
        self.assertEqual(alpha[0], 3)

    def test_javascript_symbols(self) -> None:
        r = TreeContextRanker()
        syms = r.extract_symbols("app.js", "function greet(){}\nconst x = 1;\n")
        self.assertIn("function greet", [s[1] for s in syms])

    def test_popularity_boost_hub_signal(self) -> None:
        r = TreeContextRanker()
        r.index_file("types.js", "export class Money {}\n")
        for i in range(4):
            r.index_file(f"use{i}.js", f"new Money({i});\n")
        boosts = r.popularity_boost()
        self.assertGreater(boosts.get("types.js", 0), 0)
        self.assertEqual(boosts.get("use1.js", 0), 0.0)

    def test_unsupported_extension_returns_none(self) -> None:
        r = TreeContextRanker()
        self.assertIsNone(r.index_file("data.csv", "a,b\n1,2\n"))


if __name__ == "__main__":
    unittest.main()
