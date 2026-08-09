"""Lightweight structural review of submitted code.

Correctness alone is a thin signal: two solutions can both pass every test while
differing hugely in quality. This module walks the AST to estimate loop nesting
depth (a rough complexity proxy), and checks for the habits a reviewer would
comment on anyway.
"""
from __future__ import annotations

import ast


def analyse(source: str) -> dict:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"parsed": False, "notes": [f"Syntax error on line {exc.lineno}."], "quality": 0.0}

    notes: list[str] = []
    depth = _max_loop_depth(tree)
    complexity = {0: "O(1) or recursive", 1: "linear", 2: "quadratic", 3: "cubic"}.get(
        depth, "deeply nested"
    )

    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if functions and not any(ast.get_docstring(fn) for fn in functions):
        notes.append("No docstrings on any function.")
    if depth >= 2:
        notes.append(f"Loop nesting depth {depth} suggests {complexity} time.")
    for fn in functions:
        body_lines = (fn.end_lineno or fn.lineno) - fn.lineno
        if body_lines > 40:
            notes.append(f"'{fn.name}' is {body_lines} lines; consider splitting it.")
    if any(isinstance(n, ast.Global) for n in ast.walk(tree)):
        notes.append("Uses global state.")

    quality = max(0.0, 1.0 - 0.15 * len(notes))
    return {
        "parsed": True,
        "loop_depth": depth,
        "complexity_estimate": complexity,
        "notes": notes or ["No structural issues found."],
        "quality": round(quality, 2),
    }


def _max_loop_depth(node: ast.AST, depth: int = 0) -> int:
    best = depth
    for child in ast.iter_child_nodes(node):
        step = depth + 1 if isinstance(child, (ast.For, ast.While, ast.AsyncFor)) else depth
        best = max(best, _max_loop_depth(child, step))
    return best
