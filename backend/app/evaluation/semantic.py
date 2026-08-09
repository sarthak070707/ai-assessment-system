"""Grades descriptive answers by meaning rather than exact wording.

Two-tier design, on purpose:

  Tier 1 (preferred) - sentence-transformer embeddings (SBERT). Captures paraphrase:
      "reduces lookup cost to constant time" scores well against
      "hash tables give O(1) access" even with zero shared vocabulary.

  Tier 2 (fallback)  - TF-IDF cosine similarity, implemented in pure Python in
      textsim.py. No dependencies and no model download, so the project runs on
      any machine and any Python version. Weaker on paraphrase.

The final score blends semantic similarity with rubric keyword coverage, because
similarity alone rewards answers that sound right while omitting required terms.
Anything landing in the uncertain middle band is flagged for a human, never guessed.
"""
from __future__ import annotations

import re

from ..config import get_settings
from . import textsim

settings = get_settings()

_SIMILARITY_WEIGHT = 0.7
_KEYWORD_WEIGHT = 0.3

_model = None
_model_loaded = False


def _load_model():
    """Import SBERT lazily so a missing install degrades instead of crashing."""
    global _model, _model_loaded
    if _model_loaded:
        return _model
    _model_loaded = True
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
    except Exception:
        _model = None
    return _model


def backend_name() -> str:
    return "sbert" if _load_model() is not None else "tfidf"


def _sbert_similarity(answer: str, reference: str) -> float:
    from sentence_transformers import util

    model = _load_model()
    vectors = model.encode([answer, reference], convert_to_tensor=True, show_progress_bar=False)
    return float(util.cos_sim(vectors[0], vectors[1]).item())


def _tfidf_similarity(answer: str, reference: str) -> float:
    return textsim.similarity(answer, reference, mode="word")


def similarity(answer: str, reference: str) -> float:
    if not answer.strip() or not reference.strip():
        return 0.0
    if _load_model() is not None:
        return _sbert_similarity(answer, reference)
    return _tfidf_similarity(answer, reference)


def keyword_coverage(answer: str, keywords: list[str] | None) -> tuple[float, list[str]]:
    if not keywords:
        return 1.0, []
    tokens = set(re.findall(r"[a-z0-9]+", answer.lower()))
    missing = []
    hits = 0
    for keyword in keywords:
        parts = set(re.findall(r"[a-z0-9]+", keyword.lower()))
        if parts and parts.issubset(tokens):
            hits += 1
        else:
            missing.append(keyword)
    return hits / len(keywords), missing


def grade(answer: str, reference: str, keywords: list[str] | None, max_score: float) -> dict:
    sim = max(0.0, min(1.0, similarity(answer, reference)))
    coverage, missing = keyword_coverage(answer, keywords)
    blended = _SIMILARITY_WEIGHT * sim + _KEYWORD_WEIGHT * coverage

    # Confidence falls as the score approaches the decision boundary between the
    # review band's edges - that midpoint is exactly where the model is least sure.
    midpoint = (settings.review_lower + settings.review_upper) / 2
    half_band = max(0.01, (settings.review_upper - settings.review_lower) / 2)
    confidence = round(min(1.0, abs(blended - midpoint) / half_band), 2)
    needs_review = settings.review_lower <= blended <= settings.review_upper

    if not answer.strip():
        return {
            "score": 0.0, "similarity": 0.0, "coverage": 0.0, "confidence": 1.0,
            "needs_review": False, "missing_keywords": keywords or [],
            "backend": backend_name(), "feedback": "No answer submitted.",
        }

    if needs_review:
        feedback = "Borderline answer held for examiner review."
    elif missing:
        feedback = "Missing expected concepts: " + ", ".join(missing[:4]) + "."
    else:
        feedback = "Covers the reference answer's key concepts."

    return {
        "score": round(blended * max_score, 2),
        "similarity": round(sim, 3),
        "coverage": round(coverage, 3),
        "confidence": confidence,
        "needs_review": needs_review,
        "missing_keywords": missing,
        "backend": backend_name(),
        "feedback": feedback,
    }
