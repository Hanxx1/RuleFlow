import json
import sqlite3

import pytest

from app.auth import conn
from helpers import account, client, head


@pytest.fixture
def confirmed_case():
    user = account("case-deadline@example.com")
    headers = head(user)
    imported = client.post("/api/v1/imports/text", headers=headers, json={
        "text": "请准备申请表。报名截止2026-10-25。", "consent": True,
    })
    case_id = imported.json()["data"]["case_id"]
    path = f"/api/v1/cases/{case_id}"
    review = client.get(path + "/reviews", headers=headers).json()["data"]
    deadline = next(d for d in review["candidate"]["dates"] if d["role"] == "deadline")
    response = client.post(path + "/confirm", headers=headers, json={
        "revision": review["revision"], "consent": True, "deadline_id": deadline["id"],
        "action_ids": [action["id"] for action in review["candidate"]["actions"]],
    })
    assert response.status_code == 200, response.text
    return case_id, headers, user["user"]["id"]


@pytest.mark.parametrize("expanded", [False, True], ids=["legacy", "with-task-id"])
@pytest.mark.parametrize("operation", ["create", "edit"])
@pytest.mark.parametrize("reject_write", [False, True], ids=["save", "rollback"])
def test_case_deadline_evidence(confirmed_case, expanded, operation, reject_write):
    case_id, headers, owner = confirmed_case
    path = f"/api/v1/cases/{case_id}"
    db = conn()
    if expanded:
        db.execute("ALTER TABLE evidence ADD COLUMN task_id TEXT REFERENCES tasks(id)")
    original = client.get(path, headers=headers).json()["data"]
    old_refs = original["deadline_evidence_ids"]
    assert old_refs and (original["deadline"], original["deadline_source"]) == ("2026-10-25", "document")
    review = client.get(path + "/reviews", headers=headers).json()["data"]
    assert review["status"] == "confirmed" and review["decision"] and review["confirmed_at"]
    deadline = "2099-01-12"

    def save():
        if operation == "create":
            return client.post("/api/v1/cases", headers=headers, json={"title": "测试事项", "deadline": deadline})
        return client.patch(path, headers=headers, json={"deadline": deadline})

    if reject_write:
        db.execute("""CREATE TEMP TRIGGER reject_deadline BEFORE INSERT ON evidence
                      WHEN NEW.source_name = '用户填写'
                      BEGIN SELECT RAISE(ABORT, 'test deadline write failure'); END""")
        before = list(db.iterdump())
        with pytest.raises(sqlite3.IntegrityError, match="test deadline write failure"):
            save()
        assert not db.in_transaction
        assert list(db.iterdump()) == before
        return

    prior_ids = {r[0] for r in db.execute("SELECT id FROM evidence")}
    response = save()
    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    saved_id = saved["id"]
    assert (saved_id == case_id) == (operation == "edit")
    ref, = saved["deadline_evidence_ids"]
    assert (saved["deadline"], saved["deadline_source"]) == (deadline, "user_input")
    row = db.execute("SELECT deadline, deadline_source, deadline_evidence_ids_json FROM cases WHERE id=?",
                     (saved_id,)).fetchone()
    assert (row["deadline"], row["deadline_source"], json.loads(row["deadline_evidence_ids_json"])) == (
        deadline, "user_input", [ref])
    assert {r[0] for r in db.execute("SELECT id FROM evidence")} - prior_ids == {ref}
    evidence = db.execute("SELECT * FROM evidence WHERE id=?", (ref,)).fetchone()
    assert (evidence["owner_id"], evidence["case_id"], evidence["source_name"]) == (owner, saved_id, "用户填写")
    assert evidence["text"] == f"用户填写截止时间为 {deadline}"
    if "task_id" in evidence.keys():
        assert evidence["task_id"] is None
    if operation == "edit":
        assert all(db.execute("SELECT 1 FROM evidence WHERE id=? AND case_id=? AND owner_id=?",
                              (old_ref, case_id, owner)).fetchone() for old_ref in old_refs)
        updated = client.get(path + "/reviews", headers=headers).json()["data"]
        assert (updated["status"], updated["revision"]) == ("needs_confirmation", review["revision"] + 1)
        assert updated["decision"] is None and updated["confirmed_at"] is None
