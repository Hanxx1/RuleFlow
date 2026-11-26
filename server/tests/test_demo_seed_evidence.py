import json
import sqlite3
from dataclasses import replace

import pytest

from app.auth import conn
from app.demo import bootstrap


def expected_task_refs(owner, case_id, nodes, blocks, *, assessment=False):
    by_id = {block["id"]: block for block in blocks}
    expected = {}
    for task in nodes:
        task_key = ("task:" if assessment else "") + task["id"]
        refs = []
        for key in task["evidence" if assessment else "evidence_ids"]:
            evidence_key = ("evidence:" if assessment else "") + key
            ref = "block:" + bootstrap._id(owner, evidence_key)
            refs.append((ref, by_id[key]["source_name"], by_id[key]["text"]))
        assert refs
        expected[bootstrap._id(owner, task_key)] = (case_id, refs)
    return expected


@pytest.mark.parametrize("account_seed", [False, True], ids=["public", "account"])
@pytest.mark.parametrize("expanded", [False, True], ids=["legacy", "with-task-id"])
def test_demo_seed_recovers_and_preserves_task_evidence(monkeypatch, account_seed, expanded):
    db = conn()
    owner = "demo-fixture-owner"
    monkeypatch.setattr(bootstrap, "SETTINGS", replace(bootstrap.SETTINGS, demo_mode=True))
    with db:
        db.execute("INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)",
                   (owner, "fixture@example.test", "unused", "now"))
        if expanded:
            db.execute("ALTER TABLE evidence ADD COLUMN task_id TEXT REFERENCES tasks(id)")

    def seed():
        if account_seed:
            return bootstrap.bootstrap_owner(owner)
        with db:
            bootstrap._seed_public_cases(db, owner)

    bundles = json.loads((bootstrap.DEMO_ROOT / "public-cases.json").read_text(encoding="utf-8"))
    last_block = bundles[-1]["blocks"][-1]
    with db:
        db.execute("CREATE TEMP TABLE denied_ref(id TEXT PRIMARY KEY)")
        db.execute("INSERT INTO denied_ref VALUES(?)", ("block:" + bootstrap._id(owner, last_block["id"]),))
        db.execute("""CREATE TEMP TRIGGER fail_late BEFORE INSERT ON evidence
                      WHEN NEW.id IN (SELECT id FROM denied_ref)
                      BEGIN SELECT RAISE(ABORT, 'fixture write failed'); END""")
    empty = list(db.iterdump())
    with pytest.raises(sqlite3.IntegrityError, match="fixture write failed"):
        seed()
    assert not db.in_transaction
    assert list(db.iterdump()) == empty
    db.execute("DROP TRIGGER temp.fail_late")

    result = seed()
    expected = {}
    for bundle in bundles:
        case_id = bootstrap._id(owner, bundle["id"])
        expected.update(expected_task_refs(owner, case_id, bundle["tasks"]["nodes"], bundle["blocks"]))
    if account_seed:
        assert result["seeded"] is True
        nodes = json.loads((bootstrap.ASSESSMENT / "tasks.json").read_text(encoding="utf-8"))["nodes"]
        blocks = json.loads((bootstrap.ASSESSMENT / "blocks.json").read_text(encoding="utf-8"))
        expected.update(expected_task_refs(owner, bootstrap._id(owner, "case:assessment-2024"),
                                           nodes, blocks, assessment=True))

    tasks = db.execute("SELECT * FROM tasks WHERE owner_id=?", (owner,)).fetchall()
    assert {task["id"] for task in tasks} == set(expected)
    for task in tasks:
        case_id, refs = expected[task["id"]]
        assert task["case_id"] == case_id
        assert json.loads(task["evidence_ids_json"]) == [ref for ref, _, _ in refs]
        for ref, source, text in refs:
            row = db.execute("SELECT * FROM evidence WHERE id=? AND owner_id=? AND case_id=?",
                             (ref, owner, case_id)).fetchone()
            assert row is not None
            assert (row["source_name"], row["text"]) == (source, text)
            if expanded:
                assert row["task_id"] is None

    seeded = list(db.iterdump())
    result = seed()
    if account_seed:
        assert result["seeded"] is False
    assert list(db.iterdump()) == seeded
