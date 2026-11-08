"""RF-043 S01/S04/S20/S21: isolated API boundary regression tests."""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from app.api import planning
from app.auth import conn
from helpers import client, head
from test_schedule_drafts import setup_case

START = '2099-01-01T08:00:00+08:00'
END = '2099-01-01T12:00:00+08:00'


def context():
    account, case_id = setup_case('rf043-boundary@example.com')
    headers = head(account)
    tasks = client.get('/api/v1/cases/' + case_id + '/plan', headers=headers).json()['data']['ordered_tasks']
    for task in tasks:
        response = client.put('/api/v1/tasks/' + task['id'] + '/planning', headers=headers,
                              json={'duration_minutes': 30})
        assert response.status_code == 200, response.text
    return headers, case_id, [task['id'] for task in tasks]


def create_draft(headers, ids, **overrides):
    response = client.post('/api/v1/schedule/drafts', headers=headers,
                           json={'task_ids': ids, 'window_start': START, 'window_end': END, **overrides})
    assert response.status_code == 200, response.text
    return response.json()['data']


def schedule(headers):
    return client.get('/api/v1/schedule', headers=headers).json()['data']


def test_s01_single_task_preview_does_not_save():
    headers, _, ids = context()
    result = create_draft(headers, ids[:1])
    assert len(result['suggestions']) == 1
    item = result['suggestions'][0]
    assert (item['task_id'], item['starts_at'], item['ends_at']) == (ids[0], '2099-01-01T00:00:00Z', '2099-01-01T00:30:00Z')
    assert result['unscheduled'] == []
    assert schedule(headers) == []


@pytest.mark.parametrize('scheduled', [False, True], ids=['missing', 'full-90-minutes'])
def test_s04_external_predecessor(scheduled):
    headers, case_id, ids = context()
    before, after = ids
    response = client.put('/api/v1/tasks/' + before + '/planning', headers=headers, json={'duration_minutes': 90})
    assert response.status_code == 200, response.text
    response = client.post('/api/v1/cases/' + case_id + '/edges', headers=headers,
                           json={'before_task_id': before, 'after_task_id': after})
    assert response.status_code == 200, response.text
    if scheduled:
        response = client.post('/api/v1/schedule/items', headers=headers,
                               json={'title': 'synthetic predecessor', 'kind': 'task', 'task_id': before,
                                     'starts_at': START, 'ends_at': '2099-01-01T09:30:00+08:00'})
        assert response.status_code == 200, response.text
    existing = schedule(headers)
    result = create_draft(headers, [after])
    assert schedule(headers) == existing
    if scheduled:
        assert len(result['suggestions']) == 1
        assert result['suggestions'][0]['starts_at'] == '2099-01-01T01:30:00Z'
        response = client.post('/api/v1/schedule/drafts/' + result['draft_id'] + '/commit', headers=headers, json={'consent': True})
        assert response.status_code == 200, response.text
        assert response.json()['data']['saved_count'] == 1
        assert len(schedule(headers)) == 2
    else:
        assert result['suggestions'] == []
        assert [(item['task_id'], item['reason']) for item in result['unscheduled']] == [(after, 'blocked_by_predecessor')]


@pytest.mark.parametrize('start,end', [
    ('2099-01-01T08:00:00', END),
    (START, '2099-01-01T12:00:00'),
    (START, START),
    (END, START),
    (START, (datetime.fromisoformat(START) + timedelta(days=91)).isoformat()),
], ids=['start-no-offset', 'end-no-offset', 'equal', 'reversed', '91-days'])
def test_s20_invalid_window_rejected(start, end):
    headers, _, ids = context()
    response = client.post('/api/v1/schedule/drafts', headers=headers,
                           json={'task_ids': ids[:1], 'window_start': start, 'window_end': end})
    assert response.status_code == 422, response.text
    assert schedule(headers) == []
    with conn() as c:
        assert c.execute('SELECT COUNT(*) FROM schedule_drafts').fetchone()[0] == 0


def test_s20_no_deadline_defaults_to_fourteen_days():
    headers, _, ids = context()
    result = create_draft(headers, ids[:1], window_end=None)
    assert datetime.fromisoformat(result['window_end']) - datetime.fromisoformat(result['window_start']) == timedelta(days=14)
    assert len(result['suggestions']) == 1
    assert schedule(headers) == []


def test_s21_second_validation_failure_rolls_back_and_allows_retry(monkeypatch):
    headers, _, ids = context()
    result = create_draft(headers, ids)
    assert len(result['suggestions']) == 2
    original = planning.validate_schedule_write
    counts = []

    def fail_second(c, *args, **kwargs):
        counts.append(c.execute('SELECT COUNT(*) FROM schedule_items').fetchone()[0])
        original(c, *args, **kwargs)
        if len(counts) == 2:
            raise HTTPException(409, 'synthetic second validation failure')

    url = '/api/v1/schedule/drafts/' + result['draft_id'] + '/commit'
    with monkeypatch.context() as patch:
        patch.setattr(planning, 'validate_schedule_write', fail_second)
        response = client.post(url, headers=headers, json={'consent': True})
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == 'synthetic second validation failure'
    assert counts == [0, 1]
    assert schedule(headers) == []
    with conn() as c:
        row = c.execute('SELECT state,committed_at FROM schedule_drafts WHERE id=?', (result['draft_id'],)).fetchone()
        assert (row['state'], row['committed_at']) == ('pending', None)
    response = client.post(url, headers=headers, json={'consent': True})
    assert response.status_code == 200, response.text
    assert response.json()['data']['saved_count'] == 2
    assert len(schedule(headers)) == 2
