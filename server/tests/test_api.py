import json
import os
import socket
import httpx
import pytest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.main import fetch_public,parse_url_blocks
from helpers import client, account, head, confirm_import

def test_health_endpoint():
 r=client.get('/health')
 assert r.status_code==200 and r.json()['data']['status']=='ok'

def complete_batch(batch_id):
 from app.auth import conn
 with conn() as connection:connection.execute("UPDATE import_batches SET demo_processing_at='2000-01-01T00:00:00+00:00',demo_completed_at='2000-01-01T00:00:01+00:00' WHERE id=?",(batch_id,))
def dns_rows(*addresses):return [(socket.AF_INET6 if ':' in address else socket.AF_INET,socket.SOCK_STREAM,6 if ':' in address else 6,'',(address,0,0,0) if ':' in address else (address,0)) for address in addresses]

def test_import_batch_schema_migration_is_applied():
 from app.auth import conn
 from app.main import database
 database()
 with conn() as connection:
  assert connection.execute('SELECT name FROM schema_migrations WHERE version=5').fetchone()['name']=='import_batches'
  assert {'import_batches','import_sources','import_analysis_runs'} <= {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
def test_demo_api_has_evidence():
 p=client.get('/api/v1/demo/notices/assessment').json()['data']; assert p['relevance']['evidence'] and p['workspace']=='demo'
def test_account_owner_isolation_and_import_privacy():
 a,b=account('one@example.com'),account('two@example.com')
 draft=client.post('/api/v1/imports/text',headers=head(a),json={'text':'电话13812345678'}).json()['data']
 assert draft['state']=='needs_confirmation' and '****' in draft['privacy']['redacted_text']
 case=client.post('/api/v1/cases',headers=head(a),json={'title':'真实招聘通知','category':'career'}).json()['data']
 assert client.get('/api/v1/cases/'+case['id'],headers=head(b)).status_code==404
 assert client.get('/api/v1/cases',headers=head(b)).json()['data']==[]
def test_refresh_rotates_and_reset_revokes_sessions():
 a=account('three@example.com'); first=a['refresh_token']
 assert client.get('/api/v1/profile',headers={'Authorization':'Bearer '+first}).status_code==401
 assert client.post('/api/v1/auth/refresh',json={'token':a['access_token']}).status_code==401
 devices=client.get('/api/v1/auth/sessions',headers=head(a)).json()['data']
 assert len(devices)==1 and devices[0]['device_name'] is None
 fresh=client.post('/api/v1/auth/refresh',json={'token':first}).json()['data']
 assert client.post('/api/v1/auth/refresh',json={'token':first}).status_code==401
 reset=client.post('/api/v1/auth/password/reset-request',json={'email':'three@example.com'}).json()['data']
 assert client.post('/api/v1/auth/password/reset',json={'token':reset['development_reset_token'],'password':'new correct horse battery'}).status_code==200
 assert client.post('/api/v1/auth/refresh',json={'token':fresh['refresh_token']}).status_code==401
def test_case_resource_bundle_is_owner_scoped():
 a,b=account('resources-a@example.com'),account('resources-b@example.com')
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'报名截止 2026-10-01','consent':True}).json()['data']
 resources=client.get('/api/v1/cases/'+imported['case_id']+'/resources',headers=head(a))
 assert resources.status_code==200 and resources.json()['data']['evidence'][0]['locator']=='全文'
 assert client.get('/api/v1/cases/'+imported['case_id']+'/resources',headers=head(b)).status_code==404

def test_url_import_rejects_private_network_before_fetch():
 a=account('url-safe@example.com')
 r=client.post('/api/v1/imports/url',headers=head(a),json={'url':'http://127.0.0.1/private','consent':True})
 assert r.status_code==422 and r.json()['detail']['code']=='url_unsafe_address'

def test_public_url_and_csu_proxy_synthetic_dns_are_accepted(monkeypatch):
 def resolve(host,*args,**kwargs):
  assert host=='cse.csu.edu.cn'
  return dns_rows('198.18.0.57')
 monkeypatch.setattr('app.parsing.socket.getaddrinfo',resolve)
 monkeypatch.setattr('app.main.local_proxy_for',lambda scheme:True)
 transport=httpx.MockTransport(lambda request:httpx.Response(200,headers={'content-type':'text/html'},content='<html><body>综合测评通知</body></html>'))
 raw,mime,final_url=fetch_public('https://cse.csu.edu.cn/info/1040/11465.htm',transport=transport)
 assert '综合测评'.encode() in raw and mime=='text/html' and final_url.endswith('11465.htm')

def test_redirect_to_private_address_is_rejected(monkeypatch):
 monkeypatch.setattr('app.parsing.socket.getaddrinfo',lambda *args,**kwargs:dns_rows('93.184.216.34'))
 transport=httpx.MockTransport(lambda request:httpx.Response(302,headers={'location':'http://127.0.0.1/admin'}))
 with pytest.raises(HTTPException) as caught:fetch_public('https://public.example/start',transport=transport)
 assert caught.value.detail['code']=='url_unsafe_address'

