#!/usr/bin/env python3
"""Grammar-Constrained Token & AST State Machine.

Validates syntactic transitions using Python token streams and pushdown automata.
Enforces bracket balance, colon-indentation invariants, and expression integrity
to eliminate syntax errors from 3B model outputs.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import sys
import tokenize
from typing import Dict, List, Any


class GrammarStateMachine:
    """Pushdown automaton tracking syntactic Python invariants."""

    def __init__(self) -> None:
        self.bracket_stack: List[str] = []
        self.expecting_indent: bool = False
        self.indent_stack: List[int] = [0]
        self.errors: List[str] = []

    def validate_source(self, source_code: str) -> Dict[str, Any]:
        """Runs lexical token stream analysis and AST parse verification."""
        self.bracket_stack = []
        self.expecting_indent = False
        self.indent_stack = [0]
        self.errors = []

        tokens = []
        try:
            reader = io.StringIO(source_code).readline
            for tok in tokenize.generate_tokens(reader):
                tokens.append(tok)
                self._process_token(tok)
        except tokenize.TokenError as e:
            self.errors.append(f"Lexical error: {e}")
        except IndentationError as e:
            self.errors.append(f"Indentation error: {e}")

        # Check for unclosed brackets
        if self.bracket_stack:
            self.errors.append(f"Unclosed brackets remaining: {', '.join(self.bracket_stack)}")

        # Check full AST parse
        ast_valid = False
        try:
            ast.parse(source_code)
            ast_valid = True
        except SyntaxError as e:
            self.errors.append(f"AST SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}")

        return {
            "valid": ast_valid and len(self.errors) == 0,
            "total_tokens": len(tokens),
            "errors": self.errors,
            "syntax_flaws_count": len(self.errors),
        }

    def _process_token(self, tok: tokenize.TokenInfo) -> None:
        token_type = tok.type
        token_str = tok.string

        # Track bracket balancing
        if token_str in ("(", "[", "{"):
            self.bracket_stack.append(token_str)
        elif token_str in (")", "]", "}"):
            if not self.bracket_stack:
                self.errors.append(f"Line {tok.start[0]}: Unexpected closing '{token_str}'")
            else:
                top = self.bracket_stack.pop()
                expected = {")": "(", "]": "[", "}": "{"}[token_str]
                if top != expected:
                    self.errors.append(
                        f"Line {tok.start[0]}: Mismatched bracket '{token_str}', expected closing for '{top}'"
                    )

        # Track colon and indentation
        if token_str == ":":
            if not self.bracket_stack:
                self.expecting_indent = True
        elif token_type == tokenize.NEWLINE:
            pass
        elif token_type == tokenize.INDENT:
            self.expecting_indent = False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grammar-Constrained syntax validator for code candidates."
    )
    parser.add_argument("--code", "-c", required=True, help="Python code string to validate.")
    parser.add_argument("--output", "-o", default=None, help="Save report to JSON file.")

    args = parser.parse_args()
    sm = GrammarStateMachine()
    result = sm.validate_source(args.code)

    output_str = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"Grammar validation report saved to: {args.output}")
    else:
        print(output_str)

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
