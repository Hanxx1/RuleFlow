"""Clone read-only fixtures into an owner-scoped, mutable Demo workspace."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from ..auth import conn
from ..settings import SETTINGS


ROOT = Path(__file__).resolve().parents[3]
DEMO_ROOT = ROOT / "shared" / "demo"
ASSESSMENT = DEMO_ROOT / "assessment_2024"
DEMO_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
NAMESPACE = uuid.UUID("c0d4f8b0-a25c-4ab2-8d76-6db109f7597d")


def fixture_version() -> str:
    payload = json.loads((DEMO_ROOT / "fixture_version.json").read_text(encoding="utf-8"))
    return str(payload["version"])


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(owner_id: str, key: str) -> str:
    owner_namespace = uuid.uuid5(NAMESPACE, owner_id)
    return str(uuid.uuid5(owner_namespace, key))


def _remap_ast(value: Any, evidence_ids: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _remap_ast(item, evidence_ids) for key, item in value.items()}
    if isinstance(value, list):
        return [evidence_ids.get(str(item), item) for item in value]
    return value


def _ast_evidence(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = set(value.get("evidence", [])) if isinstance(value.get("evidence"), list) else set()
        for item in value.values():
            found.update(_ast_evidence(item))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_ast_evidence(item))
        return found
    return set()


def _seed_public_cases(connection,owner_id):
    """Append stable public samples only inside the explicitly enabled Demo database."""
    bundles=_load(DEMO_ROOT/'public-cases.json')
    fixture_time=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    for bundle in bundles:
        case_id=_id(owner_id,bundle['id'])
        if connection.execute('SELECT 1 FROM cases WHERE id=? AND owner_id=?',(case_id,owner_id)).fetchone():continue
        notice=bundle['notice'];refs={b['id']:'block:'+_id(owner_id,b['id']) for b in bundle['blocks']}
        connection.execute('INSERT INTO cases(id,owner_id,title,category,status,relevance,deadline,created_at,updated_at,deadline_source,deadline_evidence_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(case_id,owner_id,notice['title'],notice['category'],'demo','UNKNOWN',None,fixture_time,fixture_time,None,'[]'))
        for block in bundle['blocks']:
            connection.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(refs[block['id']],owner_id,case_id,block['source_name'],block['text'],block['locator']+' '+block['source_url'],None,fixture_time))
        for task in bundle['tasks']['nodes']:
            if not task['evidence_ids'] or any(ref not in refs for ref in task['evidence_ids']):raise ValueError('Public fixture lacks evidence')
            connection.execute('INSERT INTO tasks(id,owner_id,case_id,title,status,deadline,evidence_ids_json,created_at,updated_at,duration_minutes) VALUES(?,?,?,?,?,?,?,?,?,?)',(_id(owner_id,task['id']),owner_id,case_id,task['title'],'todo',None,json.dumps([refs[ref] for ref in task['evidence_ids']]),fixture_time,fixture_time,None))


def bootstrap_owner(owner_id: str) -> dict[str, str | bool]:
    if not SETTINGS.demo_mode:
        raise RuntimeError("Demo bootstrap requires DEMO_MODE=true")

    # Imported lazily to avoid moving or duplicating the existing schema owner.
    from ..main import database

    database()
    version = fixture_version()
    with conn() as connection:
        prior = connection.execute(
            "SELECT fixture_version FROM demo_seed_state WHERE owner_id=?", (owner_id,)
        ).fetchone()
        if prior:
            if prior["fixture_version"] != version:
                raise RuntimeError("Demo fixture version changed; run app.demo.reset for this user")
            for rule in _load(ASSESSMENT/'rules.json'):
                rule_id=_id(owner_id,f"rule:{rule['rule_key']}")
                if connection.execute('SELECT 1 FROM rules WHERE id=? AND owner_id=?',(rule_id,owner_id)).fetchone():
                    connection.execute('INSERT OR IGNORE INTO rule_semantics VALUES(?,?,?)',(rule_id,owner_id,'action_trigger' if rule['rule_key']=='moral_bonus' else 'scope'))
            _seed_public_cases(connection,owner_id)
            return {"seeded": False, "fixture_version": version}

        user = connection.execute("SELECT id FROM users WHERE id=?", (owner_id,)).fetchone()
        if not user:
            raise ValueError("Demo owner does not exist")

        now = _stamp()
        notice = _load(ASSESSMENT / "notice.json")
        blocks = _load(ASSESSMENT / "blocks.json")
        rules = _load(ASSESSMENT / "rules.json")
        task_graph = _load(ASSESSMENT / "tasks.json")
        profile = _load(ASSESSMENT / "profiles" / "undergraduate_2024.json")
        schedule = _load(DEMO_ROOT / "schedule.json")
        vault_manifest = _load(DEMO_ROOT / "files" / "manifest.json")
        case_id = _id(owner_id, "case:assessment-2024")
        deadline_evidence_id = next(
            "block:" + _id(owner_id, f"evidence:{block['id']}")
            for block in blocks
            if block["id"] == "block:deadline:4"
        )

        connection.execute(
            "INSERT INTO cases(id,owner_id,title,category,status,relevance,deadline,created_at,updated_at,deadline_source,deadline_evidence_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                case_id,
                owner_id,
                notice["title"],
                "academic",
                "in_progress",
                "UNKNOWN",
                notice.get("deadline"),
                now,
                now,
                "document",
                json.dumps([deadline_evidence_id]),
            ),
        )

        evidence_ids: dict[str, str] = {}
        for block in blocks:
            evidence_id = "block:" + _id(owner_id, f"evidence:{block['id']}")
            evidence_ids[block["id"]] = evidence_id
            connection.execute(
                "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)",
                (
                    evidence_id,
                    owner_id,
                    case_id,
                    block["source_name"],
                    block["text"],
                    block.get("locator"),
                    block.get("page"),
                    now,
                ),
            )

        for rule in rules:
            ast = _remap_ast(rule["ast"], evidence_ids)
            refs = sorted(_ast_evidence(ast))
            connection.execute(
                "INSERT INTO rules VALUES(?,?,?,?,?,?,?)",
                (
                    _id(owner_id, f"rule:{rule['rule_key']}"),
                    owner_id,
                    case_id,
                    rule["title"],
                    json.dumps(ast, ensure_ascii=False),
                    json.dumps(refs, ensure_ascii=False),
                    now,
                ),
            )

        task_ids: dict[str, str] = {}
        for rule in rules:
            connection.execute('INSERT OR REPLACE INTO rule_semantics VALUES(?,?,?)',(_id(owner_id,f"rule:{rule['rule_key']}"),owner_id,'action_trigger' if rule['rule_key']=='moral_bonus' else 'scope'))
        durations = {"confirm-bonus": 15, "prepare-proof": 30, "fill-form": 30, "class-review": 20, "check-result": 10}
        for task in task_graph["nodes"]:
            task_id = _id(owner_id, f"task:{task['id']}")
            task_ids[task["id"]] = task_id
            refs = [evidence_ids[ref] for ref in task.get("evidence", [])]
            connection.execute(
                "INSERT INTO tasks(id,owner_id,case_id,title,status,deadline,evidence_ids_json,created_at,updated_at,duration_minutes) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    owner_id,
                    case_id,
                    task["title"],
                    task.get("status", "todo"),
                    task.get("deadline"),
                    json.dumps(refs, ensure_ascii=False),
                    now,
                    now,
                    durations.get(task["id"]),
                ),
            )

        for before, after in task_graph["edges"]:
            connection.execute(
                "INSERT INTO task_edges VALUES(?,?,?,?,?)",
                (
                    _id(owner_id, f"edge:{before}:{after}"),
                    owner_id,
                    case_id,
                    task_ids[before],
                    task_ids[after],
                ),
            )

        schedule_base = datetime.now(DEMO_TIMEZONE).date()
        for item in schedule["items"]:
            item_date = schedule_base + timedelta(days=int(item["day_offset"]))
            starts_at = datetime.combine(
                item_date, time.fromisoformat(item["starts_at"]), tzinfo=DEMO_TIMEZONE
            )
            ends_at = datetime.combine(
                item_date, time.fromisoformat(item["ends_at"]), tzinfo=DEMO_TIMEZONE
            )
            connection.execute(
                "INSERT INTO schedule_items(id,owner_id,case_id,task_id,title,kind,starts_at,ends_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    _id(owner_id, f"schedule:{item['key']}"),
                    owner_id,
                    None,
                    None,
                    item["title"],
                    item["kind"],
                    starts_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    ends_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    now,
                    now,
                ),
            )

        material_seed = [
            ("德育加分申请表", "block:form:5"),
            ("证明材料", "block:rules:23"),
        ]
        material_ids: dict[str, str] = {}
        for title, source_ref in material_seed:
            material_id = _id(owner_id, f"material:{title}")
            material_ids[title] = material_id
            connection.execute(
                "INSERT INTO materials VALUES(?,?,?,?,?,?,?)",
                (
                    material_id,
                    owner_id,
                    case_id,
                    title,
                    "missing",
                    json.dumps([evidence_ids[source_ref]], ensure_ascii=False),
                    now,
                ),
            )
        for task_key, material_title in (("prepare-proof", "证明材料"), ("fill-form", "德育加分申请表")):
            connection.execute(
                "INSERT INTO task_material_links(owner_id,task_id,material_id) VALUES(?,?,?)",
                (owner_id, task_ids[task_key], material_ids[material_title]),
            )

        for item in vault_manifest["items"]:
            file_path = DEMO_ROOT / "files" / item["file"]
            vault_id = _id(owner_id, f"vault:{item['key']}")
            connection.execute(
                "INSERT INTO vault_items(id,owner_id,name,category,mime,size,content_provider,content_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    vault_id,
                    owner_id,
                    item["name"],
                    item["category"],
                    item["mime"],
                    file_path.stat().st_size,
                    "fixture",
                    item["file"],
                    now,
                    now,
                ),
            )
            if item.get("case_link"):
                connection.execute(
                    "INSERT INTO vault_case_links(owner_id,vault_item_id,case_id) VALUES(?,?,?)",
                    (owner_id, vault_id, case_id),
                )
            for task_key in item.get("task_keys", []):
                connection.execute(
                    "INSERT INTO vault_task_links(owner_id,vault_item_id,task_id) VALUES(?,?,?)",
                    (owner_id, vault_id, task_ids[task_key]),
                )

        for key, value in profile.items():
            connection.execute(
                "INSERT INTO facts VALUES(?,?,?,?,?,?,?)",
                (
                    _id(owner_id, f"profile:{key}"),
                    owner_id,
                    None,
                    f"profile.{key}",
                    json.dumps(value, ensure_ascii=False),
                    "demo_fixture",
                    now,
                ),
            )

        _seed_public_cases(connection,owner_id)
        connection.execute(
            "INSERT INTO demo_seed_state(owner_id,fixture_version,seeded_at) VALUES(?,?,?)",
            (owner_id, version, now),
        )
    return {"seeded": True, "fixture_version": version, "case_id": case_id}
