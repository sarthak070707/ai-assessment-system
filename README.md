# Online Technical Assessment System with AI-Based Evaluation and Analytics

A web platform that creates, delivers and grades technical assessments — MCQ, coding and
descriptive — using AI evaluation, and reports skill-level diagnostics for candidates and examiners.

The design principle throughout: **the AI grades, but it also reports how sure it is.**
Low-confidence scores are escalated to a human instead of being quietly accepted.

---

## Run it

Two terminals. Python 3.11+ and Node 18+.

Every backend dependency is pure Python — nothing needs a C or C++ compiler, so `pip install`
works on any platform and any recent Python without build tools. Verified on 3.11 through 3.14.

**Terminal 1 — backend** (Mac/Linux)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed.py                     # loads demo users, 6 questions, 1 assessment
uvicorn app.main:app --reload
```

**Terminal 1 — backend** (Windows PowerShell)

PowerShell blocks script execution by default, so allow it for your user once:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python seed.py
uvicorn app.main:app --reload
```

Note: `&&` only works in PowerShell 7+. On Windows PowerShell 5.1 run each line separately.

**Terminal 2 — frontend** (same on all platforms)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

Two separate portals:

**Staff** — `http://localhost:5173/#/admin` (sign in with staff ID or email)

| Staff ID | Password | Role |
|---|---|---|
| `EXO001` | `control123` | Exam office — sees and edits everything |
| `CS204` | `teach123` | Dr. Rao — teaches Algorithms, Data Structures |
| `CS311` | `teach123` | Prof. Sharma — teaches Databases, System Design |

**Candidates** — `http://localhost:5173/#/login`

Enrolled for the demo: `21BCS1042`, `21BCS1043`, `21BCS1044`. They hold no password.

**No exam codes are seeded, deliberately.** A fixed code such as `RAO-2025` sitting in the seed file
would contradict the model the rest of the system enforces — codes are randomly generated,
single-use, and issued by a person. To sit a paper: sign in as staff above, open **Candidates**,
select a student and press **Generate codes**. Two clicks, and it is the real flow rather than a
demo shortcut.

Interactive API docs: **http://localhost:8000/docs** — every endpoint is callable from the browser,
which is the fastest way to demo the backend in a viva.

---

## Architecture

```
React (Vite)  ──HTTP/JSON──>  FastAPI  ──SQLAlchemy──>  SQLite / PostgreSQL
                                 │
                                 ├── MCQ grader          exact match
                                 ├── Coding grader       sandboxed run + AST static analysis
                                 ├── Descriptive grader  SBERT embeddings → TF-IDF fallback
                                 ├── Plagiarism check    char n-gram cosine across submissions
                                 └── Analytics           skill proficiency, percentile, timing
```

SQLite is the default so the project runs anywhere with zero setup. Switch to PostgreSQL by
changing one line in `.env` — no code changes.

---

## How each question type is graded

### MCQ
Exact match against the stored key. Confidence is always 1.0.

### Coding — `evaluation/code_runner.py`, `guard.py`, `static_analysis.py`
Three layers, in order:

1. **Pre-flight guard.** The submission's AST is scanned before anything runs. Imports of `os`,
   `subprocess`, `socket` etc., and calls to `open`, `eval`, `exec`, `__import__` are rejected,
   along with dunder-attribute access (the `__class__.__subclasses__` escape chain).
2. **Sandboxed execution.** Each submission runs as a separate isolated process (`python -I -S`)
   in a temp directory with a wall-clock timeout and Unix rlimits on CPU, address space, file size
   and process count. Infinite loops time out; allocation bombs die with `MemoryError`.
3. **Static analysis.** The AST is walked for maximum loop-nesting depth (a complexity proxy),
   function length, docstrings and global state.

Final score = **80% test-case pass ratio + 20% structural quality**, with one guard: a submission
that passes *no* tests scores zero regardless of quality. Without that guard, unmodified starter
code earns the full quality component for having no structural problems — a real defect caught
during testing, and the kind of thing worth checking in any weighted grading scheme.

