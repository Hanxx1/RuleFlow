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
