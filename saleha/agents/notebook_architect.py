"""NotebookArchitectAgent: a notebook for a topic, written by the model and then run.

The model writes the cells (markdown and Python); every code cell is
compiled, screened by the AST security auditor, and then the cells are
executed in order in one throwaway process, each cell's printed output and
error recorded on the cell -- so the exported .ipynb carries real outputs,
and a cell that raises is marked `has_error`, not passed over.

With no model answering, a five-cell starter notebook is returned, marked
`from_template`, and nothing is executed.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import AgentResponse, BaseAgent
from saleha.core.ui.notebook_engine import NotebookCell, NotebookDocument, notebook_engine

_MARK = "@@SALEHA-CELL@@"


@dataclass
class NotebookSynthesisResult:
    """Output from NotebookArchitectAgent."""
    title: str
    cell_count: int
    notebook_doc: NotebookDocument
    ipynb_json: str
    generation_time_ms: float = 0.0
    model_used: str = ""
    from_template: bool = True
    executed: bool = False
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None      # True: every code cell compiled and ran without an error


def _starter(topic: str) -> List[NotebookCell]:
    return [
        NotebookCell("cell_01", "markdown", f"# {topic}\n\n*Starter template: replace with real analysis.*"),
        NotebookCell("cell_02", "code", "# Setup (placeholder): replace with the real imports.\nprint('setup')"),
        NotebookCell("cell_03", "sql", "-- Query (placeholder): replace with a real query.\nSELECT 1;"),
        NotebookCell("cell_04", "code", "# Computation (placeholder)\nresult = None\nprint(result)"),
        NotebookCell("cell_05", "markdown", "### Summary (placeholder)\n- Nothing here was executed or verified."),
    ]


def run_cells(cells: List[NotebookCell], timeout: float = 60.0) -> ac.Check:
    """Execute the code cells in order in one process; record each cell's output or error on it."""
    code_cells = [c for c in cells if c.cell_type == "code"]
    if not code_cells:
        return ac.Check("cells run", ac.NOT_RUN, "no code cells")
    runner = ["import json, sys, traceback, io, contextlib", "ns = {}", "results = []"]
    for c in code_cells:
        runner.append(f"src = {json.dumps(c.source)}")
        runner.append("buf = io.StringIO()\nerr = ''\n"
                      "try:\n    with contextlib.redirect_stdout(buf):\n        exec(compile(src, 'cell', 'exec'), ns)\n"
                      "except Exception as e:\n    err = f'{type(e).__name__}: {e}'\n"
                      "results.append({'out': buf.getvalue()[-4000:], 'err': err})")
    runner.append(f"print({json.dumps(_MARK)} + json.dumps(results))")
    joined = "\n\n".join(c.source for c in code_cells)
    safe = ac.check_safe(joined)
    if safe.status != ac.PASS:
        return ac.Check("cells run", ac.NOT_RUN, f"not run: {safe.detail}")
    check, out = ac.run_python("\n".join(runner), timeout=timeout, name="cells run", screen=False)
    if _MARK not in out:
        return check if check.status != ac.PASS else ac.Check("cells run", ac.FAIL, "no results came back")
    results = json.loads(out.split(_MARK, 1)[1].splitlines()[0])
    for n, (cell, res) in enumerate(zip(code_cells, results), 1):
        cell.execution_count, cell.output_text = n, res["out"]
        cell.has_error, cell.error_diagnostic = bool(res["err"]), res["err"]
    failed = [f"{c.cell_id}: {c.error_diagnostic}" for c in code_cells if c.has_error]
    return ac.Check("cells run", ac.FAIL if failed else ac.PASS,
                    "; ".join(failed)[:300] if failed else f"{len(code_cells)} code cell(s) ran")


class NotebookArchitectAgent(BaseAgent):
    """Writes a notebook with the model, then compiles and runs its code cells."""

    def __init__(self, role: str = "Interactive Notebook Architect", model: str = "auto"):
        super().__init__(role=role, model=model)
        self.name = "NotebookArchitectAgent"

    def execute(self, prompt: str) -> AgentResponse:
        """Standard Agent execution."""
        start = time.perf_counter()
        result = self.synthesize_notebook(prompt)
        state = ("template cells -- replace with real analysis" if result.from_template else
                 "every code cell ran" if result.verified else "some cells failed or were not run")
        content = (f"Notebook: {result.title}\n- Total Cells: {result.cell_count} ({state})\n"
                   "- Export Format: Standard Jupyter `.ipynb` (nbformat v4.5)\n")
        return AgentResponse(success=True, content=content, model_used=result.model_used,
                             response_time=(time.perf_counter() - start) * 1000, tokens_used=0)

    def synthesize_notebook(self, topic: str) -> NotebookSynthesisResult:
        """A notebook for `topic` whose code cells were run; the starter template when no model answers."""
        start = time.perf_counter()
        clean_topic = topic.strip() or "Autonomous Data Engineering"
        prompt = (
            f"Write a short Jupyter notebook about: {clean_topic}\n"
            "Use alternating fenced blocks, in order: ```markdown blocks for explanations and ```python blocks "
            "for code. The code must run top to bottom with the Python standard library only (no files, no "
            "network), and print its results. 3-6 code blocks. No other text.")

        def build(content: str) -> Tuple[List[NotebookCell], List[ac.Check]]:
            cells: List[NotebookCell] = []
            for info, body in ac.fenced_blocks(content):
                kind = "code" if info.split()[:1] in (["python"], ["py"]) else "markdown"
                cells.append(NotebookCell(f"cell_{len(cells) + 1:02d}", kind, body))
            code = [c for c in cells if c.cell_type == "code"]
            checks = [ac.Check("has code cells", ac.PASS if code else ac.FAIL, f"{len(code)} code cell(s)")]
            bad = [f"{c.cell_id}: {ac.check_python(c.source).detail}" for c in code
                   if ac.check_python(c.source).status != ac.PASS]
            checks.append(ac.Check("code cells compile", ac.FAIL if bad else ac.PASS, "; ".join(bad)))
            if code and not bad:
                checks.append(run_cells(cells))
            return cells, checks

        cells, checks, resp, _rounds = ac.produce(self, prompt, build)
        from_template = not cells
        if from_template:
            # The starter notebook is placeholders and is not run: never called verified.
            checks = ac.fallback_note(checks, cells is not None)
            cells = _starter(clean_topic)
        nb = NotebookDocument(notebook_id=f"nb_{uuid.uuid4().hex[:8]}", title=clean_topic, cells=cells)
        executed = any(c.execution_count for c in cells)
        return NotebookSynthesisResult(
            title=clean_topic, cell_count=len(cells), notebook_doc=nb,
            ipynb_json=notebook_engine.export_to_ipynb(nb),
            generation_time_ms=round((time.perf_counter() - start) * 1000, 2),
            model_used="template (no usable model answer)" if from_template else resp.model_used,
            from_template=from_template, executed=executed, checks=ac.as_dicts(checks),
            verified=None if from_template else ac.verdict(checks))


notebook_architect = NotebookArchitectAgent()
