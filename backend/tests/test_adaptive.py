"""Adaptive selection: the maths, the serving loop, and the reporting.

The statistical tests are the cheapest insurance in the suite. An error in the
ability estimate produces a plausible-looking number that is quietly wrong, and
nothing downstream would reveal it.
"""
import pytest

from app.evaluation import adaptive as A


# --- the model -------------------------------------------------------------

def test_information_peaks_where_difficulty_meets_ability():
    """The basis of the selection rule: serve the item pitched at the candidate."""
    for b in (-1.0, 0.0, 1.0):
        at_ability = A.information(b, b)
        assert at_ability == pytest.approx(0.25, abs=1e-6)
        assert at_ability > A.information(b + 2, b)
        assert at_ability > A.information(b - 2, b)


def test_probability_is_even_at_matched_difficulty():
    assert A.probability(0.0, 0.0) == pytest.approx(0.5)
    assert A.probability(2.0, 0.0) > 0.8
    assert A.probability(-2.0, 0.0) < 0.2


def test_ability_rises_with_success_and_falls_with_failure():
    all_right, _ = A.estimate_ability([(0.0, 1.0)] * 5)
    all_wrong, _ = A.estimate_ability([(0.0, 0.0)] * 5)
    mixed, _ = A.estimate_ability([(0.0, 1.0), (0.0, 0.0)] * 2)
    assert all_wrong < mixed < all_right


def test_estimate_stays_finite_when_every_answer_is_correct():
    """Maximum likelihood diverges here; the prior is what keeps this usable."""
    theta, se = A.estimate_ability([(1.0, 1.0)] * 8)
    assert -4.0 < theta < 4.0
    assert se > 0


def test_precision_improves_as_answers_accumulate():
    _, few = A.estimate_ability([(0.0, 1.0)] * 2)
    _, many = A.estimate_ability([(0.0, 1.0)] * 10)
    assert many < few


def test_partial_credit_lands_between_right_and_wrong():
    wrong, _ = A.estimate_ability([(0.0, 0.0)] * 4)
    half, _ = A.estimate_ability([(0.0, 0.5)] * 4)
    right, _ = A.estimate_ability([(0.0, 1.0)] * 4)
    assert wrong < half < right


def test_stopping_requires_a_minimum_number_of_items():
    """One lucky answer can produce a convincing standard error that means nothing."""
    stop, _ = A.should_stop(answered=1, standard_error=0.01,
                            max_questions=10, target_se=0.4, pool_size=10)
    assert stop is False


def test_stopping_on_precision_and_on_length():
    precise, reason = A.should_stop(5, 0.2, 10, 0.4, 10)
    assert precise and reason == "precision"
    long_enough, reason = A.should_stop(10, 0.9, 10, 0.4, 20)
    assert long_enough and reason == "length"


# --- selection -------------------------------------------------------------

class FakeQuestion:
    def __init__(self, id, difficulty, skill):
        self.id, self.difficulty, self.skill = id, difficulty, skill
        self.difficulty_b = None


def test_selection_matches_difficulty_to_ability():
    pool = [FakeQuestion(1, "easy", "A"), FakeQuestion(2, "medium", "B"),
            FakeQuestion(3, "hard", "C")]
    assert A.select_next(pool, set(), theta=-1.5, skill_counts={}).difficulty == "easy"
    assert A.select_next(pool, set(), theta=1.5, skill_counts={}).difficulty == "hard"


def test_selection_spreads_across_subjects():
    """Pure maximum-information selection would measure one topic precisely and
    leave the rest unmeasured."""
    pool = [FakeQuestion(1, "medium", "Algorithms"), FakeQuestion(2, "medium", "Databases")]
    chosen = A.select_next(pool, set(), theta=0.0, skill_counts={"Algorithms": 3})
    assert chosen.skill == "Databases"


def test_served_questions_are_never_repeated():
    pool = [FakeQuestion(1, "medium", "A"), FakeQuestion(2, "medium", "A")]
    assert A.select_next(pool, {1, 2}, theta=0.0, skill_counts={}) is None


# --- the serving loop ------------------------------------------------------

@pytest.fixture()
def adaptive_paper(client, db, make_staff, make_candidate):
    from app.models import Assessment, Question

    office, _ = make_staff("EXO001", role="controller", subjects=())
    make_candidate("21BCS0001")
    make_candidate("21BCS0002")

    spread = [("easy", "Algorithms"), ("medium", "Algorithms"), ("hard", "Algorithms"),
              ("easy", "Databases"), ("medium", "Databases"), ("hard", "Databases")]
    questions = [
        Question(kind="mcq", skill=skill, difficulty=difficulty, max_score=10,
                 prompt=f"{difficulty} {skill} question", options=["a", "b"],
                 correct_option=0, created_by=office.id)
        for difficulty, skill in spread
    ]
    db.add_all(questions)
    db.commit()
    for q in questions:
        db.refresh(q)

    assessment = Assessment(title="Adaptive", question_ids=[q.id for q in questions],
                            duration_minutes=30, mode="adaptive",
                            adaptive_max_questions=4, adaptive_target_se=0.3,
                            created_by=office.id, is_published=True)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment.id


