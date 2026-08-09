"""Flags submissions that are suspiciously close to another candidate's.

Two strategies, chosen by what the text is:

  Code -> structural comparison. The submission is parsed to an AST and every
      identifier is rewritten to a positional placeholder (v0, v1, f0...), so
      `seen`/`d` and `nums`/`arr` collapse to the same token. The normalised
      structure is then compared. This survives the rename-everything edit that
      defeats plain text matching, which is the most common way a copied answer
      is disguised.

  Prose (or code that will not parse) -> character n-gram overlap, which
      survives reflowed whitespace and punctuation changes.

Both return a score in [0, 1]. Anything at or above THRESHOLD is surfaced to an
examiner as a flag. It is never an automatic penalty: similar answers to a narrow
question are expected, and only a human should draw the conclusion.
"""
from __future__ import annotations

import ast
import re
from collections import Counter

from . import textsim

THRESHOLD = 0.85


class _Anonymiser(ast.NodeTransformer):
    """Rewrites identifiers to placeholders assigned in order of first appearance."""

    def __init__(self) -> None:
        self.names: dict[str, str] = {}
        self.functions: dict[str, str] = {}

    def _placeholder(self, name: str, table: dict[str, str], prefix: str) -> str:
        if name not in table:
            table[name] = f"{prefix}{len(table)}"
        return table[name]

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self._placeholder(node.id, self.names, "v")
        return self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._placeholder(node.arg, self.names, "v")
        node.annotation = None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.name = self._placeholder(node.name, self.functions, "f")
        # A docstring is free text, not structure.
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(getattr(first, "value", None), ast.Constant)
            and isinstance(first.value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
        return self.generic_visit(node)


_KGRAM = 5


def _node_sequence(tree: ast.AST) -> list[str]:
    """Pre-order sequence of node types, with operators and literals kept.

    Node *order* is what distinguishes one algorithm from another. A dict lookup
    and a nested loop over the same inputs produce clearly different sequences,
    while a renamed copy produces an identical one.
    """
    sequence: list[str] = []

    def walk(node: ast.AST) -> None:
        label = type(node).__name__
        if isinstance(node, ast.Constant):
            label += f":{type(node.value).__name__}"
        elif isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp)):
            label += f":{type(node.op).__name__}"
        elif isinstance(node, ast.Compare):
            label += ":" + ",".join(type(o).__name__ for o in node.ops)
        sequence.append(label)
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(tree)
    return sequence


def _structural_fingerprint(source: str) -> Counter | None:
    """Return k-gram counts over the normalised node sequence, or None if unparseable.

    Overlapping k-grams (k=5) are the same idea as the winnowing fingerprints used
    by established plagiarism tools: short enough to survive small edits, long
    enough that shared boilerplate does not swamp the signal.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    try:
        normalised = _Anonymiser().visit(tree)
        ast.fix_missing_locations(normalised)
        sequence = _node_sequence(normalised)
    except (RecursionError, ValueError, AttributeError):
        return None

    if len(sequence) < _KGRAM:
        return Counter([">".join(sequence)]) if sequence else None
    return Counter(
        ">".join(sequence[i:i + _KGRAM]) for i in range(len(sequence) - _KGRAM + 1)
    )


def _normalise_text(text: str) -> str:
    text = re.sub(r"#.*", "", text)
    text = re.sub(r'"""(.*?)"""', "", text, flags=re.S)
    return re.sub(r"\s+", " ", text).strip().lower()


def max_similarity(candidate: str, others: list[str]) -> float:
    """Highest similarity between `candidate` and any other submission."""
    corpus = [t for t in others if t and t.strip()]
    if not candidate.strip() or not corpus:
        return 0.0

    fingerprint = _structural_fingerprint(candidate)
    if fingerprint is not None:
        peers = [_structural_fingerprint(t) for t in corpus]
        structural = [p for p in peers if p is not None]
        if structural:
            return round(
                max(textsim.raw_cosine(fingerprint, p) for p in structural), 3
            )

    return round(
        textsim.max_similarity(
            _normalise_text(candidate), [_normalise_text(t) for t in corpus], mode="char"
        ),
        3,
    )


def is_suspicious(score: float) -> bool:
    return score >= THRESHOLD