def test_url_failure_types_have_distinct_codes(monkeypatch):
 monkeypatch.setattr('app.parsing.socket.getaddrinfo',lambda *args,**kwargs:(_ for _ in ()).throw(socket.gaierror('missing')))
 with pytest.raises(HTTPException) as dns:fetch_public('https://missing.example')
 assert dns.value.detail['code']=='url_dns_failed'
 monkeypatch.setattr('app.parsing.socket.getaddrinfo',lambda *args,**kwargs:dns_rows('93.184.216.34'))
 timeout_transport=httpx.MockTransport(lambda request:(_ for _ in ()).throw(httpx.ReadTimeout('slow',request=request)))
 with pytest.raises(HTTPException) as timeout:fetch_public('https://public.example',transport=timeout_transport)
 assert timeout.value.status_code==504 and timeout.value.detail['code']=='url_timeout'
 with pytest.raises(HTTPException) as http_error:fetch_public('https://public.example',transport=httpx.MockTransport(lambda request:httpx.Response(503)))
 assert http_error.value.detail['code']=='url_http_error'
 with pytest.raises(HTTPException) as too_large:fetch_public('https://public.example',max_bytes=2,transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'abc')))
 assert too_large.value.detail['code']=='url_content_too_large'
 with pytest.raises(HTTPException) as parse_error:parse_url_blocks(b'abc','application/octet-stream','file.bin')
 assert parse_error.value.detail['code']=='url_content_parse_failed'

def test_url_import_persists_evidence_and_evaluates(monkeypatch):
 a=account('url-import@example.com')
 html=('<html><body>2023\u7ea7\u53ca\u4ee5\u540e\u672c\u79d1\u751f\u53ef\u7533\u8bf7</body></html>').encode('utf-8')
 monkeypatch.setattr('app.main.fetch_public',lambda url:(html,'text/html',url))
 imported=client.post('/api/v1/imports/url',headers=head(a),json={'url':'https://example.com/notice','consent':True}).json()['data']
 assert imported['state']=='review' and imported['blocks']==1 and imported['analysis']['rules']==1
def test_general_notice_creates_evidenced_rule_dag_and_material():
 a=account('analysis@example.com')
 notice='2023级及以后本科生可申请。请准备申请表和成绩单，截止 2026-10-01。'
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':notice,'consent':True}).json()['data']
 bundle=client.get('/api/v1/cases/'+imported['case_id']+'/resources',headers=head(a)).json()['data']
 assert bundle['rules'][0]['ast']['op']=='gte' and bundle['rules'][0]['evidence_ids']
 assert {x['title'] for x in bundle['materials']}=={'申请表','成绩单'}
 assert bundle['tasks']==[]
 confirm_import(a,imported['case_id'])
 plan=client.get('/api/v1/cases/'+imported['case_id']+'/plan',headers=head(a)).json()['data']
 assert len(plan['ordered_tasks'])==1 and len(plan['edges'])==0
 client.put('/api/v1/cases/'+imported['case_id']+'/facts',headers=head(a),json={'key':'profile.enrollment_year','value':2024})
 outcome=client.get('/api/v1/cases/'+imported['case_id']+'/evaluate',headers=head(a)).json()['data']
 assert outcome['relevance']=='TRUE'

def test_import_auto_evaluates_when_profile_is_known():
 a=account('auto-evaluate@example.com')
 assert client.put('/api/v1/profile',headers=head(a),json={'facts':{'student_type':'undergraduate','enrollment_year':2024,'college':'计算机学院','major':'计算机科学'}}).status_code==200
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'2023级及以后本科生可申请。','consent':True}).json()['data']
 assert imported['analysis']['relevance']=='TRUE' and imported['analysis']['relevance_reason'] is None
 case=client.get('/api/v1/cases/'+imported['case_id'],headers=head(a)).json()['data']
 assert case['relevance']=='TRUE' and case['relevance_reason'] is None

def test_relevance_reason_distinguishes_profile_from_notice_information_and_recalculates():
 a=account('relevance-reasons@example.com')
 client.put('/api/v1/profile',headers=head(a),json={'facts':{'student_type':'undergraduate','college':'计算机学院','major':'计算机科学'}})
 ranked=client.post('/api/v1/imports/text',headers=head(a),json={'text':'申请人成绩排名须在前 30%。','consent':True}).json()['data']
 missing=client.get('/api/v1/cases/'+ranked['case_id']+'/evaluate',headers=head(a)).json()['data']
 assert missing['relevance']=='UNKNOWN' and missing['reason']=='missing_profile_fact'
 assert missing['missing_profile_fields']==['profile.rank_percent']
 completeness=client.get('/api/v1/profile/completeness',headers=head(a)).json()['data']
 assert 'rank_percent' in completeness['required_fields'] and completeness['score']<100
 client.put('/api/v1/profile',headers=head(a),json={'facts':{'rank_percent':20}})
 updated=client.get('/api/v1/cases/'+ranked['case_id'],headers=head(a)).json()['data']
 assert updated['relevance']=='TRUE' and updated['relevance_reason'] is None
 plain=client.post('/api/v1/imports/text',headers=head(a),json={'text':'请同学们按时查看学院通知。','consent':True}).json()['data']
 unknown=client.get('/api/v1/cases/'+plain['case_id']+'/resources',headers=head(a)).json()['data']
 assert unknown['evaluation']['reason']=='insufficient_evidence'
 assert unknown['evaluation']['missing_profile_fields']==[]
 assert all('个人画像' not in question for question in unknown['analysis']['questions'])

def test_llm_analysis_is_persisted_and_visible(monkeypatch):
 from app.ai import AIAnalysis
 class FakeProvider:
  model_id='deepseek-chat'
  def analyze(self,evidence):
   ref=evidence[0]['id']
   return AIAnalysis.model_validate({'title':'AI 通知','category':'academic','summary':'AI 提取了适用条件和下一步。','rules':[{'label':'入学年份要求','ast':{'op':'gte','field':'profile.enrollment_year','value':2023,'evidence':[ref]},'evidence_ids':[ref],'evidence_quotes':{ref:'2023级及以后'}}],'materials':[],'tasks':[{'title':'准备申请表','deadline':None,'evidence_ids':[ref],'evidence_quotes':{ref:'申请表'}}],'questions':['请确认个人入学年份。'],'review_reasons':[]})
 monkeypatch.setattr('app.main.get_llm_provider',lambda:FakeProvider())
 a=account('ai-success@example.com')
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'2023级及以后。请准备申请表。','consent':True}).json()['data']
 assert imported['analysis']['analysis_mode']=='llm'
 resources=client.get('/api/v1/cases/'+imported['case_id']+'/resources',headers=head(a)).json()['data']
 assert resources['analysis']['mode']=='llm' and resources['rules'][0]['label']=='入学年份要求'

