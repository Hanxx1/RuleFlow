from test_api import client, account, head


def setup_case(email):
    a = account(email)
    case_id = client.post('/api/v1/imports/text', headers=head(a), json={'text':'请填写申请表。请上传作品。','consent':True}).json()['data']['case_id']
    review = client.get('/api/v1/cases/'+case_id+'/reviews', headers=head(a)).json()['data']
    assert client.post('/api/v1/cases/'+case_id+'/confirm', headers=head(a), json={'revision':review['revision'],'action_ids':[item['id'] for item in review['candidate']['actions']],'no_deadline':True,'consent':True}).status_code == 200
    return a, case_id


def draft(a, case_id):
    response = client.post('/api/v1/schedule/drafts', headers=head(a), json={'case_id':case_id,'window_start':'2026-10-20T08:00:00+08:00','window_end':'2026-10-22T21:00:00+08:00'})
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_draft_owner_consent_atomic_commit_and_idempotence():
    a, case_id = setup_case('draft-owner@example.com')
    b = account('draft-other@example.com')
    result = draft(a, case_id)
    assert len(result['suggestions']) == 2
    url = '/api/v1/schedule/drafts/'+result['draft_id']+'/commit'
    assert client.post(url, headers=head(b), json={'consent':True}).status_code == 404
    assert client.post(url, headers=head(a), json={}).status_code == 422
    assert client.get('/api/v1/schedule', headers=head(a)).json()['data'] == []
    assert client.post(url, headers=head(a), json={'consent':True}).json()['data']['saved_count'] == 2
    assert client.post(url, headers=head(a), json={'consent':True}).json()['data']['idempotent']
    assert len(client.get('/api/v1/schedule', headers=head(a)).json()['data']) == 2


def test_changed_occupancy_invalidates_whole_draft():
    a, case_id = setup_case('draft-stale@example.com')
    result = draft(a, case_id)
    assert client.post('/api/v1/schedule/items', headers=head(a), json={'title':'课程','kind':'course','starts_at':'2026-10-20T08:00:00+08:00','ends_at':'2026-10-20T09:00:00+08:00'}).status_code == 200
    response = client.post('/api/v1/schedule/drafts/'+result['draft_id']+'/commit', headers=head(a), json={'consent':True})
    assert response.status_code == 409 and response.json()['detail']['code'] == 'DRAFT_STALE'
    assert len(client.get('/api/v1/schedule', headers=head(a)).json()['data']) == 1
    assert draft(a, case_id)['suggestions'][0]['starts_at'] == '2026-10-20T01:00:00Z'


def test_changed_confirmation_invalidates_draft():
    a, case_id = setup_case('draft-review@example.com')
    result = draft(a, case_id)
    client.patch('/api/v1/cases/'+case_id, headers=head(a), json={'deadline':'2026-10-21'})
    assert client.post('/api/v1/schedule/drafts/'+result['draft_id']+'/commit', headers=head(a), json={'consent':True}).status_code == 409
    assert client.get('/api/v1/schedule', headers=head(a)).json()['data'] == []
