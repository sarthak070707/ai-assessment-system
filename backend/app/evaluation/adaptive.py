"""Adaptive item selection using a Rasch (one-parameter logistic) model.

A fixed paper asks everyone the same questions, which wastes most of them: a
strong candidate learns nothing from the easy items and a weak one learns nothing
from the hard ones. An adaptive paper estimates ability as it goes and serves the
question that will tell it the most next.

    P(correct | theta, b) = 1 / (1 + exp(-(theta - b)))

`theta` is candidate ability, `b` is item difficulty, both on the same logit
scale. The model says a candidate has even odds on an item pitched exactly at
their ability, and the item is most informative at that point — which is the
whole basis of the selection rule below.

== The honest limitation ==

Proper IRT calibrates `b` for every item from a large corpus of historical
responses. This system has no such corpus, so `b` is derived from the difficulty
label the examiner assigned. That makes the selection genuinely Rasch-driven but
only as accurate as those labels: an item tagged "easy" that everyone fails will
keep being served to weak candidates until someone re-labels it.

The structure to fix that is already present. `calibrate` below recovers item
difficulty from observed pass rates, so once an institution has run a paper a few
times the labels can be replaced by measurements. It is not wired into the
serving path, because calibrating on a handful of attempts would be worse than
the labels it replaced.
"""
from __future__ import annotations

import math

# Difficulty labels mapped onto the logit scale. A candidate of average ability
# (theta = 0) has roughly 73% odds on an easy item, 50% on medium, 27% on hard.
DIFFICULTY_B = {"easy": -1.0, "medium": 0.0, "hard": 1.0}

# Ability is estimated over a grid rather than by maximum likelihood. MLE
# diverges to infinity when a candidate answers everything right or everything
# wrong, which happens constantly in a short paper; a prior keeps the estimate
# finite and honest about its own uncertainty.
_GRID = [(-4.0 + 0.1 * i) for i in range(81)]
_PRIOR_SD = 1.0


def difficulty_of(question) -> float:
    """Item difficulty on the logit scale."""
    explicit = getattr(question, "difficulty_b", None)
    if explicit is not None:
        return float(explicit)
    return DIFFICULTY_B.get((question.difficulty or "medium").lower(), 0.0)


def probability(theta: float, b: float) -> float:
    """Rasch probability of a correct response."""
    return 1.0 / (1.0 + math.exp(-(theta - b)))


def information(theta: float, b: float) -> float:
    """Fisher information an item carries at a given ability.

    For the Rasch model this is P(1-P), which peaks at 0.25 when b equals theta.
    Selecting the most informative item therefore means selecting the item whose
    difficulty is closest to the current ability estimate.
    """
    p = probability(theta, b)
    return p * (1.0 - p)


def estimate_ability(responses: list[tuple[float, float]]) -> tuple[float, float]:
    """Expected a posteriori ability estimate and its standard error.

    `responses` is a list of (difficulty, score_fraction). Score fractions are
    used rather than right/wrong because coding and descriptive answers earn
    partial credit; the fraction is treated as the probability the candidate has
    mastered the item, which is a reasonable reading of a partial score and
    avoids discarding information by rounding it to a binary.
    """
    if not responses:
        return 0.0, _PRIOR_SD

    posterior = []
    for theta in _GRID:
        # Normal prior centred on average ability, in log space to avoid
        # underflow once a paper runs to any length.
        log_p = -0.5 * (theta / _PRIOR_SD) ** 2
        for b, fraction in responses:
            p = min(max(probability(theta, b), 1e-9), 1 - 1e-9)
            f = min(max(fraction, 0.0), 1.0)
            log_p += f * math.log(p) + (1 - f) * math.log(1 - p)
        posterior.append(log_p)

    peak = max(posterior)
    weights = [math.exp(v - peak) for v in posterior]
    total = sum(weights)
    if total <= 0:
        return 0.0, _PRIOR_SD

    mean = sum(t * w for t, w in zip(_GRID, weights)) / total
    variance = sum(((t - mean) ** 2) * w for t, w in zip(_GRID, weights)) / total
    return round(mean, 3), round(math.sqrt(variance), 3)


def select_next(pool, served_ids: set[int], theta: float, skill_counts: dict[str, int]):
    """Choose the most informative unserved item, balanced across subjects.

    Pure maximum-information selection would happily serve six algorithms
    questions in a row if those happened to sit nearest the ability estimate,
    producing a precise measurement of one subject and no measurement of the
    rest. The penalty term trades a little statistical efficiency for a paper
    that still covers the syllabus.
    """
    candidates = [q for q in pool if q.id not in served_ids]
    if not candidates:
        return None

    def value(question):
        info = information(theta, difficulty_of(question))
        already = skill_counts.get(question.skill, 0)
        return info - 0.06 * already

    return max(candidates, key=value)


def should_stop(answered: int, standard_error: float, max_questions: int,
                target_se: float, pool_size: int) -> tuple[bool, str]:
    """Whether the paper has learned enough to stop.

    Two conditions, whichever comes first: the ability estimate is precise
    enough, or the paper has run its length. A minimum of three items applies
    regardless, because the standard error after one lucky answer can look
    convincing while meaning nothing.
    """
    if answered >= min(max_questions, pool_size):
        return True, "length"
    if answered >= 3 and standard_error <= target_se:
        return True, "precision"
    return False, ""


def to_percentage(theta: float) -> float:
    """Ability on the logit scale expressed as a 0-100 figure for reporting.

    Purely presentational. Logits are the right scale for the mathematics and
    the wrong one for a results page, where a candidate needs a number they can
    interpret without knowing what a logit is.
    """
    return round(100 * probability(theta, 0.0), 1)


def calibrate(observations: list[tuple[float, float]]) -> float:
    """Recover an item's difficulty from observed responses.

    `observations` is a list of (candidate_ability, score_fraction) for one item.
    Solves for the b that best explains what actually happened, which is how the
    label-derived difficulty above would eventually be replaced by a measured
    one. Provided for completeness and not used in the serving path: calibrating
    on a handful of attempts produces a worse estimate than the label.
    """
    if len(observations) < 2:
        return 0.0

    best_b, best_ll = 0.0, float("-inf")
    for step in range(-40, 41):
        b = step * 0.1
        ll = 0.0
        for theta, fraction in observations:
            p = min(max(probability(theta, b), 1e-9), 1 - 1e-9)
            f = min(max(fraction, 0.0), 1.0)
            ll += f * math.log(p) + (1 - f) * math.log(1 - p)
        if ll > best_ll:
            best_ll, best_b = ll, b
    return round(best_b, 2)
