"""RF-038/039 compatibility baseline for an existing Case task and its EvidenceRef."""
import json
import sqlite3
from contextlib import closing

from app import auth
from app.bootstrap import database
from helpers import account, client, confirm_import, head


def test_legacy_case_task_status_and_evidence_survive_restore(tmp_path, monkeypatch):
    original = tmp_path / "legacy.sqlite"
    restored = tmp_path / "restored.sqlite"
    monkeypatch.setattr(auth, "DB", original)
    database()
    user = account("legacy-task@example.com")
    headers = head(user)
    notice = "请准备实验报告。"
    imported = client.post("/api/v1/imports/text", headers=headers,
                           json={"text": notice, "consent": True})
    assert imported.status_code == 200
    case_id = imported.json()["data"]["case_id"]
    resources_url = f"/api/v1/cases/{case_id}/resources"

    def resources():
        response = client.get(resources_url, headers=headers)
        assert response.status_code == 200
        return response.json()["data"]

    source_rows = resources()["evidence"]
    evidence = next(row for row in source_rows if notice in row["text"])
    refs = [evidence["id"]]
    title = "整理实验报告（兼容基线）"
    payload = {"title": title, "evidence_ids": refs}
    create_url = f"/api/v1/cases/{case_id}/tasks"
    assert client.post(create_url, headers=headers, json=payload).status_code == 409
    confirm_import(user, case_id)
    creation = client.post(create_url, headers=headers, json=payload)
    assert creation.status_code == 200
    task = creation.json()["data"]
    task_id = task["id"]
    owner = evidence["owner_id"]

    def check_task(row, status):
        assert (row["id"], row["case_id"], row["owner_id"], row["title"],
                row["evidence_ids"], row["status"]) == (task_id, case_id, owner, title, refs, status)

    before = resources()
    assert [r["id"] for r in before["tasks"] if r["title"] == title] == [task_id]
    original_ids = {r["id"] for r in before["tasks"]}
    check_task(task, "todo")
    check_task(next(r for r in before["tasks"] if r["id"] == task_id), "todo")

    def persisted(path):
        with closing(sqlite3.connect(path)) as conn:
            return conn.execute("SELECT id, case_id, owner_id, title, evidence_ids_json, status "
                                "FROM tasks WHERE id=?", (task_id,)).fetchone()

    with closing(sqlite3.connect(original)) as source, closing(sqlite3.connect(restored)) as target:
        source.backup(target)
    baseline = persisted(original)
    assert persisted(restored) == baseline
    monkeypatch.setattr(auth, "DB", restored)
    for status in ("in_progress", "done"):
        response = client.patch(f"/api/v1/tasks/{task_id}", headers=headers, json={"status": status})
        assert response.status_code == 200
        check_task(response.json()["data"], status)
        current = resources()
        assert {r["id"] for r in current["tasks"]} == original_ids
        check_task(next(r for r in current["tasks"] if r["id"] == task_id), status)
        assert next(r for r in current["evidence"] if r["id"] == refs[0]) == evidence
        actual = persisted(restored)
        assert actual[:4] == (task_id, case_id, owner, title)
        assert json.loads(actual[4]) == refs and actual[5] == status
    assert persisted(original) == baseline and baseline[5] == "todo"
    print("BASELINE " + json.dumps(dict(task_id=task_id, case_id=case_id, owner_id=owner,
          evidence_ids=refs, status_sequence=["todo", "in_progress", "done"],
          case_task_count=len(original_ids), original_status=baseline[5]), ensure_ascii=False))