def test_llm_failure_falls_back_to_local_analysis(monkeypatch):
 from app.ai import AIUnavailable
 class BrokenProvider:
  model_id='deepseek-chat'
  def analyze(self,evidence): raise AIUnavailable('timeout')
 monkeypatch.setattr('app.main.get_llm_provider',lambda:BrokenProvider())
 a=account('ai-fallback@example.com')
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'2023级及以后本科生可申请。','consent':True}).json()['data']
 assert imported['analysis']['analysis_mode']=='local_fallback'
 assert '回退本地规则抽取' in imported['analysis']['review_reasons'][0]
def test_profile_is_private_and_reused_by_evaluation():
 a,b=account('profile-a@example.com'),account('profile-b@example.com')
 assert client.put('/api/v1/profile',headers=head(a),json={'facts':{'enrollment_year':2024,'student_type':'undergraduate'}}).status_code==200
 assert client.get('/api/v1/profile',headers=head(a)).json()['data']['enrollment_year']==2024
 assert client.get('/api/v1/profile',headers=head(b)).json()['data']=={}
def test_sync_is_idempotent_owner_scoped_and_tombstone_versioned():
 a,b=account('sync-a@example.com'),account('sync-b@example.com')
 first={'operation_id':'operation-0001','changes':[{'entity_type':'task','entity_id':'t1','version':1,'payload':{'status':'todo'}}]}
 one=client.post('/api/v2/sync/push',headers=head(a),json=first).json()['data']
 again=client.post('/api/v2/sync/push',headers=head(a),json=first).json()['data']
 assert one==again and one['accepted']==['t1']
 assert client.get('/api/v2/sync/pull',headers=head(b)).json()['data']['changes']==[]
 deleted={'operation_id':'operation-0002','changes':[{'entity_type':'task','entity_id':'t1','version':2,'payload':{},'deleted':True}]}
 assert client.post('/api/v2/sync/push',headers=head(a),json=deleted).json()['data']['accepted']==['t1']
 stale={'operation_id':'operation-0003','changes':[{'entity_type':'task','entity_id':'t1','version':1,'payload':{'status':'done'}}]}
 assert client.post('/api/v2/sync/push',headers=head(a),json=stale).json()['data']['conflicts'][0]['server_version']==2

def test_task_material_and_edge_reject_cross_case_references():
 a=account('cross-case@example.com')
 first=client.post('/api/v1/imports/text',headers=head(a),json={'text':'第一份通知，请填写申请表。','consent':True}).json()['data']
 second=client.post('/api/v1/imports/text',headers=head(a),json={'text':'第二份通知，请准备成绩单。','consent':True}).json()['data']
 confirm_import(a,first['case_id']);confirm_import(a,second['case_id'])
 first_resources=client.get('/api/v1/cases/'+first['case_id']+'/resources',headers=head(a)).json()['data']
 second_resources=client.get('/api/v1/cases/'+second['case_id']+'/resources',headers=head(a)).json()['data']
 foreign_evidence=second_resources['evidence'][0]['id']
 assert client.post('/api/v1/cases/'+first['case_id']+'/tasks',headers=head(a),json={'title':'错误任务','evidence_ids':[foreign_evidence]}).status_code==422
 assert client.post('/api/v1/cases/'+first['case_id']+'/materials',headers=head(a),json={'title':'错误材料','evidence_ids':[foreign_evidence]}).status_code==422
 assert client.post('/api/v1/cases/'+first['case_id']+'/edges',headers=head(a),json={'before_task_id':first_resources['tasks'][0]['id'],'after_task_id':second_resources['tasks'][0]['id']}).status_code==422

def test_case_search_filter_sort_patch_and_owner_isolation():
 a,b=account('case-query-a@example.com'),account('case-query-b@example.com')
 first=client.post('/api/v1/cases',headers=head(a),json={'title':'秋季实习申请','category':'career','status':'draft','deadline':'2026-10-10'}).json()['data']
 client.post('/api/v1/cases',headers=head(a),json={'title':'程序设计竞赛','category':'competition','status':'completed','deadline':'2026-09-30'})
 searched=client.get('/api/v1/cases?q=实习&category=career&sort=title_asc&limit=1',headers=head(a))
 assert [item['id'] for item in searched.json()['data']]==[first['id']]
 assert searched.json()['meta']['pagination']['limit']==1
 completed=client.get('/api/v1/cases?status=completed',headers=head(a)).json()['data']
 assert len(completed)==1 and completed[0]['title']=='程序设计竞赛'
 changed=client.patch('/api/v1/cases/'+first['id'],headers=head(a),json={'title':'秋季实习材料提交','category':'academic','status':'in_progress','deadline':'2026-10-12'}).json()['data']
 assert changed['title']=='秋季实习材料提交' and changed['deadline_source']=='user_input'
 assert len(changed['deadline_evidence_ids'])==1
 evidence=client.get('/api/v1/cases/'+first['id']+'/resources',headers=head(a)).json()['data']['evidence']
 assert next(item for item in evidence if item['id']==changed['deadline_evidence_ids'][0])['source_name']=='用户填写'
 assert client.patch('/api/v1/cases/'+first['id'],headers=head(b),json={'title':'越权修改'}).status_code==404

