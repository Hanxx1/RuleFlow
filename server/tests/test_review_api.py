from helpers import client,account,head


def test_explicit_dependency_is_confirmed_and_compiled_with_clock():
    a = account('dependency-review@example.com')
    case_id = client.post('/api/v1/imports/text',headers=head(a),json={'text':'请先下载申请表，然后填写申请表。北京时间截止2026-10-25下午5点。','consent':True}).json()['data']['case_id']
    review = client.get('/api/v1/cases/'+case_id+'/reviews',headers=head(a)).json()['data']
    assert len(review['candidate']['dependencies']) == 1
    body = {'revision':1,'action_ids':[review['candidate']['actions'][1]['id']],'deadline_id':review['candidate']['dates'][0]['id'],'consent':True}
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json=body).status_code == 422
    body['action_ids'] = [item['id'] for item in review['candidate']['actions']]
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json=body).status_code == 200
    plan = client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']
    assert len(plan['edges']) == 1 and plan['ordered_tasks'][0]['deadline'] == '2026-10-25T17:00:00+08:00'


def test_new_analysis_needs_explicit_owner_confirmation_and_preserves_unknown():
    a,b = account('review-api-a@example.com'),account('review-api-b@example.com')
    imported = client.post('/api/v1/imports/text',headers=head(a),json={'text':'发布于2026-10-01。请准备申请表。报名截止2026-10-25。排名前20%。','consent':True}).json()['data']
    case_id = imported['case_id']
    assert client.get('/api/v1/cases/'+case_id,headers=head(a)).json()['data']['deadline'] is None
    assert client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']['ordered_tasks'] == []
    assert client.get('/api/v1/cases/'+case_id+'/reviews',headers=head(b)).status_code == 404
    review = client.get('/api/v1/cases/'+case_id+'/reviews',headers=head(a)).json()['data']
    refs = review['candidate']['actions'][0]['evidence_ids']
    blocked = client.post('/api/v1/cases/'+case_id+'/tasks',headers=head(a),json={'title':'绕过确认','evidence_ids':refs})
    assert blocked.status_code == 409 and blocked.json()['detail']['code'] == 'REVIEW_REQUIRED'
    publication,deadline = review['candidate']['dates']
    body = {'revision':review['revision'],'action_ids':[item['id'] for item in review['candidate']['actions']],'deadline_id':deadline['id'],'consent':True}
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json={**body,'consent':False}).status_code == 422
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json={**body,'deadline_id':publication['id']}).status_code == 422
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json={**body,'revision':99}).status_code == 409
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(b),json=body).status_code == 404
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json=body).status_code == 200
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json=body).status_code == 200
    plan = client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']
    assert len(plan['ordered_tasks']) == 1 and plan['edges'] == []
    case = client.get('/api/v1/cases/'+case_id,headers=head(a)).json()['data']
    assert case['deadline'] == '2026-10-25' and case['relevance'] == 'UNKNOWN'
    client.patch('/api/v1/cases/'+case_id,headers=head(a),json={'deadline':'2026-10-26','status':'in_progress'})
    task_id = plan['ordered_tasks'][0]['id']
    payload = {'title':'绕过日期复核','kind':'task','task_id':task_id,'starts_at':'2026-10-20T08:00:00+08:00','ends_at':'2026-10-20T09:00:00+08:00'}
    assert client.post('/api/v1/schedule/items',headers=head(a),json=payload).status_code == 409
    assert client.post('/api/v1/schedule/preview',headers=head(a),json={'task_ids':[task_id]}).status_code == 409
    assert client.patch('/api/v1/tasks/'+task_id,headers=head(a),json={'status':'done'}).status_code == 409


def test_ordinary_announcement_never_compiles_a_fake_submission():
    a = account('review-plain@example.com')
    case_id = client.post('/api/v1/imports/text',headers=head(a),json={'text':'图书馆开放时间有所调整。','consent':True}).json()['data']['case_id']
    review = client.get('/api/v1/cases/'+case_id+'/reviews',headers=head(a)).json()['data']
    assert review['candidate']['actions'] == []
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json={'revision':1,'action_ids':[],'no_deadline':True,'consent':True}).status_code == 200
    assert client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']['ordered_tasks'] == []


