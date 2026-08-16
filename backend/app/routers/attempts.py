from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import (
    code_claim, current_user, exam_claim, owns_or_controls, require_exam_access, require_staff
)
from ..network import require_exam_network
from ..evaluation.engine import grade_answer
from ..models import Answer, Assessment, Attempt, ProctorEvent, Question, User
from ..schemas import (
    AttemptOut, AttemptResult, ProctorEventIn, QuestionOut, ReviewIn, SubmitIn
)

router = APIRouter(prefix="/api/attempts", tags=["attempts"])


@router.post("/start/{assessment_id}", dependencies=[Depends(require_exam_network)])
def start_attempt(
    assessment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    claim: int | None = Depends(exam_claim),
    code_id: int | None = Depends(code_claim),
):
    require_exam_access(assessment_id, claim)
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")

    # One sitting per code. A submitted attempt ends that code for good; the
    # session token outlives the exam, so without this a candidate could return
    # to the paper and start again on the same sign-in.
    spent = db.scalar(
        select(Attempt).where(
            Attempt.user_id == user.id,
            Attempt.assessment_id == assessment_id,
            Attempt.status == "submitted",
            Attempt.access_code_id == code_id if code_id is not None else Attempt.id.is_(None),
        )
    )
    if spent:
        raise HTTPException(
            409,
            "You have already submitted this paper. If you need to sit it again, "
            "ask your invigilator to issue a new exam code.",
        )

    # Resuming is fine and expected — a browser crash mid-paper should not cost a
    # candidate their sitting, so an unfinished attempt is handed straight back.
    attempt = db.scalar(
        select(Attempt).where(
            Attempt.user_id == user.id,
            Attempt.assessment_id == assessment_id,
            Attempt.status == "in_progress",
        )
    )
    if attempt is None:
        questions = db.scalars(
            select(Question).where(Question.id.in_(assessment.question_ids))
        ).all()
        attempt = Attempt(
            user_id=user.id,
            assessment_id=assessment_id,
            access_code_id=code_id,
            max_score=sum(q.max_score for q in questions),
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

    # Time left is computed from when the attempt began, not from the duration.
    # Sending the full duration every time meant reloading the page reset the
    # clock, so a candidate could refresh their way through an unlimited exam.
    started = attempt.started_at.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    remaining = max(0, int(assessment.duration_minutes * 60 - elapsed))

    ordered = _ordered_questions(db, assessment)
    return {
        "attempt": AttemptOut.model_validate(attempt),
        "assessment": {
            "id": assessment.id,
            "title": assessment.title,
            "duration_minutes": assessment.duration_minutes,
            "seconds_remaining": remaining,
        },
        # Answer keys and test cases are never serialised to the candidate.
        "questions": [QuestionOut.model_validate(q) for q in ordered],
    }


def _ordered_questions(db: Session, assessment: Assessment) -> list[Question]:
    questions = db.scalars(
        select(Question).where(Question.id.in_(assessment.question_ids))
    ).all()
    by_id = {q.id: q for q in questions}
    return [by_id[qid] for qid in assessment.question_ids if qid in by_id]


@router.post("/{attempt_id}/events", status_code=204)
def log_event(
    attempt_id: int,
    payload: ProctorEventIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    attempt = _owned_attempt(db, attempt_id, user)
    elapsed = int((datetime.now(timezone.utc) - attempt.started_at.replace(tzinfo=timezone.utc)).total_seconds())
    db.add(ProctorEvent(
        attempt_id=attempt.id,
        question_id=payload.question_id,
        event_type=payload.event_type,
        detail=payload.detail[:255],
        seconds_into_attempt=max(0, elapsed),
    ))
    attempt.integrity_flags += 1
    db.commit()


@router.post("/{attempt_id}/submit", response_model=AttemptResult)
def submit_attempt(
    attempt_id: int,
    payload: SubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    attempt = _owned_attempt(db, attempt_id, user)
    if attempt.status == "submitted":
        raise HTTPException(409, "This attempt has already been submitted.")

    questions = {q.id: q for q in db.scalars(select(Question)).all()}
    total = 0.0

    for item in payload.answers:
        question = questions.get(item.question_id)
        if question is None:
            continue
        answer = Answer(
            attempt_id=attempt.id,
            question_id=question.id,
            response_text=item.response_text,
            selected_option=item.selected_option,
            seconds_spent=item.seconds_spent,
        )
        db.add(answer)
        db.flush()  # assign an id so peer-similarity can exclude this row
        grade_answer(db, answer, question)
        total += answer.score

    attempt.total_score = round(total, 2)
    attempt.status = "submitted"
    attempt.submitted_at = datetime.now(timezone.utc)

    # A submission arriving well past the deadline means the client clock was not
    # what stopped the candidate. Recorded rather than rejected: discarding the
    # work would punish someone whose connection dropped at the wrong moment.
    assessment = db.get(Assessment, attempt.assessment_id)
    if assessment:
        started = attempt.started_at.replace(tzinfo=timezone.utc)
        overrun = (attempt.submitted_at - started).total_seconds() - assessment.duration_minutes * 60
        if overrun > 60:
            db.add(ProctorEvent(
                attempt_id=attempt.id,
                event_type="late_submission",
                detail=f"Submitted {int(overrun // 60)} min after the deadline",
                seconds_into_attempt=int(assessment.duration_minutes * 60 + overrun),
            ))
            attempt.integrity_flags += 1
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/mine", response_model=list[AttemptOut])
def my_attempts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(
        select(Attempt).where(Attempt.user_id == user.id).order_by(Attempt.id.desc())
    ).all()


@router.get("/{attempt_id}", response_model=AttemptResult)
def get_attempt(
    attempt_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    attempt = db.get(Attempt, attempt_id)
    if not attempt or (attempt.user_id != user.id and user.role == "candidate"):
        raise HTTPException(404, "Attempt not found.")
    return attempt


@router.get("/review/queue")
def review_queue(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """Flagged answers, scoped to papers this examiner owns.

    A professor should not be marking another subject's scripts, and the exam
    office sees everything.
    """
    rows = db.scalars(select(Answer).where(Answer.needs_review.is_(True))).all()
    if user.role != "controller":
        allowed = {
            a.id for a in db.scalars(
                select(Assessment).where(Assessment.created_by == user.id)
            ).all()
        }
        rows = [
            r for r in rows
            if (db.get(Attempt, r.attempt_id).assessment_id if db.get(Attempt, r.attempt_id) else None) in allowed
        ]
    return [
        {
            "answer_id": row.id,
            "attempt_id": row.attempt_id,
            "question_id": row.question_id,
            "prompt": row.question.prompt,
            "response_text": row.response_text,
            "ai_score": row.score,
            "max_score": row.question.max_score,
            "confidence": row.confidence,
            "similarity_flag": row.similarity_flag,
            "feedback": row.feedback,
            "integrity_flags": [
                {"type": e.event_type, "detail": e.detail}
                for e in (db.get(Attempt, row.attempt_id).events if db.get(Attempt, row.attempt_id) else [])
                if e.question_id == row.question_id
            ],
        }
        for row in rows
    ]


@router.post("/review/{answer_id}", status_code=204)
def apply_review(
    answer_id: int, payload: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(404, "Answer not found.")
    attempt = db.get(Attempt, answer.attempt_id)
    paper = db.get(Assessment, attempt.assessment_id) if attempt else None
    if paper and not owns_or_controls(user, paper.created_by):
        raise HTTPException(403, "This answer belongs to another examiner's assessment.")
    attempt.total_score = round(attempt.total_score - answer.score + payload.score, 2)
    answer.score = payload.score
    answer.needs_review = False
    answer.confidence = 1.0
    answer.feedback = payload.feedback or "Score confirmed by examiner."
    db.commit()


def _owned_attempt(db: Session, attempt_id: int, user: User) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404, "Attempt not found.")
    return attempt
