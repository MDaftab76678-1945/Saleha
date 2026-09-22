---
name: code-knowledge-graph
description: Repository-wide AST Call-Graph and Directed Acyclic Graph (DAG) topology builder for structural dependency tracking and blast radius analysis.
---

# Code Knowledge Graph Engine

## Overview

The `code-knowledge-graph` parses all Python source files in the repository to build a unified **Call-Graph & Import DAG**. It exposes programmatic queries to discover callers, callees, class hierarchies, and structural dependencies without brute-force string searches.

## Safety & Invariants

1. **Deterministic Static Analysis:** Graph is built strictly using the Python standard `ast` module.
2. **Platform Portable:** Handles Windows path formats with normalized Unix forward slashes.

## Usage

Build and inspect the repository graph:

```bash
python .agents/skills/code-knowledge-graph/scripts/build_ast_graph.py --target saleha/core --output scratch/ast_graph.json
```
