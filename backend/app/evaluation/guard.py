"""Static pre-flight check run before any candidate code is executed.

Process rlimits stop runaway resource use but do not stop a submission from
reading or writing files. This module rejects submissions that reach for the
filesystem, the network, the process table or dynamic import before they ever
run. It is defence in depth, layered under the sandbox rather than replacing it:
a denylist can be evaded, so treat this as the first gate, not the only one.

For untrusted public traffic, run submissions in a network-less container.
"""
from __future__ import annotations

import ast

BANNED_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "ctypes",
    "importlib", "builtins", "multiprocessing", "threading", "http",
    "urllib", "requests", "pickle", "marshal", "tempfile", "glob", "signal",
}

BANNED_NAMES = {
    "open", "eval", "exec", "compile", "__import__", "input",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "memoryview",
}


def check(source: str) -> str | None:
    """Return a rejection reason, or None if the submission may run."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"Syntax error on line {exc.lineno}: {exc.msg}."

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BANNED_MODULES:
                    return f"Import of '{root}' is not allowed in submissions."
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BANNED_MODULES:
                return f"Import of '{root}' is not allowed in submissions."
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            return f"Use of '{node.id}' is not allowed in submissions."
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            # Blocks the __class__ / __subclasses__ sandbox-escape chain.
            return f"Access to dunder attribute '{node.attr}' is not allowed."

    return None
