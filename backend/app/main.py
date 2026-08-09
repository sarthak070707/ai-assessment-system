from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .evaluation import semantic
from .routers import analytics, assessments, attempts, auth, candidates, questions, staff

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Technical Assessment System",
    description=(
        "Online technical assessment platform with AI-based evaluation and analytics. "
        "Grades MCQ, coding and descriptive answers, flags low-confidence scores for "
        "human review, and reports skill-level diagnostics."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router, questions.router, assessments.router,
    attempts.router, analytics.router, candidates.router, staff.router,
):
    app.include_router(router)


@app.get("/api/health", tags=["system"])
def health():
    """Reports which semantic backend is live, so you can tell at a glance whether
    SBERT loaded or the system fell back to TF-IDF."""
    return {"status": "ok", "semantic_backend": semantic.backend_name()}
