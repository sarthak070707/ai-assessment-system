from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "candidate"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str | None = None
    staff_id: str | None = None
    enrollment_no: str | None = None
    full_name: str
    department: str | None = None
    subjects: list | None = None
    role: str
    must_change_password: bool = False


class StaffCreate(BaseModel):
    staff_id: str
    full_name: str
    department: str | None = None
    subjects: list[str] = []
    email: EmailStr | None = None
    role: str = "examiner"


class StaffUpdate(BaseModel):
    full_name: str | None = None
    department: str | None = None
    subjects: list[str] | None = None


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    staff_id: str | None = None
    email: str | None = None
    full_name: str
    department: str | None = None
    subjects: list | None = None
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None = None


class TempCredential(BaseModel):
    staff_id: str | None = None
    full_name: str
    temporary_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class ExamLogin(BaseModel):
    enrollment_no: str
    access_code: str


class CandidateCreate(BaseModel):
    enrollment_no: str
    full_name: str


class IssueCodes(BaseModel):
    """Issue codes to a list of enrolment numbers for one assessment."""
    assessment_id: int
    enrollment_numbers: list[str]
    valid_hours: int | None = None


class IssuedCode(BaseModel):
    enrollment_no: str
    full_name: str
    access_code: str
    valid_until: datetime | None = None


class AccessCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    assessment_id: int
    enrollment_no: str
    issued_at: datetime
    valid_until: datetime | None = None
    used_at: datetime | None = None
    revoked: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class QuestionCreate(BaseModel):
    kind: str
    skill: str
    difficulty: str = "medium"
    prompt: str
    max_score: float = 10.0
    options: list[str] | None = None
    correct_option: int | None = None
    starter_code: str | None = None
    test_cases: list[dict] | None = None
    reference_answer: str | None = None
    rubric_keywords: list[str] | None = None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    skill: str
    difficulty: str
    prompt: str
    max_score: float
    options: list | None = None
    starter_code: str | None = None


class QuestionAdminOut(QuestionOut):
    created_by: int | None = None
    author_name: str | None = None
    correct_option: int | None = None
    test_cases: list | None = None
    reference_answer: str | None = None
    rubric_keywords: list | None = None


class ImportPreviewIn(BaseModel):
    """Pasted text, as an alternative to uploading a file."""
    text: str
    default_marks: float = 5.0


class ImportedQuestion(BaseModel):
    source_number: int
    kind: str
    prompt: str
    options: list[str] = []
    correct_option: int | None = None
    reference_answer: str = ""
    rubric_keywords: list[str] = []
    max_score: float
    difficulty: str
    warnings: list[str] = []

    # Generation only. The reference solution is what verifies the test cases,
    # and is shown to the examiner so they can see what was checked against.
    starter_code: str | None = None
    reference_solution: str | None = None
    test_cases: list[dict] | None = None


class ImportPreviewOut(BaseModel):
    questions: list[ImportedQuestion]
    total: int
    needs_attention: int
    source_characters: int
    backend: str = "rules"
    note: str = ""


class GenerateIn(BaseModel):
    """Write questions from a syllabus rather than extracting them from a paper."""
    syllabus: str
    skill: str
    kind: str = "mcq"
    difficulty: str = "medium"
    count: int = 5
    max_score: float = 5.0


class ImportCommitIn(BaseModel):
    """Questions the examiner has reviewed and is ready to save."""
    skill: str
    questions: list[QuestionCreate]


class AssessmentCreate(BaseModel):
    title: str
    description: str = ""
    duration_minutes: int = 45
    question_ids: list[int]
    mode: str = "fixed"
    adaptive_max_questions: int = 10
    adaptive_target_se: float = 0.4


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_by: int | None = None
    author_name: str | None = None

    # Candidate-facing state for the current session. Computed server-side
    # because only the server knows which code opened this session; the browser
    # can only see which papers exist.
    opens_with_your_code: bool = True
    sitting_used: bool = False
    in_progress: bool = False

    title: str
    description: str
    duration_minutes: int
    question_ids: list
    mode: str = "fixed"
    adaptive_max_questions: int = 10
    adaptive_target_se: float = 0.4
    is_published: bool


class AnswerIn(BaseModel):
    question_id: int
    response_text: str = ""
    selected_option: int | None = None
    seconds_spent: int = 0


class SubmitIn(BaseModel):
    answers: list[AnswerIn]


class DraftIn(BaseModel):
    answers: list[AnswerIn]


class AdaptiveAnswerIn(BaseModel):
    """One answer in an adaptive paper, graded on arrival."""
    question_id: int
    response_text: str = ""
    selected_option: int | None = None
    seconds_spent: int = 0


class AdaptiveStep(BaseModel):
    """What happens after an adaptive answer: another question, or the end."""
    finished: bool
    question: QuestionOut | None = None
    answered: int
    max_questions: int
    ability_percent: float
    precision: float
    stop_reason: str | None = None
    attempt_id: int


class DraftOut(BaseModel):
    saved_at: datetime


class ProctorEventIn(BaseModel):
    event_type: str
    detail: str = ""
    question_id: int | None = None


class ProctorEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_type: str
    detail: str
    question_id: int | None = None
    seconds_into_attempt: int = 0


class AnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    question_id: int
    score: float
    confidence: float
    needs_review: bool
    similarity_flag: float
    feedback: str
    seconds_spent: int
    detail: dict | None = None


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    assessment_id: int
    status: str
    started_at: datetime
    submitted_at: datetime | None = None
    total_score: float
    max_score: float
    integrity_flags: int


class AttemptResult(AttemptOut):
    answers: list[AnswerOut] = []


class ReviewIn(BaseModel):
    score: float
    feedback: str = ""
