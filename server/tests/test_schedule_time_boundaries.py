"""RF-043 S05/S06: deterministic time regressions; no production clock changes."""
import json
from datetime import datetime, timezone

import pytest

from app.api import planning
from app.auth import conn
from app.services import schedule_drafts
from helpers import client
from test_schedule_boundaries import START, END, context, schedule


@pytest.fixture
def clock(monkeypatch):
    from schedule_clock import freeze_schedule_clock
    return freeze_schedule_clock(monkeypatch, '2099-01-01T07:59:00+08:00')


def preview(headers, ids, endpoint='drafts', **overrides):
    return client.post('/api/v1/schedule/' + endpoint, headers=headers,
                       json={'task_ids': ids, 'window_start': START, 'window_end': END, **overrides})


def draft_state(draft_id):
    with conn() as c:
        row = c.execute('SELECT state,committed_at FROM schedule_drafts WHERE id=?', (draft_id,)).fetchone()
    return row['state'], row['committed_at']


@pytest.mark.parametrize('endpoint', ['preview', 'drafts'])
@pytest.mark.parametrize('now', ['2099-01-01T12:01:00+08:00', '2099-01-01T08:15:00+08:00'],
                         ids=['whole-window-past', 'window-straddles-now'])
def test_s05_preview_never_offers_past_start(clock, endpoint, now):
    headers, _, ids = context()
    clock.instant = datetime.fromisoformat(now)
    existing = schedule(headers)
    response = preview(headers, ids[:1], endpoint)
    assert schedule(headers) == existing
    assert response.status_code == 422, response.text
    assert response.json()['detail'] == '排程窗口起点不能早于服务器当前时间，请重新选择时间'
    with conn() as c:
        assert c.execute('SELECT COUNT(*) FROM schedule_drafts').fetchone()[0] == 0


@pytest.mark.parametrize('now', ['2099-01-01T08:00:01+08:00', '2099-01-01T08:31:00+08:00'],
                         ids=['first-segment-started', 'first-segment-ended'])
def test_s06_elapsed_time_invalidates_pending_draft_without_data_changes(clock, now):
    headers, case_id, ids = context()
    response = preview(headers, ids)
    assert response.status_code == 200, response.text
    draft = response.json()['data']
    assert [item['starts_at'] for item in draft['suggestions']] == [
        '2099-01-01T00:00:00Z', '2099-01-01T00:30:00Z']
    with conn() as c:
        owner = c.execute('SELECT owner_id FROM cases WHERE id=?', (case_id,)).fetchone()['owner_id']
        before_hash = schedule_drafts.snapshot(c, owner)
        row = c.execute('SELECT created_at,state_hash FROM schedule_drafts WHERE id=?',
                        (draft['draft_id'],)).fetchone()
        assert datetime.fromisoformat(row['created_at']) == clock.instant.astimezone(timezone.utc)
        assert row['state_hash'] == before_hash
    existing = schedule(headers)
    clock.instant = datetime.fromisoformat(now)
    with conn() as c:
        assert schedule_drafts.snapshot(c, owner) == before_hash
    response = client.post('/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit',
                           headers=headers, json={'consent': True})
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'DRAFT_EXPIRED'
    assert schedule(headers) == existing
    assert draft_state(draft['draft_id']) == ('pending', None)


@pytest.mark.parametrize('endpoint', ['preview', 'drafts'])
def test_s05_omitted_start_uses_server_now(clock, endpoint):
    headers, _, ids = context()
    clock.instant = datetime.fromisoformat('2099-01-01T08:15:00+08:00')
    response = preview(headers, ids[:1], endpoint, window_start=None)
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert datetime.fromisoformat(result['window_start'].replace('Z', '+00:00')) == clock.instant
    assert result['suggestions'][0]['starts_at'] == '2099-01-01T00:30:00Z'
    assert schedule(headers) == []


def test_s06_future_commit_and_late_idempotent_retry(clock):
    headers, _, ids = context()
    response = preview(headers, ids[:1])
    assert response.status_code == 200, response.text
    draft = response.json()['data']
    url = '/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit'
    response = client.post(url, headers=headers, json={'consent': True})
    assert response.status_code == 200, response.text
    assert response.json()['data']['saved_count'] == 1
    existing = schedule(headers)
    state = draft_state(draft['draft_id'])
    clock.instant = datetime.fromisoformat('2099-01-01T12:01:00+08:00')
    response = client.post(url, headers=headers, json={'consent': True})
    assert response.status_code == 200, response.text
    assert response.json()['data']['idempotent'] is True
    assert schedule(headers) == existing
    assert draft_state(draft['draft_id']) == state


