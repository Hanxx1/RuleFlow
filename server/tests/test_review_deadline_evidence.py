import json

import pytest

from app.auth import conn
from app.services.review import compiled_task_id, invalidate_review
from helpers import client, head
from test_schedule_drafts import setup_case


@pytest.mark.parametrize("scope", ["task", "case"])
@pytest.mark.parametrize("expanded", [False, True], ids=["legacy", "with-task-id"])
@pytest.mark.parametrize("conflict", [False, True], ids=["allowed", "conflict"])
def test_deadline_confirmation_with_existing_schedule(scope, expanded, conflict):
    account, case_id = setup_case("review-deadline@example.com")
    owner, headers = account["user"]["id"], head(account)
    path = f"/api/v1/cases/{case_id}"
    actions = client.get(path + "/reviews", headers=headers).json()["data"]["candidate"]["actions"]
    task_ids = [compiled_task_id(owner, case_id, action["id"], action) for action in actions]
    first, second = task_ids
    planning = client.put(f"/api/v1/tasks/{first}/planning", headers=headers,
                          json={"duration_minutes": 30})
    assert planning.status_code == 200, planning.text
    planning_ref, = planning.json()["data"]["evidence_ids"]
    schedule = client.post("/api/v1/schedule/items", headers=headers, json={
        "case_id": case_id, "task_id": first, "kind": "task", "title": "截止复核样例",
        "starts_at": "2099-01-10T10:00:00+08:00", "ends_at": "2099-01-10T10:30:00+08:00",
    })
    assert schedule.status_code == 200, schedule.text
    schedule_query = "SELECT * FROM schedule_items WHERE id=?"
    schedule_key = (schedule.json()["data"]["id"],)
    with conn() as db:
        invalidate_review(db, owner, case_id)
        if expanded:
            db.execute("ALTER TABLE evidence ADD COLUMN task_id TEXT REFERENCES tasks(id)")
    original_schedule = tuple(db.execute(schedule_query, schedule_key).fetchone())
    original_ids = {row[0] for row in db.execute("SELECT id FROM evidence")}
    deadline = "2099-01-09" if conflict else "2099-01-11"
    revision = client.get(path + "/reviews", headers=headers).json()["data"]["revision"]
    body = dict(revision=revision, action_ids=[action["id"] for action in actions], consent=True)
    if scope == "task":
        body.update(no_deadline=True, task_deadlines={actions[0]["id"]: {"manual_deadline": deadline}})
    else:
        body["manual_deadline"] = deadline

    before = list(db.iterdump())
    response = client.post(path + "/confirm", headers=headers, json=body)
    assert tuple(db.execute(schedule_query, schedule_key).fetchone()) == original_schedule
    if conflict:
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "REVIEW_SCHEDULE_CONFLICT"
        assert list(db.iterdump()) == before
        return

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "confirmed"
    ref, = {row[0] for row in db.execute("SELECT id FROM evidence")} - original_ids
    evidence = db.execute("SELECT * FROM evidence WHERE id=?", (ref,)).fetchone()
    assert (evidence["owner_id"], evidence["case_id"], evidence["source_name"]) == (owner, case_id, "用户确认")
    assert deadline in evidence["text"]
    if expanded:
        assert evidence["task_id"] is None
    case = db.execute("SELECT deadline, deadline_source, deadline_evidence_ids_json FROM cases WHERE id=?",
                      (case_id,)).fetchone()
    assert case["deadline"] == (deadline if scope == "case" else None)
    assert case["deadline_source"] == ("user_input" if scope == "case" else None)
    assert json.loads(case["deadline_evidence_ids_json"]) == ([ref] if scope == "case" else [])
    for task_id, action in zip((first, second), actions):
        task = db.execute("SELECT deadline, evidence_ids_json FROM tasks WHERE id=?", (task_id,)).fetchone()
        has_deadline = scope == "case" or task_id == first
        assert task["deadline"] == (deadline if has_deadline else None)
        refs = set(action["evidence_ids"])
        if task_id == first:
            refs.add(planning_ref)
        if has_deadline:
            refs.add(ref)
        assert set(json.loads(task["evidence_ids_json"])) == refs