def test_case_progress_and_plan_actionability_follow_task_status():
 a=account('plan-progress@example.com')
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'请准备申请表，并于 2026-10-01 前提交。','consent':True}).json()['data']
 case_id=imported['case_id']
 confirm_import(a,case_id)
 tasks=client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']['ordered_tasks']
 # Dependencies are an explicit user choice; array order is not evidence of a dependency.
 prepared=next(task for task in tasks if task['title'].startswith('准备'))
 submitted=next(task for task in tasks if task['title'].startswith('提交'))
 assert client.post('/api/v1/cases/'+case_id+'/edges',headers=head(a),json={'before_task_id':prepared['id'],'after_task_id':submitted['id']}).status_code==200
 before_case=client.get('/api/v1/cases/'+case_id,headers=head(a)).json()['data']
 before=client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']
 assert before_case['task_count']==2 and before_case['progress']==0
 assert before['overall_progress']==0 and before['completed_tasks']==0 and before['pending_tasks']==2
 assert before['ordered_tasks'][0]['is_actionable'] is True
 assert before['ordered_tasks'][1]['is_actionable'] is False
 assert {'duration_minutes','materials','files','is_actionable'} <= set(before['ordered_tasks'][0])
 assert before['ordered_tasks'][0]['materials'][0]['title']=='申请表'
 first_task=before['ordered_tasks'][0]['id'];second_task=before['ordered_tasks'][1]['id']
 client.patch('/api/v1/tasks/'+first_task,headers=head(a),json={'status':'done'})
 after_case=client.get('/api/v1/cases/'+case_id,headers=head(a)).json()['data']
 after=client.get('/api/v1/cases/'+case_id+'/plan',headers=head(a)).json()['data']
 assert after_case['done_task_count']==1 and after_case['progress']==50
 assert after['overall_progress']==50 and after['completed_tasks']==1 and after['pending_tasks']==1
 assert [task['id'] for task in after['current_tasks']]==[second_task]
 assert after['ordered_tasks'][1]['is_actionable'] is True

def test_profile_completeness_is_computed_from_owner_profile():
 a,b=account('complete-a@example.com'),account('complete-b@example.com')
 assert client.get('/api/v1/profile/completeness',headers=head(a)).json()['data']['score']==0
 client.put('/api/v1/profile',headers=head(a),json={'facts':{'student_type':'undergraduate','enrollment_year':2024}})
 partial=client.get('/api/v1/profile/completeness',headers=head(a)).json()['data']
 assert partial['score']==50 and partial['missing_fields']==['college','major']
 client.put('/api/v1/profile',headers=head(a),json={'facts':{'college':'示例学院','major':'计算机'}})
 assert client.get('/api/v1/profile/completeness',headers=head(a)).json()['data']['score']==100
 assert client.get('/api/v1/profile/completeness',headers=head(b)).json()['data']['score']==0

def test_privacy_analyze_returns_structured_non_overlapping_findings():
 text='身份证11010519491231002X 手机13812345678 银行卡6222020200088888888 邮箱a@example.com'
 result=client.post('/api/v1/privacy/analyze',json={'text':text}).json()['data']
 assert [item['type'] for item in result['findings']]==['id_card','phone','bank_card','email']
 assert '138****5678' in result['redacted_text'] and '11010519491231002X' not in result['redacted_text']
 assert result['unsupported_types']==[] and result['persisted'] is False
 for finding in result['findings']:
  assert text[finding['start']:finding['end']]==finding['original']

def test_device_revoke_is_owner_scoped_and_revokes_its_access_family():
 a,b=account('device-a@example.com'),account('device-b@example.com')
 session_id=client.get('/api/v1/auth/sessions',headers=head(a)).json()['data'][0]['id']
 assert client.delete('/api/v1/auth/sessions/'+session_id,headers=head(b)).status_code==404
 revoked=client.delete('/api/v1/auth/sessions/'+session_id,headers=head(a)).json()['data']
 assert revoked=={'id':session_id,'revoked':True}
 assert client.get('/api/v1/profile',headers=head(a)).status_code==401

def test_account_settings_get_patch_and_owner_isolation():
 a,b=account('settings-a@example.com'),account('settings-b@example.com')
 initial=client.get('/api/v1/account/settings',headers=head(a)).json()['data']
 assert initial['locale']=='zh-CN' and initial['timezone']=='Asia/Shanghai' and initial['display_name'] is None
 changed=client.patch('/api/v1/account/settings',headers=head(a),json={'display_name':'小知','locale':'zh-CN','timezone':'Asia/Shanghai'}).json()['data']
 assert changed['display_name']=='小知'
 assert client.get('/api/v1/account/settings',headers=head(b)).json()['data']['display_name'] is None
 assert client.patch('/api/v1/account/settings',headers=head(a),json={'timezone':'Mars/Base'}).status_code==422

def test_schedule_crud_and_owner_isolation():
 a,b=account('schedule-a@example.com'),account('schedule-b@example.com')
 created=client.post('/api/v1/schedule/items',headers=head(a),json={'title':'专注时间','kind':'busy','starts_at':'2099-01-02T08:00:00+08:00','ends_at':'2099-01-02T09:00:00+08:00'}).json()['data']
 assert created['kind']=='busy' and created['starts_at']=='2099-01-02T00:00:00Z'
 assert [item['id'] for item in client.get('/api/v1/schedule',headers=head(a)).json()['data']]==[created['id']]
 assert client.get('/api/v1/schedule',headers=head(b)).json()['data']==[]
 assert client.patch('/api/v1/schedule/items/'+created['id'],headers=head(b),json={'title':'越权'}).status_code==404
 changed=client.patch('/api/v1/schedule/items/'+created['id'],headers=head(a),json={'title':'复习时间','starts_at':'2099-01-02T09:00:00+08:00','ends_at':'2099-01-02T10:00:00+08:00'}).json()['data']
 assert changed['title']=='复习时间' and changed['starts_at']=='2099-01-02T01:00:00Z'
 assert client.delete('/api/v1/schedule/items/'+created['id'],headers=head(a)).json()['data']['deleted'] is True
 assert client.get('/api/v1/schedule',headers=head(a)).json()['data']==[]

