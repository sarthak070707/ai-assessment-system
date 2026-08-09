"""Examiner tools for enrolling candidates and issuing exam codes."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import owns_or_controls, require_staff
from ..models import Assessment, ExamAccessCode, User
from ..schemas import AccessCodeOut, CandidateCreate, IssueCodes, IssuedCode, UserOut
from ..security import generate_access_code, hash_password

router = APIRouter(prefix="/api/candidates", tags=["candidates"])
settings = get_settings()


@router.get("", response_model=list[UserOut])
def list_candidates(db: Session = Depends(get_db), _=Depends(require_staff)):
    return db.scalars(
        select(User).where(User.role == "candidate").order_by(User.enrollment_no)
    ).all()


@router.post("", response_model=UserOut, status_code=201)
def enrol_candidate(
    payload: CandidateCreate, db: Session = Depends(get_db), _=Depends(require_staff)
):
    """Register a candidate against their enrolment number.

    No password is set. Candidates never hold a standing credential - access is
    granted per exam, by code, and expires with it.
    """
    enrollment = payload.enrollment_no.strip().upper()
    if not enrollment:
        raise HTTPException(400, "An enrolment number is required.")
    if db.scalar(select(User).where(User.enrollment_no == enrollment)):
        raise HTTPException(409, f"{enrollment} is already enrolled.")

    user = User(
        enrollment_no=enrollment,
        full_name=payload.full_name.strip() or enrollment,
        role="candidate",
        password_hash="",   # unusable: candidates authenticate by exam code only
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/codes", response_model=list[IssuedCode], status_code=201)
def issue_codes(
    payload: IssueCodes, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    """Generate one-time exam codes for a list of enrolment numbers.

    The plaintext codes are returned once, here, for the examiner to distribute.
    Only hashes are stored, so this response cannot be reproduced later - if a
    code is lost, issue a fresh one rather than looking the old one up.
    """
    assessment = db.get(Assessment, payload.assessment_id)
    if not assessment or not owns_or_controls(user, assessment.created_by):
        raise HTTPException(404, "Assessment not found.")

    hours = payload.valid_hours or settings.access_code_hours
    valid_until = datetime.now(timezone.utc) + timedelta(hours=hours)

    issued: list[IssuedCode] = []
    for raw in payload.enrollment_numbers:
        enrollment = raw.strip().upper()
        if not enrollment:
            continue
        user = db.scalar(select(User).where(User.enrollment_no == enrollment))
        if not user:
            raise HTTPException(400, f"{enrollment} is not enrolled. Add them first.")

        # Supersede any unused code for the same paper, so a reissue invalidates
        # the previous slip rather than leaving two live codes in circulation.
        previous = db.scalars(
            select(ExamAccessCode).where(
                ExamAccessCode.enrollment_no == enrollment,
                ExamAccessCode.assessment_id == payload.assessment_id,
                ExamAccessCode.used_at.is_(None),
                ExamAccessCode.revoked.is_(False),
            )
        ).all()
        for old in previous:
            old.revoked = True

        code = generate_access_code()
        db.add(ExamAccessCode(
            assessment_id=payload.assessment_id,
            enrollment_no=enrollment,
            code_hash=hash_password(code),
            valid_until=valid_until,
        ))
        issued.append(IssuedCode(
            enrollment_no=enrollment, full_name=user.full_name,
            access_code=code, valid_until=valid_until,
        ))

    db.commit()
    return issued


@router.get("/codes/{assessment_id}", response_model=list[AccessCodeOut])
def list_codes(
    assessment_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    """Status of every code issued for an assessment. Plaintext is never returned."""
    paper = db.get(Assessment, assessment_id)
    if not paper or not owns_or_controls(user, paper.created_by):
        raise HTTPException(404, "Assessment not found.")
    return db.scalars(
        select(ExamAccessCode)
        .where(ExamAccessCode.assessment_id == assessment_id)
        .order_by(ExamAccessCode.enrollment_no)
    ).all()


@router.post("/codes/{code_id}/revoke", status_code=204)
def revoke_code(code_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    record = db.get(ExamAccessCode, code_id)
    if not record:
        raise HTTPException(404, "Code not found.")
    paper = db.get(Assessment, record.assessment_id)
    if paper and not owns_or_controls(user, paper.created_by):
        raise HTTPException(404, "Code not found.")
    record.revoked = True
    db.commit()