def sit_adaptive(client, headers, assessment_id, correct):
    """Work through an adaptive paper, returning the difficulties served."""
    start = client.post(f"/api/attempts/start/{assessment_id}", headers=headers).json()
    attempt_id = start["attempt"]["id"]
    question = start["questions"][0]
    served = []
    while question:
        served.append(question["difficulty"])
        step = client.post(f"/api/attempts/{attempt_id}/answer", headers=headers, json={
            "question_id": question["id"],
            "selected_option": 0 if correct else 1,
            "seconds_spent": 10}).json()
        question = step["question"]
        if step["finished"]:
            return attempt_id, served, step
    return attempt_id, served, None


def test_only_the_current_question_is_sent(client, adaptive_paper, sit):
    """Sending the pool would let a candidate read every item out of the response."""
    headers = sit(adaptive_paper, "21BCS0001")
    start = client.post(f"/api/attempts/start/{adaptive_paper}", headers=headers).json()
    assert len(start["questions"]) == 1
    assert start["assessment"]["mode"] == "adaptive"


def test_paper_respects_the_question_limit(client, adaptive_paper, sit):
    """Pins an off-by-one: a stale relationship count served one question too many."""
    headers = sit(adaptive_paper, "21BCS0001")
    _, served, step = sit_adaptive(client, headers, adaptive_paper, correct=True)
    assert len(served) == 4
    assert step["answered"] == 4


def test_strong_and_weak_candidates_receive_different_papers(client, adaptive_paper, sit):
    strong_headers = sit(adaptive_paper, "21BCS0001")
    weak_headers = sit(adaptive_paper, "21BCS0002")

    _, strong, strong_step = sit_adaptive(client, strong_headers, adaptive_paper, correct=True)
    _, weak, weak_step = sit_adaptive(client, weak_headers, adaptive_paper, correct=False)

    assert strong != weak
    assert strong_step["ability_percent"] > weak_step["ability_percent"]
    assert "hard" in strong
    assert "easy" in weak


def test_cannot_answer_a_question_that_was_not_served(client, adaptive_paper, sit):
    headers = sit(adaptive_paper, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{adaptive_paper}",
                             headers=headers).json()["attempt"]["id"]
    r = client.post(f"/api/attempts/{attempt_id}/answer", headers=headers,
                    json={"question_id": 9999, "selected_option": 0})
    assert r.status_code == 400


def test_cannot_answer_the_same_question_twice(client, adaptive_paper, sit):
    headers = sit(adaptive_paper, "21BCS0001")
    start = client.post(f"/api/attempts/start/{adaptive_paper}", headers=headers).json()
    attempt_id, question = start["attempt"]["id"], start["questions"][0]
    body = {"question_id": question["id"], "selected_option": 0}
    assert client.post(f"/api/attempts/{attempt_id}/answer", headers=headers, json=body).status_code == 200
    assert client.post(f"/api/attempts/{attempt_id}/answer", headers=headers, json=body).status_code == 409


def test_only_served_questions_count_towards_the_total(client, adaptive_paper, sit):
    """A candidate cannot lose marks for items the algorithm chose not to ask."""
    headers = sit(adaptive_paper, "21BCS0001")
    attempt_id, served, _ = sit_adaptive(client, headers, adaptive_paper, correct=True)
    result = client.get(f"/api/attempts/{attempt_id}", headers=headers).json()
    assert result["max_score"] == len(served) * 10


# --- reporting -------------------------------------------------------------

def test_adaptive_candidates_are_ranked_by_ability_not_marks(client, adaptive_paper, sit):
    """Their scores are out of different totals and are not on a common scale."""
    strong_headers = sit(adaptive_paper, "21BCS0001")
    weak_headers = sit(adaptive_paper, "21BCS0002")
    strong_id, _, _ = sit_adaptive(client, strong_headers, adaptive_paper, correct=True)
    weak_id, _, _ = sit_adaptive(client, weak_headers, adaptive_paper, correct=False)

    strong = client.get(f"/api/analytics/attempt/{strong_id}", headers=strong_headers).json()
    weak = client.get(f"/api/analytics/attempt/{weak_id}", headers=weak_headers).json()

    assert strong["ranked_on"] == weak["ranked_on"] == "ability"
    assert strong["percentile"] > weak["percentile"]


def test_fixed_papers_are_still_ranked_by_score(client, db, make_staff, make_candidate, sit):
    from app.models import Assessment, Question

    rao, _ = make_staff("CS204", subjects=("Algorithms",))
    make_candidate("21BCS0003")
    question = Question(kind="mcq", skill="Algorithms", difficulty="easy", max_score=5,
                        prompt="Q", options=["a", "b"], correct_option=0, created_by=rao.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    assessment = Assessment(title="Fixed", question_ids=[question.id], duration_minutes=10,
                            created_by=rao.id, is_published=True)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    headers = sit(assessment.id, "21BCS0003")
    attempt_id = client.post(f"/api/attempts/start/{assessment.id}",
                             headers=headers).json()["attempt"]["id"]
    client.post(f"/api/attempts/{attempt_id}/submit", headers=headers,
                json={"answers": [{"question_id": question.id, "selected_option": 0}]})

    analytics = client.get(f"/api/analytics/attempt/{attempt_id}", headers=headers).json()
    assert analytics["ranked_on"] == "score"
    assert analytics["adaptive"] is None
