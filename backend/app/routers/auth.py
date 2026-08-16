from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import current_user
from ..models import Assessment, ExamAccessCode, User
from ..network import require_exam_network
from ..schemas import ExamLogin, Token, UserCreate, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Create a staff account. Candidates are enrolled by an examiner, not self-served."""
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "That email is already registered.")
    if payload.role == "controller" and db.scalar(select(User).where(User.role == "controller")):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "An exam office account already exists. Further staff are added from inside the portal.",
        )
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role if payload.role in {"controller", "examiner"} else "examiner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def staff_login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Staff sign-in by staff ID or email.

    Both are accepted because professors know their staff ID while the exam
    office tends to work from email. They resolve to the same account either way.
    """
    identifier = form.username.strip()
    user = db.scalar(
        select(User).where(
            (User.staff_id == identifier.upper()) | (User.email == identifier.lower())
        )
    )
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Staff ID or password is incorrect.")
    if user.role not in {"controller", "examiner"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This is the staff portal. Candidates sign in with an enrolment number and exam code.",
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated.")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # A session is still issued when a password change is pending: the holder
    # needs one to reach the change-password route. Every other staff route
    # refuses it until the flag clears.
    return Token(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.post("/exam", response_model=Token, dependencies=[Depends(require_exam_network)])
def exam_login(payload: ExamLogin, request: Request, db: Session = Depends(get_db)):
    """Candidate sign-in: enrolment number plus a single-use code for one paper.

    Failures are reported with one generic message. Distinguishing 'no such
    enrolment number' from 'wrong code' would let someone probe the register to
    discover which candidates are scheduled for a paper.
    """
    rejection = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "That enrolment number and exam code do not match."
    )

    enrollment = payload.enrollment_no.strip()
    code = payload.access_code.strip().upper()

    user = db.scalar(select(User).where(User.enrollment_no == enrollment))
    if not user:
        raise rejection

    candidates = db.scalars(
        select(ExamAccessCode).where(
            ExamAccessCode.enrollment_no == enrollment,
            ExamAccessCode.revoked.is_(False),
        )
    ).all()

    record = next((c for c in candidates if verify_password(code, c.code_hash)), None)
    if record is None:
        raise rejection

    now = datetime.now(timezone.utc)
    if record.used_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This exam code has already been used. Ask the invigilator to issue a new one.",
        )
    if record.valid_from and now < record.valid_from.replace(tzinfo=timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This exam has not opened yet.")
    if record.valid_until and now > record.valid_until.replace(tzinfo=timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This exam code has expired.")

    assessment = db.get(Assessment, record.assessment_id)
    if not assessment or not assessment.is_published:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This assessment is not currently open.")

    record.used_at = now
    db.commit()

    return Token(
        access_token=create_access_token(
            user.id, user.role, exam_id=record.assessment_id, code_id=record.id
        ),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
