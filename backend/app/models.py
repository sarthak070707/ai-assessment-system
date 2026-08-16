from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Three kinds of account, distinguished by how they are identified.

      controller - the exam office. Creates staff accounts, sees everything.
      examiner   - a professor. Signs in with a staff ID, owns the questions and
                   papers they create, and cannot edit a colleague's.
      candidate  - a student. Enrolment number, no standing password at all.

    Each has its own identifier because each is issued by a different process:
    staff IDs come from HR, enrolment numbers from the student register. Forcing
    everyone onto email would create identities nobody's records are keyed on.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    staff_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    enrollment_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)

    full_name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Subjects this examiner is assigned to teach. Questions may only be written
    # within them, so a professor cannot author into a colleague's subject even
    # by typing its name - which free-text tagging allowed.
    subjects: Mapped[list | None] = mapped_column(JSON, nullable=True)

    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="candidate")

    # Set when an account is created with a temporary password. Every staff route
    # is refused until it clears, so an account issued by the exam office cannot
    # keep running on a password that office still knows.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempts: Mapped[list["Attempt"]] = relationship(back_populates="user")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # mcq | coding | descriptive
    skill: Mapped[str] = mapped_column(String(60), index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    prompt: Mapped[str] = mapped_column(Text)
    max_score: Mapped[float] = mapped_column(Float, default=10.0)

    # mcq
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_option: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # coding
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_cases: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # descriptive
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric_keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Ownership. The bank is readable by all staff so questions can be shared
    # across subjects, but only the author (or the exam office) may change one.
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    author: Mapped["User | None"] = relationship()


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=45)
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    author: Mapped["User | None"] = relationship()


class Attempt(Base):
    """One sitting of one paper by one candidate.

    Tied to the access code that opened it, not just to the paper. A candidate
    gets one attempt per code: submitting ends that sitting for good, and a
    re-sit requires the invigilator to issue a fresh code. This is how an
    invigilated exam already works — a machine dies, the candidate is re-admitted
    with a new slip — and it means "no retakes" does not need a separate override
    that could be misused.
    """

    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"))
    access_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_access_codes.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)
    integrity_flags: Mapped[int] = mapped_column(Integer, default=0)

    # Work in progress, saved periodically while the paper is open. Held as a
    # blob on the attempt rather than as Answer rows so that unsubmitted drafts
    # never reach the grader or the plagiarism comparison, which reads every
    # other submission for the same question.
    draft_answers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    draft_saved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="attempts")
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )
    events: Mapped[list["ProctorEvent"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))

    response_text: Mapped[str] = mapped_column(Text, default="")
    selected_option: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seconds_spent: Mapped[int] = mapped_column(Integer, default=0)

    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    similarity_flag: Mapped[float] = mapped_column(Float, default=0.0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    attempt: Mapped["Attempt"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship()


class ExamAccessCode(Base):
    """A single-use code admitting one enrolment number to one assessment.

    Modelled on how invigilated exams actually issue access: the code is tied to
    both the candidate and the paper, is valid for a stated window, and is spent
    once used. A permanent password would let a candidate re-enter a paper they
    have already sat, or sit a paper they were never scheduled for.

    Only the hash is stored. The plaintext is shown to the examiner once, at
    generation, and cannot be recovered afterwards - the same reason passwords
    are hashed, and it means a leaked database does not hand over exam access.
    """

    __tablename__ = "exam_access_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"))
    enrollment_no: Mapped[str] = mapped_column(String(40), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))

    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    assessment: Mapped["Assessment"] = relationship()


class ProctorEvent(Base):
    """One integrity signal, tied to the question that was on screen.

    A bare count tells an examiner something happened but not what or where.
    Three tab switches spread evenly across a paper reads very differently from
    three during one hard question, and only the second is worth asking about.
    """

    __tablename__ = "proctor_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"))
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(String(255), default="")
    seconds_into_attempt: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempt: Mapped["Attempt"] = relationship(back_populates="events")
