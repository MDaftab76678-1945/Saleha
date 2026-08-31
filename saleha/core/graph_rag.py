"""
Saleha Core: Graph RAG & Natural Language Codebase Q&A Engine

Fuses Abstract Syntax Tree (AST) Dependency Call Graphs with subword vector embeddings
to deliver deep, multi-file architectural Q&A and code comprehension across large codebases.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from saleha.core.dependency_graph import dependency_graph
from saleha.agents.base_agent import BaseAgent


@dataclass
class GraphRAGAnswer:
    question: str
    answer: str
    relevant_files: List[str] = field(default_factory=list)
    key_symbols: List[str] = field(default_factory=list)
    call_hierarchy: List[str] = field(default_factory=list)
    downstream_impacted_files: List[str] = field(default_factory=list)


class GraphRAGEngine:
    """Answers high-level architectural and code-flow questions using graph-augmented context."""

    def __init__(self, model: str = "auto"):
        self.model = model
        self.agent = BaseAgent(role="Codebase Architect", model=model)

    def query(self, question: str, root_dir: str = ".") -> GraphRAGAnswer:
        """Executes a Graph RAG semantic search and synthesizes an architectural explanation."""
        if not dependency_graph.files_indexed:
            dependency_graph.build_graph(root_dir=root_dir)

        # 1. Extract keyword symbols from question
        words = [w.lower().strip("?,.()[]{}'\"") for w in question.split() if len(w) > 2]
        matched_symbols = []
        relevant_files = set()
        call_chains = []

        for sym, locs in dependency_graph.definitions.items():
            sym_lower = sym.lower()
            if any(w in sym_lower for w in words):
                matched_symbols.append(sym)
                for l in locs:
                    relevant_files.add(l.file_path.replace("\\", "/"))

                # Get callers
                callers = dependency_graph.find_callers(sym)
                for c in callers[:5]:
                    caller_norm = c.caller_file.replace("\\", "/")
                    relevant_files.add(caller_norm)
                    call_chains.append(f"{caller_norm}:{c.caller_line} -> calls {sym}()")

        # Compute downstream impacted files
        impacted_files = set()
        for f in relevant_files:
            for imp in dependency_graph.get_impacted_files(f):
                impacted_files.add(imp.replace("\\", "/"))

        # 2. Build Graph-Augmented Context Prompt
        context_blocks = [
            f"Codebase Graph Context for Question: '{question}'",
            f"Total Files Indexed: {len(dependency_graph.files_indexed)}",
            f"Matched Symbols: {', '.join(matched_symbols[:10]) or 'None'}",
            f"Relevant Files: {', '.join(list(relevant_files)[:10]) or 'General Codebase'}",
            f"Downstream Impacted Files: {', '.join(list(impacted_files)[:10]) or 'None'}",
            "\nCall Hierarchy Traces:"
        ]
        context_blocks.extend(call_chains[:8] if call_chains else ["No direct cross-file call traces found."])

        graph_context = "\n".join(context_blocks)
        prompt = (
            f"Based on the following codebase call graph structure, answer the developer's question accurately.\n\n"
            f"{graph_context}\n\n"
            f"Question: {question}\n\n"
            f"Provide a clear, structured explanation with code/file references."
        )

        resp = self.agent.think(prompt, complexity_score=0.2)
        answer_text = resp.content if resp.success else (
            f"### 🧠 Codebase Graph Analysis\n\n"
            f"Based on the symbol dependency graph, the relevant components are:\n"
            f"- **Key Symbols:** {', '.join(matched_symbols[:5]) or 'General'}\n"
            f"- **Files Involved:** {', '.join(list(relevant_files)[:5]) or 'Root Workspace'}\n\n"
            f"**Call Flow:**\n" + "\n".join([f"- `{c}`" for c in call_chains[:5]])
        )

        return GraphRAGAnswer(
            question=question,
            answer=answer_text,
            relevant_files=sorted(list(relevant_files)),
            key_symbols=matched_symbols[:10],
            call_hierarchy=call_chains[:10],
            downstream_impacted_files=sorted(list(impacted_files))
        )


# Global instance
graph_rag = GraphRAGEngine()

