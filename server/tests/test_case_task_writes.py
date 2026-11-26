import json

import pytest

from app.auth import conn
from helpers import client, head
from test_schedule_drafts import setup_case


@pytest.fixture(params=["legacy", "expanded"])
def case_context(request):
    account, case_id = setup_case("task-writes@example.com")
    db = conn()
    if request.param == "expanded":
        db.execute("ALTER TABLE evidence ADD COLUMN task_id TEXT REFERENCES tasks(id)")
    return db, account["user"]["id"], case_id, head(account)


def check_case_evidence(db, ref, owner, case_id, source):
    row = db.execute("SELECT * FROM evidence WHERE id=?", (ref,)).fetchone()
    assert (row["owner_id"], row["case_id"], row["source_name"]) == (owner, case_id, source)
    if "task_id" in row.keys():
        assert row["task_id"] is None
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
    return row["text"]


def test_manual_task_preserves_source_and_adds_timing_evidence(case_context):
    db, owner, case_id, headers = case_context
    source = db.execute("SELECT id FROM evidence WHERE owner_id=? AND case_id=? LIMIT 1",
                        (owner, case_id)).fetchone()["id"]
    response = client.post(f"/api/v1/cases/{case_id}/tasks", headers=headers, json={
        "title": "准备材料", "duration_minutes": 45, "evidence_ids": [source],
    })
    assert response.status_code == 200, response.text
    task = db.execute("SELECT * FROM tasks WHERE id=?", (response.json()["data"]["id"],)).fetchone()
    assert (task["owner_id"], task["case_id"], task["duration_minutes"]) == (owner, case_id, 45)
    original, timing = json.loads(task["evidence_ids_json"])
    assert original == source and timing != source
    assert "45分钟" in check_case_evidence(db, timing, owner, case_id, "用户填写任务安排")


def test_dependency_preserves_direction_and_evidence(case_context):
    db, owner, case_id, headers = case_context
    path = f"/api/v1/cases/{case_id}"
    tasks = client.get(path + "/plan", headers=headers).json()["data"]["ordered_tasks"]
    before, after = tasks
    assert before["is_actionable"] and after["is_actionable"]
    response = client.post(path + "/edges", headers=headers, json={
        "before_task_id": before["id"], "after_task_id": after["id"],
    })
    assert response.status_code == 200, response.text
    edge_id = response.json()["data"]["id"]
    edge = db.execute("SELECT * FROM task_edges WHERE id=?", (edge_id,)).fetchone()
    assert (edge["owner_id"], edge["case_id"]) == (owner, case_id)
    assert (edge["before_task_id"], edge["after_task_id"]) == (before["id"], after["id"])
    link = db.execute("SELECT * FROM task_edge_evidence WHERE edge_id=?", (edge_id,)).fetchone()
    assert (link["owner_id"], link["source"]) == (owner, "user_input")
    ref, = json.loads(link["evidence_ids_json"])
    text = check_case_evidence(db, ref, owner, case_id, "用户填写依赖")
    assert before["title"] in text and after["title"] in text
    updated = client.get(path + "/plan", headers=headers).json()["data"]["ordered_tasks"]
    assert {t["id"]: t["is_actionable"] for t in updated} == {before["id"]: True, after["id"]: False}
