"""Routes each answer to the grader that suits its question type, then records
a per-answer confidence so low-certainty scores can be escalated to a human."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Answer, Attempt, Question
from . import plagiarism, semantic, static_analysis
from .code_runner import run_tests

# Correctness dominates; structure is a modifier, not a gate.
_TESTS_WEIGHT = 0.8
_QUALITY_WEIGHT = 0.2


def grade_answer(db: Session, answer: Answer, question: Question) -> None:
    if question.kind == "mcq":
        _grade_mcq(answer, question)
    elif question.kind == "coding":
        _grade_coding(db, answer, question)
    else:
        _grade_descriptive(db, answer, question)


def _grade_mcq(answer: Answer, question: Question) -> None:
    correct = answer.selected_option == question.correct_option
    answer.score = question.max_score if correct else 0.0
    answer.confidence = 1.0
    answer.needs_review = False
    answer.feedback = "Correct." if correct else "Incorrect option selected."
    answer.detail = {"selected": answer.selected_option, "correct": question.correct_option}


def _grade_coding(db: Session, answer: Answer, question: Question) -> None:
    tests = run_tests(answer.response_text, question.test_cases or [])
    quality = static_analysis.analyse(answer.response_text)

    # Structural quality modifies working code; it is not a consolation prize.
    # A submission that passes no tests scores zero however tidy it looks -
    # otherwise unmodified starter code earns marks for having no problems.
    if tests["ratio"] == 0:
        raw = 0.0
    else:
        raw = _TESTS_WEIGHT * tests["ratio"] + _QUALITY_WEIGHT * quality["quality"]
    answer.score = round(raw * question.max_score, 2)

    # A partial pass is the ambiguous case: the logic is close but wrong somewhere,
    # which is precisely where a human should look before the score stands.
    partial = 0 < tests["ratio"] < 1
    answer.confidence = 0.6 if partial else 1.0
    answer.needs_review = partial and not quality["parsed"]

    passed = sum(1 for case in tests["cases"] if case["passed"])
    answer.feedback = (
        f"{passed}/{len(tests['cases'])} test cases passed. "
        f"Estimated complexity: {quality.get('complexity_estimate', 'n/a')}."
    )
    answer.similarity_flag = _similarity_against_peers(db, answer, question)
    if plagiarism.is_suspicious(answer.similarity_flag):
        answer.needs_review = True
        answer.feedback += " Flagged: closely matches another submission."

    answer.detail = {
        "tests": [c for c in tests["cases"] if not c["hidden"]],
        "hidden_passed": sum(1 for c in tests["cases"] if c["hidden"] and c["passed"]),
        "hidden_total": sum(1 for c in tests["cases"] if c["hidden"]),
        "quality": quality,
    }


def _grade_descriptive(db: Session, answer: Answer, question: Question) -> None:
    result = semantic.grade(
        answer.response_text,
        question.reference_answer or "",
        question.rubric_keywords,
        question.max_score,
    )
    answer.score = result["score"]
    answer.confidence = result["confidence"]
    answer.needs_review = result["needs_review"]
    answer.feedback = result["feedback"]
    answer.similarity_flag = _similarity_against_peers(db, answer, question)
    if plagiarism.is_suspicious(answer.similarity_flag):
        answer.needs_review = True
        answer.feedback += " Flagged: closely matches another submission."
    answer.detail = {
        "similarity": result["similarity"],
        "coverage": result["coverage"],
        "missing_keywords": result["missing_keywords"],
        "backend": result["backend"],
    }


def _similarity_against_peers(db: Session, answer: Answer, question: Question) -> float:
    """Compare this answer against other *candidates'* submissions.

    A candidate who retakes an assessment naturally submits much the same answer
    again. Comparing against their own earlier attempts would flag them for
    copying themselves, which is both wrong and the fastest way to make examiners
    ignore the review queue. Only other people count as peers.
    """
    attempt = db.get(Attempt, answer.attempt_id)
    if attempt is None:
        return 0.0

    peers = db.scalars(
        select(Answer.response_text)
        .join(Attempt, Answer.attempt_id == Attempt.id)
        .where(
            Answer.question_id == question.id,
            Answer.id != answer.id,
            Attempt.user_id != attempt.user_id,
        )
    ).all()
    return round(plagiarism.max_similarity(answer.response_text, list(peers)), 3)