def test_schedule_preview_is_deterministic_read_only_and_respects_deadline_busy_blocks():
 a=account('schedule-preview@example.com')
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'请准备申请表。','consent':True}).json()['data']
 confirm_import(a,imported['case_id'])
 resources=client.get('/api/v1/cases/'+imported['case_id']+'/resources',headers=head(a)).json()['data']
 task=client.post('/api/v1/cases/'+imported['case_id']+'/tasks',headers=head(a),json={'title':'提交申请','deadline':'2099-01-01T12:00:00+08:00','duration_minutes':60,'evidence_ids':[resources['evidence'][0]['id']]}).json()['data']
 busy={'title':'上午课程','kind':'course','starts_at':'2099-01-01T08:00:00+08:00','ends_at':'2099-01-01T10:00:00+08:00','case_id':imported['case_id']}
 client.post('/api/v1/schedule/items',headers=head(a),json=busy)
 request={'task_ids':[task['id']],'window_start':'2099-01-01T08:00:00+08:00','window_end':'2099-01-01T18:00:00+08:00','timezone':'Asia/Shanghai'}
 before=client.get('/api/v1/schedule',headers=head(a)).json()['data']
 first=client.post('/api/v1/schedule/preview',headers=head(a),json=request).json()['data']
 second=client.post('/api/v1/schedule/preview',headers=head(a),json=request).json()['data']
 after=client.get('/api/v1/schedule',headers=head(a)).json()['data']
 assert first==second and before==after
 assert first['suggestions'][0]['starts_at']=='2099-01-01T02:00:00Z'
 suggestion=first['suggestions'][0]
 confirmed=client.post('/api/v1/schedule/items',headers=head(a),json={'title':suggestion['title'],'kind':'task','starts_at':suggestion['starts_at'],'ends_at':suggestion['ends_at'],'case_id':suggestion['case_id'],'task_id':suggestion['task_id']}).json()['data']
 assert confirmed['case_id']==imported['case_id'] and confirmed['task_id']==task['id']
 client.delete('/api/v1/schedule/items/'+confirmed['id'],headers=head(a))
 client.post('/api/v1/schedule/items',headers=head(a),json={**busy,'title':'材料讨论','kind':'busy','starts_at':'2099-01-01T10:00:00+08:00','ends_at':'2099-01-01T12:00:00+08:00'})
 blocked=client.post('/api/v1/schedule/preview',headers=head(a),json=request).json()['data']
 assert blocked['suggestions']==[] and blocked['unscheduled'][0]['reason']=='no_available_slot'

def test_schedule_rejects_cross_owner_and_cross_case_task_links():
 a,b=account('schedule-link-a@example.com'),account('schedule-link-b@example.com')
 first=client.post('/api/v1/imports/text',headers=head(a),json={'text':'第一事项申请表。','consent':True}).json()['data']
 second=client.post('/api/v1/imports/text',headers=head(a),json={'text':'第二事项，请准备证明材料。','consent':True}).json()['data']
 confirm_import(a,second['case_id'])
 task=client.get('/api/v1/cases/'+second['case_id']+'/plan',headers=head(a)).json()['data']['ordered_tasks'][0]
 payload={'title':'错误关联','kind':'task','starts_at':'2099-02-01T08:00:00+08:00','ends_at':'2099-02-01T09:00:00+08:00','case_id':first['case_id'],'task_id':task['id']}
 assert client.post('/api/v1/schedule/items',headers=head(a),json=payload).status_code==422
 payload['case_id']=second['case_id']
 assert client.post('/api/v1/schedule/items',headers=head(b),json=payload).status_code==404

def test_knowledge_fixture_quote_is_verbatim_and_confidence_is_null():
 from app.providers.knowledge import DEMO_KNOWLEDGE_ROOT,DemoFixtureKnowledgeProvider
 provider=DemoFixtureKnowledgeProvider()
 result=provider.search({'title':'综合测评德育加分'},[{'id':'e1','text':'请提交德育加分证明材料并交班级审核'}],[])
 assert result['status']=='available' and result['items']
 source=(DEMO_KNOWLEDGE_ROOT/'student_assessment_regulations.json').read_text(encoding='utf-8')
 assert all(item['quote'] in source for item in result['items'])
 assert all(item['confidence'] is None and item['match_type']=='fixture_keyword' for item in result['items'])

def test_real_mode_knowledge_does_not_fall_back_to_demo_fixture():
 a,b=account('knowledge-real@example.com'),account('knowledge-other@example.com')
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'综合测评德育加分证明材料。','consent':True}).json()['data']
 result=client.get('/api/v1/cases/'+imported['case_id']+'/knowledge-evidence',headers=head(a)).json()['data']
 assert result=={'status':'unavailable','items':[],'reason':'knowledge_provider_not_configured'}
 assert client.get('/api/v1/cases/'+imported['case_id']+'/knowledge-evidence',headers=head(b)).status_code==404