Two submissions that both pass every test still do not score identically if one is quadratic and
the other linear:

| Submission | Tests passed | Score /15 |
|---|---|---|
| Unmodified starter code | 0/3 | 0.0 |
| Wrong answer | 0/3 | 0.0 |
| Partially correct | 2/3 | 10.55 |
| Correct, quadratic | 3/3 | 14.1 |
| Correct, linear | 3/3 | 14.55 |

> **Honest limitation, and say this in your viva:** process isolation plus a denylist is defence in
> depth, not a security boundary. A determined attacker can evade a denylist. For untrusted public
> traffic you would run each submission in a network-less container. The code is structured so the
> runner can be swapped without touching the grading logic.

### Descriptive — `evaluation/semantic.py`
The interesting part of the project. Two tiers:

- **Tier 1 (preferred):** sentence-transformer embeddings (SBERT). Captures paraphrase — an answer
  saying *"reduces lookup cost to constant time"* scores well against a reference saying
  *"hash tables give O(1) access"* despite sharing almost no vocabulary.
- **Tier 2 (automatic fallback):** TF-IDF cosine similarity. Installs in seconds, needs no model
  download, so the project runs on any machine. Weaker on paraphrase.

To enable Tier 1, uncomment `sentence-transformers` in `requirements.txt` and reinstall. The system
detects it at runtime — `GET /api/health` reports which backend is live.

Score = `0.7 × semantic similarity + 0.3 × rubric keyword coverage`. Similarity alone rewards
answers that *sound* right while omitting required terms, so coverage keeps it grounded.

**The confidence threshold.** Scores landing in the uncertain middle band (default 0.35–0.65,
configurable) are never auto-awarded. They are flagged `needs_review` and pushed to the examiner's
queue. Confidence is computed as distance from the band's midpoint — the point where the model is
least sure. This is the design decision most worth defending: it is what separates a grading system
you can trust from one that is confidently wrong.

### Plagiarism — `evaluation/plagiarism.py`
Two strategies, chosen by what the submission is.

**Code → structural comparison.** The submission is parsed to an AST and every identifier is
rewritten to a positional placeholder, so `seen`/`d` and `nums`/`arr` collapse to the same token.
Overlapping 5-grams over the resulting node-type sequence are then compared — the same fingerprinting
idea used by established tools like MOSS. This catches the rename-everything edit that defeats plain
text matching, which is the usual way a copied answer is disguised.

**Prose → character n-gram overlap**, which survives reflowed whitespace and punctuation changes.

Measured behaviour on the two-sum solution:

| Variant | Score | Flagged |
|---|---|---|
| Identical | 1.00 | yes |
| Reflowed whitespace | 1.00 | yes |
| All variables renamed | 1.00 | yes |
| Docstring and comments added | 1.00 | yes |
| Different algorithm, same question | 0.10 | no |
| Different question entirely | 0.24 | no |

Anything ≥ 0.85 is **flagged for a human, not auto-penalised** — similar answers to a narrow
question are expected, and only a person should draw the conclusion.

> One design note worth defending: TF-IDF is deliberately *not* used here. Across two documents,
> IDF down-weights exactly the terms they share, so a copied answer can score lower than an
> unrelated one. Overlap is the whole signal, so it is measured directly with raw-count cosine.

---

## Access model

Modelled on how invigilated university exams actually run, rather than on a generic web login.

**Candidates are identified by enrolment number, not email.** The institution already issues one,
and it is what the exam register is keyed on. Requiring an email would create a second identity to
reconcile.

**Candidates hold no standing password.** Access is granted per sitting by a single-use code tied
to one paper and one enrolment number, valid for a stated window. A permanent password would let a
candidate re-enter a paper they had already sat, or open one they were never scheduled for.

**Codes are stored hashed.** The plaintext is shown to the examiner once, at generation, and cannot
be recovered — the same reasoning as passwords. A leaked database does not hand over exam access.
Reissuing revokes any unused code for the same paper, so two live codes never circulate at once.

