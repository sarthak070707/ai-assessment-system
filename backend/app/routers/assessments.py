from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import (
    code_claim, current_user, exam_claim, owns_or_controls, require_ownership, require_staff
)
from ..models import Assessment, Attempt, Question, User
from ..schemas import AssessmentCreate, AssessmentOut

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


def _with_author(a: Assessment) -> AssessmentOut:
    out = AssessmentOut.model_validate(a)
    out.author_name = a.author.full_name if a.author else None
    return out


@router.get("", response_model=list[AssessmentOut])
def list_assessments(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    exam: int | None = Depends(exam_claim),
    code_id: int | None = Depends(code_claim),
):
    """Candidates see published papers. Examiners see only their own. The office sees all.

    For a candidate each paper also carries whether *this session* can sit it.
    Working that out in the browser is not possible: it depends on which code
    opened the session, and the browser only knows which papers exist. Deciding
    it here is also what stops the page offering a button that would be refused.
    """
    stmt = select(Assessment).order_by(Assessment.id)
    if user.role == "candidate":
        stmt = stmt.where(Assessment.is_published.is_(True))
    elif user.role == "examiner":
        stmt = stmt.where(Assessment.created_by == user.id)

    papers = [_with_author(a) for a in db.scalars(stmt).all()]
    if user.role != "candidate":
        return papers

    for paper in papers:
        # A candidate token is scoped to one paper; the rest are visible but shut.
        paper.opens_with_your_code = exam is None or exam == paper.id

        paper.sitting_used = db.scalar(
            select(Attempt.id).where(
                Attempt.user_id == user.id,
                Attempt.assessment_id == paper.id,
                Attempt.status == "submitted",
                Attempt.access_code_id == code_id,
            ).limit(1)
        ) is not None

        paper.in_progress = db.scalar(
            select(Attempt.id).where(
                Attempt.user_id == user.id,
                Attempt.assessment_id == paper.id,
                Attempt.status == "in_progress",
            ).limit(1)
        ) is not None

    return papers


@router.get("/{assessment_id}", response_model=AssessmentOut)
def get_assessment(
    assessment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")
    if user.role == "examiner" and not owns_or_controls(user, assessment.created_by):
        raise HTTPException(404, "Assessment not found.")
    return _with_author(assessment)


def _check_questions(db: Session, question_ids: list[int], user: User) -> None:
    """Validate the question set, and that the examiner owns every question in it.

    Without this an examiner could assemble a paper out of a colleague's
    questions by posting their ids directly, which would expose the very content
    the bank isolation exists to protect.
    """
    if not question_ids:
        raise HTTPException(400, "An assessment needs at least one question.")

    questions = db.scalars(select(Question).where(Question.id.in_(question_ids))).all()
    missing = set(question_ids) - {q.id for q in questions}
    if missing:
        raise HTTPException(400, f"These questions no longer exist: {sorted(missing)}")

    if user.role != "controller":
        foreign = [q.id for q in questions if q.created_by != user.id]
        if foreign:
            raise HTTPException(
                403, f"You can only use your own questions. Not yours: {sorted(foreign)}"
            )


@router.post("", response_model=AssessmentOut, status_code=201)
def create_assessment(
    payload: AssessmentCreate, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    _check_questions(db, payload.question_ids, user)
    assessment = Assessment(**payload.model_dump(), created_by=user.id)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _with_author(assessment)


@router.put("/{assessment_id}", response_model=AssessmentOut)
def update_assessment(
    assessment_id: int,
    payload: AssessmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")
    require_ownership(user, assessment.created_by, "assessment")
    _check_questions(db, payload.question_ids, user)

    # Changing the question set mid-cohort would make results incomparable
    # between candidates who sat different versions of the same paper.
    in_progress = db.scalar(
        select(Attempt.id).where(
            Attempt.assessment_id == assessment_id, Attempt.status == "in_progress"
        ).limit(1)
    )
    if in_progress and set(payload.question_ids) != set(assessment.question_ids or []):
        raise HTTPException(
            409,
            "A candidate is partway through this assessment. You can edit the title and "
            "duration, but not the questions until they finish.",
        )

    for field, value in payload.model_dump().items():
        setattr(assessment, field, value)
    db.commit()
    db.refresh(assessment)
    return _with_author(assessment)


@router.post("/{assessment_id}/publish", response_model=AssessmentOut)
def toggle_publish(
    assessment_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    """Publish or unpublish. Unpublished assessments are hidden from candidates."""
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")
    require_ownership(user, assessment.created_by, "assessment")
    assessment.is_published = not assessment.is_published
    db.commit()
    db.refresh(assessment)
    return _with_author(assessment)


@router.delete("/{assessment_id}", status_code=204)
def delete_assessment(
    assessment_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")
    require_ownership(user, assessment.created_by, "assessment")
    attempted = db.scalar(
        select(Attempt.id).where(Attempt.assessment_id == assessment_id).limit(1)
    )
    if attempted:
        raise HTTPException(
            409,
            "Candidates have already attempted this assessment, so deleting it would "
            "destroy their results. Unpublish it instead.",
        )
    db.delete(assessment)
    db.commit()
