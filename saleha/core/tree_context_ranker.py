"""
Saleha Core: Tree-sitter Context Ranker (Aider-style structural ranking)

OPTIONAL layer -- pip install saleha[codeintel]:
    tree-sitter + tree-sitter-python / -javascript / -typescript (+go/rust)

Kya naya deta hai jo regex/keyword nahi de sakte:
1. Accurate multi-language symbols -- JS/TS ke liye bhi real AST definitions
   (pehle sirf Python-AST tha, baaki languages regex guess).
2. Symbol-popularity signal -- kitni doosri files kisi symbol ko reference
   karti hain; hub modules naturally up-rank hote hain.

Graceful degradation: grammars na hon to available=False, packer apne
existing keyword/AST path pe chalta rehta hai (CI core install safe).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

LANG_MODULES = {
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
}

DEF_NODE_TYPES = {
    "python": {"function_definition": "def", "class_definition": "class"},
    "javascript": {
        "function_declaration": "function",
        "generator_function_declaration": "function",
        "method_definition": "method",
        "class_declaration": "class",
    },
    "typescript": {
        "function_declaration": "function",
        "function_signature": "function",
        "method_definition": "method",
        "method_signature": "method",
        "class_declaration": "class",
        "abstract_class_declaration": "class",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
    },
    "go": {"function_declaration": "func", "method_declaration": "method"},
    "rust": {"function_item": "fn", "struct_item": "struct",
             "enum_item": "enum", "trait_item": "trait"},
}

MAX_IDENTIFIERS_PER_FILE = 2000


@dataclass
class FileFacts:
    lang: str
    defines: Set[str] = field(default_factory=set)
    references: Set[str] = field(default_factory=set)


def _load_parsers() -> Dict[str, tuple]:
    """Available grammars se parsers banao; jo na milein silently skip."""
    parsers: Dict[str, tuple] = {}
    try:
        from tree_sitter import Language, Parser
    except ImportError:
        return parsers
    import importlib
    for lang_key, module_name in LANG_MODULES.items():
        try:
            mod = importlib.import_module(module_name)
            lang = Language(mod.language())
            try:
                parser = Parser(lang)
            except TypeError:
                parser = Parser()
                parser.set_language(lang)  # type: ignore[attr-defined]
            parsers[lang_key] = (parser, lang)
        except Exception:
            continue
    return parsers


class TreeContextRanker:
    """Tree-sitter backed symbol extractor + hub-popularity booster."""

    def __init__(self):
        self.parsers = _load_parsers()
        self._files: Dict[str, FileFacts] = {}

    @property
    def available(self) -> bool:
        return bool(self.parsers)

    def supported(self, ext: str) -> bool:
        return EXT_TO_LANG.get(ext.lower(), "") in self.parsers

    def reset(self):
        self._files.clear()

    # ------------------------------------------------------------------
    def _walk(self, rel_path: str, code: str, lang: str):
        parser, _lang_obj = self.parsers[lang]
        tree = parser.parse(code.encode("utf-8", errors="replace"))
        defs: List[Tuple[int, str]] = []
        refs: Set[str] = set()
        def_types = DEF_NODE_TYPES.get(lang, {})
        stack = [tree.root_node]
        ident_count = 0
        while stack:
            n = stack.pop()
            ntype = n.type
            if ntype == "identifier" and ident_count < MAX_IDENTIFIERS_PER_FILE:
                refs.add(n.text.decode(errors="replace"))
                ident_count += 1
            if ntype in def_types:
                name_node = n.child_by_field_name("name")
                if name_node is not None:
                    lineno = n.start_point[0] + 1
                    label = f"{def_types[ntype]} {name_node.text.decode(errors='replace')}"
                    defs.append((lineno, label))
            for child in reversed(n.children):
                stack.append(child)
        return defs, refs

    def index_file(self, rel_path: str, code: str) -> Optional[FileFacts]:
        ext = "." + rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
        lang = EXT_TO_LANG.get(ext)
        if not lang or lang not in self.parsers or not code.strip():
            return None
        defs, refs = self._walk(rel_path, code, lang)
        facts = FileFacts(lang=lang)
        facts.defines = {label.split(" ", 1)[1] for _, label in defs}
        facts.references = refs
        self._files[rel_path] = facts
        return facts

    def extract_symbols(self, rel_path: str, code: str) -> List[Tuple[int, str]]:
        """(lineno, 'def name') list -- packer display ke liye direct."""
        ext = "." + rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
        lang = EXT_TO_LANG.get(ext)
        if not lang or lang not in self.parsers or not code.strip():
            return []
        defs, _refs = self._walk(rel_path, code, lang)
        return defs[:80]

    def popularity_boost(self) -> Dict[str, float]:
        """File-level boost: jo symbols DOOSRI files reference karti hain.
        Hub modules (shared types/utils) naturally up-rank hote hain."""
        all_defined: Dict[str, str] = {}
        for rel, facts in self._files.items():
            for sym in facts.defines:
                all_defined.setdefault(sym, rel)

        referrers: Dict[str, Set[str]] = {}
        for rel, facts in self._files.items():
            for sym in facts.references:
                owner = all_defined.get(sym)
                if owner and owner != rel:
                    referrers.setdefault(sym, set()).add(rel)

        import math
        boosts: Dict[str, float] = {}
        for rel, facts in self._files.items():
            boost = 0.0
            for sym in facts.defines:
                n_referrers = len(referrers.get(sym, ()))
                if n_referrers:
                    boost += 2.0 * math.log1p(n_referrers)
            boosts[rel] = round(boost, 3)
        return boosts