@pytest.mark.parametrize('endpoint', ['preview', 'drafts'])
@pytest.mark.parametrize('now,status', [
    ('2099-01-01T00:00:00+00:00', 200),
    ('2099-01-01T00:00:00.000001+00:00', 422),
])
def test_s05_equal_instant_and_microsecond_past(clock, endpoint, now, status):
    headers, _, ids = context()
    clock.instant = datetime.fromisoformat(now)
    response = preview(headers, ids[:1], endpoint)
    assert response.status_code == status, response.text
    assert schedule(headers) == []
    if status == 422:
        with conn() as c:
            assert c.execute('SELECT COUNT(*) FROM schedule_drafts').fetchone()[0] == 0


@pytest.mark.parametrize('now,status', [
    ('2099-01-01T00:00:00+00:00', 200),
    ('2099-01-01T00:00:00.000001+00:00', 409),
])
def test_s06_equal_instant_and_microsecond_expiry(clock, now, status):
    headers, _, ids = context()
    draft = preview(headers, ids[:1]).json()['data']
    clock.instant = datetime.fromisoformat(now)
    response = client.post('/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit',
                           headers=headers, json={'consent': True})
    assert response.status_code == status, response.text
    if status == 409:
        assert response.json()['detail']['code'] == 'DRAFT_EXPIRED'
        assert schedule(headers) == []
        assert draft_state(draft['draft_id']) == ('pending', None)


def test_s06_expired_last_item_is_rejected_before_any_validation_or_write(clock, monkeypatch):
    headers, _, ids = context()
    response = client.post('/api/v1/schedule/items', headers=headers,
                           json={'title': 'existing busy', 'kind': 'busy',
                                 'starts_at': '2099-01-01T13:00:00+08:00',
                                 'ends_at': '2099-01-01T14:00:00+08:00'})
    assert response.status_code == 200, response.text
    existing = schedule(headers)
    draft = preview(headers, ids).json()['data']
    # Persist reversed suggestion order to ensure the gate checks every item up front.
    with conn() as c:
        row = c.execute('SELECT result_json FROM schedule_drafts WHERE id=?', (draft['draft_id'],)).fetchone()
        result = json.loads(row['result_json'])
        result['suggestions'].reverse()
        c.execute('UPDATE schedule_drafts SET result_json=? WHERE id=?',
                  (json.dumps(result), draft['draft_id']))
    calls = []
    original = planning.validate_schedule_write

    def observe(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(planning, 'validate_schedule_write', observe)
    clock.instant = datetime.fromisoformat('2099-01-01T08:15:00+08:00')
    response = client.post('/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit',
                           headers=headers, json={'consent': True})
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'DRAFT_EXPIRED'
    assert calls == []
    assert schedule(headers) == existing
    assert draft_state(draft['draft_id']) == ('pending', None)


def test_s06_old_draft_with_future_items_is_not_expired_by_age(clock):
    headers, _, ids = context()
    clock.instant = datetime.fromisoformat('2098-01-01T07:59:00+08:00')
    response = preview(headers, ids[:1])
    assert response.status_code == 200, response.text
    draft = response.json()['data']
    clock.instant = datetime.fromisoformat('2099-01-01T07:59:00+08:00')
    response = client.post('/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit',
                           headers=headers, json={'consent': True})
    assert response.status_code == 200, response.text
    assert response.json()['data']['saved_count'] == 1


def test_s06_empty_draft_preserves_no_write_semantics(clock):
    headers, _, ids = context()
    response = client.post('/api/v1/schedule/items', headers=headers,
                           json={'title': 'busy window', 'kind': 'busy', 'starts_at': START, 'ends_at': END})
    assert response.status_code == 200, response.text
    existing = schedule(headers)
    response = preview(headers, ids[:1])
    assert response.status_code == 200, response.text
    draft = response.json()['data']
    assert draft['suggestions'] == []
    clock.instant = datetime.fromisoformat('2099-01-01T12:01:00+08:00')
    response = client.post('/api/v1/schedule/drafts/' + draft['draft_id'] + '/commit',
                           headers=headers, json={'consent': True})
    assert response.status_code == 200, response.text
    assert response.json()['data']['saved_count'] == 0
    assert schedule(headers) == existing
