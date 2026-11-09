"""RF-043 S03: desired preview behavior and legacy draft write protection."""
from datetime import datetime, timedelta

import pytest

from app.auth import conn
from app.services.schedule import preview_schedule
from app.services.schedule_drafts import create_draft as persist_draft, snapshot
from helpers import client, head
from test_schedule_drafts import setup_case
from test_schedule_boundaries import START, END, context, schedule


def partial_predecessor(minutes, required=90):
    headers, case_id, (before, after) = context()
    response = client.put('/api/v1/tasks/' + before + '/planning', headers=headers,
                          json={'duration_minutes': required, 'splittable': True})
    assert response.status_code == 200, response.text
    response = client.post('/api/v1/cases/' + case_id + '/edges', headers=headers,
                           json={'before_task_id': before, 'after_task_id': after})
    assert response.status_code == 200, response.text
    finish = datetime.fromisoformat(START) + timedelta(minutes=minutes)
    response = client.post('/api/v1/schedule/items', headers=headers,
                           json={'title': 'synthetic partial predecessor', 'kind': 'task',
                                 'task_id': before, 'starts_at': START, 'ends_at': finish.isoformat()})
    assert response.status_code == 200, response.text
    return headers, case_id, after, finish


@pytest.mark.parametrize('minutes', [30, 89], ids=['30-of-90', '89-of-90'])
@pytest.mark.parametrize('endpoint', ['preview', 'drafts'])
def test_s03_preview_blocks_partially_scheduled_external_predecessor(minutes, endpoint):
    headers, _, after, _ = partial_predecessor(minutes)
    existing = schedule(headers)
    response = client.post('/api/v1/schedule/' + endpoint, headers=headers,
                           json={'task_ids': [after], 'window_start': START, 'window_end': END})
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert schedule(headers) == existing
    assert result['suggestions'] == []
    assert [(item['task_id'], item['reason']) for item in result['unscheduled']] == [
        (after, 'blocked_by_predecessor')]


@pytest.mark.parametrize('minutes', [30, 89], ids=['30-of-90', '89-of-90'])
def test_s03_legacy_partial_predecessor_draft_cannot_commit(minutes):
    headers, case_id, after, finish = partial_predecessor(minutes)
    existing = schedule(headers)
    # Seed a persisted draft shaped like the old buggy preview. This must remain
    # rejected even after the preview is fixed; no mock bypasses write validation.
    result = {'suggestions': [{'case_id': case_id, 'task_id': after, 'title': 'synthetic successor',
                              'starts_at': finish.isoformat(),
                              'ends_at': (finish + timedelta(minutes=30)).isoformat()}]}
    with conn() as c:
        owner_id = c.execute('SELECT owner_id FROM cases WHERE id=?', (case_id,)).fetchone()['owner_id']
        draft = persist_draft(c, owner_id, result, snapshot(c, owner_id))
    response = client.post('/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit',
                           headers=headers, json={'consent': True})
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == '前置步骤尚未完成或未完整安排在此步骤之前'
    assert schedule(headers) == existing
    with conn() as c:
        row = c.execute('SELECT state,committed_at FROM schedule_drafts WHERE id=?',
                        (draft['draft_id'],)).fetchone()
        assert (row['state'], row['committed_at']) == ('pending', None)



def external_preview(minutes, *, durations, status='todo', other_minutes=0):
    start = datetime.fromisoformat(START)
    blocks = []
    cursor = start
    for amount in minutes:
        finish = cursor + timedelta(minutes=amount)
        blocks.append({'task_id': 'before', 'kind': 'task',
                       'starts_at': cursor.isoformat(), 'ends_at': finish.isoformat()})
        cursor = finish + timedelta(minutes=30)
    if other_minutes:
        blocks.append({'task_id': 'unrelated', 'kind': 'task', 'starts_at': cursor.isoformat(),
                       'ends_at': (cursor + timedelta(minutes=other_minutes)).isoformat()})
    return preview_schedule(
        [{'id': 'after', 'case_id': 'case', 'title': 'successor', 'duration_minutes': 30}],
        [{'before_task_id': 'before', 'after_task_id': 'after'}], blocks,
        start, datetime.fromisoformat(END), 'Asia/Shanghai', {'before': status, 'after': 'todo'},
        all_task_durations=durations)


