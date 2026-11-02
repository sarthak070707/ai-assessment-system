"""Shared fixtures.

Every test runs against its own throwaway database. Sharing one would make the
suite order-dependent — the plagiarism checks compare a submission against every
other submission for the same question, so a leftover row from an earlier test
silently changes a later result.

DATABASE_URL is set before app modules are imported because the engine is built
at import time from the settings object.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(monkeypatch):
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-used-anywhere-real")

    # Set to empty rather than deleted. config.py loads .env on import with
    # override=False, so a *deleted* key is simply restored from the file and the
    # suite quietly starts calling the live API - slow, billable and
    # non-deterministic. An empty value is already present, so the loader leaves
    # it alone, and is_configured() treats it as absent.
    monkeypatch.setenv("GROQ_API_KEY", "")

    for name in [m for m in list(sys.modules) if m.startswith("app")]:
        del sys.modules[name]

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c

    # Release the file before deleting it. Windows refuses to unlink a file that
    # is still open, so without disposing the engine every teardown raises
    # PermissionError; Linux allows it and hides the problem.
    from app.database import engine
    engine.dispose()
    try:
        os.unlink(path)
    except PermissionError:
        pass   # a stray handle should not fail an otherwise passing test


@pytest.fixture()
def db(client):
    from app.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


# --- builders --------------------------------------------------------------

@pytest.fixture()
def make_staff(db):
    from app.models import User
    from app.security import hash_password

    def _make(staff_id="CS100", role="examiner", subjects=("Algorithms",), password="pw-for-tests"):
        user = User(
            staff_id=staff_id, full_name=f"Staff {staff_id}", role=role,
            subjects=list(subjects), password_hash=hash_password(password), is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, password

    return _make


@pytest.fixture()
def make_candidate(db):
    from app.models import User

    def _make(enrollment="21BCS0001"):
        user = User(enrollment_no=enrollment, full_name=f"Candidate {enrollment}",
                    role="candidate", password_hash="")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture()
def auth(client):
    def _auth(identifier, password):
        r = client.post("/api/auth/login", data={"username": identifier, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    return _auth


@pytest.fixture()
def issue_code(db):
    """Issue an exam code directly, bypassing the API, for test setup."""
    from datetime import datetime, timedelta, timezone
    from app.models import ExamAccessCode
    from app.security import hash_password

    def _issue(assessment_id, enrollment, code="TEST-CODE"):
        db.add(ExamAccessCode(
            assessment_id=assessment_id, enrollment_no=enrollment,
            code_hash=hash_password(code),
            valid_until=datetime.now(timezone.utc) + timedelta(hours=2),
        ))
        db.commit()
        return code

    return _issue


@pytest.fixture()
def sit(client, issue_code):
    """Sign a candidate into a paper and return their auth header."""
    def _sit(assessment_id, enrollment, code=None):
        code = code or issue_code(assessment_id, enrollment, f"C-{assessment_id}-{enrollment}")
        r = client.post("/api/auth/exam",
                        json={"enrollment_no": enrollment, "access_code": code})
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    return _sit
