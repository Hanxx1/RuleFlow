"""Immutable owner-scoped drafts with optimistic concurrency checks."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from .schedule import parse_instant


class DraftError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


def snapshot(c, owner_id):
    payload = {}
    for table in ('tasks', 'task_edges', 'schedule_items', 'case_reviews','task_planning','schedule_locks'):
        rows = [dict(row) for row in c.execute('SELECT * FROM '+table+' WHERE owner_id=?', (owner_id,))]
        payload[table] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def create_draft(c, owner_id, result, state_hash):
    draft_id = str(uuid.uuid4())
    c.execute('INSERT INTO schedule_drafts VALUES(?,?,?,?,?,?,?)',
              (draft_id, owner_id, state_hash, json.dumps(result, ensure_ascii=False), 'pending', datetime.now(timezone.utc).isoformat(), None))
    return {**result, 'draft_id': draft_id, 'state': 'pending'}


def commit_draft(c, owner_id, draft_id, consent, validate, calendar_revision=None):
    row = c.execute('SELECT * FROM schedule_drafts WHERE id=? AND owner_id=?', (draft_id, owner_id)).fetchone()
    if not row:
        raise DraftError('DRAFT_NOT_FOUND', '排程草稿不存在', 404)
    if not consent:
        raise DraftError('CONFIRMATION_REQUIRED', '请明确确认保存整份排程草稿', 422)
    result = json.loads(row['result_json'])
    if result.get('calendar_revision') is not None and calendar_revision != result.get('calendar_revision'):
        raise DraftError('CALENDAR_STALE','本机课表已变化或版本缺失，请重新预览')
    for item in result['suggestions']:
        for block in result.get('calendar_blocks',[]):
            if parse_instant(item['starts_at'])<parse_instant(block['ends_at']) and parse_instant(block['starts_at'])<parse_instant(item['ends_at']):
                raise DraftError('CALENDAR_CONFLICT','排程草稿与确认课表冲突')
    if row['state'] == 'committed':
        return {'draft_id': draft_id, 'state': 'committed', 'idempotent': True}
    if snapshot(c, owner_id) != row['state_hash']:
        raise DraftError('DRAFT_STALE', '任务、核对状态或日程已变化，请重新预览')
    now_instant = datetime.now(timezone.utc)
    if any(parse_instant(item['starts_at']) < now_instant for item in result['suggestions']):
        raise DraftError('DRAFT_EXPIRED', '草案中的安排已过时，请重新预览')
    now = now_instant.isoformat()
    for item in result['suggestions']:
        validate(c, owner_id, item['case_id'], item['task_id'], item['starts_at'], item['ends_at'], allow_split=item.get('splittable',False))
        c.execute('INSERT INTO schedule_items(id,owner_id,case_id,task_id,title,kind,starts_at,ends_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (str(uuid.uuid4()), owner_id, item['case_id'], item['task_id'], item['title'], 'task', item['starts_at'], item['ends_at'], now, now))
    c.execute("UPDATE schedule_drafts SET state='committed',committed_at=? WHERE id=? AND owner_id=?", (now, draft_id, owner_id))
    return {'draft_id': draft_id, 'state': 'committed', 'saved_count': len(result['suggestions']), 'idempotent': False}
