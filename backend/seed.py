"""Loads a demo cohort, a 6-question bank and one published assessment.

Run once:  python seed.py
"""
from app.database import Base, SessionLocal, engine
from app.models import Assessment, Question, User
from app.security import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if db.query(User).count():
    print("Database already seeded. Delete assessment.db to start over.")
    raise SystemExit

db.add_all([
    User(staff_id="EXO001", email="controller@college.edu", full_name="Exam Office",
         department="Examinations", role="controller",
         password_hash=hash_password("control123")),
    User(staff_id="CS204", email="rao@college.edu", full_name="Dr. Rao",
         department="Computer Science", subjects=["Algorithms", "Data Structures"],
         role="examiner", password_hash=hash_password("teach123")),
    User(staff_id="CS311", email="sharma@college.edu", full_name="Prof. Sharma",
         department="Computer Science", subjects=["Databases", "System Design"],
         role="examiner", password_hash=hash_password("teach123")),
    # Candidates hold no standing password - they sign in with a per-exam code.
    User(enrollment_no="21BCS1042", full_name="Aarti Menon", role="candidate", password_hash=""),
    User(enrollment_no="21BCS1043", full_name="Bharat Iyer", role="candidate", password_hash=""),
    User(enrollment_no="21BCS1044", full_name="Chetna Sood", role="candidate", password_hash=""),
])

questions = [
    Question(
        kind="mcq", skill="Data Structures", difficulty="easy", max_score=5,
        prompt="What is the average-case time complexity of a lookup in a well-sized hash table?",
        options=["O(1)", "O(log n)", "O(n)", "O(n log n)"],
        correct_option=0,
    ),
    Question(
        kind="mcq", skill="Databases", difficulty="medium", max_score=5,
        prompt="Which normal form removes transitive dependencies on the primary key?",
        options=["1NF", "2NF", "3NF", "BCNF"],
        correct_option=2,
    ),
    Question(
        kind="coding", skill="Algorithms", difficulty="easy", max_score=15,
        prompt=(
            "Write a function `solve(nums, target)` that returns the indices of the two "
            "numbers in `nums` that add up to `target`, as a list [i, j] with i < j. "
            "Exactly one solution exists."
        ),
        starter_code="def solve(nums, target):\n    # your code here\n    pass\n",
        test_cases=[
            {"name": "Basic pair", "entrypoint": "solve", "input": [[2, 7, 11, 15], 9], "expected": [0, 1]},
            {"name": "Negatives", "entrypoint": "solve", "input": [[-3, 4, 3, 90], 0], "expected": [0, 2]},
            {"name": "Large input", "entrypoint": "solve", "input": [list(range(2000)), 3997], "expected": [1998, 1999], "hidden": True},
        ],
    ),
    Question(
        kind="coding", skill="Algorithms", difficulty="medium", max_score=15,
        prompt=(
            "Write a function `solve(s)` that returns the length of the longest substring "
            "of `s` containing no repeating characters."
        ),
        starter_code="def solve(s):\n    # your code here\n    pass\n",
        test_cases=[
            {"name": "Repeats", "entrypoint": "solve", "input": ["abcabcbb"], "expected": 3},
            {"name": "All same", "entrypoint": "solve", "input": ["bbbbb"], "expected": 1},
            {"name": "Empty string", "entrypoint": "solve", "input": [""], "expected": 0, "hidden": True},
        ],
    ),
    Question(
        kind="descriptive", skill="Databases", difficulty="medium", max_score=10,
        prompt="Explain what a database index is and the trade-off it introduces.",
        reference_answer=(
            "An index is an auxiliary data structure, usually a B-tree, that stores a sorted "
            "mapping from column values to row locations. It lets the database find matching "
            "rows without a full table scan, cutting read time from linear to logarithmic. "
            "The trade-off is that every insert, update and delete must also modify the index, "
            "so writes get slower and the index consumes extra storage."
        ),
        rubric_keywords=["b-tree", "full table scan", "write", "storage"],
    ),
    Question(
        kind="descriptive", skill="System Design", difficulty="hard", max_score=10,
        prompt="Why would you put a message queue between two services instead of calling one from the other directly?",
        reference_answer=(
            "A queue decouples the producer from the consumer so neither has to be available "
            "at the same moment. It absorbs traffic spikes by buffering work, letting the "
            "consumer process at its own rate instead of failing under load. It also isolates "
            "failure: if the consumer crashes, messages persist and are retried rather than "
            "lost. The cost is added latency, eventual consistency and operational complexity."
        ),
        rubric_keywords=["decouple", "buffer", "retry", "latency"],
    ),
]
db.add_all(questions)
db.commit()

# Attribute the seeded bank so ownership rules have something to act on.
rao = db.query(User).filter(User.staff_id == "CS204").first()
sharma = db.query(User).filter(User.staff_id == "CS311").first()
for q in questions:
    q.created_by = sharma.id if q.skill in {"Databases", "System Design"} else rao.id
db.commit()

# Each examiner sets their own paper from their own subjects. Two professors do
# not co-author one exam, so the seed must not create a paper that mixes their
# questions - that would contradict the ownership rule the API enforces.
rao_questions = [q for q in questions if q.created_by == rao.id]
sharma_questions = [q for q in questions if q.created_by == sharma.id]

papers = [
    Assessment(
        title="Algorithms and Data Structures — Mid Semester",
        description="Set by Dr. Rao. Covers complexity, arrays and hashing.",
        duration_minutes=45,
        question_ids=[q.id for q in rao_questions],
        created_by=rao.id,
    ),
    Assessment(
        title="Databases and System Design — Mid Semester",
        description="Set by Prof. Sharma. Covers normalisation, indexing and service architecture.",
        duration_minutes=45,
        question_ids=[q.id for q in sharma_questions],
        created_by=sharma.id,
    ),
]
db.add_all(papers)
db.commit()

# Guard against the seed drifting out of step with the rule the API enforces.
for paper in papers:
    owned = {q.id for q in questions if q.created_by == paper.created_by}
    stray = set(paper.question_ids) - owned
    assert not stray, f"'{paper.title}' contains questions owned by another examiner: {stray}"

# Issue demo exam codes so the candidate portal is usable straight away.
from datetime import datetime, timedelta, timezone
from app.models import ExamAccessCode

valid_until = datetime.now(timezone.utc) + timedelta(days=365)

# A code admits one candidate to one paper, so every student sitting both papers
# needs one code per paper.
demo_codes = {
    papers[0].id: {"21BCS1042": "RAO-2025", "21BCS1043": "RAO-2026", "21BCS1044": "RAO-2027"},
    papers[1].id: {"21BCS1042": "SHA-2025", "21BCS1043": "SHA-2026", "21BCS1044": "SHA-2027"},
}
for paper_id, codes in demo_codes.items():
    for enrollment, code in codes.items():
        db.add(ExamAccessCode(
            assessment_id=paper_id, enrollment_no=enrollment,
            code_hash=hash_password(code), valid_until=valid_until,
        ))
db.commit()

print("Seeded 3 staff, 3 candidates, 6 questions, 2 assessments.\n")
print("  Staff portal      /#/admin   (staff ID or email)")
print("    EXO001  / control123   Exam Office  (controller - sees everything)")
print("    CS204   / teach123     Dr. Rao      teaches Algorithms, Data Structures")
print("    CS311   / teach123     Prof. Sharma teaches Databases, System Design\n")
print("  Candidate portal  /#/login   (one code per paper)")
for paper in papers:
    print(f"    {paper.title}")
    for enrollment, code in demo_codes[paper.id].items():
        print(f"      {enrollment} / {code}")
