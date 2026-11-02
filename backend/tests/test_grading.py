"""Grading behaviour for the three question types.

These cover the rules that decide a candidate's mark, so a regression here is
the most damaging kind: it is silent, and it is wrong in a direction nobody
notices until someone appeals.
"""
import pytest


# --- coding ----------------------------------------------------------------

CASES = [
    {"name": "pair", "entrypoint": "solve", "input": [[2, 7, 11, 15], 9], "expected": [0, 1]},
    {"name": "negatives", "entrypoint": "solve", "input": [[-3, 4, 3, 90], 0], "expected": [0, 2]},
    {"name": "hidden", "entrypoint": "solve", "input": [[1, 2], 3], "expected": [0, 1], "hidden": True},
]

LINEAR = ("def solve(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n"
          "        if target - n in seen:\n            return [seen[target - n], i]\n"
          "        seen[n] = i\n")
QUADRATIC = ("def solve(nums, target):\n    for i in range(len(nums)):\n"
             "        for j in range(i + 1, len(nums)):\n"
             "            if nums[i] + nums[j] == target:\n                return [i, j]\n")
UNTOUCHED = "def solve(nums, target):\n    # your code here\n    pass\n"


def score_code(source, max_score=15.0):
    from app.evaluation.code_runner import run_tests
    from app.evaluation import static_analysis

    tests = run_tests(source, CASES)
    quality = static_analysis.analyse(source)
    raw = 0.0 if tests["ratio"] == 0 else 0.8 * tests["ratio"] + 0.2 * quality["quality"]
    return round(raw * max_score, 2), tests


def test_unmodified_starter_code_scores_zero(client):
    """Structural quality must not be credited without correctness.

    Empty code genuinely has no structural faults, so crediting quality
    independently awarded 20% for submitting nothing.
    """
    score, tests = score_code(UNTOUCHED)
    assert tests["ratio"] == 0
    assert score == 0.0


def test_wrong_answer_scores_zero(client):
    score, _ = score_code("def solve(nums, target):\n    return [9, 9]\n")
    assert score == 0.0


def test_partial_pass_earns_partial_credit(client):
    source = ("def solve(nums, target):\n"
              "    if nums[0] + nums[1] == target:\n        return [0, 1]\n    return [0, 0]\n")
    score, tests = score_code(source)
    assert 0 < tests["ratio"] < 1
    assert 0 < score < 15.0


def test_complexity_separates_two_correct_solutions(client):
    """Both pass every test; the linear solution should still score higher."""
    linear, linear_tests = score_code(LINEAR)
    quadratic, quad_tests = score_code(QUADRATIC)
    assert linear_tests["ratio"] == quad_tests["ratio"] == 1.0
    assert linear > quadratic


# --- the sandbox -----------------------------------------------------------

@pytest.mark.parametrize("label,source", [
    ("infinite loop", "def solve(nums, target):\n    while True: pass\n"),
    ("memory bomb", "def solve(nums, target):\n    return [0] * (10 ** 9)\n"),
    ("file write", "def solve(nums, target):\n    open('/tmp/x','w').write('hi')\n    return [0,1]\n"),
    ("file read", "def solve(nums, target):\n    return open('/etc/passwd').read()\n"),
    ("import os", "import os\ndef solve(nums, target):\n    return os.listdir('/')\n"),
    ("subprocess", "import subprocess\ndef solve(nums, target):\n    return 1\n"),
    ("dunder escape", "def solve(nums, target):\n    return ().__class__.__bases__\n"),
])
def test_hostile_submissions_never_pass(client, label, source):
    from app.evaluation.code_runner import run_tests
    assert run_tests(source, CASES)["ratio"] == 0.0, label


def test_syntax_error_is_reported_not_crashed(client):
    from app.evaluation.code_runner import run_tests
    result = run_tests("def solve(nums, target)\n    return 1\n", CASES)
    assert result["ratio"] == 0.0
    assert "syntax" in result["cases"][0]["error"].lower()


# --- descriptive -----------------------------------------------------------

REFERENCE = ("An index is an auxiliary B-tree structure that stores a sorted mapping from column "
             "values to row locations, letting the database find matching rows without a full "
             "table scan. The trade-off is that every write must also update the index, so "
             "inserts get slower and the index consumes extra storage.")
KEYWORDS = ["b-tree", "full table scan", "write", "storage"]


def grade_text(answer, max_score=10.0):
    from app.evaluation import semantic
    return semantic.grade(answer, REFERENCE, KEYWORDS, max_score)


def test_strong_answer_outscores_weak_one(client):
    strong = grade_text("An index is a b-tree mapping column values to row locations, avoiding a "
                        "full table scan. Writes get slower and it uses extra storage.")
    weak = grade_text("An index makes the database faster when you search.")
    assert strong["score"] > weak["score"]


def test_empty_answer_scores_zero_with_full_confidence(client):
    """An empty answer is confidently zero, not uncertain — it must not reach review."""
    result = grade_text("")
    assert result["score"] == 0.0
    assert result["confidence"] == 1.0
    assert result["needs_review"] is False


def test_uncertain_answer_is_escalated_not_scored(client):
    """The central design decision: an uncertain score goes to a human."""
    result = grade_text("A queue decouples the producer from the consumer so neither needs to be "
                        "available at the same time, and buffers traffic spikes.")
    if result["needs_review"]:
        assert result["confidence"] < 1.0
    else:
        assert result["confidence"] == 1.0


def test_missing_keywords_are_reported(client):
    result = grade_text("An index speeds up lookups by avoiding a full table scan.")
    assert any(k in result["missing_keywords"] for k in ("b-tree", "storage"))


def test_grader_reports_which_backend_ran(client):
    """Without an API key the system must fall back, and say so."""
    from app.evaluation import semantic
    assert semantic.backend_name() == "tfidf"