@pytest.mark.parametrize('minutes,allowed', [([30, 30], False), ([30, 30, 30], True)])
def test_s03_external_predecessor_sums_all_segments(minutes, allowed):
    result = external_preview(minutes, durations={'before': 90})
    if allowed:
        assert len(result['suggestions']) == 1
        # 08:00-08:30, 09:00-09:30, 10:00-10:30; never start before the last segment.
        assert result['suggestions'][0]['starts_at'] == '2099-01-01T02:30:00Z'
        assert result['unscheduled'] == []
    else:
        assert result['suggestions'] == []
        assert result['unscheduled'][0]['reason'] == 'blocked_by_predecessor'


@pytest.mark.parametrize('status', ['done', 'skipped'])
def test_s03_completed_status_compatibility(status):
    result = external_preview([30], durations={'before': 90}, status=status)
    assert len(result['suggestions']) == 1
    assert result['unscheduled'] == []


@pytest.mark.parametrize('durations', [None, {}, {'unrelated': 30}])
def test_s03_missing_external_duration_metadata_blocks(durations):
    result = external_preview([90], durations=durations)
    assert result['suggestions'] == []
    assert result['unscheduled'][0]['reason'] == 'blocked_by_predecessor'


@pytest.mark.parametrize('minutes,allowed', [(29, False), (30, True)])
def test_s03_null_duration_preserves_existing_thirty_minute_default(minutes, allowed):
    result = external_preview([minutes], durations={'before': None})
    assert bool(result['suggestions']) is allowed
    if not allowed:
        assert result['unscheduled'][0]['reason'] == 'blocked_by_predecessor'


def test_s03_unrelated_task_minutes_do_not_complete_predecessor():
    result = external_preview([30], durations={'before': 90}, other_minutes=60)
    assert result['suggestions'] == []
    assert result['unscheduled'][0]['reason'] == 'blocked_by_predecessor'


def test_s03_exact_non_slot_duration_can_preview_and_commit():
    headers, _, after, _ = partial_predecessor(31, required=31)
    response = client.post('/api/v1/schedule/drafts', headers=headers,
                           json={'task_ids': [after], 'window_start': START, 'window_end': END})
    assert response.status_code == 200, response.text
    draft = response.json()['data']
    assert len(draft['suggestions']) == 1
    assert draft['suggestions'][0]['starts_at'] == '2099-01-01T01:00:00Z'
    response = client.post('/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit',
                           headers=headers, json={'consent': True})
    assert response.status_code == 200, response.text
    assert response.json()['data']['saved_count'] == 1


def test_s03_other_owner_schedule_does_not_unlock_or_leak_into_preview():
    headers, _, after, _ = partial_predecessor(30)
    other, other_case = setup_case('s03-other-owner@example.com')
    other_headers = head(other)
    other_tasks = client.get('/api/v1/cases/' + other_case + '/plan',
                             headers=other_headers).json()['data']['ordered_tasks']
    foreign_id = other_tasks[0]['id']
    response = client.post('/api/v1/schedule/items', headers=other_headers,
                           json={'title': 'foreign predecessor', 'kind': 'task', 'task_id': foreign_id,
                                 'starts_at': START, 'ends_at': '2099-01-01T09:30:00+08:00'})
    assert response.status_code == 200, response.text
    existing = schedule(headers)
    foreign_existing = schedule(other_headers)
    response = client.post('/api/v1/schedule/preview', headers=headers,
                           json={'task_ids': [after], 'window_start': START, 'window_end': END})
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert result['suggestions'] == []
    assert [(item['task_id'], item['reason']) for item in result['unscheduled']] == [
        (after, 'blocked_by_predecessor')]
    assert result['considered_blocks'] == 1
    assert schedule(headers) == existing
    assert schedule(other_headers) == foreign_existing
    response = client.post('/api/v1/schedule/preview', headers=headers,
                           json={'task_ids': [foreign_id], 'window_start': START, 'window_end': END})
    assert response.status_code == 404
