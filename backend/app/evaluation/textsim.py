"""TF-IDF vectorisation and cosine similarity, in pure Python.

Why not scikit-learn: the project only needs two functions from it, and pulling in
scikit-learn plus numpy means ~100 MB of compiled extensions that must have a
prebuilt wheel for your exact interpreter. On a new Python release those wheels
lag, pip falls back to compiling from source, and the install fails on any machine
without a C++ toolchain. Written out longhand, this file has zero dependencies and
installs instantly on every platform and Python version.

The maths follows scikit-learn's TfidfVectorizer defaults so results are
comparable: smoothed IDF, raw term frequency, L2-normalised vectors.

    idf(t) = ln((1 + N) / (1 + df(t))) + 1

The +1 terms are Laplace smoothing - they stop a term appearing in every document
from producing a zero or undefined weight.
"""
from __future__ import annotations

import math
import re
from collections import Counter

# Trimmed from scikit-learn's English stop list: function words that appear in
# nearly every answer and would otherwise dominate the similarity score.
STOP_WORDS = frozenset("""
a about above after again against all am an and any are as at be because been
before being below between both but by can cannot could did do does doing down
during each few for from further had has have having he her here hers herself him
himself his how i if in into is it its itself just me more most my myself no nor
not now of off on once only or other our ours ourselves out over own same she
should so some such than that the their theirs them themselves then there these
they this those through to too under until up very was we were what when where
which while who whom why will with you your yours yourself yourselves
""".split())


def word_tokens(text: str, ngram_range: tuple[int, int] = (1, 2)) -> Counter:
    """Lowercased word unigrams and bigrams, stop words removed.

    Bigrams matter here: "not normalised" and "normalised" carry opposite
    meanings, and unigrams alone would score them as near-identical.
    """
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP_WORDS]
    grams: list[str] = []
    for n in range(ngram_range[0], ngram_range[1] + 1):
        grams.extend(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))
    return Counter(grams)


def char_ngrams(text: str, n_range: tuple[int, int] = (3, 5)) -> Counter:
    """Character n-grams, for plagiarism comparison.

    Character-level matching survives renamed variables and reflowed whitespace,
    which is exactly how a copied submission usually differs from its source.
    """
    cleaned = re.sub(r"\s+", " ", text.lower()).strip()
    grams: list[str] = []
    for n in range(n_range[0], n_range[1] + 1):
        grams.extend(cleaned[i:i + n] for i in range(len(cleaned) - n + 1))
    return Counter(grams)


def tfidf_vectors(documents: list[Counter]) -> list[dict[str, float]]:
    """Convert term counts into L2-normalised TF-IDF vectors."""
    total = len(documents)
    if not total:
        return []

    document_frequency: Counter = Counter()
    for counts in documents:
        document_frequency.update(counts.keys())

    vectors: list[dict[str, float]] = []
    for counts in documents:
        weights = {
            term: freq * (math.log((1 + total) / (1 + document_frequency[term])) + 1)
            for term, freq in counts.items()
        }
        norm = math.sqrt(sum(w * w for w in weights.values()))
        vectors.append({t: w / norm for t, w in weights.items()} if norm else {})
    return vectors


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Dot product of two L2-normalised sparse vectors, which is their cosine."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(weight * b.get(term, 0.0) for term, weight in a.items())


def raw_cosine(a: Counter, b: Counter) -> float:
    """Cosine on L2-normalised raw counts, with no IDF term.

    For near-duplicate detection IDF is actively harmful: across only two
    documents, any term they share gets down-weighted precisely because it is
    shared, so a copied answer can score lower than an unrelated one. Overlap
    is the whole signal here, so it is measured directly.
    """
    if not a or not b:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if not norm_a or not norm_b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(count * b.get(term, 0) for term, count in a.items())
    return dot / (norm_a * norm_b)


def similarity(text_a: str, text_b: str, mode: str = "word") -> float:
    """Cosine similarity between two strings, in [0, 1]."""
    tokenise = char_ngrams if mode == "char" else word_tokens
    counts = [tokenise(text_a), tokenise(text_b)]
    if not counts[0] or not counts[1]:
        return 0.0
    vectors = tfidf_vectors(counts)
    return max(0.0, min(1.0, cosine(vectors[0], vectors[1])))


def max_similarity(candidate: str, corpus: list[str], mode: str = "char") -> float:
    """Highest overlap between `candidate` and any document in `corpus`.

    Uses raw-count cosine rather than TF-IDF - see raw_cosine for why.
    """
    tokenise = char_ngrams if mode == "char" else word_tokens
    documents = [d for d in corpus if d and d.strip()]
    if not candidate.strip() or not documents:
        return 0.0

    target = tokenise(candidate)
    if not target:
        return 0.0
    return max((raw_cosine(target, tokenise(d)) for d in documents), default=0.0)
