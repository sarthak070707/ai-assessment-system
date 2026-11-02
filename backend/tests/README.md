# Test suite

    cd backend
    pip install -r requirements.txt -r requirements-dev.txt
    pytest

If the API tests error with "requires the httpx2 package", that dependency is missing:
starlette's TestClient needs it to drive the app in-process. The 35 tests that touch
no HTTP will still pass without it, which is a useful signal in itself — it means the
grading and statistics are fine and only the transport is unconfigured.

105 tests, no network access required. Every test runs against its own throwaway
database — sharing one would make the suite order-dependent, since the plagiarism
checks compare a submission against every other submission for the same question
and a leftover row silently changes a later result.

| Module | Covers |
|---|---|
| `test_grading.py` | Scoring for the three question types; the code sandbox against hostile submissions; confidence escalation |
| `test_access_control.py` | Examiner isolation, subject boundaries, portal separation, staff account lifecycle |
| `test_exam_lifecycle.py` (17) | Exam codes, the clock, drafts and resumption, one sitting per code, integrity events |
| `test_adaptive.py` | The Rasch model, item selection, the serving loop, ability-based ranking |
| `test_import_and_integrity.py` | Document parsing, prompt-injection validation, plagiarism detection |

Two isolation details the suite depends on, both of which failed silently before being fixed:

**`GROQ_API_KEY` is set to empty, not deleted.** `config.py` loads `.env` on import with
`override=False`, so a deleted key is simply restored from the file and the suite starts calling the
live API — slow, billable and non-deterministic. An empty value is already present, so the loader
leaves it alone.

**The database engine is disposed before the temporary file is unlinked.** Windows refuses to delete
a file that is still open; Linux allows it and hides the problem entirely. Without this, every
teardown raises `PermissionError` on Windows while passing on Linux.

Several tests pin down specific defects and say so in their docstring, so that a
regression fails with an explanation rather than a bare assertion. The clock test
is the one to keep: without it, a paper could be sat indefinitely by reloading.