def test_vault_crud_content_links_and_delete_cleanup():
 from app.auth import conn
 from app.settings import SETTINGS
 a,b=account('vault-a@example.com'),account('vault-b@example.com')
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'请准备证明材料。','consent':True}).json()['data']
 confirm_import(a,imported['case_id'])
 task=client.get('/api/v1/cases/'+imported['case_id']+'/plan',headers=head(a)).json()['data']['ordered_tasks'][0]
 content='这是用户实际上传的材料内容。'.encode('utf-8')
 response=client.post('/api/v1/vault/items',headers=head(a),data={'consent':'true','name':'我的证明.txt','category':'proof','case_ids':json.dumps([imported['case_id']]),'task_ids':json.dumps([task['id']])},files={'file':('original.txt',content,'text/plain')})
 assert response.status_code==200
 item=response.json()['data'];assert item['name']=='我的证明.txt' and item['size']==len(content)
 assert item['case_ids']==[imported['case_id']] and item['task_ids']==[task['id']]
 linked_plan=client.get('/api/v1/cases/'+imported['case_id']+'/plan',headers=head(a)).json()['data']
 assert next(value for value in linked_plan['ordered_tasks'] if value['id']==task['id'])['files'][0]['id']==item['id']
 linked_resources=client.get('/api/v1/cases/'+imported['case_id']+'/resources',headers=head(a)).json()['data']
 assert linked_resources['files'][0]['id']==item['id']
 listed=client.get('/api/v1/vault/items?q=我的&category=proof',headers=head(a)).json()['data']
 assert [value['id'] for value in listed]==[item['id']]
 assert client.get('/api/v1/vault/items/'+item['id']+'/content',headers=head(a)).content==content
 assert client.get('/api/v1/vault/items/'+item['id']+'/content',headers=head(b)).status_code==404
 changed=client.patch('/api/v1/vault/items/'+item['id'],headers=head(a),json={'name':'更新后的证明.txt','category':'certificate','case_ids':[imported['case_id']],'task_ids':[task['id']]}).json()['data']
 assert changed['name']=='更新后的证明.txt' and changed['category']=='certificate'
 local_path=SETTINGS.vault_upload_root/a['user']['id']/item['id'];assert local_path.read_bytes()==content
 assert client.delete('/api/v1/vault/items/'+item['id'],headers=head(a)).json()['data']['deleted'] is True
 assert client.get('/api/v1/vault/items/'+item['id'],headers=head(a)).status_code==404 and not local_path.exists()
 assert next(value for value in client.get('/api/v1/cases/'+imported['case_id']+'/plan',headers=head(a)).json()['data']['ordered_tasks'] if value['id']==task['id'])['files']==[]
 with conn() as connection:
  assert connection.execute('SELECT COUNT(*) FROM vault_case_links WHERE vault_item_id=?',(item['id'],)).fetchone()[0]==0
  assert connection.execute('SELECT COUNT(*) FROM vault_task_links WHERE vault_item_id=?',(item['id'],)).fetchone()[0]==0

def test_vault_rejects_cross_owner_and_cross_case_links():
 a,b=account('vault-links-a@example.com'),account('vault-links-b@example.com')
 first=client.post('/api/v1/imports/text',headers=head(a),json={'text':'第一事项申请表。','consent':True}).json()['data']
 second=client.post('/api/v1/imports/text',headers=head(a),json={'text':'第二事项，请准备证明材料。','consent':True}).json()['data']
 confirm_import(a,second['case_id'])
 foreign=client.post('/api/v1/imports/text',headers=head(b),json={'text':'其他账户材料。','consent':True}).json()['data']
 task=client.get('/api/v1/cases/'+second['case_id']+'/plan',headers=head(a)).json()['data']['ordered_tasks'][0]
 file={'file':('proof.txt',b'proof','text/plain')}
 cross_case=client.post('/api/v1/vault/items',headers=head(a),data={'consent':'true','category':'proof','case_ids':json.dumps([first['case_id']]),'task_ids':json.dumps([task['id']])},files=file)
 assert cross_case.status_code==422
 cross_owner=client.post('/api/v1/vault/items',headers=head(a),data={'consent':'true','category':'proof','case_ids':json.dumps([foreign['case_id']]),'task_ids':'[]'},files=file)
 assert cross_owner.status_code==404

def test_dashboard_aggregates_owner_cases_deadlines_states_and_recent_order():
 a,b=account('dashboard-cases-a@example.com'),account('dashboard-cases-b@example.com')
 today=datetime.now(timezone(timedelta(hours=8))).date();far=(today+timedelta(days=30)).isoformat();soon=(today+timedelta(days=3)).isoformat()
 first=client.post('/api/v1/cases',headers=head(a),json={'title':'较早更新事项','category':'academic','status':'in_progress','deadline':far}).json()['data']
 completed=client.post('/api/v1/cases',headers=head(a),json={'title':'已完成事项','category':'career','status':'completed'}).json()['data']
 client.post('/api/v1/cases',headers=head(a),json={'title':'已归档事项','category':'other','status':'archived'})
 client.post('/api/v1/cases',headers=head(b),json={'title':'其他账户事项','category':'other','status':'in_progress','deadline':soon})
 initial=client.get('/api/v1/dashboard',headers=head(a)).json()['data']
 assert initial['total_cases']==2 and initial['in_progress_cases']==1 and initial['completed_cases']==1 and initial['due_soon_cases']==0
 assert {item['id'] for item in initial['recent_cases']}=={first['id'],completed['id']}
 other=client.get('/api/v1/dashboard',headers=head(b)).json()['data']
 assert other['total_cases']==1 and other['due_soon_cases']==1 and {item['title'] for item in other['recent_cases']}=={'其他账户事项'}
 client.patch('/api/v1/cases/'+first['id'],headers=head(a),json={'deadline':soon,'title':'最近更新事项'})
 due=client.get('/api/v1/dashboard',headers=head(a)).json()['data']
 assert due['due_soon_cases']==1 and due['recent_cases'][0]['id']==first['id']
 client.patch('/api/v1/cases/'+first['id'],headers=head(a),json={'status':'completed'})
 changed=client.get('/api/v1/dashboard',headers=head(a)).json()['data']
 assert changed['in_progress_cases']==0 and changed['completed_cases']==2 and changed['due_soon_cases']==0

