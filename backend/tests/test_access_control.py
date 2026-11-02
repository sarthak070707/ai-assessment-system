"""Who may see and do what.

These are the tests that would catch a leak rather than a miscalculation. Most
of them assert a refusal, which is easy to break without noticing: loosening an
authorisation check does not make anything fail visibly, it just quietly lets
the wrong person through.
"""
import pytest


@pytest.fixture()
def world(client, db, make_staff, make_candidate, auth):
    """Two examiners with separate subjects, an exam office, and a candidate."""
    from app.models import Assessment, Question

    office, office_pw = make_staff("EXO001", role="controller", subjects=())
    rao, rao_pw = make_staff("CS204", subjects=("Algorithms",))
    sharma, sharma_pw = make_staff("CS311", subjects=("Databases",))
    candidate = make_candidate("21BCS0001")

    rao_q = Question(kind="mcq", skill="Algorithms", difficulty="easy", max_score=5,
                     prompt="Complexity of binary search?", options=["O(1)", "O(log n)"],
                     correct_option=1, created_by=rao.id)
    sharma_q = Question(kind="mcq", skill="Databases", difficulty="medium", max_score=5,
                        prompt="Which NF removes transitive dependencies?",
                        options=["1NF", "3NF"], correct_option=1, created_by=sharma.id)
    db.add_all([rao_q, sharma_q])
    db.commit()
    db.refresh(rao_q)
    db.refresh(sharma_q)

    paper = Assessment(title="Rao's paper", question_ids=[rao_q.id], duration_minutes=30,
                       created_by=rao.id, is_published=True)
    db.add(paper)
    db.commit()
    db.refresh(paper)

    return {
        "office": auth("EXO001", office_pw),
        "rao": auth("CS204", rao_pw),
        "sharma": auth("CS311", sharma_pw),
        "rao_q": rao_q.id, "sharma_q": sharma_q.id,
        "paper": paper.id, "candidate": candidate.enrollment_no,
    }


# --- examiners cannot see each other's work --------------------------------

def test_examiner_sees_only_their_own_questions(client, world):
    mine = client.get("/api/questions", headers=world["rao"]).json()
    assert [q["id"] for q in mine] == [world["rao_q"]]


def test_exam_office_sees_every_examiner_s_questions(client, world):
    everything = client.get("/api/questions", headers=world["office"]).json()
    assert {q["id"] for q in everything} == {world["rao_q"], world["sharma_q"]}


def test_foreign_question_reports_404_not_403(client, world):
    """403 confirms the question exists, which itself discloses a paper in preparation."""
    r = client.get(f"/api/questions/{world['sharma_q']}", headers=world["rao"])
    assert r.status_code == 404


def test_examiner_cannot_edit_a_colleague_s_question(client, world):
    body = {"kind": "mcq", "skill": "Databases", "prompt": "hijacked",
            "options": ["a", "b"], "correct_option": 0, "max_score": 5}
    assert client.put(f"/api/questions/{world['sharma_q']}",
                      headers=world["rao"], json=body).status_code == 404


def test_skills_list_does_not_disclose_other_subjects(client, world):
    assert client.get("/api/questions/skills", headers=world["rao"]).json() == ["Algorithms"]


# --- subject boundaries ----------------------------------------------------

def test_examiner_cannot_author_outside_their_subjects(client, world):
    r = client.post("/api/questions", headers=world["rao"], json={
        "kind": "mcq", "skill": "Databases", "prompt": "Into someone else's subject",
        "options": ["a", "b"], "correct_option": 0, "max_score": 5})
    assert r.status_code == 403


def test_exam_office_is_not_subject_bound(client, world):
    r = client.post("/api/questions", headers=world["office"], json={
        "kind": "mcq", "skill": "Anything At All", "prompt": "Office override",
        "options": ["a", "b"], "correct_option": 0, "max_score": 5})
    assert r.status_code == 201


# --- the hole worth closing: assembling a paper from foreign questions -----

