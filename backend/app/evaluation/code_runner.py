"""Executes candidate code against hidden test cases inside a constrained subprocess.

Isolation model
---------------
Each submission runs in a throwaway temp directory as a separate process with a
wall-clock timeout and (on Unix) hard rlimits on CPU time, address space and file
size. This blocks the common failure modes in a student-facing grader: infinite
loops, fork bombs, runaway allocation and disk filling.

It is NOT a security boundary against a determined attacker. For untrusted public
traffic, run each submission in a network-less container. The interface below is
deliberately identical for both modes.

Platform note: rlimits are Unix-only. On Windows the wall-clock timeout and the
AST guard in guard.py still apply, but there is no hard memory cap.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from ..config import get_settings
from .guard import check as guard_check

settings = get_settings()

_HARNESS = """
import sys, json
{source}

def _main():
    payload = json.loads(sys.stdin.read())
    args = payload["input"]
    fn = globals().get(payload["entrypoint"])
    if fn is None:
        raise NameError("Function '%s' is not defined." % payload["entrypoint"])
    result = fn(*args) if isinstance(args, list) else fn(args)
    sys.stdout.write(json.dumps(result, default=str))

_main()
"""


def _child_env(workdir: str) -> dict:
    """Minimal environment for the sandboxed child.

    Windows needs SYSTEMROOT and a real PATH or the interpreter cannot even
    initialise (os.urandom and socket setup fail during startup), so the
    environment is built per platform rather than hardcoded.
    """
    if os.name == "nt":
        return {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
            "TEMP": workdir,
            "TMP": workdir,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    return {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}


def _limits():
    """Applied in the child process just before exec (Unix only)."""
    import resource

    mem = settings.code_memory_mb * 1024 * 1024
    cpu = settings.code_timeout_seconds
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))


def run_tests(source: str, test_cases: list[dict]) -> dict:
    """Run `source` against each test case.

    Each test case: {"input": [...], "expected": <json>, "hidden": bool, "name": str}
    Returns a per-case report plus the pass ratio used for scoring.
    """
    if not test_cases:
        return {"ratio": 0.0, "cases": [], "error": "No test cases defined."}

    rejection = guard_check(source)
    if rejection:
        return {
            "ratio": 0.0,
            "cases": [
                {"name": c.get("name", f"Case {i + 1}"), "hidden": bool(c.get("hidden")),
                 "passed": False, "error": rejection}
                for i, c in enumerate(test_cases)
            ],
            "error": rejection,
        }

    entrypoint = test_cases[0].get("entrypoint", "solve")
    results, passed = [], 0

    with tempfile.TemporaryDirectory() as workdir:
        script = os.path.join(workdir, "submission.py")
        with open(script, "w") as fh:
            fh.write(_HARNESS.format(source=source))

        for index, case in enumerate(test_cases):
            payload = f'{{"input": {_json(case.get("input"))}, "entrypoint": "{case.get("entrypoint", entrypoint)}"}}'
            record = {
                "name": case.get("name", f"Case {index + 1}"),
                "hidden": bool(case.get("hidden", False)),
                "passed": False,
                "error": "",
            }
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-S", script],
                    input=payload,
                    capture_output=True,
                    text=True,
                    timeout=settings.code_timeout_seconds,
                    cwd=workdir,
                    env=_child_env(workdir),
                    # rlimits are a Unix facility. On Windows the wall-clock
                    # timeout and the AST guard are the active protections.
                    preexec_fn=_limits if os.name == "posix" else None,
                )
            except subprocess.TimeoutExpired:
                record["error"] = f"Timed out after {settings.code_timeout_seconds}s."
                results.append(record)
                continue

            if proc.returncode != 0:
                # A negative return code means the child was killed by a signal.
                # SIGXCPU (-24) is the CPU rlimit firing before the wall clock,
                # so report it as the timeout it actually is.
                if proc.returncode < 0:
                    record["error"] = (
                        f"Exceeded the {settings.code_timeout_seconds}s CPU limit."
                        if proc.returncode == -24
                        else "Terminated: exceeded a resource limit."
                    )
                else:
                    record["error"] = _last_line(proc.stderr) or "Runtime error."
                results.append(record)
                continue

            actual = proc.stdout.strip()
            expected = _json(case.get("expected")).strip()
            record["passed"] = _equal(actual, expected)
            if not record["passed"]:
                record["error"] = "Wrong output."
                if not record["hidden"]:
                    record["expected"] = expected
                    record["actual"] = actual
            passed += int(record["passed"])
            results.append(record)

    return {"ratio": passed / len(test_cases), "cases": results, "error": ""}


def _json(value) -> str:
    import json

    return json.dumps(value)


def _equal(actual: str, expected: str) -> bool:
    import json

    try:
        return json.loads(actual) == json.loads(expected)
    except (json.JSONDecodeError, ValueError):
        return actual == expected


def _last_line(stderr: str) -> str:
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""
