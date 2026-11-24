import json, shutil, sqlite3, sys, tempfile, importlib.util
from contextlib import closing
from pathlib import Path
root = Path(__file__).resolve().parents[5]
sys.path.insert(0,str(root / 'server'))
from app.migrations import apply_migrations
base = root / 'docs/development/records/evidence/D_20261119'
spec = importlib.util.spec_from_file_location('checker', base / 'check_legacy_task_links.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
source = Path(sys.argv[1])  # Directory containing the closed synthetic snapshot and vault.
with tempfile.TemporaryDirectory() as tmp:
    folder = Path(tmp)
    db = folder / 'copy.sqlite'
    vault = folder / 'vault'
    assert checker.check(source/'linked.sqlite', source/'vault') == []
    shutil.copyfile(source/'linked.sqlite',db)
    shutil.copytree(source/'vault',vault)
    task_id = 'f81ff7fd-6f25-4e35-9dda-a2f4d269c008'
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("UPDATE tasks SET status='done' WHERE id=? AND status='todo'",(task_id,)).rowcount == 1
        conn.commit()
    baseline = json.loads(checker.BASELINE.read_text(encoding="utf-8-sig"))
    task, = [row for row in baseline["rows"]["tasks"] if row["id"] == task_id]
    assert task["status"] == "todo"
    task["status"] = "done"
    assert checker.check(db, vault, baseline) == []
    with closing(sqlite3.connect(db)) as conn:
        conn.execute('PRAGMA foreign_keys=ON')
        versions = list(conn.execute('SELECT version FROM schema_migrations ORDER BY version'))
        apply_migrations(conn)
        conn.commit()
        assert versions == list(conn.execute('SELECT version FROM schema_migrations ORDER BY version'))
        assert list(conn.execute('PRAGMA foreign_key_check')) == []
        assert conn.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    assert checker.check(db, vault, baseline) == []
    link, = baseline["rows"]["task_material_links"]
    assert link["task_id"] == task_id
    other, = [row for row in baseline["rows"]["tasks"]
              if row["id"] != task_id and row["owner_id"] == link["owner_id"]]
    missing_link = dict(table="task_material_links", key=link, expected_count=1, actual_count=0)
    for scenario in ("status_rollback", "reassigned_material", "deleted_material"):
        copy = folder / (scenario + ".sqlite")
        shutil.copyfile(db, copy)
        with closing(sqlite3.connect(copy)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            if scenario == "status_rollback":
                changed = conn.execute("UPDATE tasks SET status='todo' WHERE id=? AND status='done'", (task_id,))
                expected = dict(table="tasks", key={"id": task_id}, field="status", expected="done", actual="todo")
            elif scenario == "reassigned_material":
                before = conn.execute("SELECT COUNT(*) FROM task_material_links").fetchone()
                changed = conn.execute(
                    "UPDATE task_material_links SET task_id=:new_id "
                    "WHERE owner_id=:owner_id AND task_id=:task_id AND material_id=:material_id",
                    {**link, "new_id": other["id"]},
                )
                assert conn.execute("SELECT COUNT(*) FROM task_material_links").fetchone() == before
                assert conn.execute(
                    "SELECT task_id FROM task_material_links WHERE owner_id=:owner_id AND material_id=:material_id",
                    link,
                ).fetchall() == [(other["id"],)]
                expected = missing_link
            else:
                changed = conn.execute("DELETE FROM task_material_links WHERE task_id=?", (task_id,))
                expected = missing_link
            assert changed.rowcount == 1
            conn.commit()
        differences = checker.check(copy, vault, baseline)
        assert differences == [expected], differences
        print(scenario, json.dumps(differences))
    assert checker.check(db, vault, baseline) == []
    assert checker.check(source/'linked.sqlite', source/'vault') == []
    print("PASS clean completed snapshot and original snapshot")
