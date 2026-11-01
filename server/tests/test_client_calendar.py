from test_api import client,account,head,confirm_import

def test_calendar_consent_avoiding_courses_and_stale_draft():
    a=account('client-calendar@example.com');h=head(a)
    imported=client.post('/api/v1/imports/text',headers=h,json={'text':'请准备申请表。','consent':True}).json()['data'];cid=imported['case_id'];confirm_import(a,cid)
    resources=client.get('/api/v1/cases/'+cid+'/resources',headers=h).json()['data']
    task=client.post('/api/v1/cases/'+cid+'/tasks',headers=h,json={'title':'填写申请','duration_minutes':60,'evidence_ids':[resources['evidence'][0]['id']]}).json()['data']
    body={'task_ids':[task['id']],'window_start':'2099-01-01T08:00:00+08:00','window_end':'2099-01-01T18:00:00+08:00','calendar_revision':2,'calendar_blocks':[{'id':'course','starts_at':'2099-01-01T08:00:00+08:00','ends_at':'2099-01-01T10:00:00+08:00','evidence_ids':['block:client:test']}]}
    assert client.post('/api/v1/schedule/drafts',headers=h,json=body).status_code==422
    draft=client.post('/api/v1/schedule/drafts',headers=h,json={**body,'calendar_consent':True}).json()['data']
    assert draft['suggestions'][0]['starts_at']=='2099-01-01T02:00:00Z'
    url='/api/v1/schedule/drafts/'+draft['draft_id']+'/commit'
    assert client.post(url,headers=h,json={'consent':True,'calendar_revision':3}).status_code==409
    assert client.post(url,headers=h,json={'consent':True,'calendar_revision':2}).status_code==200

def test_timetable_upload_requires_consent_and_is_not_a_confirmed_course():
    a=account('timetable-parse@example.com');h=head(a);files={'file':('course.txt','高数 周一 08:00-10:00 第1-18周'.encode(),'text/plain')}
    assert client.post('/api/v1/timetable/parse',headers=h,files=files).status_code==422
    response=client.post('/api/v1/timetable/parse',headers=h,files=files,data={'consent':'true'})
    assert response.status_code==200 and response.json()['data']['status']=='needs_confirmation'
    assert response.json()['data']['lines'][0]['text'].startswith('高数')
