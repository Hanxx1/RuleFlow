import json

import pytest

from app.auth import conn
from helpers import client, head
from test_schedule_drafts import setup_case


@pytest.mark.parametrize("expanded", [False, True], ids=["legacy", "with-task-id"])
def test_planning_preferences_keep_case_evidence(expanded):
    account, case_id = setup_case("planning-evidence@example.com")
    headers = head(account)
    plan = client.get(f"/api/v1/cases/{case_id}/plan", headers=headers)
    task_id = plan.json()["data"]["ordered_tasks"][0]["id"]
    db = conn()
    if expanded:
        db.execute("ALTER TABLE evidence ADD COLUMN task_id TEXT REFERENCES tasks(id)")
    task_query = "SELECT duration_minutes, evidence_ids_json FROM tasks WHERE id=?"
    prior_refs = json.loads(db.execute(task_query, (task_id,)).fetchone()["evidence_ids_json"])
    body = dict(duration_minutes=90, splittable=True, min_chunk_minutes=30,
                max_chunk_minutes=60, importance=0.7, preference=0.4)
    response = client.put(f"/api/v1/tasks/{task_id}/planning", headers=headers, json=body)
    assert response.status_code == 200, response.text
    ref, = response.json()["data"]["evidence_ids"]

    row = db.execute("SELECT * FROM evidence WHERE id=?", (ref,)).fetchone()
    assert row["owner_id"] == account["user"]["id"]
    assert row["case_id"] == case_id
    assert row["source_name"] == "用户排程偏好"
    assert "90分钟" in row["text"]
    assert row["locator"] == "用户填写，不代表官方通知"
    assert row["page"] is None and row["created_at"]
    if expanded:
        assert row["task_id"] is None
    duration, refs = db.execute(task_query, (task_id,)).fetchone()
    assert duration == 90
    assert ref not in prior_refs and set(json.loads(refs)) == set(prior_refs) | {ref}
    saved = db.execute("SELECT * FROM task_planning WHERE task_id=?", (task_id,)).fetchone()
    assert saved["evidence_id"] == ref
    assert saved["owner_id"] == row["owner_id"]
    for key in ("splittable", "min_chunk_minutes", "max_chunk_minutes", "importance", "preference"):
        assert saved[key] == body[key]
