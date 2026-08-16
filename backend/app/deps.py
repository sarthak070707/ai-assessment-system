from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again.")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found.")
    return user


STAFF_ROLES = {"controller", "examiner"}


def require_staff(user: User = Depends(current_user)) -> User:
    """Any signed-in member of staff, with a pending password change blocking access.

    The block is enforced here rather than in the UI so a temporary password
    cannot be used against the API directly while the interface pretends the
    account is locked.
    """
    if user.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff access required.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated.")
    if user.must_change_password:
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "Set a new password before continuing.",
        )
    return user


def require_controller(user: User = Depends(require_staff)) -> User:
    """The exam office: creates staff accounts and oversees every subject."""
    if user.role != "controller":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the exam office can do that.",
        )
    return user


# Kept as an alias so existing call sites read naturally.
require_admin = require_controller


def owns_or_controls(user: User, created_by: int | None) -> bool:
    """Whether `user` may modify content authored by `created_by`.

    Unowned content - anything seeded before ownership existed - is editable by
    the exam office only, rather than by whoever happens to open it first.
    """
    if user.role == "controller":
        return True
    return created_by is not None and created_by == user.id


def require_ownership(user: User, created_by: int | None, noun: str = "item") -> None:
    if not owns_or_controls(user, created_by):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This {noun} belongs to another examiner. Ask them or the exam office to change it.",
        )


def exam_claim(token: str = Depends(oauth2_scheme)) -> int | None:
    """The assessment a candidate's token was issued for, if any."""
    payload = decode_access_token(token) or {}
    return payload.get("exam")


def code_claim(token: str = Depends(oauth2_scheme)) -> int | None:
    """The access code that opened this session, if any."""
    payload = decode_access_token(token) or {}
    return payload.get("code")


def require_exam_access(assessment_id: int, claim: int | None) -> None:
    """A candidate token opens exactly the paper its code was issued for.

    Checked against the token rather than re-read from the request, so altering
    the id in the URL cannot widen access beyond what was granted at sign-in.
    """
    if claim is not None and claim != assessment_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your exam code was issued for a different assessment.",
        )
