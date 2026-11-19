"""Exercise the migration comparison CLI using only tracked synthetic data."""
import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from app import auth

EVIDENCE = Path(__file__).resolve().parents[2] / "docs/development/records/evidence/D_20261119"
CONTENT = b"Synthetic RF-038/039 material for migration comparison.\n"

# Explicit columns keep the sample independent of JSON property and database column order.
INSERTS = {
    "tasks": "INSERT INTO tasks (id,owner_id,case_id,title,status,deadline,evidence_ids_json,created_at,updated_at,duration_minutes) VALUES (:id,:owner_id,:case_id,:title,:status,:deadline,:evidence_ids_json,:created_at,:updated_at,:duration_minutes)",
    "materials": "INSERT INTO materials (id,owner_id,case_id,title,state,evidence_ids_json,created_at) VALUES (:id,:owner_id,:case_id,:title,:state,:evidence_ids_json,:created_at)",
    "task_material_links": "INSERT INTO task_material_links (owner_id,task_id,material_id) VALUES (:owner_id,:task_id,:material_id)",
    "vault_items": "INSERT INTO vault_items (id,owner_id,name,category,mime,size,content_provider,content_key,created_at,updated_at) VALUES (:id,:owner_id,:name,:category,:mime,:size,:content_provider,:content_key,:created_at,:updated_at)",
    "vault_task_links": "INSERT INTO vault_task_links (owner_id,vault_item_id,task_id) VALUES (:owner_id,:vault_item_id,:task_id)",
    "vault_case_links": "INSERT INTO vault_case_links (owner_id,vault_item_id,case_id) VALUES (:owner_id,:vault_item_id,:case_id)",
    "schedule_items": "INSERT INTO schedule_items (id,owner_id,case_id,task_id,title,kind,starts_at,ends_at,created_at,updated_at) VALUES (:id,:owner_id,:case_id,:task_id,:title,:kind,:starts_at,:ends_at,:created_at,:updated_at)",
    "task_edges": "INSERT INTO task_edges (id,owner_id,case_id,before_task_id,after_task_id) VALUES (:id,:owner_id,:case_id,:before_task_id,:after_task_id)",
    "task_edge_evidence": "INSERT INTO task_edge_evidence (edge_id,owner_id,evidence_ids_json,source) VALUES (:edge_id,:owner_id,:evidence_ids_json,:source)",
    "task_planning": "INSERT INTO task_planning (task_id,owner_id,splittable,min_chunk_minutes,max_chunk_minutes,importance,preference,evidence_id,updated_at) VALUES (:task_id,:owner_id,:splittable,:min_chunk_minutes,:max_chunk_minutes,:importance,:preference,:evidence_id,:updated_at)",
    "evidence": "INSERT INTO evidence (id,owner_id,case_id,source_name,text,locator,page,created_at) VALUES (:id,:owner_id,:case_id,:source_name,:text,:locator,:page,:created_at)",
}


@pytest.mark.parametrize("scenario", ["complete", "missing_edge", "changed_file"])
def test_legacy_task_link_checker(tmp_path, scenario):
    baseline = json.loads((EVIDENCE / "legacy-task-links.json").read_text(encoding="utf-8-sig"))
    rows = baseline["rows"]
    task = rows["tasks"][0]
    edge_id = rows["task_edges"][0]["id"]
    item, = rows["vault_items"]
    database = tmp_path / "sample.sqlite"
    vault = tmp_path / "vault"
    file = vault / item["owner_id"] / item["content_key"]
    file.parent.mkdir(parents=True)
    file.write_bytes(CONTENT)
    assert len(CONTENT) == item["size"]
    assert hashlib.sha256(CONTENT).hexdigest() == baseline["vault_content_sha256"]
    expected = []
    with closing(sqlite3.connect(database)) as db:
        auth.conn().backup(db)  # The suite provides a fresh, initialized in-memory database.
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("INSERT INTO users (id,email,password_hash,created_at) VALUES (?,?,?,?)",
                   (task["owner_id"], "fixture@example.com", "unused", task["created_at"]))
        db.execute("INSERT INTO cases (id,owner_id,title,category,status,created_at,updated_at) "
                   "VALUES (:case_id,:owner_id,:title,'other','active',:created_at,:updated_at)", task)
        for table, insert in INSERTS.items():
            db.executemany(insert, rows[table])
        if scenario == "missing_edge":
            assert db.execute("DELETE FROM task_edges WHERE id=?", (edge_id,)).rowcount == 1
            expected = [dict(table="task_edges", key={"id": edge_id}, expected_count=1, actual_count=0)]
        db.commit()
    if scenario == "changed_file":
        changed = bytes([CONTENT[0] ^ 1]) + CONTENT[1:]
        assert len(changed) == len(CONTENT)
        file.write_bytes(changed)
        expected = [dict(vault_item_id=item["id"], file=item["name"],
                         expected_sha256=baseline["vault_content_sha256"],
                         actual_sha256=hashlib.sha256(changed).hexdigest())]

    result = subprocess.run([sys.executable, EVIDENCE / "check_legacy_task_links.py", database, vault],
                            cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == (1 if expected else 0), (result.stdout, result.stderr)
    assert json.loads(result.stdout) == {"differences": expected}