def test_dashboard_today_tasks_follow_task_status_and_schedule_changes():
 a=account('dashboard-tasks@example.com');today=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
 imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'普通通知内容。','consent':True}).json()['data']
 confirm_import(a,imported['case_id'])
 case_id=imported['case_id'];client.patch('/api/v1/cases/'+case_id,headers=head(a),json={'status':'in_progress'})
 evidence=client.get('/api/v1/cases/'+case_id+'/resources',headers=head(a)).json()['data']['evidence'][0]
 due_task=client.post('/api/v1/cases/'+case_id+'/tasks',headers=head(a),json={'title':'今日截止任务','deadline':today,'duration_minutes':30,'evidence_ids':[evidence['id']]}).json()['data']
 scheduled_task=client.post('/api/v1/cases/'+case_id+'/tasks',headers=head(a),json={'title':'今日排程任务','duration_minutes':45,'evidence_ids':[evidence['id']]}).json()['data']
 initial=client.get('/api/v1/dashboard',headers=head(a)).json()['data']
 assert [item['id'] for item in initial['today_tasks']]==[due_task['id']]
 task_count=initial['recent_cases'][0]['task_count'];assert task_count>=2 and initial['recent_cases'][0]['progress']==0
 merged_schedule=client.post('/api/v1/schedule/items',headers=head(a),json={'title':'截止任务安排','kind':'task','starts_at':f'{today}T08:00:00+08:00','ends_at':f'{today}T08:30:00+08:00','case_id':case_id,'task_id':due_task['id']}).json()['data']
 merged=client.get('/api/v1/dashboard',headers=head(a)).json()['data']['today_tasks']
 assert len(merged)==1 and merged[0]['sources']==['deadline','schedule']
 client.delete('/api/v1/schedule/items/'+merged_schedule['id'],headers=head(a))
 client.patch('/api/v1/tasks/'+due_task['id'],headers=head(a),json={'status':'done'})
 done=client.get('/api/v1/dashboard',headers=head(a)).json()['data']
 assert done['today_tasks']==[] and done['recent_cases'][0]['done_task_count']==1 and done['recent_cases'][0]['progress']==round(100/task_count)
 starts=f'{today}T09:00:00+08:00';ends=f'{today}T09:45:00+08:00'
 scheduled=client.post('/api/v1/schedule/items',headers=head(a),json={'title':'今日安排','kind':'task','starts_at':starts,'ends_at':ends,'case_id':case_id,'task_id':scheduled_task['id']}).json()['data']
 with_schedule=client.get('/api/v1/dashboard',headers=head(a)).json()['data']
 assert [item['id'] for item in with_schedule['today_tasks']]==[scheduled_task['id']]
 assert with_schedule['today_tasks'][0]['sources']==['schedule'] and with_schedule['today_tasks'][0]['schedule_item']['id']==scheduled['id']
 client.delete('/api/v1/schedule/items/'+scheduled['id'],headers=head(a))
 assert client.get('/api/v1/dashboard',headers=head(a)).json()['data']['today_tasks']==[]

def test_import_batch_persists_mixed_sources_traces_evidence_and_is_idempotent(monkeypatch):
 from app.auth import conn
 a,b=account('batch-mixed-a@example.com'),account('batch-mixed-b@example.com')
 batch=client.post('/api/v1/import-batches',headers=head(a),json={'title':'混合来源竞赛通知'}).json()['data']
 assert batch['state']=='draft' and batch['sources']==[]
 text_source=client.post(f"/api/v1/import-batches/{batch['id']}/sources/text",headers=head(a),json={'text':'2024级及以后本科生可申请，请准备申请表。截止 2026-10-10。','consent':True}).json()['data']
 html='<html><body>团队不超过 3 人，并提交成绩单。</body></html>'.encode()
 monkeypatch.setattr('app.main.fetch_public',lambda url:(html,'text/html',url))
 url_source=client.post(f"/api/v1/import-batches/{batch['id']}/sources/url",headers=head(a),json={'url':'https://example.com/notice','consent':True}).json()['data']
 file_sources=client.post(f"/api/v1/import-batches/{batch['id']}/sources/files",headers=head(a),data={'consent':'true'},files={'files':('details.txt','请阅读证明材料要求。'.encode(),'text/plain')}).json()['data']
 temporary=client.post(f"/api/v1/import-batches/{batch['id']}/sources/text",headers=head(a),json={'text':'待删除的补充说明。','consent':True}).json()['data']
 assert client.delete(f"/api/v1/import-batches/{batch['id']}/sources/{temporary['id']}",headers=head(a)).json()['data']['deleted'] is True
 assert {text_source['kind'],url_source['kind'],file_sources[0]['kind']}=={'text','url','file'}
 restored=client.get(f"/api/v1/import-batches/{batch['id']}",headers=head(a)).json()['data']
 assert restored['source_count']==3 and {source['status'] for source in restored['sources']}=={'ready'}
 assert client.get(f"/api/v1/import-batches/{batch['id']}",headers=head(b)).status_code==404
 other=client.post('/api/v1/import-batches',headers=head(a),json={}).json()['data']
 assert client.delete(f"/api/v1/import-batches/{other['id']}/sources/{text_source['id']}",headers=head(a)).status_code==404
 assert client.delete(f"/api/v1/import-batches/{batch['id']}/sources/{text_source['id']}",headers=head(b)).status_code==404
 with conn() as connection:before_get=tuple(connection.execute('SELECT state,revision,started_at,demo_processing_at,demo_completed_at,case_id,result_json FROM import_batches WHERE id=?',(batch['id'],)).fetchone())
 client.get(f"/api/v1/import-batches/{batch['id']}",headers=head(a))
 with conn() as connection:after_get=tuple(connection.execute('SELECT state,revision,started_at,demo_processing_at,demo_completed_at,case_id,result_json FROM import_batches WHERE id=?',(batch['id'],)).fetchone())
 assert before_get==after_get
 queued=client.post(f"/api/v1/import-batches/{batch['id']}/analyze",headers=head(a)).json()['data']
 assert queued['state']=='completed' and queued['case_id'] and queued['result']['successful_sources']==3
 with conn() as connection:
  stored_case=connection.execute('SELECT case_id FROM import_batches WHERE id=?',(batch['id'],)).fetchone()['case_id']
  counts_before=(connection.execute('SELECT COUNT(*) FROM cases WHERE id=?',(stored_case,)).fetchone()[0],connection.execute('SELECT COUNT(*) FROM tasks WHERE case_id=?',(stored_case,)).fetchone()[0])
 client.post(f"/api/v1/import-batches/{batch['id']}/analyze",headers=head(a))
 with conn() as connection:counts_after=(connection.execute('SELECT COUNT(*) FROM cases WHERE id=?',(stored_case,)).fetchone()[0],connection.execute('SELECT COUNT(*) FROM tasks WHERE case_id=?',(stored_case,)).fetchone()[0])
 assert counts_after==counts_before
 with conn() as connection:
  connection.execute("UPDATE import_batches SET demo_processing_at='2000-01-01T00:00:00+00:00',demo_completed_at='2099-01-01T00:00:00+00:00' WHERE id=?",(batch['id'],))
  processing_before=tuple(connection.execute('SELECT state,revision,started_at,demo_processing_at,demo_completed_at,case_id,result_json FROM import_batches WHERE id=?',(batch['id'],)).fetchone())
 processing=client.get(f"/api/v1/import-batches/{batch['id']}",headers=head(a)).json()['data']
 assert processing['state']=='completed' and processing['case_id']==stored_case and processing['result']
 with conn() as connection:assert tuple(connection.execute('SELECT state,revision,started_at,demo_processing_at,demo_completed_at,case_id,result_json FROM import_batches WHERE id=?',(batch['id'],)).fetchone())==processing_before
 complete_batch(batch['id']);completed=client.get(f"/api/v1/import-batches/{batch['id']}",headers=head(a)).json()['data']
 assert completed['state']=='completed' and completed['case_id']==stored_case and completed['result']['successful_sources']==3
 assert all(source['evidence_id'] for source in completed['sources'])
 resources=client.get(f'/api/v1/cases/{stored_case}/resources',headers=head(a)).json()['data']
 assert len(resources['evidence'])==3 and set(completed['result']['evidence_ids'])=={item['id'] for item in resources['evidence']}
 with TestClient(app) as refreshed:
  assert refreshed.get(f"/api/v1/import-batches/{batch['id']}",headers=head(a)).json()['data']['case_id']==stored_case

