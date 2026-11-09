from datetime import datetime
from app.services.schedule import preview_schedule
from helpers import client,account,head
from test_schedule_drafts import setup_case


def test_three_gaps_fit_split_task_and_unsplit_returns_conflict():
    task={'id':'a','case_id':'c','title':'作品准备','duration_minutes':90,'splittable':True,'max_chunk_minutes':60,'min_chunk_minutes':30}
    busy=[{'kind':'course','starts_at':f'2026-10-20T{start}+08:00','ends_at':f'2026-10-20T{end}+08:00'} for start,end in [('08:30:00','09:00:00'),('09:30:00','10:00:00'),('10:30:00','21:00:00')]]
    args=([],busy,datetime.fromisoformat('2026-10-20T08:00:00+08:00'),datetime.fromisoformat('2026-10-20T21:00:00+08:00'),'Asia/Shanghai',{'a':'todo'})
    result=preview_schedule([task],*args)
    assert len(result['suggestions'])==3 and sum(item['scheduled_minutes'] for item in result['suggestions'])==90
    assert {item['segment_count'] for item in result['suggestions']}=={3}
    result=preview_schedule([{**task,'splittable':False}],*args)
    assert result['suggestions']==[] and result['unscheduled'][0]['required_minutes']==90


def test_split_commit_and_independent_successor_cannot_bypass_dependencies(monkeypatch):
    from schedule_clock import freeze_schedule_clock
    freeze_schedule_clock(monkeypatch, '2026-10-20T07:59:00+08:00')
    a,case_id=setup_case('split-commit@example.com')
    tasks=client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']['ordered_tasks']
    before,after=tasks[0]['id'],tasks[1]['id']
    assert client.put('/api/v1/tasks/'+before+'/planning',headers=head(a),json={'duration_minutes':90,'splittable':True,'max_chunk_minutes':30}).status_code==200
    assert client.post('/api/v1/cases/'+case_id+'/edges',headers=head(a),json={'before_task_id':before,'after_task_id':after}).status_code==200
    assert client.post('/api/v1/schedule/items',headers=head(a),json={'title':'后置','kind':'task','task_id':after,'starts_at':'2026-10-20T08:00:00+08:00','ends_at':'2026-10-20T08:30:00+08:00'}).status_code==409
    draft=client.post('/api/v1/schedule/drafts',headers=head(a),json={'case_id':case_id,'window_start':'2026-10-20T08:00:00+08:00','window_end':'2026-10-20T21:00:00+08:00'}).json()['data']
    assert len(draft['suggestions'])==4
    result=client.post('/api/v1/schedule/drafts/'+draft['draft_id']+'/commit',headers=head(a),json={'consent':True})
    assert result.status_code==200,result.text
    assert len(client.get('/api/v1/schedule',headers=head(a)).json()['data'])==4


def test_priority_never_overrides_deadline_or_dependency():
    tasks=[{'id':'a','case_id':'c','title':'重要','importance':1,'preference':1,'duration_minutes':30}, {'id':'b','case_id':'c','title':'前置','duration_minutes':30,'deadline':'2026-10-20T08:30:00+08:00'}]
    result=preview_schedule(tasks,[{'before_task_id':'b','after_task_id':'a'}],[],datetime.fromisoformat('2026-10-20T08:00:00+08:00'),datetime.fromisoformat('2026-10-20T10:00:00+08:00'),'Asia/Shanghai',{'a':'todo','b':'todo'})
    assert [item['task_id'] for item in result['suggestions']]==['b','a']


def test_new_dependency_cannot_break_an_existing_successor_schedule():
    a,case_id=setup_case('dependency-existing-slot@example.com')
    tasks=client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']['ordered_tasks']
    before,after=tasks[0]['id'],tasks[1]['id']
    assert client.post('/api/v1/schedule/items',headers=head(a),json={'title':'已安排后置','kind':'task','task_id':after,'starts_at':'2026-10-20T08:00:00+08:00','ends_at':'2026-10-20T08:30:00+08:00'}).status_code==200
    assert client.post('/api/v1/cases/'+case_id+'/edges',headers=head(a),json={'before_task_id':before,'after_task_id':after}).status_code==409
    assert client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']['edges']==[]
