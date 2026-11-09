"""RF-043 S07: date-only timezone consistency and explicit-instant controls."""
from datetime import datetime, timezone

import pytest

from app.auth import conn
from helpers import client
from schedule_clock import freeze_schedule_clock
from test_schedule_boundaries import context, schedule


@pytest.fixture(autouse=True)
def scheduling_clock(monkeypatch):
    freeze_schedule_clock(monkeypatch, '2098-12-31T00:00:00+00:00')


def task_with_deadline(deadline, duration=30):
    headers, case_id, _ = context()
    resources = client.get('/api/v1/cases/' + case_id + '/resources', headers=headers).json()['data']
    response = client.post('/api/v1/cases/' + case_id + '/tasks', headers=headers,
                           json={'title': 'synthetic timezone deadline', 'deadline': deadline,
                                 'duration_minutes': duration, 'evidence_ids': [resources['evidence'][0]['id']]})
    assert response.status_code == 200, response.text
    return headers, response.json()['data']['id']


def draft_for(headers, task_id, zone, start, end):
    response = client.post('/api/v1/schedule/drafts', headers=headers,
                           json={'task_ids': [task_id], 'timezone': zone,
                                 'window_start': start, 'window_end': end})
    assert response.status_code == 200, response.text
    return response.json()['data']


def commit(headers, draft):
    return client.post('/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit',
                       headers=headers, json={'consent': True})


@pytest.mark.parametrize('start,duration', [('2099-01-01T17:00:00Z', 30),
                                           ('2099-01-01T15:30:00Z', 60)],
                         ids=['after-shanghai-day-end', 'crosses-shanghai-day-end'])
def test_s07_date_only_preview_must_not_offer_uncommittable_deadline(start, duration):
    headers, task_id = task_with_deadline('2099-01-01', duration)
    existing = schedule(headers)
    draft = draft_for(headers, task_id, 'UTC', start, '2099-01-01T20:00:00Z')
    assert schedule(headers) == existing
    assert draft['suggestions'] == []
    assert len(draft['unscheduled']) == 1
    assert draft['unscheduled'][0]['task_id'] == task_id
    assert draft['unscheduled'][0]['reason'] == (
        'deadline_passed' if duration == 30 else 'no_available_slot')


@pytest.mark.parametrize('zone', ['UTC', 'Asia/Shanghai'])
def test_s07_date_only_before_both_cutoffs_can_commit(zone):
    headers, task_id = task_with_deadline('2099-01-01')
    draft = draft_for(headers, task_id, zone, '2099-01-01T08:00:00Z', '2099-01-01T10:00:00Z')
    assert len(draft['suggestions']) == 1
    assert draft['suggestions'][0]['starts_at'] == '2099-01-01T08:00:00Z'
    response = commit(headers, draft)
    assert response.status_code == 200, response.text
    assert response.json()['data']['saved_count'] == 1


@pytest.mark.parametrize('zone', ['UTC', 'Asia/Shanghai'])
@pytest.mark.parametrize('deadline', ['2099-01-01T08:30:00Z', '2099-01-01T16:30:00+08:00'])
def test_s07_explicit_offset_exact_deadline_is_same_instant_and_commits(zone, deadline):
    headers, task_id = task_with_deadline(deadline)
    with conn() as c:
        assert c.execute('SELECT deadline FROM tasks WHERE id=?', (task_id,)).fetchone()['deadline'] == '2099-01-01T08:30:00Z'
    draft = draft_for(headers, task_id, zone, '2099-01-01T08:00:00Z', '2099-01-01T10:00:00Z')
    assert len(draft['suggestions']) == 1
    assert draft['suggestions'][0]['ends_at'] == '2099-01-01T08:30:00Z'
    response = commit(headers, draft)
    assert response.status_code == 200, response.text
    assert response.json()['data']['saved_count'] == 1


@pytest.mark.parametrize('zone', ['UTC', 'Asia/Shanghai'])
def test_s07_explicit_offset_insufficient_time_blocks(zone):
    headers, task_id = task_with_deadline('2099-01-01T08:29:59.999999Z')
    draft = draft_for(headers, task_id, zone, '2099-01-01T08:00:00Z', '2099-01-01T10:00:00Z')
    assert draft['suggestions'] == []
    assert draft['unscheduled'][0]['reason'] == 'no_available_slot'
    assert schedule(headers) == []


def test_s07_naive_timestamp_is_rejected_at_task_input():
    headers, case_id, _ = context()
    resources = client.get('/api/v1/cases/' + case_id + '/resources', headers=headers).json()['data']
    response = client.post('/api/v1/cases/' + case_id + '/tasks', headers=headers,
                           json={'title': 'naive deadline', 'deadline': '2099-01-01T16:30:00',
                                 'duration_minutes': 30, 'evidence_ids': [resources['evidence'][0]['id']]})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize('endpoint', ['preview', 'drafts'])
