"""
Regenerates docs/CLI_REFERENCE.md from the live Click command tree.

Usage: python scripts/gen_cli_docs.py
The rendering lives in saleha.core.governance.doc_sync so that this script and
`saleha governance docs` can never produce two different references.
"""
from __future__ import annotations

import io
import sys

from saleha.core.governance.doc_sync import render_cli_reference


def main() -> int:
    text = render_cli_reference()
    target = "docs/CLI_REFERENCE.md"
    with io.open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {target}: {text.count(chr(10))} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
