from helpers import client, account, head
from app.auth import conn


def test_actual_retry_and_history_are_owner_scoped_and_preserve_old_rules():
    a, b = account('retry-history@example.com'), account('retry-history-other@example.com')
    imported = client.post('/api/v1/imports/text',headers=head(a),json={'text':'仅限2023级。请填写申请表。','consent':True}).json()['data']
    case_id = imported['case_id']; url = '/api/v1/imports/'+imported['id']+'/retry'
    with conn() as c:
        old = [row['id'] for row in c.execute('SELECT id FROM rules WHERE case_id=?',(case_id,))]
    assert client.post(url,headers=head(b),json={'consent':True}).status_code == 404
    assert client.post(url,headers=head(a),json={}).status_code == 422
    assert client.post(url,headers=head(a),json={'consent':True}).json()['data']['state'] == 'completed'
    assert client.get('/api/v1/imports/'+imported['id']+'/progress',headers=head(a)).json()['data']['stage'] == 'review_required'
    history = client.get('/api/v1/cases/'+case_id+'/analysis-history',headers=head(a)).json()['data']
    assert [row['revision'] for row in history] == [2,1]
    assert client.get('/api/v1/cases/'+case_id+'/analysis-history',headers=head(b)).status_code == 404
    with conn() as c:
        assert old == [row['id'] for row in c.execute('SELECT id FROM rules WHERE case_id=?',(case_id,))]
        assert c.execute('SELECT COUNT(*) FROM tasks WHERE case_id=?',(case_id,)).fetchone()[0] == 0


def test_retry_failure_is_persisted_without_sensitive_error(monkeypatch):
    monkeypatch.setattr('app.main.stamp', lambda: '2026-11-10T00:00:00+00:00')
    a = account('retry-failure@example.com')
    imported = client.post('/api/v1/imports/text',headers=head(a),json={'text':'请填写申请表。','consent':True}).json()['data']
    def fail(*args):raise RuntimeError('PRIVATE_INPUT_MUST_NOT_APPEAR')
    monkeypatch.setattr('app.main.analyze_case',fail)
    result = client.post('/api/v1/imports/'+imported['id']+'/retry',headers=head(a),json={'consent':True})
    assert result.status_code == 502 and 'PRIVATE_INPUT' not in result.text
    progress = client.get('/api/v1/imports/'+imported['id']+'/progress',headers=head(a)).json()['data']
    assert progress['state'] == 'failed' and progress['error'] == 'ANALYSIS_FAILED'


def test_cancelled_retry_never_persists_new_candidates(monkeypatch):
    import app.main as main
    a = account('retry-cancel@example.com')
    imported = client.post('/api/v1/imports/text',headers=head(a),json={'text':'请填写申请表。','consent':True}).json()['data']
    original = main.get_llm_provider
    def cancel_before_analysis():
        client.post('/api/v1/imports/'+imported['id']+'/cancel',headers=head(a))
        return original()
    monkeypatch.setattr(main,'get_llm_provider',cancel_before_analysis)
    result = client.post('/api/v1/imports/'+imported['id']+'/retry',headers=head(a),json={'consent':True}).json()['data']
    assert result['state'] == 'cancelled'
    assert len(client.get('/api/v1/cases/'+imported['case_id']+'/analysis-history',headers=head(a)).json()['data']) == 1


def test_progress_tracks_latest_retry_when_timestamps_match(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, 'stamp', lambda: '2026-11-10T00:00:00+00:00')
    a, b = account('same-time@example.com'), account('same-time-other@example.com')
    imported = client.post('/api/v1/imports/text', headers=head(a),
                           json={'text': '请填写申请表。', 'consent': True}).json()['data']
    url = '/api/v1/imports/' + imported['id']
    original = main.analyze_case

    def fail(*args):
        raise RuntimeError('PRIVATE_INPUT_MUST_NOT_APPEAR')

    monkeypatch.setattr(main, 'analyze_case', fail)
    previous_ids = set()
    for attempt in range(2):
        response = client.post(url + '/retry', headers=head(a), json={'consent': True})
        assert response.status_code == 502
        with conn() as c:
            failed = c.execute("SELECT id FROM analysis_jobs WHERE import_id=? AND state='failed'",
                               (imported['id'],)).fetchall()
        assert len(failed) == attempt + 1
        progress_response = client.get(url + '/progress', headers=head(a))
        progress = progress_response.json()['data']
        failed_ids = {row['id'] for row in failed}
        expected_id = (failed_ids - previous_ids).pop()
        assert progress['id'] == expected_id
        assert progress['state'] == 'failed' and progress['error'] == 'ANALYSIS_FAILED'
        assert 'PRIVATE_INPUT' not in response.text + progress_response.text
        previous_ids = failed_ids

    monkeypatch.setattr(main, 'analyze_case', original)
    recovered = client.post(url + '/retry', headers=head(a), json={'consent': True}).json()['data']
    progress = client.get(url + '/progress', headers=head(a)).json()['data']
    assert progress['id'] == recovered['job_id']
    assert progress['state'] == 'completed' and progress['error'] is None
    assert client.get(url + '/progress', headers=head(b)).status_code == 404
    with conn() as c:
        assert c.execute('SELECT COUNT(DISTINCT created_at) FROM analysis_jobs WHERE import_id=?',
                         (imported['id'],)).fetchone()[0] == 1
