"""Sitting a paper: codes, timing, resumption and the limits on re-sitting.

Several of these pin down defects that a candidate could have benefited from.
A regression in the clock test in particular would restore a hole that let a
paper be sat indefinitely by reloading the page.
"""
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture()
def paper(client, db, make_staff, make_candidate):
    from app.models import Assessment, Question

    rao, _ = make_staff("CS204", subjects=("Algorithms",))
    make_candidate("21BCS0001")
    make_candidate("21BCS0002")

    questions = [
        Question(kind="mcq", skill="Algorithms", difficulty="easy", max_score=5,
                 prompt=f"Question {i}", options=["a", "b"], correct_option=0,
                 created_by=rao.id)
        for i in range(3)
    ]
    db.add_all(questions)
    db.commit()
    for q in questions:
        db.refresh(q)

    assessment = Assessment(title="Paper", question_ids=[q.id for q in questions],
                            duration_minutes=45, created_by=rao.id, is_published=True)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment.id, [q.id for q in questions]


# --- exam codes ------------------------------------------------------------

def test_code_is_single_use(client, paper, issue_code):
    assessment_id, _ = paper
    code = issue_code(assessment_id, "21BCS0001", "ONCE-ONLY")

    first = client.post("/api/auth/exam",
                        json={"enrollment_no": "21BCS0001", "access_code": code})
    assert first.status_code == 200

    second = client.post("/api/auth/exam",
                         json={"enrollment_no": "21BCS0001", "access_code": code})
    assert second.status_code == 409


def test_code_is_case_insensitive(client, paper, issue_code):
    assessment_id, _ = paper
    issue_code(assessment_id, "21BCS0001", "MIXED-CASE")
    r = client.post("/api/auth/exam",
                    json={"enrollment_no": "21BCS0001", "access_code": "mixed-case"})
    assert r.status_code == 200