def test_import_batch_partial_failure_failed_and_failed_source_recovery(monkeypatch):
 from app.auth import conn
 def unavailable(url):raise HTTPException(502,'网页读取失败')
 monkeypatch.setattr('app.main.fetch_public',unavailable)
 a=account('batch-failure@example.com')
 batch=client.post('/api/v1/import-batches',headers=head(a),json={'title':'部分失败通知'}).json()['data']
 client.post(f"/api/v1/import-batches/{batch['id']}/sources/text",headers=head(a),json={'text':'请准备申请表。','consent':True})
 failed_source=client.post(f"/api/v1/import-batches/{batch['id']}/sources/url",headers=head(a),json={'url':'https://unavailable.example/notice','consent':True}).json()['data']
 assert failed_source['status']=='failed' and failed_source['error']=='网页读取失败'
 client.post(f"/api/v1/import-batches/{batch['id']}/analyze",headers=head(a));complete_batch(batch['id'])
 partial=client.get(f"/api/v1/import-batches/{batch['id']}",headers=head(a)).json()['data']
 assert partial['state']=='partial_failure' and partial['case_id'] and partial['failed_source_count']==1
 case_id=partial['case_id']
 assert failed_source['evidence_id'] is None and failed_source['reason']=='source_failed'
 assert failed_source['id'] not in {source['id'] for source in partial['sources'] if source['evidence_id']}
 with conn() as connection:task_count=connection.execute('SELECT COUNT(*) FROM tasks WHERE case_id=?',(case_id,)).fetchone()[0]
 assert client.delete(f"/api/v1/import-batches/{batch['id']}/sources/{failed_source['id']}",headers=head(a)).json()['data']['deleted'] is True
 assert client.get(f"/api/v1/import-batches/{batch['id']}",headers=head(a)).json()['data']['state']=='draft'
 client.post(f"/api/v1/import-batches/{batch['id']}/analyze",headers=head(a));complete_batch(batch['id'])
 recovered=client.get(f"/api/v1/import-batches/{batch['id']}",headers=head(a)).json()['data']
 assert recovered['state']=='completed' and recovered['case_id']==case_id and recovered['failed_source_count']==0
 with conn() as connection:
  assert connection.execute('SELECT COUNT(*) FROM cases WHERE id=?',(case_id,)).fetchone()[0]==1
  assert connection.execute('SELECT COUNT(*) FROM tasks WHERE case_id=?',(case_id,)).fetchone()[0]==task_count
 failed_batch=client.post('/api/v1/import-batches',headers=head(a),json={}).json()['data']
 client.post(f"/api/v1/import-batches/{failed_batch['id']}/sources/url",headers=head(a),json={'url':'https://unavailable.example/only','consent':True})
 client.post(f"/api/v1/import-batches/{failed_batch['id']}/analyze",headers=head(a));complete_batch(failed_batch['id'])
 failed=client.get(f"/api/v1/import-batches/{failed_batch['id']}",headers=head(a)).json()['data']
 assert failed['state']=='failed' and failed['case_id'] is None and failed['result']['error']=='没有可分析的成功来源'
 assert failed['result']['reason']=='source_failed' and failed['result']['evidence_ids']==[]
