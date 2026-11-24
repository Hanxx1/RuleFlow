"""Read-only check of a closed SQLite snapshot and its local vault against RF-038/039."""
import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

BASELINE = Path(__file__).with_name("legacy-task-links.json")
KEYS = {
    "tasks": ("id",), "materials": ("id",),
    "task_material_links": ("owner_id", "task_id", "material_id"),
    "vault_items": ("id",), "vault_task_links": ("owner_id", "vault_item_id", "task_id"),
    "vault_case_links": ("owner_id", "vault_item_id", "case_id"),
    "schedule_items": ("id",), "task_edges": ("id",),
    "task_edge_evidence": ("edge_id",), "task_planning": ("task_id",), "evidence": ("id",),
}


def check(database, vault, baseline=None):
    if baseline is None:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
    differences = []
    for suffix in ("-wal", "-journal"):
        sidecar = Path(str(database) + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError("Use a closed, checkpointed snapshot: " + sidecar.name)
    if not vault.is_dir():
        raise ValueError("Vault directory missing: " + str(vault))
    uri = database.resolve(strict=True).as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        for table, keys in KEYS.items():
            expected_rows = baseline["rows"][table]
            columns = {row["name"] for row in db.execute("SELECT name FROM pragma_table_info(?)", (table,))}
            missing = set(expected_rows[0]) - columns
            if missing:
                differences.append(dict(table=table, missing_columns=sorted(missing)))
                continue
            where = " AND ".join(f'"{key}"=?' for key in keys)
            for expected in expected_rows:
                identity = {key: expected[key] for key in keys}
                matches = db.execute(f'SELECT * FROM "{table}" WHERE {where}', tuple(identity.values())).fetchall()
                if len(matches) != 1:
                    differences.append(dict(table=table, key=identity, expected_count=1, actual_count=len(matches)))
                    continue
                for field, value in expected.items():
                    actual = matches[0][field]
                    if field.endswith("_json") and actual != value:
                        try:
                            if json.loads(actual) == json.loads(value):
                                continue
                        except (TypeError, ValueError):
                            pass
                    if actual != value:
                        differences.append(dict(table=table, key=identity, field=field, expected=value, actual=actual))
    # This baseline has one local vault item and one recorded content digest.
    item, = baseline["rows"]["vault_items"]
    path = (vault / item["owner_id"] / item["content_key"]).resolve()
    if not path.is_relative_to(vault.resolve()):
        raise ValueError("Vault path outside snapshot")
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if digest != baseline["vault_content_sha256"]:
        differences.append(dict(vault_item_id=item["id"], file=item["name"],
                                expected_sha256=baseline["vault_content_sha256"], actual_sha256=digest))
    return differences


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("vault", type=Path)
    args = parser.parse_args()
    try:
        diff = check(args.database, args.vault)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
    print(json.dumps({"differences": diff}, ensure_ascii=True, indent=2))
    sys.exit(1 if diff else 0)
