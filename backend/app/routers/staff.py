"""Exam-office management of professor accounts."""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_controller
from ..models import Assessment, Question, User
from ..schemas import PasswordChange, StaffCreate, StaffOut, StaffUpdate, TempCredential
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api/staff", tags=["staff"])

_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _temp_password() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(10))


@router.get("", response_model=list[StaffOut])
def list_staff(db: Session = Depends(get_db), _=Depends(require_controller)):
    return db.scalars(
        select(User).where(User.role.in_(["controller", "examiner"])).order_by(User.staff_id)
    ).all()


@router.post("", response_model=TempCredential, status_code=201)
def create_staff(
    payload: StaffCreate, db: Session = Depends(get_db), _=Depends(require_controller)
):
    """Create a professor account with a one-time temporary password.

    The password is returned once, here. It is stored only as a hash, and the
    account is flagged so every staff route is refused until the holder replaces
    it — so the exam office cannot keep working access to an account it issued.
    """
    staff_id = payload.staff_id.strip().upper()
    if not staff_id:
        raise HTTPException(400, "A staff ID is required.")
    if db.scalar(select(User).where(User.staff_id == staff_id)):
        raise HTTPException(409, f"Staff ID {staff_id} is already in use.")
    if payload.email and db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "That email is already registered.")
    if payload.role not in {"controller", "examiner"}:
        raise HTTPException(400, "Role must be controller or examiner.")

    temporary = _temp_password()
    subjects = sorted({s.strip() for s in payload.subjects if s.strip()})
    if payload.role == "examiner" and not subjects:
        raise HTTPException(
            400,
            "Assign at least one subject. An examiner can only write questions "
            "within the subjects they teach.",
        )

    user = User(
        staff_id=staff_id,
        email=payload.email or None,
        full_name=payload.full_name.strip() or staff_id,
        department=payload.department or None,
        subjects=subjects,
        role=payload.role,
        password_hash=hash_password(temporary),
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TempCredential(
        staff_id=user.staff_id, full_name=user.full_name, temporary_password=temporary
    )


@router.put("/{user_id}", response_model=StaffOut)
def update_staff(
    user_id: int, payload: StaffUpdate, db: Session = Depends(get_db), _=Depends(require_controller)
):
    """Adjust a staff member's details, including which subjects they teach.

    Removing a subject does not touch questions already written in it. Those stay
    with their author and remain gradeable; the restriction applies to new work.
    """
    user = db.get(User, user_id)
    if not user or user.role not in {"controller", "examiner"}:
        raise HTTPException(404, "Staff member not found.")

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or user.full_name
    if payload.department is not None:
        user.department = payload.department or None
    if payload.subjects is not None:
        cleaned = sorted({s.strip() for s in payload.subjects if s.strip()})
        if user.role == "examiner" and not cleaned:
            raise HTTPException(400, "An examiner needs at least one subject.")
        user.subjects = cleaned

    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset", response_model=TempCredential)
def reset_password(user_id: int, db: Session = Depends(get_db), _=Depends(require_controller)):
    """Issue a fresh temporary password, e.g. when a professor is locked out."""
    user = db.get(User, user_id)
    if not user or user.role not in {"controller", "examiner"}:
        raise HTTPException(404, "Staff member not found.")
    temporary = _temp_password()
    user.password_hash = hash_password(temporary)
    user.must_change_password = True
    db.commit()
    return TempCredential(
        staff_id=user.staff_id, full_name=user.full_name, temporary_password=temporary
    )


@router.post("/{user_id}/deactivate", response_model=StaffOut)
def toggle_active(user_id: int, db: Session = Depends(get_db), me: User = Depends(require_controller)):
    user = db.get(User, user_id)
    if not user or user.role not in {"controller", "examiner"}:
        raise HTTPException(404, "Staff member not found.")
    if user.id == me.id:
        raise HTTPException(400, "You cannot deactivate your own account.")

    # Deactivating rather than deleting: their questions and papers stay
    # attributed, and results already graded remain traceable to an author.
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}/content")
def staff_content(user_id: int, db: Session = Depends(get_db), _=Depends(require_controller)):
    """What a staff member owns — checked before deactivating them."""
    return {
        "questions": db.scalar(
            select(Question.id).where(Question.created_by == user_id).limit(1)
        ) is not None,
        "question_count": len(db.scalars(select(Question.id).where(Question.created_by == user_id)).all()),
        "assessment_count": len(db.scalars(select(Assessment.id).where(Assessment.created_by == user_id)).all()),
    }


@router.post("/change-password", status_code=204)
def change_password(
    payload: PasswordChange, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """Replace your own password.

    Deliberately depends on `current_user`, not `require_staff`: an account with
    a pending password change is blocked everywhere else, so if this route
    demanded a cleared flag the holder could never clear it.
    """
    if user.role not in {"controller", "examiner"}:
        raise HTTPException(403, "Candidates sign in with a single-use exam code instead.")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(401, "Your current password is incorrect.")
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Choose a password of at least 8 characters.")
    if payload.new_password == payload.current_password:
        raise HTTPException(400, "The new password must be different from the current one.")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()
