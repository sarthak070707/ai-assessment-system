from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import owns_or_controls, require_controller, require_ownership, require_staff
from ..models import Answer, Assessment, Question, User
from ..importer import extract_questions, extract_text
from ..schemas import (
    ImportCommitIn, ImportPreviewIn, ImportPreviewOut, QuestionAdminOut, QuestionCreate
)

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _with_author(question: Question) -> QuestionAdminOut:
    out = QuestionAdminOut.model_validate(question)
    out.author_name = question.author.full_name if question.author else None
    return out


@router.get("", response_model=list[QuestionAdminOut])
def list_questions(
    skill: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    """An examiner sees only their own questions. The exam office sees all.

    Read access is restricted, not just write. An unsat question bank *is* the
    exam paper: a colleague who can read it can leak it, whether carelessly or
    otherwise. Convenience of reuse across subjects is not worth that exposure,
    so isolation is the default and the exam office is the only shared view.
    """
    stmt = select(Question)
    if user.role != "controller":
        stmt = stmt.where(Question.created_by == user.id)
    if skill:
        stmt = stmt.where(Question.skill == skill)
    if kind:
        stmt = stmt.where(Question.kind == kind)
    return [_with_author(q) for q in db.scalars(stmt.order_by(Question.id)).all()]


def _check_subject(payload: QuestionCreate, user: User) -> None:
    """An examiner may only write within the subjects they are assigned.

    Enforced here rather than by limiting the dropdown, because the dropdown is
    a convenience and the API is the boundary.
    """
    if user.role == "controller":
        return
    allowed = user.subjects or []
    if not allowed:
        raise HTTPException(
            403, "You have no subjects assigned. Ask the exam office to assign one."
        )
    if payload.skill.strip() not in allowed:
        raise HTTPException(
            403,
            f"'{payload.skill}' is not one of your subjects. You teach: {', '.join(allowed)}.",
        )


def _validate(payload: QuestionCreate) -> None:
    """Reject questions the grader could not score, at write time.

    Catching this here rather than during grading matters: a question missing its
    answer key only fails when a candidate is midway through an exam, which is the
    worst possible moment to discover it.
    """
    if payload.kind not in {"mcq", "coding", "descriptive"}:
        raise HTTPException(400, "Type must be mcq, coding or descriptive.")

    if payload.kind == "mcq":
        if not payload.options or len(payload.options) < 2:
            raise HTTPException(400, "Multiple choice questions need at least two options.")
        if payload.correct_option is None:
            raise HTTPException(400, "Select which option is correct.")
        if not 0 <= payload.correct_option < len(payload.options):
            raise HTTPException(400, "The correct option must be one of the options listed.")
        if any(not o.strip() for o in payload.options):
            raise HTTPException(400, "Options cannot be blank.")

    if payload.kind == "coding":
        if not payload.test_cases:
            raise HTTPException(400, "Coding questions need at least one test case.")
        for index, case in enumerate(payload.test_cases, start=1):
            if "input" not in case or "expected" not in case:
                raise HTTPException(400, f"Test case {index} needs both an input and an expected output.")
            if not str(case.get("entrypoint", "")).strip():
                raise HTTPException(400, f"Test case {index} needs a function name to call.")

    if payload.kind == "descriptive" and not (payload.reference_answer or "").strip():
        raise HTTPException(400, "Descriptive questions need a reference answer to grade against.")

    if not payload.prompt.strip():
        raise HTTPException(400, "The question text cannot be empty.")
    if payload.max_score <= 0:
        raise HTTPException(400, "Marks must be greater than zero.")


@router.post("", response_model=QuestionAdminOut, status_code=201)
def create_question(
    payload: QuestionCreate, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    _validate(payload)
    _check_subject(payload, user)
    question = Question(**payload.model_dump(), created_by=user.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    return _with_author(question)


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _preview(text: str, default_marks: float) -> ImportPreviewOut:
    drafts, backend, note = extract_questions(text, default_marks)
    if not drafts:
        # Report why nothing came back. Defaulting to a formatting complaint hides
        # the common case - the AI reader failed and the fallback cannot cope with
        # this layout - and sends the examiner to fix a document that is fine.
        if backend == "rules" and "unavailable" in note:
            raise HTTPException(400, f"{note} That parser needs questions numbered 'Q1.' or '1)'.")
        raise HTTPException(
            400,
            "No questions found in that document. Questions should start with a number, "
            "like 'Q1.' or '1)'.",
        )
    return ImportPreviewOut(
        questions=drafts,
        total=len(drafts),
        needs_attention=sum(1 for d in drafts if d["warnings"]),
        source_characters=len(text),
        backend=backend,
        note=note,
    )


@router.post("/import/file", response_model=ImportPreviewOut)
async def import_file(
    file: UploadFile = File(...),
    default_marks: float = 5.0,
    _=Depends(require_staff),
):
    """Read a question paper and return drafts for review. Nothing is saved here.

    Extraction from a human-formatted document is guesswork, and a mis-read
    answer key would mark correct work wrong at scale. So this endpoint only
    proposes; /import/commit is what writes, and only after an examiner has
    looked at every question.
    """
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That file is larger than 5 MB.")
    if not data:
        raise HTTPException(400, "That file is empty.")

    try:
        text = extract_text(file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return _preview(text, default_marks)


@router.post("/import/text", response_model=ImportPreviewOut)
def import_text(payload: ImportPreviewIn, _=Depends(require_staff)):
    """Same as /import/file, for questions pasted straight in."""
    if not payload.text.strip():
        raise HTTPException(400, "Paste some questions first.")
    return _preview(payload.text, payload.default_marks)


@router.post("/import/commit", response_model=list[QuestionAdminOut], status_code=201)
def import_commit(
    payload: ImportCommitIn, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    """Save reviewed questions into the bank, all or nothing.

    A partial import would leave an examiner unsure which questions made it, so
    a single invalid question rolls the whole batch back with its position named.
    """
    if not payload.questions:
        raise HTTPException(400, "No questions to save.")

    created: list[Question] = []
    for position, item in enumerate(payload.questions, start=1):
        item.skill = payload.skill
        try:
            _validate(item)
            _check_subject(item, user)
        except HTTPException as exc:
            db.rollback()
            raise HTTPException(exc.status_code, f"Question {position}: {exc.detail}") from exc

        question = Question(**item.model_dump(), created_by=user.id)
        db.add(question)
        created.append(question)

    db.commit()
    for question in created:
        db.refresh(question)
    return [_with_author(q) for q in created]


# Declared before /{question_id}: FastAPI matches routes in definition order, so
# a literal path must precede a parameterised one that could also swallow it.
@router.get("/skills", response_model=list[str])
def list_skills(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    stmt = select(Question.skill)
    if user.role != "controller":
        stmt = stmt.where(Question.created_by == user.id)
    return sorted({s for s in db.scalars(stmt).all()})


@router.get("/{question_id}", response_model=QuestionAdminOut)
def get_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    question = db.get(Question, question_id)
    # Reported as 404 rather than 403: confirming a question exists but belongs
    # to someone else still leaks that a paper is being prepared.
    if not question or not owns_or_controls(user, question.created_by):
        raise HTTPException(404, "Question not found.")
    return _with_author(question)


@router.put("/{question_id}", response_model=QuestionAdminOut)
def update_question(
    question_id: int,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    """Edit an existing question.

    Note this does not re-grade answers already submitted against this question.
    Past scores stay as they were, which is deliberate - retroactively changing a
    candidate's mark because a rubric was reworded afterwards would be unfair.
    """
    question = db.get(Question, question_id)
    if not question or not owns_or_controls(user, question.created_by):
        raise HTTPException(404, "Question not found.")
    _validate(payload)
    _check_subject(payload, user)

    for field, value in payload.model_dump().items():
        setattr(question, field, value)
    db.commit()
    db.refresh(question)
    return _with_author(question)


@router.delete("/{question_id}", status_code=204)
def delete_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    question = db.get(Question, question_id)
    if not question or not owns_or_controls(user, question.created_by):
        raise HTTPException(404, "Question not found.")

    # Answers reference questions, so deleting one out from under a submitted
    # attempt would orphan those rows and break every result page that shows it.
    answered = db.scalar(select(Answer.id).where(Answer.question_id == question_id).limit(1))
    if answered:
        raise HTTPException(
            409,
            "This question has already been answered by candidates and cannot be deleted. "
            "Remove it from the assessment instead.",
        )

    used_in = db.scalars(select(Assessment).where(Assessment.question_ids.isnot(None))).all()
    for assessment in used_in:
        if question_id in (assessment.question_ids or []):
            raise HTTPException(
                409, f"This question is used by the assessment '{assessment.title}'. Remove it there first."
            )

    db.delete(question)
    db.commit()