**The session token carries the paper it was issued for.** Authorisation is bound to the token
rather than re-derived from whatever id the client sends, so editing the assessment id in the URL
cannot widen access. Verified by test: a candidate holding a code for paper 1 gets 403 on paper 2.

**Failed sign-ins return one generic message.** Distinguishing "no such enrolment number" from
"wrong code" would let someone probe the register to discover who is scheduled for a paper.

**Exam access can be confined to named networks** via `EXAM_ALLOWED_NETWORKS` (comma-separated
CIDR), mirroring an institution restricting a paper to lab machines. Blank means unrestricted,
which is the correct default for local development.

> Be straight about this one in a viva: network restriction is a real control but a soft one. It is
> defeated by a VPN, or by someone on the campus network who should not be sitting the paper. It is
> one layer alongside the exam code and the proctor signals, not a boundary on its own. The same
> caveat applies to the two separate portals — a distinct examiner URL is **not** a security
> measure. The actual protection is `require_admin` on every staff endpoint, which returns 403
> regardless of which page the request came from. The split buys role-appropriate UX and stops
> the candidate login page advertising staff credentials.

## Examiner tools

Examiners get a different application to candidates, not the same one with extra buttons.

**Question bank** (`/questions`) — create, edit and delete questions across all three types, filtered
by skill and type. The editor changes shape with the question type: options and a correct answer for
MCQ, starter code and JSON test cases for coding, a reference answer and rubric keywords for
descriptive.

**Assessment builder** (`/assessments`) — assemble papers from the bank, set duration, and
publish or unpublish. The question picker filters by type and difficulty, so a paper of only medium
multiple-choice questions can be built without reading past everything that cannot belong in it.
These are filters on the picker rather than constraints on the paper: a mixed paper is still allowed,
and a note appears if the selection spans several types. Unpublished papers are invisible to candidates.

**Candidates** (`/candidates`) — enrol candidates by enrolment number and generate exam codes in
bulk, with a live view of which have been issued and which have been used.

**Review queue** (`/review`) — only the answers the grader was unsure about.

Three rules are enforced server-side rather than by hiding buttons:

- A question that candidates have already answered **cannot be deleted** — it would orphan those
  answers and break every result page showing them. Unpublish the assessment instead.
- An assessment with attempts against it **cannot be deleted**, for the same reason.
- The question set **cannot be changed while a candidate is mid-attempt**, since two people would
  then have sat different versions of the same paper.

Editing a question deliberately does **not** re-grade answers already submitted against it.
Retroactively changing someone's mark because a rubric was reworded afterwards would be unfair.

## Integrity monitoring

`components/useProctor.js` reports tab switches, window blur, full-screen exit and paste events
into answer fields. The **server** owns the count — the client is never trusted to keep the tally.
Events are recorded, not blocked; the examiner decides what a pattern means.

---

## Analytics

Per attempt: score, percentage, percentile against the cohort, proficiency per skill, time spent
per question, and generated revision recommendations for skills below 70%.

Per assessment (examiner only): cohort size, average/high/low, proficiency by skill, and the five
questions with the lowest average score — which surfaces bad questions as much as weak candidates.

---