def test_cannot_build_a_paper_from_a_colleague_s_questions(client, world):
    """Hiding questions from a list means nothing if their ids can still be posted."""
    r = client.post("/api/assessments", headers=world["rao"], json={
        "title": "Sneaky", "question_ids": [world["sharma_q"]], "duration_minutes": 10})
    assert r.status_code == 403


def test_blocked_even_when_mixed_with_own_questions(client, world):
    r = client.post("/api/assessments", headers=world["rao"], json={
        "title": "Mixed", "question_ids": [world["rao_q"], world["sharma_q"]],
        "duration_minutes": 10})
    assert r.status_code == 403


# --- portals do not blur ---------------------------------------------------

def test_candidate_cannot_sign_in_at_the_staff_door(client, world, issue_code):
    code = issue_code(world["paper"], world["candidate"], "DOORTEST")
    r = client.post("/api/auth/login",
                    data={"username": world["candidate"], "password": code})
    assert r.status_code == 401


def test_staff_cannot_sign_in_with_an_exam_code(client, world):
    r = client.post("/api/auth/exam",
                    json={"enrollment_no": "CS204", "access_code": "pw-for-tests"})
    assert r.status_code == 401


def test_candidate_cannot_reach_the_question_bank(client, world, sit):
    headers = sit(world["paper"], world["candidate"])
    assert client.get("/api/questions", headers=headers).status_code == 403


def test_candidate_cannot_issue_exam_codes(client, world, sit):
    headers = sit(world["paper"], world["candidate"])
    r = client.post("/api/candidates/codes", headers=headers,
                    json={"assessment_id": world["paper"], "enrollment_numbers": ["21BCS0001"]})
    assert r.status_code == 403


# --- answer keys never leave the server ------------------------------------

def test_candidate_payload_carries_no_answer_key(client, world, sit):
    headers = sit(world["paper"], world["candidate"])
    served = client.post(f"/api/attempts/start/{world['paper']}", headers=headers).json()
    for question in served["questions"]:
        assert "correct_option" not in question
        assert "test_cases" not in question
        assert "reference_answer" not in question


# --- staff account lifecycle ----------------------------------------------

def test_temporary_password_blocks_every_staff_route(client, world):
    """Enforced on the server: the interface cannot be the thing holding the door."""
    created = client.post("/api/staff", headers=world["office"], json={
        "staff_id": "ME402", "full_name": "Dr. Mehta", "subjects": ["Mechanical"]}).json()

    r = client.post("/api/auth/login",
                    data={"username": "ME402", "password": created["temporary_password"]})
    assert r.status_code == 200
    assert r.json()["user"]["must_change_password"] is True

    headers = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert client.get("/api/questions", headers=headers).status_code == 428

    client.post("/api/staff/change-password", headers=headers, json={
        "current_password": created["temporary_password"], "new_password": "a-real-password"})
    after = client.post("/api/auth/login",
                        data={"username": "ME402", "password": "a-real-password"})
    assert after.status_code == 200
    assert client.get("/api/questions",
                      headers={"Authorization": "Bearer " + after.json()["access_token"]}
                      ).status_code == 200


def test_old_temporary_password_stops_working(client, world):
    created = client.post("/api/staff", headers=world["office"], json={
        "staff_id": "ME403", "full_name": "Dr. Singh", "subjects": ["Civil"]}).json()
    temp = created["temporary_password"]
    login = client.post("/api/auth/login", data={"username": "ME403", "password": temp})
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    client.post("/api/staff/change-password", headers=headers,
                json={"current_password": temp, "new_password": "something-else-entirely"})

    assert client.post("/api/auth/login",
                       data={"username": "ME403", "password": temp}).status_code == 401


def test_examiner_cannot_create_staff(client, world):
    r = client.post("/api/staff", headers=world["rao"],
                    json={"staff_id": "X1", "full_name": "X", "subjects": ["Algorithms"]})
    assert r.status_code == 403
