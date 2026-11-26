import hashlib
import json
import sqlite3

import pytest

from app.auth import conn
from app.services.documents import document_root
from helpers import client, head
from test_schedule_drafts import setup_case


@pytest.fixture(params=["legacy", "expanded"])
def context(request):
    user, case_id = setup_case("source-writes@example.com")
    db = conn()
    if request.param == "expanded":
        db.execute("ALTER TABLE evidence ADD COLUMN task_id TEXT REFERENCES tasks(id)")
    return db, head(user), user["user"]["id"], case_id


def fail_then_retry(db, trigger_sql, submit):
    db.execute(trigger_sql)
    before = list(db.iterdump())
    files = originals()
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        submit()
    assert not db.in_transaction
    assert list(db.iterdump()) == before
    assert originals() == files
    db.execute("DROP TRIGGER temp.reject_write")
    response = submit()
    assert response.status_code == 200, response.text
    return response.json()["data"]


def originals():
    return {p: p.read_bytes() for p in document_root().rglob("*") if p.is_file()}


def read_evidence(db, ref, owner, case_id):
    row = db.execute("SELECT * FROM evidence WHERE id=? AND owner_id=? AND case_id=?",
                     (ref, owner, case_id)).fetchone()
    assert row is not None
    if "task_id" in row.keys():
        assert row["task_id"] is None
    return row


def test_text_import_rollback_and_retry(context):
    db, headers, owner, _ = context
    text = "请填写合成申请表。"
    def submit():
        return client.post("/api/v1/imports/text", headers=headers, json={"text": text, "consent": True})
    data = fail_then_retry(db, """CREATE TEMP TRIGGER reject_write BEFORE INSERT ON import_case_sources
                           BEGIN SELECT RAISE(ABORT, 'injected failure'); END""", submit)
    ref = data["evidence_id"]
    row = read_evidence(db, ref, owner, data["case_id"])
    assert (row["source_name"], row["text"]) == ("用户导入文本", text)
    source = db.execute("SELECT case_id,evidence_ids_json FROM import_case_sources WHERE import_id=? AND owner_id=?",
                        (data["id"], owner)).fetchone()
    assert (source["case_id"], json.loads(source["evidence_ids_json"])) == (data["case_id"], [ref])
    path = "/api/v1/imports/" + data["id"]
    job = client.get(path + "/progress", headers=headers).json()["data"]
    assert (job["state"], job["stage"]) == ("completed", "review_required")
    retry = client.post(path + "/retry", headers=headers, json={"consent": True})
    assert retry.status_code == 200
    assert retry.json()["data"]["case_id"] == data["case_id"]


@pytest.mark.parametrize("failure_table", ["case_attachment_documents", "evidence_lines"])
def test_attachment_rollback_and_retry(context, failure_table):
    db, headers, owner, case_id = context
    raw = "合成原件正文".encode()
    before = originals()
    def submit():
        return client.post(f"/api/v1/cases/{case_id}/attachments", headers=headers,
                           files={"file": ("fixture.txt", raw, "text/plain")}, data={"consent": "true"})
    data = fail_then_retry(db, f"""CREATE TEMP TRIGGER reject_write BEFORE INSERT ON {failure_table}
                           BEGIN SELECT RAISE(ABORT, 'injected failure'); END""", submit)
    doc = data["document_id"]
    assert originals() == {**before, document_root() / owner / doc: raw}
    ref, = db.execute("SELECT evidence_id FROM case_attachment_documents WHERE document_id=? AND case_id=? AND owner_id=?",
                      (doc, case_id, owner)).fetchone()
    receipt = read_evidence(db, ref, owner, case_id)
    assert receipt["source_name"] == "用户补充附件记录" and "fixture.txt" in receipt["text"]
    line_ref, = db.execute("SELECT evidence_id FROM evidence_lines WHERE document_id=? AND owner_id=?",
                           (doc, owner)).fetchone()
    assert read_evidence(db, line_ref, owner, case_id)["text"].encode() == raw


def test_knowledge_attach_rollback_and_repeat(context):
    db, headers, owner, case_id = context
    text = "奖学金申请条件为专业排名前20%。"
    document = client.post("/api/v1/knowledge/text", headers=headers,
                           json={"title": "测试条款", "text": text, "consent": True}).json()["data"]
    chunk = client.post("/api/v1/knowledge/search", headers=headers,
                        json={"query": "奖学金"}).json()["data"]["items"][0]
    def submit():
        return client.post(f"/api/v1/cases/{case_id}/knowledge/{chunk['id']}/attach",
                           headers=headers, json={"consent": True})
    data = fail_then_retry(db, """CREATE TEMP TRIGGER reject_write BEFORE INSERT ON knowledge_evidence_sources
                           BEGIN SELECT RAISE(ABORT, 'injected failure'); END""", submit)
    ref = data["evidence_id"]
    assert not data["already_attached"]
    row = read_evidence(db, ref, owner, case_id)
    assert (row["text"], row["source_name"]) == (text, "测试条款")
    link = db.execute("SELECT document_id,chunk_hash FROM knowledge_evidence_sources WHERE evidence_id=? AND owner_id=?",
                      (ref, owner)).fetchone()
    assert tuple(link) == (document["document_id"], hashlib.sha256(text.encode()).hexdigest())
    ids = list(db.execute("SELECT id FROM evidence ORDER BY id"))
    again = submit().json()["data"]
    assert again["already_attached"] and again["evidence_id"] == ref
    assert list(db.execute("SELECT id FROM evidence ORDER BY id")) == ids