## API reference

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/login` | staff | Examiner sign-in (email) |
| `POST` | `/api/auth/exam` | candidate | Exam sign-in (enrolment no. + code) |
| `POST` | `/api/candidates` | admin | Enrol a candidate |
| `POST` | `/api/candidates/codes` | admin | Issue single-use exam codes |
| `GET` | `/api/candidates/codes/{id}` | admin | Code status (never plaintext) |
| `GET` | `/api/assessments` | any user | List published assessments |
| `POST` | `/api/questions` | admin | Add a question |
| `PUT` | `/api/questions/{id}` | admin | Edit a question |
| `DELETE` | `/api/questions/{id}` | admin | Delete (blocked if answered) |
| `POST` | `/api/assessments` | admin | Build a paper |
| `PUT` | `/api/assessments/{id}` | admin | Edit a paper |
| `POST` | `/api/assessments/{id}/publish` | admin | Show/hide from candidates |
| `POST` | `/api/attempts/start/{id}` | candidate | Begin attempt (answer keys stripped) |
| `POST` | `/api/attempts/{id}/events` | candidate | Log an integrity event |
| `POST` | `/api/attempts/{id}/submit` | candidate | Submit and trigger grading |
| `GET` | `/api/attempts/review/queue` | admin | Low-confidence answers |
| `POST` | `/api/attempts/review/{id}` | admin | Override a score |
| `GET` | `/api/analytics/attempt/{id}` | owner/admin | Candidate diagnostics |
| `GET` | `/api/analytics/assessment/{id}` | admin | Cohort analytics |

Answer keys, test cases and reference answers are **never** serialised into the candidate payload —
`QuestionOut` omits them at the schema level rather than relying on the frontend to hide them.

---

## Verifying it works

Sample run from the seeded assessment (60 marks total):

```
q1 mcq          5.0/5    conf 1.00              Correct.
q2 mcq          0.0/5    conf 1.00              Incorrect option selected.
q3 coding      14.55/15  conf 1.00              3/3 tests passed. Complexity: linear.
q4 coding      14.1/15   conf 1.00              3/3 tests passed. Complexity: quadratic.
q5 descriptive  4.62/10  conf 0.25  → REVIEW    Borderline answer held for examiner review.
q6 descriptive  0.0/10   conf 1.00              Missing: decouple, buffer, retry, latency.
```

Note q3 vs q4: both passed every test, different scores, because static analysis caught the
quadratic solution. And q5 went to a human rather than guessing.

Sandbox behaviour under attack:

```
infinite loop   → Timed out after 5s
memory bomb     → MemoryError
open() a file   → Rejected: use of 'open' is not allowed
import os       → Rejected: import of 'os' is not allowed
```

---

## Configuration

All in `backend/.env`:

| Variable | Default | Effect |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./assessment.db` | Swap to PostgreSQL here |
| `JWT_SECRET` | dev placeholder | **Change before deploying** |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SBERT model for descriptive grading |
| `REVIEW_LOWER` / `REVIEW_UPPER` | `0.35` / `0.65` | Widen to send more answers to humans |
| `CODE_TIMEOUT_SECONDS` | `5` | Wall-clock limit per test case |
| `CODE_MEMORY_MB` | `256` | Address-space cap per submission |
| `EXAM_ALLOWED_NETWORKS` | blank | CIDR allowlist for exam access; blank = unrestricted |
| `ACCESS_CODE_VALID_HOURS` | `6` | Default lifetime of a freshly issued exam code |

---

## Known limitations

Worth stating plainly rather than being caught on:

- The code sandbox is hardened but not a true security boundary (see above).
- On Windows there is no hard memory cap: `rlimit` is a Unix facility, so only the wall-clock
  timeout and the AST guard apply. Grading is otherwise identical across platforms.
- The built-in TF-IDF grader matches on vocabulary, not meaning, so it scores a correct answer
  written in unexpected words too harshly. Install `sentence-transformers` for true paraphrase
  handling. This is why the confidence threshold matters: the weaker the grader, the more it
  escalates rather than guessing.
- Adaptive difficulty and webcam-based face monitoring are described in the project abstract but
  are **not implemented** — they are listed as future scope. Only claim what runs.
- Grading rules are versioned but stored scores are not, so results graded before a rule change are
  not comparable with results graded after. A `grader_version` column on `answers` would fix this.
- Grading is synchronous. Under real load, submission grading belongs on a task queue (Celery/RQ).
- Only Python submissions are supported. The runner interface is language-agnostic; adding another
  language means adding a harness.

## Future scope

Adaptive item selection using IRT · webcam proctoring · LLM-based descriptive grading (Groq) ·
multi-language code execution · Celery queue for asynchronous grading · `grader_version` tracking ·
fine-tuning the semantic grader on a corpus of human-marked answers.