def test_legacy_review_is_opt_in_idempotent_and_keeps_task_ids():
    from app.auth import conn
    a,b = account('review-legacy@example.com'),account('review-legacy-other@example.com')
    case_id = client.post('/api/v1/imports/text',headers=head(a),json={'text':'请填写申请表。','consent':True}).json()['data']['case_id']
    with conn() as connection:
        connection.execute('DELETE FROM case_reviews WHERE owner_id=? AND case_id=?',(a['user']['id'],case_id))
        connection.execute("INSERT INTO tasks(id,owner_id,case_id,title,status,deadline,evidence_ids_json,created_at,updated_at,duration_minutes) SELECT 'legacy-task',owner_id,case_id,'填写申请表','done',NULL,json_array(id),'now','now',NULL FROM evidence WHERE case_id=?",(case_id,))
    url='/api/v1/cases/'+case_id+'/reviews/prepare'
    assert client.post(url,headers=head(b)).status_code==404
    review=client.post(url,headers=head(a)).json()['data']
    assert client.post(url,headers=head(a)).json()['data']==review
    assert review['status']=='needs_confirmation'
    body={'revision':review['revision'],'action_ids':[item['id'] for item in review['candidate']['actions']],'no_deadline':True,'consent':True}
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json=body).status_code==200
    tasks=client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']['ordered_tasks']
    assert len(tasks)==1 and tasks[0]['id']=='legacy-task' and tasks[0]['status']=='done'


def test_migration_review_gate_is_idempotent_and_preserves_existing_data():
    from app.auth import conn
    from app.main import database
    from app.migrations import apply_migrations
    database()
    with conn() as connection:
        counts=[connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('cases','tasks','case_reviews','review_events')]
        version=connection.execute('SELECT name,checksum,applied_at FROM schema_migrations WHERE version=6').fetchone()
        apply_migrations(connection)
        assert counts==[connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('cases','tasks','case_reviews','review_events')]
        assert tuple(version)==tuple(connection.execute('SELECT name,checksum,applied_at FROM schema_migrations WHERE version=6').fetchone())
        assert version['name']=='analysis_review_gate'


def test_cancelling_a_scheduled_candidate_rolls_back_the_whole_confirmation():
    a=account('review-rollback@example.com')
    case_id=client.post('/api/v1/imports/text',headers=head(a),json={'text':'请填写申请表。请上传作品。','consent':True}).json()['data']['case_id']
    review=client.get('/api/v1/cases/'+case_id+'/reviews',headers=head(a)).json()['data']
    body={'revision':1,'action_ids':[item['id'] for item in review['candidate']['actions']],'no_deadline':True,'consent':True}
    assert client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json=body).status_code==200
    tasks=client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']['ordered_tasks']
    first=next(task for task in tasks if task['title']=='填写申请表')
    assert client.post('/api/v1/schedule/items',headers=head(a),json={'title':'填写申请表','kind':'task','task_id':first['id'],'starts_at':'2099-01-01T08:00:00+08:00','ends_at':'2099-01-01T09:00:00+08:00'}).status_code==200
    client.patch('/api/v1/cases/'+case_id,headers=head(a),json={'deadline':'2099-01-02'})
    before=client.get('/api/v1/cases/'+case_id+'/resources',headers=head(a)).json()['data']
    remaining=[item['id'] for item in review['candidate']['actions'] if item['title']!='填写申请表']
    result=client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json={'revision':2,'action_ids':remaining,'manual_deadline':'2099-01-03','consent':True})
    assert result.status_code==409 and result.json()['detail']['code']=='REVIEW_TASK_SCHEDULED'
    after=client.get('/api/v1/cases/'+case_id+'/resources',headers=head(a)).json()['data']
    assert before['tasks']==after['tasks'] and before['evidence']==after['evidence']
    assert client.get('/api/v1/cases/'+case_id,headers=head(a)).json()['data']['deadline']=='2099-01-02'
    assert client.get('/api/v1/cases/'+case_id+'/reviews',headers=head(a)).json()['data']['status']=='needs_confirmation'
