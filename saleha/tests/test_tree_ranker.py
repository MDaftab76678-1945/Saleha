"""Tree-sitter context ranker tests (real + fake extractor paths)."""
import os
import tempfile
import unittest

from saleha.core.repo_context_packer import RepoContextPacker

try:
    from saleha.core.tree_context_ranker import TreeContextRanker
    _HAS_TS = TreeContextRanker().available
except Exception:
    _HAS_TS = False


class FakeRanker:
    """Deterministic stub: 'hub.js' ko fixed boost deta hai."""

    def __init__(self):
        self.indexed = []

    @property
    def available(self):
        return True

    def supported(self, ext):
        return ext in (".js", ".py")

    def reset(self):
        pass

    def index_file(self, rel, code):
        self.indexed.append(rel)
        facts = type("F", (), {"defines": {"sharedThing"}, "references": set()})()
        return facts

    def extract_symbols(self, rel, code):
        return [(1, "function sharedThing")]

    def popularity_boost(self):
        return {"src/hub.js": 10.0}


class PackerRankerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "src"))
        with open(os.path.join(self.root, "src", "plain.py"), "w") as f:
            f.write("value = 1\n")
        with open(os.path.join(self.root, "src", "hub.js"), "w") as f:
            f.write("export function sharedThing() {}\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_fake_ranker_boost_changes_ranking(self):
        # hub.js ka base score kam hoga (task 'plain' se match plain.py),
        # par popularity boost use upar le aayega.
        packer = RepoContextPacker(root_dir=self.root,
                                   symbol_ranker=FakeRanker())
        ctx = packer.pack("plain value", budget_chars=3000)
        sym_lines = [l for l in ctx.splitlines() if l.startswith("- src/") and "::" in l]
        self.assertTrue(sym_lines, ctx)
        self.assertIn("hub.js", sym_lines[0])

    def test_ranker_receives_indexed_files(self):
        fake = FakeRanker()
        RepoContextPacker(root_dir=self.root,
                          symbol_ranker=fake).pack("anything")
        self.assertTrue(fake.indexed)  # files index hui


@unittest.skipIf(not _HAS_TS, "tree-sitter grammars not installed")
class RealTreeSitterTests(unittest.TestCase):
    def test_python_symbols_with_lines(self):
        r = TreeContextRanker()
        syms = r.extract_symbols("m.py", "import os\n\nclass Alpha:\n    def beta(self):\n        pass\n")
        labels = [s[1] for s in syms]
        self.assertIn("class Alpha", labels)
        self.assertIn("def beta", labels)
        alpha = next(s for s in syms if s[1] == "class Alpha")
        self.assertEqual(alpha[0], 3)

    def test_javascript_symbols(self):
        r = TreeContextRanker()
        syms = r.extract_symbols("app.js", "function greet(){}\nconst x = 1;\n")
        self.assertIn("function greet", [s[1] for s in syms])

    def test_popularity_boost_hub_signal(self):
        r = TreeContextRanker()
        r.index_file("types.js", "export class Money {}\n")
        for i in range(4):
            r.index_file(f"use{i}.js", f"new Money({i});\n")
        boosts = r.popularity_boost()
        self.assertGreater(boosts.get("types.js", 0), 0)
        self.assertEqual(boosts.get("use1.js", 0), 0.0)

    def test_unsupported_extension_returns_none(self):
        r = TreeContextRanker()
        self.assertIsNone(r.index_file("data.csv", "a,b\n1,2\n"))


if __name__ == "__main__":
    unittest.main()
