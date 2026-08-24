"""
Saleha Core: Multi-File Editor Agent (C1)

Pehle Saleha sirf single-file refactor (SmartPatcher) aur naye project
generation kar pata tha -- EXISTING repo ke kai files ko ek goal ke under
surgically badalna possible nahi tha. Ye agent Aider/Cline ke core workflow
ka local-first version hai:

1. RepoContextPacker se task-relevant context pack
2. Coder se structured JSON edit-plan maango:
     {"edits": [{"path": "src/x.py", "action": "create|edit",
                 "content": "<FULL final file>"}]}
3. Validate: path-traversal block, size caps, action whitelist
4. ATOMIC apply: saare writes memory me taiyaar -> ek bhi fail ho to poori
   transaction ROLLBACK (originals restore / created files delete)
5. Python files par static gate (syntax+safety) apply se PEHLE

Default DRY-RUN hai -- disk kuch nahi badalta jab tak apply=True na ho.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

MAX_FILES = 50
MAX_FILE_CHARS = 200_000
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass
class PlannedEdit:
    path: str
    action: str            # create | edit
    content: str
    original_content: Optional[str] = None   # None => file pehle se nahi thi
    lines_changed: int = 0
    diff: str = ""         # unified diff (edit actions ke liye, C-polish)


@dataclass
class MultiEditResult:
    success: bool = False
    applied: bool = False                       # disk par likha gaya?
    edits: List[PlannedEdit] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    rolled_back: bool = False
    raw_response: str = ""

    @property
    def summary(self) -> str:
        if self.errors:
            return "; ".join(self.errors[:3])
        parts = [f"{e.action}:{e.path} (~{e.lines_changed} lines)" for e in self.edits]
        return ", ".join(parts) if parts else "no edits"


class MultiFileEditor:
    def __init__(self, coder_agent, root_dir: str = ".", tester=None,
                 max_context_chars: int = 8000):
        self.coder = coder_agent
        self.root_dir = os.path.abspath(root_dir)
        from saleha.agents.tester import TesterAgent
        self.tester = tester or TesterAgent()
        self.max_context_chars = max_context_chars

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def edit(self, goal: str, apply: bool = False,
             files_hint: Optional[List[str]] = None) -> MultiEditResult:
        result = MultiEditResult()

        context_block = ""
        try:
            from saleha.core.repo_context_packer import RepoContextPacker
            packed = RepoContextPacker(root_dir=self.root_dir).pack(
                goal, budget_chars=self.max_context_chars
            )
            if packed:
                context_block = f"\n\nCurrent repository context:\n{packed}\n"
        except Exception as ctx_err:
            result.errors.append(f"context pack skipped: {ctx_err}")

        hint_line = ""
        if files_hint:
            hint_line = "\nFocus especially on these files:\n" + "\n".join(
                f"- {f}" for f in files_hint[:20]
            )

        prompt = f"""Task: Plan surgical multi-file edits for this repository.

Goal: {goal}
{hint_line}{context_block}

