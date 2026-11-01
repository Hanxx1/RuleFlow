"""Owner-scoped analysis review storage and atomic, idempotent task compilation."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone


class ReviewError(ValueError):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def read_review(connection, owner_id: str, case_id: str) -> dict | None:
    row = connection.execute("SELECT * FROM case_reviews WHERE owner_id=? AND case_id=?", (owner_id, case_id)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item.pop("owner_id")
    item["candidate"] = json.loads(item.pop("candidate_json"))
    item["decision"] = json.loads(item.pop("decision_json")) if item["decision_json"] else None
    return item


def save_review(connection, owner_id: str, case_id: str, candidate: dict):
    row = connection.execute("SELECT revision FROM case_reviews WHERE owner_id=? AND case_id=?", (owner_id, case_id)).fetchone()
    revision = row[0] + 1 if row else 1
    payload = json.dumps(candidate, ensure_ascii=False)
    connection.execute("""INSERT INTO case_reviews(owner_id,case_id,revision,status,candidate_json,decision_json,confirmed_at)
        VALUES(?,?,?,'needs_confirmation',?,NULL,NULL)
        ON CONFLICT(owner_id,case_id) DO UPDATE SET revision=excluded.revision,status='needs_confirmation',
        candidate_json=excluded.candidate_json,decision_json=NULL,confirmed_at=NULL""", (owner_id, case_id, revision, payload))
    connection.execute("INSERT INTO review_events VALUES(?,?,?,?,?,?,?)",
                       (str(uuid.uuid4()), owner_id, case_id, revision, "analysis_created", "{}", now()))


def require_confirmed(connection, owner_id: str, case_id: str):
    review = read_review(connection, owner_id, case_id)
    # Legacy imported Cases are gated as well. Explicit Demo fixtures have status=demo.
    case = connection.execute("SELECT status FROM cases WHERE id=? AND owner_id=?", (case_id, owner_id)).fetchone()
    if case is None:
        raise ReviewError("CASE_NOT_FOUND", "事项不存在", 404)
    imported = connection.execute("SELECT 1 FROM analysis_metadata WHERE case_id=? AND owner_id=?", (case_id, owner_id)).fetchone()
    if (review and review["status"] != "confirmed") or (not review and imported and case[0] != "demo"):
        raise ReviewError("REVIEW_REQUIRED", "请先核对分析候选并确认行动步骤")


def invalidate_review(connection, owner_id: str, case_id: str):
    connection.execute("UPDATE case_reviews SET revision=revision+1,status='needs_confirmation',decision_json=NULL,confirmed_at=NULL WHERE owner_id=? AND case_id=?", (owner_id, case_id))


def compiled_task_id(owner_id: str, case_id: str, action_id: str, action: dict) -> str:
    return action.get("existing_task_id") or str(uuid.uuid5(uuid.NAMESPACE_URL, f"review:{owner_id}:{case_id}:{action_id}"))


def confirm_review(connection, owner_id: str, case_id: str, revision: int, action_ids: list[str],
                   deadline_id: str | None, manual_deadline: str | None, no_deadline: bool,
                   task_deadlines: dict | None = None):
    review = read_review(connection, owner_id, case_id)
    if not review:
        raise ReviewError("REVIEW_NOT_FOUND", "当前事项没有可确认的分析候选", 404)
    if review["revision"] != revision:
        raise ReviewError("REVIEW_STALE", "分析已发生变化，请重新读取候选")
    if len(action_ids) != len(set(action_ids)):
        raise ReviewError("REVIEW_INVALID", "行动项不能重复", 422)
    actions = {item["id"]: item for item in review["candidate"]["actions"]}
    if set(action_ids) - actions.keys():
        raise ReviewError("REVIEW_INVALID", "行动项不属于当前分析", 422)
    if sum((bool(deadline_id), bool(manual_deadline), no_deadline)) != 1:
        raise ReviewError("REVIEW_INVALID", "请选择截止日期、填写日期或明确暂不设置截止日期", 422)
    refs, value, source = [], None, None
    if deadline_id:
        selected = next((item for item in review["candidate"]["dates"] if item["id"] == deadline_id), None)
        if not selected or selected["role"] != "deadline" or not selected["value"]:
            raise ReviewError("REVIEW_INVALID", "该日期不是完整有效的截止候选，请人工核对后填写", 422)
        value, refs, source = selected["value"], selected["evidence_ids"], "document"
    if manual_deadline:
        try:
            value = date.fromisoformat(manual_deadline).isoformat()
        except ValueError:
            raise ReviewError("REVIEW_INVALID", "人工截止日期必须为有效的 YYYY-MM-DD", 422)
        source = "user_input"
    decision = {"action_ids": sorted(action_ids), "deadline_id": deadline_id,
                "manual_deadline": manual_deadline, "no_deadline": no_deadline}
    overrides = task_deadlines or {}
    if set(overrides)-set(action_ids):
        raise ReviewError('REVIEW_INVALID','任务日期只能绑定所选行动项',422)
    resolved = {}
    for action_id, choice in overrides.items():
        if not isinstance(choice,dict) or set(choice)-{'deadline_id','manual_deadline','no_deadline'}:
            raise ReviewError('REVIEW_INVALID','任务截止日期结构无效',422)
        candidate_id, manual, empty = choice.get('deadline_id'), choice.get('manual_deadline'), choice.get('no_deadline',False)
        if type(empty) is not bool or sum((bool(candidate_id),bool(manual),empty))!=1:
            raise ReviewError('REVIEW_INVALID','每项任务须明确选择一种截止日期处理方式',422)
        task_value, task_evidence, task_source = None, [], None
        if candidate_id:
            selected=next((d for d in review['candidate']['dates'] if d['id']==candidate_id),None)
            if not selected or selected['role']!='deadline' or not selected['value'] or not selected['evidence_ids']:
                raise ReviewError('REVIEW_INVALID','任务截止候选无效或缺少证据',422)
            task_value,task_evidence,task_source=selected['value'],selected['evidence_ids'],'document'
        if manual:
            try:task_value=date.fromisoformat(manual).isoformat()
            except (ValueError,TypeError):raise ReviewError('REVIEW_INVALID','任务人工日期必须为有效 YYYY-MM-DD',422)
            task_source='user_input'
        resolved[action_id]=(task_value,task_evidence,task_source)
    if overrides:decision['task_deadlines']=overrides
    if review["status"] == "confirmed":
        if review["decision"] != decision:
            raise ReviewError("REVIEW_ALREADY_CONFIRMED", "已确认的分析不能以不同选择重复提交")
        return read_review(connection, owner_id, case_id)
    # Validate all references inside the same transaction that compiles the tasks.
    all_refs = set(refs)
    for _, task_refs, _ in resolved.values():all_refs.update(task_refs)
    for action_id in action_ids:
        all_refs.update(actions[action_id]["evidence_ids"])
        existing_id = actions[action_id].get("existing_task_id")
        if existing_id and not connection.execute("SELECT 1 FROM tasks WHERE id=? AND owner_id=? AND case_id=?", (existing_id, owner_id, case_id)).fetchone():
            raise ReviewError("REVIEW_INVALID", "旧步骤不属于当前事项", 422)
        if not actions[action_id]["evidence_ids"]:
            raise ReviewError("REVIEW_INVALID", "行动项缺少证据", 422)
    for ref in all_refs:
        evidence = connection.execute("SELECT text FROM evidence WHERE id=? AND owner_id=? AND case_id=?", (ref, owner_id, case_id)).fetchone()
        if evidence is None:
            raise ReviewError("EVIDENCE_INVALID", "候选证据已失效，请重新分析", 422)
        for action_id in action_ids:
            quote = actions[action_id].get("evidence_quotes", {}).get(ref)
            if quote and quote not in evidence[0]:
                raise ReviewError("EVIDENCE_INVALID", "行动证据短引与原文不一致", 422)
    dependencies = review['candidate'].get('dependencies', [])
    for edge in dependencies:
        if edge['after_action_id'] in action_ids and edge['before_action_id'] not in action_ids:
            raise ReviewError('REVIEW_DEPENDENCY_REQUIRED', '所选步骤依赖未选择的前置动作，请核对并同时选择', 422)
        if edge['after_action_id'] in action_ids:
            for ref in edge['evidence_ids']:
                evidence = connection.execute('SELECT text FROM evidence WHERE id=? AND owner_id=? AND case_id=?', (ref, owner_id, case_id)).fetchone()
                if not evidence or edge['quote'] not in evidence[0]:
                    raise ReviewError('EVIDENCE_INVALID', '依赖短引已失效', 422)
    if dependencies:
        graph={}
        for edge in connection.execute('SELECT before_task_id,after_task_id FROM task_edges WHERE owner_id=? AND case_id=?',(owner_id,case_id)):
            graph.setdefault(edge['before_task_id'],set()).add(edge['after_task_id'])
        for edge in dependencies:
            if edge['after_action_id'] in action_ids:
                before=compiled_task_id(owner_id,case_id,edge['before_action_id'],actions[edge['before_action_id']])
                after=compiled_task_id(owner_id,case_id,edge['after_action_id'],actions[edge['after_action_id']])
                graph.setdefault(before,set()).add(after)
        visited=set();active=set()
        def visit(node):
            if node in active:raise ReviewError('REVIEW_DEPENDENCY_CYCLE','原文依赖或已有依赖形成环，请人工核对',422)
            if node in visited:return
            active.add(node)
            for child in graph.get(node,()):visit(child)
            active.remove(node);visited.add(node)
        for node in graph:visit(node)
    # Reconfirmation must not leave an existing schedule beyond a newly selected deadline.
    from .schedule import _deadline, timezone_for, parse_instant
    for action_id in action_ids:
        task_value=resolved.get(action_id,(value,refs,source))[0]
        if not task_value:continue
        cutoff=_deadline(task_value,timezone_for('Asia/Shanghai'))
        task_id=compiled_task_id(owner_id,case_id,action_id,actions[action_id])
        for block in connection.execute('SELECT ends_at FROM schedule_items WHERE owner_id=? AND task_id=?',(owner_id,task_id)):
            if cutoff is None or parse_instant(block['ends_at'])>cutoff:
                raise ReviewError('REVIEW_SCHEDULE_CONFLICT','该步骤已有日程超出新截止日期，请先调整日程再确认',409)
    timestamp = now()
    if source == "user_input":
        ref = "block:" + str(uuid.uuid4())
        connection.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)",
                           (ref, owner_id, case_id, "用户确认", f"用户确认截止日期为 {value}", "用户确认记录，不代表官方文件", None, timestamp))
        refs = [ref]
    connection.execute("UPDATE cases SET deadline=?,deadline_source=?,deadline_evidence_ids_json=?,updated_at=? WHERE id=? AND owner_id=?",
                       (value, source, json.dumps(refs), timestamp, case_id, owner_id))
    for action_id in actions.keys() - set(action_ids):
        excluded_id = compiled_task_id(owner_id, case_id, action_id, actions[action_id])
        scheduled = connection.execute("SELECT 1 FROM schedule_items WHERE owner_id=? AND task_id=?", (owner_id, excluded_id)).fetchone()
        if scheduled:
            raise ReviewError("REVIEW_TASK_SCHEDULED", "取消的步骤已有日程，请先移除其日程再重新确认")
        connection.execute("UPDATE tasks SET status='skipped',updated_at=? WHERE id=? AND owner_id=? AND status IN ('todo','in_progress')", (timestamp, excluded_id, owner_id))
    for action_id in action_ids:
        action = actions[action_id]
        task_id = compiled_task_id(owner_id, case_id, action_id, action)
        planning=connection.execute('SELECT evidence_id FROM task_planning WHERE task_id=? AND owner_id=?',(task_id,owner_id)).fetchone()
        task_value, date_refs, task_source=resolved.get(action_id,(value,refs,source))
        if action_id in resolved and task_source=='user_input':
            ref='block:'+str(uuid.uuid4())
            connection.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,owner_id,case_id,'用户确认',f'用户确认任务截止日期为 {task_value}','用户确认记录，不代表官方文件',None,timestamp))
            date_refs=[ref]
        task_refs=sorted(set(action['evidence_ids'])|set(date_refs)|({planning['evidence_id']} if planning else set()))
        connection.execute("""INSERT INTO tasks(id,owner_id,case_id,title,status,deadline,evidence_ids_json,created_at,updated_at,duration_minutes)
            VALUES(?,?,?,?,'todo',?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            deadline=excluded.deadline,evidence_ids_json=excluded.evidence_ids_json,updated_at=excluded.updated_at,
            status=CASE WHEN tasks.status='skipped' THEN 'todo' ELSE tasks.status END""", (task_id, owner_id, case_id, action["title"], task_value,
            json.dumps(task_refs), timestamp, timestamp, action.get("duration_minutes")))
        for material in connection.execute("SELECT id,title FROM materials WHERE owner_id=? AND case_id=?", (owner_id, case_id)).fetchall():
            if material["title"] in action["title"]:
                connection.execute("INSERT OR IGNORE INTO task_material_links VALUES(?,?,?)", (owner_id, task_id, material["id"]))
    for edge in dependencies:
        if edge['after_action_id'] in action_ids:
            before = compiled_task_id(owner_id, case_id, edge['before_action_id'], actions[edge['before_action_id']])
            after = compiled_task_id(owner_id, case_id, edge['after_action_id'], actions[edge['after_action_id']])
            edge_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'review-edge:{owner_id}:{case_id}:{before}:{after}'))
            connection.execute('INSERT OR IGNORE INTO task_edges VALUES(?,?,?,?,?)', (edge_id, owner_id, case_id, before, after))
            connection.execute('INSERT OR IGNORE INTO task_edge_evidence VALUES(?,?,?,?)',(edge_id,owner_id,json.dumps(edge['evidence_ids']),'document'))
    connection.execute("UPDATE case_reviews SET status='confirmed',decision_json=?,confirmed_at=? WHERE owner_id=? AND case_id=? AND revision=?",
                       (json.dumps(decision, ensure_ascii=False), timestamp, owner_id, case_id, revision))
    # Audit IDs and choices only, no upload text, personal profile or model output.
    connection.execute("INSERT INTO review_events VALUES(?,?,?,?,?,?,?)",
                       (str(uuid.uuid4()), owner_id, case_id, revision, "analysis_confirmed",
                        json.dumps({"action_ids": action_ids, "deadline_id": deadline_id, "manual_date_supplied": bool(manual_deadline), "no_deadline": no_deadline}), timestamp))
    return read_review(connection, owner_id, case_id)
