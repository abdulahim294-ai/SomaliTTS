#!/usr/bin/env python3
"""Validate the committed Kaggle notebook without executing model downloads."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

NOTEBOOK = Path("notebooks/somali_speecht5_baseline.ipynb")


def fail(message: str) -> None:
    print(f"Notebook validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not NOTEBOOK.is_file():
        fail(f"missing {NOTEBOOK}")

    try:
        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid JSON: {exc}")

    if notebook.get("nbformat") != 4 or not isinstance(notebook.get("cells"), list):
        fail("expected a nbformat 4 notebook with a cells array")

    code_cells = 0
    all_source: list[str] = []
    for index, cell in enumerate(notebook["cells"]):
        cell_type = cell.get("cell_type")
        source = cell.get("source", [])
        if not isinstance(source, list) or not all(isinstance(line, str) for line in source):
            fail(f"cell {index} has an invalid source field")
        text = "".join(source)
        all_source.append(text)

        if cell_type == "code":
            code_cells += 1
            # IPython magics are runtime directives, not Python syntax.
            python_lines = [
                line for line in text.splitlines()
                if not line.lstrip().startswith(("%", "!"))
            ]
            try:
                ast.parse("\n".join(python_lines), filename=f"cell-{index}")
            except SyntaxError as exc:
                fail(f"Python syntax error in code cell {index}: {exc}")
        elif cell_type != "markdown":
            fail(f"unsupported cell type {cell_type!r} in cell {index}")

    if code_cells < 3:
        fail(f"expected at least 3 code cells, found {code_cells}")

    source_text = "\n".join(all_source)
    required = {
        "Jelle checkpoint": "Somali-tts/Jelle_tts",
        "Diirow checkpoint": "Somali-tts/diirow_tts",
        "safe weight loading": "use_safetensors=True",
        "consent/privacy warning": "explicitly agrees",
        "native-speaker evaluation gate": "native Somali listener",
        "no-cloning disclaimer": "does not perform voice cloning",
    }
    for label, needle in required.items():
        if needle not in source_text:
            fail(f"missing {label} marker: {needle!r}")

    print(
        f"Notebook validation passed: {NOTEBOOK}, "
        f"{len(notebook['cells'])} cells, {code_cells} Python code cells."
    )


if __name__ == "__main__":
    main()