def test_s07_date_only_cannot_extend_by_request_timezone(endpoint):
    headers, task_id = task_with_deadline('2099-01-01')
    response = client.post('/api/v1/schedule/' + endpoint, headers=headers,
                           json={'task_ids': [task_id], 'timezone': 'UTC',
                                 'window_start': '2099-01-01T17:00:00Z',
                                 'window_end': '2099-01-01T20:00:00Z'})
    assert response.status_code == 200, response.text
    assert response.json()['data']['suggestions'] == []
    assert response.json()['data']['unscheduled'][0]['reason'] == 'deadline_passed'
    assert schedule(headers) == []


def test_s07_canonical_cutoff_and_explicit_instant():
    from app.services.schedule import task_deadline
    cutoff = datetime.fromisoformat('2099-01-01T15:59:59+00:00')
    assert task_deadline('2099-01-01') == cutoff
    assert task_deadline('2099-01-01T23:59:59+08:00') == cutoff
    assert task_deadline('2099-01-01T23:59:59Z').astimezone(timezone.utc).hour == 23
    assert task_deadline(None) is None
    assert task_deadline('invalid') is None


def test_s07_mixed_deadlines_sort_by_canonical_instant():
    from app.services.schedule import _sort_tasks, timezone_for
    tasks = [{'id': 'date', 'case_id': 'case', 'deadline': '2099-01-01'},
             {'id': 'instant', 'case_id': 'case', 'deadline': '2099-01-01T16:30:00Z'}]
    assert [t['id'] for t in _sort_tasks(tasks, [], timezone_for('UTC'))] == ['date', 'instant']


def test_s07_urgency_uses_same_cutoff_without_changing_work_timezone():
    from app.services.schedule import preview_schedule
    tasks = [{'id': key, 'case_id': 'case', 'title': key, 'duration_minutes': 30, 'deadline': deadline}
             for key, deadline in [('date', '2099-01-01'), ('instant', '2099-01-01T15:59:59Z')]]
    result = preview_schedule(tasks, [], [], datetime.fromisoformat('2099-01-01T08:00:00+00:00'),
                              datetime.fromisoformat('2099-01-01T12:00:00+00:00'), 'UTC',
                              {'date': 'todo', 'instant': 'todo'})
    assert len(result['suggestions']) == 2
    assert result['suggestions'][0]['starts_at'] == '2099-01-01T08:00:00Z'
    assert result['suggestions'][0]['priority_score'] == result['suggestions'][1]['priority_score']


@pytest.mark.parametrize('end,status', [('2099-01-01T15:59:59Z', 200),
                                       ('2099-01-01T15:59:59.000001Z', 409)])
def test_s07_manual_write_exact_date_cutoff_and_microsecond_after(end, status):
    headers, task_id = task_with_deadline('2099-01-01')
    response = client.post('/api/v1/schedule/items', headers=headers,
                           json={'title': 'boundary', 'kind': 'task', 'task_id': task_id,
                                 'starts_at': '2099-01-01T15:00:00Z', 'ends_at': end})
    assert response.status_code == status, response.text
    assert len(schedule(headers)) == (1 if status == 200 else 0)


def test_s07_legacy_utc_draft_still_rejected_without_writes():
    from app.services.schedule_drafts import create_draft, snapshot
    headers, task_id = task_with_deadline('2099-01-01')
    with conn() as c:
        task = c.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        result = {'timezone': 'UTC', 'suggestions': [
            {'task_id': task_id, 'case_id': task['case_id'], 'title': 'old candidate',
             'starts_at': '2099-01-01T17:00:00Z', 'ends_at': '2099-01-01T17:30:00Z'}]}
        draft = create_draft(c, task['owner_id'], result, snapshot(c, task['owner_id']))
    response = commit(headers, draft)
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == '安排超出任务截止时间'
    assert schedule(headers) == []
    with conn() as c:
        row = c.execute('SELECT state,committed_at FROM schedule_drafts WHERE id=?',
                        (draft['draft_id'],)).fetchone()
        assert (row['state'], row['committed_at']) == ('pending', None)


@pytest.mark.parametrize('endpoint', ['preview', 'drafts'])
def test_s07_workday_open_after_cutoff_cannot_create_late_suggestion(endpoint):
    headers, task_id = task_with_deadline('2099-01-01')
    response = client.post('/api/v1/schedule/' + endpoint, headers=headers,
                           json={'task_ids': [task_id], 'timezone': 'UTC',
                                 'window_start': '2099-01-01T14:00:00Z',
                                 'window_end': '2099-01-01T20:00:00Z',
                                 'preferences': {'work_start_hour': 18, 'work_end_hour': 21}})
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert result['suggestions'] == []
    assert result['unscheduled'][0]['reason'] == 'no_available_slot'
    assert schedule(headers) == []
