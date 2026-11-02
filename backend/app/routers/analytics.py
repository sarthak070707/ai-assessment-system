"""Turns raw scores into the diagnostics that make an assessment useful:
where a candidate is weak, how they rank, and where they lost time."""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_staff
from ..models import Answer, Assessment, Attempt, ProctorEvent, Question, User

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Plain-language labels. "tab_switch" is a log entry; "Left the exam tab" is what
# an examiner needs to read at a glance while deciding whether to act.
EVENT_LABELS = {
    "tab_switch": "Left the exam tab",
    "window_blur": "Switched to another window",
    "fullscreen_exit": "Left full screen",
    "paste": "Pasted text into an answer",
    "late_submission": "Submitted after the deadline",
}


def _describe(event_type: str) -> str:
    return EVENT_LABELS.get(event_type, event_type.replace("_", " ").capitalize())


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


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

    # Group events by question first, so each row of the breakdown can carry its
    # own flags rather than the examiner cross-referencing a separate list.
    events = attempt.events
    per_question: dict[int | None, list] = defaultdict(list)
    by_type: dict[str, int] = defaultdict(int)
    for event in events:
        per_question[event.question_id].append(event)
        by_type[event.event_type] += 1

    buckets: dict[str, dict] = defaultdict(lambda: {"earned": 0.0, "possible": 0.0, "seconds": 0})
    timeline = []
    for answer in attempt.answers:
        question: Question = answer.question
        bucket = buckets[question.skill]
        bucket["earned"] += answer.score
        bucket["possible"] += question.max_score
        bucket["seconds"] += answer.seconds_spent
        flags = per_question.get(question.id, [])
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
            "flags": [
                {
                    "type": e.event_type,
                    "label": _describe(e.event_type),
                    "detail": e.detail,
                    "at": _clock(e.seconds_into_attempt),
                }
                for e in flags
            ],
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

    # Ranking depends on the paper type. Two candidates on an adaptive paper are
    # served different questions worth different marks, so their raw scores are
    # not on a common scale and comparing them is meaningless - 60% of an easier
    # five questions is not 60% of a harder five. The ability estimate exists
    # precisely because it *is* comparable: it accounts for which items were
    # asked. On a fixed paper everyone sat the same questions, so the raw score
    # is the right basis.
    paper = db.get(Assessment, attempt.assessment_id)
    adaptive_paper = bool(paper and paper.mode == "adaptive")

    if adaptive_paper:
        peers = db.scalars(
            select(Attempt.ability).where(
                Attempt.assessment_id == attempt.assessment_id,
                Attempt.status == "submitted",
            )
        ).all()
        percentile = _percentile(attempt.ability, list(peers))
        ranked_on = "ability"
    else:
        peers = db.scalars(
            select(Attempt.total_score).where(
                Attempt.assessment_id == attempt.assessment_id,
                Attempt.status == "submitted",
            )
        ).all()
        percentile = _percentile(attempt.total_score, list(peers))
        ranked_on = "score"

    weakest = sorted(skills, key=lambda s: s["proficiency"])[:3]
    return {
        "attempt_id": attempt.id,
        "total_score": attempt.total_score,
        "max_score": attempt.max_score,
        "percentage": round(100 * attempt.total_score / attempt.max_score, 1) if attempt.max_score else 0.0,
        "percentile": percentile,
        "ranked_on": ranked_on,
        "adaptive_paper": adaptive_paper,
        "cohort_size": len(peers),
        "adaptive": ({
            "ability_percent": __import__("app.evaluation.adaptive", fromlist=["x"]).to_percentage(attempt.ability),
            "ability_logit": attempt.ability,
            "precision": attempt.ability_se,
            "stop_reason": attempt.stop_reason,
            "questions_served": len(attempt.answers),
        } if attempt.stop_reason else None),
        "integrity_flags": attempt.integrity_flags,
        "integrity": {
            "total": len(events),
            "by_type": [
                {"type": t, "label": _describe(t), "count": n}
                for t, n in sorted(by_type.items(), key=lambda kv: -kv[1])
            ],
            # Events raised while no question was on screen - between questions,
            # or before the first one loaded.
            "unattributed": [
                {
                    "label": _describe(e.event_type),
                    "detail": e.detail,
                    "at": _clock(e.seconds_into_attempt),
                }
                for e in per_question.get(None, [])
            ],
        },
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