Rules:
1. Return ONLY one ```json block with FULL final file contents (no diffs).
2. Use relative paths. action must be "create" (new file) or "edit" (existing).
3. Keep changes minimal and focused on the goal.
4. Maximum {MAX_FILES} files.

Format:
```json
{{"edits": [{{"path": "relative/file.py", "action": "edit", "content": "..."}}]}}
```"""
        resp = self.coder.think(prompt, complexity_score=6.0)
        result.raw_response = resp.content if resp.success else ""
        if not resp.success:
            result.errors.append(f"coder failed: {resp.error_message}")
            return result

        edits, parse_err = self._parse_edits(resp.content)
        if parse_err:
            result.errors.append(parse_err)
            return result
        if not edits:
            result.errors.append("model returned zero edits")
            return result
        result.edits = edits

        # Validation (dry-run included)
        val_errs = self._validate(edits)
        if val_errs:
            result.errors.extend(val_errs)
            return result

        result.success = True
        if not apply:
            return result

        # Atomic apply + rollback
        ok, apply_errs, rolled_back = self._apply_atomic(edits)
        result.applied = ok
        result.rolled_back = rolled_back
        result.errors.extend(apply_errs)
        result.success = ok and not rolled_back
        return result

    # ------------------------------------------------------------------
    # Parsing / validation
    # ------------------------------------------------------------------
    def _parse_edits(self, raw: str) -> Tuple[List[PlannedEdit], Optional[str]]:
        m = _JSON_BLOCK_RE.search(raw or "")
        payload = None
        if m:
            try:
                payload = json.loads(m.group(1))
            except json.JSONDecodeError as err:
                return [], f"invalid JSON in code fence: {err}"
        else:
            # Pura output hi JSON ho sakta hai (fence bhool gaya model)
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return [], "no ```json block found in model response"

        if not isinstance(payload, dict) or not isinstance(payload.get("edits"), list):
            return [], 'payload must be {"edits": [...]}'

        edits: List[PlannedEdit] = []
        for i, item in enumerate(payload["edits"][:MAX_FILES]):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip().replace("\\", "/")
            action = str(item.get("action", "edit")).strip().lower()
            content = item.get("content", "")
            if action not in ("create", "edit"):
                return [], f"edit #{i}: invalid action '{action}'"
            if not isinstance(content, str) or len(content) > MAX_FILE_CHARS:
                return [], f"edit #{i}: missing/oversized content"
            edit_obj = PlannedEdit(
                path=path, action=action, content=content,
                lines_changed=len(content.splitlines()),
            )
            # Unified diff preview (existing files ke liye)
            abs_p = self._safe_abs_path(path) if path else None
            if action == "edit" and abs_p and os.path.isfile(abs_p):
                try:
                    with open(abs_p, "r", encoding="utf-8", errors="replace") as f:
                        old = f.read()
                    from saleha.core.codebase_indexer import SmartPatcher
                    edit_obj.diff = SmartPatcher.create_unified_diff(old, content, path)[:4000]
                except OSError:
                    pass
            edits.append(edit_obj)
        return edits, None

    def _safe_abs_path(self, rel: str) -> Optional[str]:
        if not rel or rel.startswith("/") or (len(rel) > 1 and rel[1] == ":"):
            return None
        abs_p = os.path.abspath(os.path.join(self.root_dir, rel))
        root_abs = os.path.abspath(self.root_dir)
        if not abs_p.startswith(root_abs + os.sep):
            return None
        return abs_p

    def _validate(self, edits: List[PlannedEdit]) -> List[str]:
        errs: List[str] = []
        seen = set()
        for e in edits:
            if not e.path:
                errs.append("empty path")
                continue
            if e.path in seen:
                errs.append(f"duplicate path: {e.path}")
                continue
            seen.add(e.path)
            abs_p = self._safe_abs_path(e.path)
            if abs_p is None:
                errs.append(f"path traversal blocked: {e.path}")
                continue
            exists = os.path.isfile(abs_p)
            if e.action == "create" and exists:
                errs.append(f"create but exists: {e.path}")
            if e.action == "edit" and not exists:
                errs.append(f"edit but missing: {e.path}")
            # Static gate for python content (syntax + safety), apply se pehle
            if e.path.endswith(".py"):
                tr = self.tester.test_code(e.content)
                if not tr.passed and tr.error_type in ("SyntaxError", "SecurityViolation", "EmptyCode"):
                    errs.append(f"{e.path}: {tr.error_type}: {tr.error_message[:160]}")
        return errs

    # ------------------------------------------------------------------
    # Atomic apply
    # ------------------------------------------------------------------
    def _apply_atomic(self, edits: List[PlannedEdit]) -> Tuple[bool, List[str], bool]:
        originals: Dict[str, Optional[str]] = {}
        written: List[str] = []
        errs: List[str] = []

        # Phase 1: originals read (rollback snapshot)
        for e in edits:
            abs_p = self._safe_abs_path(e.path)
            e.original_content = None
            if abs_p and os.path.isfile(abs_p):
                try:
                    with open(abs_p, "r", encoding="utf-8", errors="replace") as f:
                        e.original_content = f.read()
                    originals[abs_p] = e.original_content
                except OSError as err:
                    errs.append(f"read failed {e.path}: {err}")
                    return False, errs, False

        # Phase 2: write everything; pehli failure par poori rollback
        try:
            for e in edits:
                abs_p = self._safe_abs_path(e.path)
                os.makedirs(os.path.dirname(abs_p), exist_ok=True)
                mode = "r+" if os.path.isfile(abs_p) else "w"
                with open(abs_p, "w", encoding="utf-8") as f:
                    f.write(e.content if e.content.endswith("\n") else e.content + "\n")
                written.append(abs_p)
        except OSError as err:
            errs.append(f"write failed: {err}")
            # Rollback
            rb_errs = []
            for wpath in written:
                try:
                    orig = originals.get(wpath)
                    if orig is None:
                        os.remove(wpath)          # nayi file -> delete
                    else:
                        with open(wpath, "w", encoding="utf-8") as f:
                            f.write(orig)          # purani file -> restore
                except OSError as rb:
                    rb_errs.append(str(rb))
            if rb_errs:
                errs.append(f"rollback issues: {'; '.join(rb_errs)}")
            return False, errs, True

        return True, errs, False