def test_wrong_code_and_unknown_enrolment_look_identical(client, paper, issue_code):
    """Distinguishing them would let the register be probed for who is scheduled."""
    assessment_id, _ = paper
    issue_code(assessment_id, "21BCS0001", "REAL-CODE")

    wrong = client.post("/api/auth/exam",
                        json={"enrollment_no": "21BCS0001", "access_code": "WRONG"})
    unknown = client.post("/api/auth/exam",
                          json={"enrollment_no": "99XXX9999", "access_code": "REAL-CODE"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_code_opens_only_the_paper_it_was_issued_for(client, db, paper, issue_code, make_staff):
    from app.models import Assessment

    assessment_id, question_ids = paper
    other = Assessment(title="Other paper", question_ids=question_ids,
                       duration_minutes=30, is_published=True)
    db.add(other)
    db.commit()
    db.refresh(other)

    code = issue_code(assessment_id, "21BCS0001", "SCOPED")
    headers = {"Authorization": "Bearer " + client.post(
        "/api/auth/exam", json={"enrollment_no": "21BCS0001", "access_code": code}
    ).json()["access_token"]}

    assert client.post(f"/api/attempts/start/{assessment_id}", headers=headers).status_code == 200
    assert client.post(f"/api/attempts/start/{other.id}", headers=headers).status_code == 403


# --- the clock -------------------------------------------------------------

def test_remaining_time_survives_a_reload(client, db, paper, sit):
    """The defect this pins: the clock restarted at full duration on every load,
    so a 45-minute paper could be sat indefinitely by refreshing."""
    from app.models import Attempt

    assessment_id, _ = paper
    headers = sit(assessment_id, "21BCS0001")
    first = client.post(f"/api/attempts/start/{assessment_id}", headers=headers).json()
    attempt_id = first["attempt"]["id"]
    assert first["assessment"]["seconds_remaining"] > 2600

    attempt = db.get(Attempt, attempt_id)
    attempt.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.commit()

    resumed = client.post(f"/api/attempts/start/{assessment_id}", headers=headers).json()
    assert 800 < resumed["assessment"]["seconds_remaining"] < 1000


def test_expired_paper_reports_no_time_left(client, db, paper, sit):
    from app.models import Attempt

    assessment_id, _ = paper
    headers = sit(assessment_id, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=headers).json()["attempt"]["id"]

    attempt = db.get(Attempt, attempt_id)
    attempt.started_at = datetime.now(timezone.utc) - timedelta(minutes=70)
    db.commit()

    resumed = client.post(f"/api/attempts/start/{assessment_id}", headers=headers).json()
    assert resumed["assessment"]["seconds_remaining"] == 0


def test_late_submission_is_flagged_not_rejected(client, db, paper, sit):
    """Discarding the work would punish someone whose connection dropped."""
    from app.models import Attempt

    assessment_id, question_ids = paper
    headers = sit(assessment_id, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=headers).json()["attempt"]["id"]

    attempt = db.get(Attempt, attempt_id)
    attempt.started_at = datetime.now(timezone.utc) - timedelta(minutes=70)
    db.commit()

    r = client.post(f"/api/attempts/{attempt_id}/submit", headers=headers,
                    json={"answers": [{"question_id": question_ids[0], "selected_option": 0}]})
    assert r.status_code == 200
    assert r.json()["integrity_flags"] >= 1


# --- drafts and resumption -------------------------------------------------

def test_draft_is_restored_on_resume(client, paper, sit):
    assessment_id, question_ids = paper
    headers = sit(assessment_id, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=headers).json()["attempt"]["id"]

    client.put(f"/api/attempts/{attempt_id}/draft", headers=headers, json={"answers": [
        {"question_id": question_ids[0], "selected_option": 1, "seconds_spent": 42}]})

    resumed = client.post(f"/api/attempts/start/{assessment_id}", headers=headers).json()
    assert len(resumed["draft_answers"]) == 1
    assert resumed["draft_answers"][0]["selected_option"] == 1
    assert resumed["draft_answers"][0]["seconds_spent"] == 42


def test_drafts_are_not_graded(client, db, paper, sit):
    """Unsubmitted work must not reach the grader or the plagiarism comparison,
    which reads every other submission for the same question."""
    from app.models import Answer

    assessment_id, question_ids = paper
    headers = sit(assessment_id, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=headers).json()["attempt"]["id"]
    client.put(f"/api/attempts/{attempt_id}/draft", headers=headers, json={"answers": [
        {"question_id": question_ids[0], "selected_option": 0}]})

    assert db.query(Answer).filter(Answer.attempt_id == attempt_id).count() == 0


def test_draft_cannot_be_saved_after_submission(client, paper, sit):
    assessment_id, question_ids = paper
    headers = sit(assessment_id, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=headers).json()["attempt"]["id"]
    client.post(f"/api/attempts/{attempt_id}/submit", headers=headers,
                json={"answers": [{"question_id": question_ids[0], "selected_option": 0}]})

    r = client.put(f"/api/attempts/{attempt_id}/draft", headers=headers, json={"answers": []})
    assert r.status_code == 409


def test_another_candidate_cannot_write_to_your_draft(client, paper, sit, issue_code):
    assessment_id, _ = paper
    mine = sit(assessment_id, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=mine).json()["attempt"]["id"]

    theirs = sit(assessment_id, "21BCS0002")
    assert client.put(f"/api/attempts/{attempt_id}/draft", headers=theirs,
                      json={"answers": []}).status_code == 404


# --- one sitting per code --------------------------------------------------

def test_submitting_ends_the_sitting_for_that_code(client, paper, sit):
    assessment_id, question_ids = paper
    headers = sit(assessment_id, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=headers).json()["attempt"]["id"]
    client.post(f"/api/attempts/{attempt_id}/submit", headers=headers,
                json={"answers": [{"question_id": question_ids[0], "selected_option": 0}]})

    assert client.post(f"/api/attempts/start/{assessment_id}",
                       headers=headers).status_code == 409


def test_a_fresh_code_permits_a_new_sitting(client, paper, sit, issue_code):
    """A machine dying mid-paper has to be recoverable, and the recovery path is
    the one invigilators already use rather than a separate override."""
    assessment_id, question_ids = paper
    first = sit(assessment_id, "21BCS0001", issue_code(assessment_id, "21BCS0001", "FIRST"))
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=first).json()["attempt"]["id"]
    client.post(f"/api/attempts/{attempt_id}/submit", headers=first,
                json={"answers": [{"question_id": question_ids[0], "selected_option": 0}]})

    second = sit(assessment_id, "21BCS0001", issue_code(assessment_id, "21BCS0001", "SECOND"))
    resumed = client.post(f"/api/attempts/start/{assessment_id}", headers=second)
    assert resumed.status_code == 200
    assert resumed.json()["attempt"]["id"] != attempt_id


def test_unfinished_attempt_is_handed_back_not_restarted(client, paper, sit):
    assessment_id, _ = paper
    headers = sit(assessment_id, "21BCS0001")
    first = client.post(f"/api/attempts/start/{assessment_id}", headers=headers).json()
    again = client.post(f"/api/attempts/start/{assessment_id}", headers=headers).json()
    assert first["attempt"]["id"] == again["attempt"]["id"]


# --- integrity events ------------------------------------------------------

def test_integrity_event_records_the_question_on_screen(client, paper, sit):
    """A bare count cannot distinguish a noisy laptop from a cluster on one question."""
    assessment_id, question_ids = paper
    headers = sit(assessment_id, "21BCS0001")
    attempt_id = client.post(f"/api/attempts/start/{assessment_id}",
                             headers=headers).json()["attempt"]["id"]

    client.post(f"/api/attempts/{attempt_id}/events", headers=headers, json={
        "event_type": "paste", "detail": "412 chars", "question_id": question_ids[1]})
    client.post(f"/api/attempts/{attempt_id}/submit", headers=headers, json={
        "answers": [{"question_id": q, "selected_option": 0} for q in question_ids]})

    analytics = client.get(f"/api/analytics/attempt/{attempt_id}", headers=headers).json()
    flagged = [row for row in analytics["timeline"] if row["flags"]]
    assert len(flagged) == 1
    assert flagged[0]["question_id"] == question_ids[1]
    assert flagged[0]["flags"][0]["label"] == "Pasted text into an answer"


# --- what a candidate is shown ---------------------------------------------

def test_candidate_sees_only_the_paper_their_code_opens(client, db, paper, sit):
    """Listing every published paper made the first screen a menu of exams the
    candidate cannot open, which is noise at the worst possible moment."""
    from app.models import Assessment

    assessment_id, question_ids = paper
    other = Assessment(title="Someone else's paper", question_ids=question_ids,
                       duration_minutes=30, is_published=True)
    db.add(other)
    db.commit()

    headers = sit(assessment_id, "21BCS0001")
    listed = client.get("/api/assessments", headers=headers).json()
    assert [a["id"] for a in listed] == [assessment_id]


def test_staff_still_see_every_paper_they_own(client, db, paper, make_staff, auth):
    from app.models import Assessment

    assessment_id, question_ids = paper
    rao = db.query(__import__("app.models", fromlist=["User"]).User).filter_by(staff_id="CS204").first()
    second = Assessment(title="Rao's other paper", question_ids=question_ids,
                        duration_minutes=20, created_by=rao.id, is_published=False)
    db.add(second)
    db.commit()

    headers = auth("CS204", "pw-for-tests")
    listed = client.get("/api/assessments", headers=headers).json()
    assert len(listed) == 2
