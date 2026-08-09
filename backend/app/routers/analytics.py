"""Turns raw scores into the diagnostics that make an assessment useful:
where a candidate is weak, how they rank, and where they lost time."""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_staff
from ..models import Answer, Assessment, Attempt, Question, User

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/attempt/{attempt_id}")
def attempt_analytics(
    attempt_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    attempt = db.get(Attempt, attempt_id)
    if not attempt or (attempt.user_id != user.id and user.role == "candidate"):
        raise HTTPException(404, "Attempt not found.")
    if user.role == "examiner" and attempt.user_id != user.id:
        paper = db.get(Assessment, attempt.assessment_id)
        if paper and paper.created_by != user.id:
            raise HTTPException(404, "Attempt not found.")

    buckets: dict[str, dict] = defaultdict(lambda: {"earned": 0.0, "possible": 0.0, "seconds": 0})
    timeline = []
    for answer in attempt.answers:
        question: Question = answer.question
        bucket = buckets[question.skill]
        bucket["earned"] += answer.score
        bucket["possible"] += question.max_score
        bucket["seconds"] += answer.seconds_spent
        timeline.append({
            "question_id": question.id,
            "skill": question.skill,
            "kind": question.kind,
            "difficulty": question.difficulty,
            "score": answer.score,
            "max_score": question.max_score,
            "seconds_spent": answer.seconds_spent,
            "confidence": answer.confidence,
            "needs_review": answer.needs_review,
        })

    skills = [
        {
            "skill": skill,
            "earned": round(data["earned"], 2),
            "possible": round(data["possible"], 2),
            "proficiency": round(100 * data["earned"] / data["possible"], 1) if data["possible"] else 0.0,
            "seconds": data["seconds"],
        }
        for skill, data in sorted(buckets.items())
    ]

    peers = db.scalars(
        select(Attempt.total_score).where(
            Attempt.assessment_id == attempt.assessment_id, Attempt.status == "submitted"
        )
    ).all()
    percentile = _percentile(attempt.total_score, list(peers))

    weakest = sorted(skills, key=lambda s: s["proficiency"])[:3]
    return {
        "attempt_id": attempt.id,
        "total_score": attempt.total_score,
        "max_score": attempt.max_score,
        "percentage": round(100 * attempt.total_score / attempt.max_score, 1) if attempt.max_score else 0.0,
        "percentile": percentile,
        "cohort_size": len(peers),
        "integrity_flags": attempt.integrity_flags,
        "skills": skills,
        "timeline": timeline,
        "recommendations": [
            f"Revise {s['skill']} - currently at {s['proficiency']}%."
            for s in weakest if s["proficiency"] < 70
        ] or ["No weak areas detected in this attempt."],
    }


@router.get("/assessment/{assessment_id}")
def cohort_analytics(
    assessment_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    paper = db.get(Assessment, assessment_id)
    if not paper or (user.role == "examiner" and paper.created_by != user.id):
        raise HTTPException(404, "Assessment not found.")
    attempts = db.scalars(
        select(Attempt).where(
            Attempt.assessment_id == assessment_id, Attempt.status == "submitted"
        )
    ).all()
    if not attempts:
        return {"cohort_size": 0, "average": 0, "skills": [], "hardest_questions": []}

    scores = [a.total_score for a in attempts]
    buckets: dict[str, dict] = defaultdict(lambda: {"earned": 0.0, "possible": 0.0})
    per_question: dict[int, dict] = defaultdict(lambda: {"earned": 0.0, "possible": 0.0, "prompt": ""})

    for attempt in attempts:
        for answer in attempt.answers:
            question: Question = answer.question
            buckets[question.skill]["earned"] += answer.score
            buckets[question.skill]["possible"] += question.max_score
            row = per_question[question.id]
            row["earned"] += answer.score
            row["possible"] += question.max_score
            row["prompt"] = question.prompt[:90]

    hardest = sorted(
        (
            {
                "question_id": qid,
                "prompt": row["prompt"],
                "average_percent": round(100 * row["earned"] / row["possible"], 1) if row["possible"] else 0.0,
            }
            for qid, row in per_question.items()
        ),
        key=lambda r: r["average_percent"],
    )[:5]

    return {
        "cohort_size": len(attempts),
        "average": round(sum(scores) / len(scores), 2),
        "highest": max(scores),
        "lowest": min(scores),
        "flagged_answers": db.scalar(
            select(Answer.id).where(Answer.needs_review.is_(True)).limit(1)
        ) is not None,
        "skills": [
            {
                "skill": skill,
                "proficiency": round(100 * data["earned"] / data["possible"], 1) if data["possible"] else 0.0,
            }
            for skill, data in sorted(buckets.items())
        ],
        "hardest_questions": hardest,
    }


def _percentile(score: float, cohort: list[float]) -> float:
    if not cohort:
        return 0.0
    below = sum(1 for value in cohort if value < score)
    return round(100 * below / len(cohort), 1)
