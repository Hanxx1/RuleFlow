"""RuleFlow API. Private and mutable Demo data is always owner-scoped."""
from __future__ import annotations
import base64,hashlib,ipaddress,json,mimetypes,os,re,uuid
from urllib.parse import quote,urljoin,urlparse
import httpx
from datetime import date,datetime,time,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import Depends,FastAPI,File,HTTPException,UploadFile,Form,Query,Response
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
from pydantic import BaseModel,Field,ValidationError
from .auth import router as auth_router,conn,init,current_user,envelope
from .privacy import analyze as analyze_privacy,redact
from .rules import evaluate,status_for
from .ai import AIAnalysis,AIInvalidOutput,AIUnavailable,configured_provider,validate_candidates,PROMPT_VERSION,PARSER_VERSION
from .parsing import HostResolutionError,UnsafeHostError,local_proxy_for,parse_bytes,resolve_public_host
from .migrations import apply_migrations
from .providers.knowledge import get_knowledge_provider
from .providers.vault import get_vault_content_provider
from .services.schedule import parse_instant,preview_schedule,timezone_for,utc_iso
from .services.date_candidates import extract_dates
from .services.action_candidates import extract_actions
from .services.dependency_candidates import extract_dependencies
from .services.link_candidates import attachments as attachment_candidates
from .services.review import ReviewError,read_review,save_review,confirm_review,require_confirmed,invalidate_review
from .services.documents import store_document,bind_document,document_root,content_path,preview as document_preview
from .services.file_validation import DocumentError,read_upload
from .services.profile_facts import validate_facts,valid_value,ProfileError
from .services.relevance import evaluate_rules
from .services.rule_candidates import extract_rules
from .services.knowledge import index_document,search as search_knowledge,answer_with_sources
from .services.redaction import scan_document,redact_copy
from .services.schedule_drafts import snapshot as schedule_snapshot,create_draft,commit_draft,DraftError
from .settings import SETTINGS
from .services.fact_history import normalize_validity,record_fact,expired
from .services.interests import bind_interest,soft_relevance
from .services.unsupported_conditions import extract_unsupported
from .services.attachment_requirements import inventory as attachment_inventory

ROOT=Path(__file__).resolve().parents[2]; DEMO=ROOT/'shared'/'demo'/'assessment_2024'; MAX_FILE_BYTES=20*1024*1024
ALLOWED={'application/pdf','text/plain','text/html','application/xhtml+xml','image/png','image/jpeg','application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
app=FastAPI(title='Zhishi RuleFlow API',version='2.0.0')
origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173,https://localhost,capacitor://localhost').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['*'],allow_headers=['Authorization','Content-Type'])
app.include_router(auth_router,prefix='/api/v1/auth')
def stamp():return datetime.now(timezone.utc).isoformat()
def data(x,meta=None):return envelope(x,meta)
def load(name):return json.loads((DEMO/name).read_text(encoding='utf-8'))
def database():
 init()
 with conn() as c:c.executescript("""
 CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,title TEXT NOT NULL,category TEXT NOT NULL,status TEXT NOT NULL,relevance TEXT NOT NULL DEFAULT 'UNKNOWN',deadline TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,deadline_source TEXT,deadline_evidence_ids_json TEXT NOT NULL DEFAULT '[]',FOREIGN KEY(owner_id) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT,key TEXT NOT NULL,value_json TEXT NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,source_name TEXT NOT NULL,text TEXT NOT NULL,locator TEXT,page INTEGER,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS rules(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,label TEXT NOT NULL,ast_json TEXT NOT NULL,evidence_ids_json TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,deadline TEXT,evidence_ids_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,duration_minutes INTEGER);
 CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,kind TEXT NOT NULL,name TEXT,state TEXT NOT NULL,privacy_json TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS analysis_jobs(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,import_id TEXT NOT NULL,state TEXT NOT NULL,stage TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS materials(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,title TEXT NOT NULL,state TEXT NOT NULL,evidence_ids_json TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS task_edges(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,before_task_id TEXT NOT NULL,after_task_id TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS conflicts(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,field TEXT NOT NULL,left_evidence_id TEXT NOT NULL,right_evidence_id TEXT NOT NULL,state TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS analysis_metadata(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,mode TEXT NOT NULL,model_id TEXT NOT NULL,prompt_version TEXT NOT NULL,parser_version TEXT NOT NULL,input_hash TEXT NOT NULL,cost_summary TEXT,summary TEXT NOT NULL,questions_json TEXT NOT NULL,review_reasons_json TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sync_operations(owner_id TEXT NOT NULL,operation_id TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(owner_id,operation_id));
 CREATE TABLE IF NOT EXISTS sync_changes(cursor INTEGER PRIMARY KEY AUTOINCREMENT,owner_id TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,version INTEGER NOT NULL,payload_json TEXT NOT NULL,deleted_at TEXT,created_at TEXT NOT NULL);
 """);apply_migrations(c)
@app.on_event('startup')
def startup():database()
CASE_CATEGORIES={'academic','award','exam','competition','career','research','other'}
CASE_STATUSES={'draft','review','in_progress','completed','archived'}
class CaseIn(BaseModel):title:str=Field(min_length=1,max_length=300);category:str='other';status:str='draft';deadline:str|None=None
class CasePatch(BaseModel):title:str|None=Field(default=None,min_length=1,max_length=300);category:str|None=None;status:str|None=None;deadline:str|None=None
class FactIn(BaseModel):key:str=Field(pattern=r'^profile\.[a-z_]+$');value:object;scope:str='case';valid_until:str|None=None
class TaskIn(BaseModel):title:str=Field(min_length=1,max_length=300);deadline:str|None=None;duration_minutes:int|None=Field(default=None,ge=1,le=1440);evidence_ids:list[str]=[]
class PatchTask(BaseModel):status:str
class TextImport(BaseModel):text:str=Field(min_length=1,max_length=200000);title:str|None=None;consent:bool=False
class UrlImport(BaseModel):url:str=Field(min_length=8,max_length=2048);title:str|None=None;consent:bool=False;include_attachments:bool=True
class ImportBatchIn(BaseModel):title:str|None=Field(default=None,max_length=300)
class EdgeIn(BaseModel):before_task_id:str;after_task_id:str
class MaterialIn(BaseModel):title:str=Field(min_length=1,max_length=300);evidence_ids:list[str]
class SyncChange(BaseModel):entity_type:str;entity_id:str;version:int;payload:dict={};deleted:bool=False
class SyncPush(BaseModel):operation_id:str=Field(min_length=8,max_length=128);changes:list[SyncChange]
class ProfileIn(BaseModel):facts:dict[str,object];valid_until:dict[str,str|None]=Field(default_factory=dict)
class PrivacyIn(BaseModel):text:str=Field(min_length=1,max_length=200000)
class AccountSettingsPatch(BaseModel):display_name:str|None=Field(default=None,max_length=100);locale:str|None=Field(default=None,min_length=2,max_length=16);timezone:str|None=Field(default=None,min_length=1,max_length=64)
class ScheduleItemIn(BaseModel):title:str=Field(min_length=1,max_length=200);kind:str;starts_at:str;ends_at:str;case_id:str|None=None;task_id:str|None=None
class ScheduleItemPatch(BaseModel):title:str|None=Field(default=None,min_length=1,max_length=200);kind:str|None=None;starts_at:str|None=None;ends_at:str|None=None;case_id:str|None=None;task_id:str|None=None
class SchedulePreferencesIn(BaseModel):work_start_hour:int=Field(default=8,ge=0,le=22,strict=True);work_end_hour:int=Field(default=21,ge=1,le=23,strict=True);buffer_minutes:int=Field(default=0,ge=0,le=120,strict=True);daily_max_minutes:int=Field(default=780,ge=30,le=1380,strict=True)
class CalendarBlockIn(BaseModel):
 model_config={'extra':'forbid'}
 id:str=Field(max_length=200)
 starts_at:str
 ends_at:str
 evidence_ids:list[str]=Field(min_length=1,max_length=5)
class SchedulePreviewIn(BaseModel):case_id:str|None=None;task_ids:list[str]=Field(default_factory=list);window_start:str|None=None;window_end:str|None=None;timezone:str='Asia/Shanghai';preferences:SchedulePreferencesIn=Field(default_factory=SchedulePreferencesIn);calendar_blocks:list[CalendarBlockIn]=Field(default_factory=list,max_length=2000);calendar_consent:bool=False;calendar_revision:int|None=Field(default=None,ge=0)
class DraftCommitIn(BaseModel):consent:bool=False;calendar_revision:int|None=Field(default=None,ge=0)
class AttachmentImportIn(BaseModel):index:int=Field(ge=0,le=9);consent:bool=False
class TaskPlanningIn(BaseModel):duration_minutes:int=Field(ge=1,le=1440,strict=True);splittable:bool=False;min_chunk_minutes:int=Field(default=30,ge=30,le=240,strict=True);max_chunk_minutes:int=Field(default=60,ge=30,le=240,strict=True);importance:float=Field(default=0,ge=0,le=1);preference:float=Field(default=0,ge=0,le=1)
class ScheduleSeriesIn(ScheduleItemIn):count:int=Field(ge=2,le=13,strict=True);every_weeks:int=Field(default=1,ge=1,le=4,strict=True);timezone:str='Asia/Shanghai'
class ScheduleLockIn(BaseModel):locked:bool
class ProfileInterestsIn(BaseModel):categories:list[str]=Field(max_length=7)
class VaultPatch(BaseModel):name:str|None=Field(default=None,min_length=1,max_length=255);category:str|None=None;case_ids:list[str]|None=None;task_ids:list[str]|None=None
from .services.profile_facts import PROFILE_FIELDS
class ReviewConfirmation(BaseModel):
 revision:int=Field(ge=1)
 action_ids:list[str]=Field(default_factory=list,max_length=50)
 deadline_id:str|None=None
 manual_deadline:str|None=None
 no_deadline:bool=False
 consent:bool=False
 task_deadlines:dict[str,dict]=Field(default_factory=dict,max_length=50)
class KnowledgeTextIn(BaseModel):
 text:str=Field(min_length=1,max_length=200000)
 title:str=Field(min_length=1,max_length=300)
 category:str=Field(default='other',max_length=50)
 consent:bool=False
class KnowledgeSearchIn(BaseModel):
 query:str=Field(min_length=1,max_length=4000)
 top_k:int=Field(default=5,ge=1,le=10)
 category:str|None=None
class KnowledgeConsent(BaseModel):consent:bool=False
class RedactIn(BaseModel):
 revision:int=Field(ge=1)
 finding_ids:list[str]=Field(min_length=1,max_length=100)
 consent:bool=False
CORE_PROFILE_FIELDS=('student_type','enrollment_year','college','major')
SCHEDULE_KINDS={'busy','course','task'}
VAULT_CATEGORIES={'form','proof','certificate','transcript','identity','reference','other'}
def profile_values(owner_id:str,case_id:str|None=None):
 with conn() as c:
  if case_id is None:rows=c.execute('SELECT * FROM facts WHERE owner_id=? AND case_id IS NULL ORDER BY created_at,id',(owner_id,)).fetchall()
  else:rows=c.execute('SELECT * FROM facts WHERE owner_id=? AND (case_id IS NULL OR case_id=?) ORDER BY CASE WHEN case_id IS NULL THEN 0 ELSE 1 END,created_at,id',(owner_id,case_id)).fetchall()
 with conn() as c:validity={row['fact_id']:row['valid_until'] for row in c.execute('SELECT * FROM fact_validity WHERE owner_id=?',(owner_id,))}
 values={}
 for row in rows:values[row['key'].removeprefix('profile.')]=None if expired(validity.get(row['id'])) else json.loads(row['value_json'])
 return values
def rule_fields(ast):
 if not isinstance(ast,dict):return set()
 if ast.get('op') in {'and','or','not'}:return set().union(*(rule_fields(child) for child in ast.get('args',[])))
 field=ast.get('field');return {field.removeprefix('profile.')} if isinstance(field,str) and field.startswith('profile.') else set()
def required_profile_fields(owner_id:str):
 required=set(CORE_PROFILE_FIELDS)
 with conn() as c:rows=c.execute("SELECT r.ast_json FROM rules r LEFT JOIN rule_semantics s ON s.rule_id=r.id AND s.owner_id=r.owner_id WHERE r.owner_id=? AND COALESCE(s.kind,'eligibility')!='action_trigger'",(owner_id,)).fetchall()
 for row in rows:required.update(rule_fields(json.loads(row['ast_json'])))
 return sorted(required,key=lambda field:(field not in CORE_PROFILE_FIELDS,CORE_PROFILE_FIELDS.index(field) if field in CORE_PROFILE_FIELDS else field))
def effective_fact_items(owner_id:str,case_id:str):
 with conn() as c:rows=c.execute('SELECT * FROM facts WHERE owner_id=? AND (case_id IS NULL OR case_id=?) ORDER BY CASE WHEN case_id IS NULL THEN 0 ELSE 1 END,created_at,id',(owner_id,case_id)).fetchall()
 with conn() as c:validity={row['fact_id']:row['valid_until'] for row in c.execute('SELECT * FROM fact_validity WHERE owner_id=?',(owner_id,))}
 effective={}
 for row in rows:
  item=dict(row);item.pop('owner_id',None);item['valid_until']=validity.get(row['id']);item['expired']=expired(item['valid_until']);item['value']=None if item['expired'] else json.loads(item['value_json']);item.pop('value_json');item['scope']='profile' if item['case_id'] is None else 'case';effective[item['key']]=item
 return list(effective.values())
def owned(table,oid,uid):
 with conn() as c:r=c.execute(f'SELECT * FROM {table} WHERE id=? AND owner_id=?',(oid,uid)).fetchone()
 if not r:raise HTTPException(404,'资源不存在')
 return r
def validate_evidence_refs(evidence_ids:list[str],owner_id:str,case_id:str):
 if len(set(evidence_ids))!=len(evidence_ids):raise HTTPException(422,'EvidenceRef 不能重复')
 for evidence_id in evidence_ids:
  row=owned('evidence',evidence_id,owner_id)
  if row['case_id']!=case_id:raise HTTPException(422,'EvidenceRef 必须属于当前事项')
def case_json(row):
 item=dict(row)
 item['deadline_evidence_ids']=json.loads(item.pop('deadline_evidence_ids_json','[]') or '[]')
 with conn() as c:has_expiry=c.execute('SELECT 1 FROM fact_validity WHERE owner_id=? AND valid_until IS NOT NULL',(item['owner_id'],)).fetchone()
 if has_expiry:item['relevance']=evaluate_case(item['id'],item['owner_id'],persist=False)['relevance']
 return item
def parse_date(value:str|None):
 if not value:return None
 try:return date.fromisoformat(value[:10].replace('/','-'))
 except ValueError:return None

def normalize_deadline(value):
 if not value:return None
 try:return date.fromisoformat(value).isoformat() if len(value)==10 else utc_iso(parse_instant(value))
 except ValueError:raise HTTPException(422,'deadline 必须为有效ISO日期或带时区时间')
def encode_cursor(offset:int,sort:str):
 raw=json.dumps({'offset':offset,'sort':sort},separators=(',',':')).encode()
 return base64.urlsafe_b64encode(raw).decode().rstrip('=')
def decode_cursor(value:str|None,sort:str):
 if not value:return 0
 try:
  raw=base64.urlsafe_b64decode(value+'='*(-len(value)%4));payload=json.loads(raw)
  if payload.get('sort')!=sort or int(payload.get('offset',0))<0:raise ValueError
  return int(payload['offset'])
 except Exception:raise HTTPException(422,'无效分页 cursor')
def task_dtos(tasks,edges,owner_id:str,case_id:str):
 by={x['id']:dict(x) for x in tasks};predecessors={task_id:[] for task_id in by}
 for edge in edges:predecessors.setdefault(edge['after_task_id'],[]).append(edge['before_task_id'])
 with conn() as c:
  try:require_confirmed(c,owner_id,case_id);review_ready=True
  except ReviewError:review_ready=False
  links=c.execute('SELECT l.task_id,m.* FROM task_material_links l JOIN materials m ON m.id=l.material_id AND m.owner_id=l.owner_id WHERE l.owner_id=? AND m.case_id=? ORDER BY m.created_at',(owner_id,case_id)).fetchall()
  file_links=c.execute('SELECT l.task_id,v.id,v.name,v.category,v.mime,v.size,v.created_at,v.updated_at FROM vault_task_links l JOIN vault_items v ON v.id=l.vault_item_id AND v.owner_id=l.owner_id WHERE l.owner_id=? ORDER BY v.created_at',(owner_id,)).fetchall()
 materials_by_task={task_id:[] for task_id in by}
 for row in links:
  material=dict(row);task_id=material.pop('task_id');material['evidence_ids']=json.loads(material.pop('evidence_ids_json'))
  materials_by_task.setdefault(task_id,[]).append(material)
 files_by_task={task_id:[] for task_id in by}
 for row in file_links:
  item=dict(row);task_id=item.pop('task_id');item['content_url']=f"/api/v1/vault/items/{item['id']}/content";files_by_task.setdefault(task_id,[]).append(item)
 result=[]
 for task in tasks:
  item=dict(task);item['evidence_ids']=json.loads(item.pop('evidence_ids_json'))
  item['materials']=materials_by_task.get(item['id'],[]);item['files']=files_by_task.get(item['id'],[])
  item['is_actionable']=review_ready and item['status'] in {'todo','in_progress'} and all(by[parent]['status'] in {'done','skipped'} for parent in predecessors.get(item['id'],[]))
  result.append(item)
 return result

def dependency_dtos(c,owner_id,case_id):
 rows=c.execute('SELECT e.id,e.before_task_id,e.after_task_id,p.evidence_ids_json,p.source FROM task_edges e LEFT JOIN task_edge_evidence p ON p.edge_id=e.id AND p.owner_id=e.owner_id WHERE e.owner_id=? AND e.case_id=?',(owner_id,case_id)).fetchall()
 return [{'id':row['id'],'before_task_id':row['before_task_id'],'after_task_id':row['after_task_id'],'evidence_ids':json.loads(row['evidence_ids_json'] or '[]'),'source':row['source'] or 'unknown','review_needed':not bool(row['evidence_ids_json'])} for row in rows]

def schedule_item_json(row):
 item=dict(row);owner=item.pop('owner_id',None)
 with conn() as c:lock=c.execute('SELECT locked FROM schedule_locks WHERE item_id=? AND owner_id=?',(item['id'],owner)).fetchone()
 item['locked']=bool(lock and lock['locked']);return item

def vault_item_json(row):
 item=dict(row);owner_id=item.pop('owner_id');item.pop('content_provider',None);item.pop('content_key',None)
 with conn() as c:
  item['case_ids']=[r['case_id'] for r in c.execute('SELECT case_id FROM vault_case_links WHERE owner_id=? AND vault_item_id=? ORDER BY case_id',(owner_id,item['id']))]
  item['task_ids']=[r['task_id'] for r in c.execute('SELECT task_id FROM vault_task_links WHERE owner_id=? AND vault_item_id=? ORDER BY task_id',(owner_id,item['id']))]
 item['content_url']=f"/api/v1/vault/items/{item['id']}/content"
 return item

def validate_vault_links(case_ids:list[str],task_ids:list[str],owner_id:str):
 if len(set(case_ids))!=len(case_ids) or len(set(task_ids))!=len(task_ids):raise HTTPException(422,'关联 ID 不能重复')
 owned_cases={case_id:owned('cases',case_id,owner_id) for case_id in case_ids}
 owned_tasks={task_id:owned('tasks',task_id,owner_id) for task_id in task_ids}
 for task_id,task in owned_tasks.items():
  if task['case_id'] not in owned_cases:raise HTTPException(422,f'任务 {task_id} 必须关联其所属事项')

def parse_form_ids(value:str,field_name:str):
 try:parsed=json.loads(value)
 except json.JSONDecodeError:raise HTTPException(422,f'{field_name} 必须是 JSON 数组')
 if not isinstance(parsed,list) or not all(isinstance(item,str) for item in parsed):raise HTTPException(422,f'{field_name} 必须是字符串数组')
 return parsed
@app.post('/api/v2/sync/push')
def sync_push(body:SyncPush,user=Depends(current_user)):
 with conn() as c:
  prior=c.execute('SELECT result_json FROM sync_operations WHERE owner_id=? AND operation_id=?',(user['id'],body.operation_id)).fetchone()
  if prior:return data(json.loads(prior['result_json']))
  accepted=[];conflicts=[]
  for change in body.changes:
   last=c.execute('SELECT version,deleted_at FROM sync_changes WHERE owner_id=? AND entity_type=? AND entity_id=? ORDER BY cursor DESC LIMIT 1',(user['id'],change.entity_type,change.entity_id)).fetchone()
   if last and change.version<=last['version']:
    conflicts.append({'entity_id':change.entity_id,'server_version':last['version']});continue
   # A tombstone wins over stale writes; recreating needs a greater version.
   deleted=stamp() if change.deleted else None
   c.execute('INSERT INTO sync_changes(owner_id,entity_type,entity_id,version,payload_json,deleted_at,created_at) VALUES(?,?,?,?,?,?,?)',(user['id'],change.entity_type,change.entity_id,change.version,json.dumps(change.payload,ensure_ascii=False),deleted,stamp()));accepted.append(change.entity_id)
  result={'operation_id':body.operation_id,'accepted':accepted,'conflicts':conflicts}
  c.execute('INSERT INTO sync_operations VALUES(?,?,?,?)',(user['id'],body.operation_id,json.dumps(result),stamp()))
 return data(result)
@app.get('/api/v2/sync/pull')
def sync_pull(cursor:int=0,limit:int=100,user=Depends(current_user)):
 limit=max(1,min(limit,500))
 with conn() as c:rows=c.execute('SELECT cursor,entity_type,entity_id,version,payload_json,deleted_at FROM sync_changes WHERE owner_id=? AND cursor>? ORDER BY cursor LIMIT ?',(user['id'],cursor,limit)).fetchall()
 changes=[{**dict(r),'payload':json.loads(r['payload_json'])} for r in rows]
 return data({'changes':changes,'next_cursor':changes[-1]['cursor'] if changes else cursor})
@app.get('/health')
def health():
 provider=configured_provider()
 return data({'status':'ok','mode':'v2','analysis':'llm-configured' if provider.model_id!='none' else 'local-text-only','ai':{'configured':provider.model_id!='none','model_id':provider.model_id if provider.model_id!='none' else None}})

@app.post('/api/v1/timetable/parse')
async def parse_timetable(file:UploadFile=File(...),consent:bool=Form(False),user=Depends(current_user)):
 if not consent:raise HTTPException(422,'课表文件必须明确确认上传解析')
 try:
  raw=await read_upload(file);mime=file.content_type or ''
  from .services.file_validation import validate_file
  validate_file(raw,mime,file.filename or '')
  if mime not in ALLOWED:raise HTTPException(415,'不支持的课表格式')
  lines=parse_bytes(raw,mime,file.filename or '')
 except DocumentError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
 except HTTPException:raise
 except Exception:raise HTTPException(422,'课表解析失败，请使用清晰文件或手工填写')
 return data({'lines':[{'id':'block:client:'+str(uuid.uuid4()),'text':line['text'],'locator':line.get('locator'),'bbox':line.get('bbox')} for line in lines],'status':'needs_confirmation','warning':'未自动加入课表；原始文件不保存，文字需在客户端核对'})
@app.get('/api/v1/demo/notices/assessment')
def demo():
 p={'student_type':'undergraduate','enrollment_year':2024}; rules=load('rules.json');blocks=load('blocks.json'); by={b['id']:b for b in blocks}
 outcomes=[{**r,'evaluation':evaluate(r['ast'],p)} for r in rules]; notice=load('notice.json'); scope=outcomes[0]['evaluation']
 notice.update({'relevance':{'status':status_for(scope),'evidence':[by[x] for x in scope['supporting_evidence'] if x in by]},'rules':outcomes,'tasks':load('tasks.json'),'blocks':blocks,'workspace':'demo'})
 return data(notice)
@app.get('/api/v1/demo/scenarios')
def demo_scenarios():return data(json.loads((ROOT/'shared'/'demo'/'scenarios.v2.json').read_text(encoding='utf-8')))
@app.get('/api/v1/profile')
def get_profile(user=Depends(current_user)):
 return data(profile_values(user['id']))
@app.put('/api/v1/profile')
def put_profile(body:ProfileIn,user=Depends(current_user)):
 try:changes=validate_facts(body.facts)
 except ProfileError as exc:raise HTTPException(422,{'code':'PROFILE_INVALID','message':str(exc),'fields':exc.fields})
 if set(body.valid_until)-set(changes):raise HTTPException(422,'有效期只能设置本次填写的画像字段')
 try:validities={key:normalize_validity(value) for key,value in body.valid_until.items()}
 except ValueError as exc:raise HTTPException(422,str(exc))
 with conn() as c:
  for key,value in changes.items():
   full='profile.'+key;fid=str(uuid.uuid4());c.execute('DELETE FROM facts WHERE owner_id=? AND case_id IS NULL AND key=?',(user['id'],full));c.execute('INSERT INTO facts VALUES(?,?,?,?,?,?,?)',(fid,user['id'],None,full,json.dumps(value,ensure_ascii=False),'profile',stamp()));record_fact(c,fid,user['id'],None,full,value,validities.get(key))
  c.execute('INSERT INTO profile_versions VALUES(?,1,?) ON CONFLICT(owner_id) DO UPDATE SET revision=revision+1,updated_at=excluded.updated_at',(user['id'],stamp()))
 with conn() as c:case_ids=[r['id'] for r in c.execute("SELECT id FROM cases WHERE owner_id=? AND status!='deleted'",(user['id'],)).fetchall()]
 for case_id in case_ids:evaluate_case(case_id,user['id'])
 return data(changes)

@app.get('/api/v1/profile/history')
def profile_history(user=Depends(current_user)):
 with conn() as c:rows=c.execute('SELECT * FROM fact_history WHERE owner_id=? ORDER BY created_at DESC,id LIMIT 500',(user['id'],)).fetchall()
 return data([{**{key:row[key] for key in ('id','case_id','key','source','created_at','valid_until')},'value':json.loads(row['value_json'])} for row in rows])

@app.get('/api/v1/profile/interests')
def get_profile_interests(user=Depends(current_user)):
 with conn() as c:row=c.execute('SELECT * FROM profile_interests WHERE owner_id=?',(user['id'],)).fetchone()
 return data({'categories':json.loads(row['categories_json']) if row else [],'revision':row['revision'] if row else 0,'source':'user_input'})

@app.put('/api/v1/profile/interests')
def put_profile_interests(body:ProfileInterestsIn,user=Depends(current_user)):
 database()
 if len(body.categories)!=len(set(body.categories)) or set(body.categories)-CASE_CATEGORIES:raise HTTPException(422,'关注分类无效或重复')
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  c.execute('INSERT INTO profile_interests VALUES(?,?,1,?) ON CONFLICT(owner_id) DO UPDATE SET categories_json=excluded.categories_json,revision=revision+1,updated_at=excluded.updated_at',(user['id'],json.dumps(sorted(body.categories)),stamp()))
  for case in c.execute('SELECT id FROM cases WHERE owner_id=?',(user['id'],)).fetchall():bind_interest(c,user['id'],case['id'])
 return data({'categories':sorted(body.categories),'source':'user_input'})

@app.get('/api/v1/profile/meta')
def profile_metadata(user=Depends(current_user)):
 values=profile_values(user['id'])
 with conn() as c:
  row=c.execute('SELECT revision,updated_at FROM profile_versions WHERE owner_id=?',(user['id'],)).fetchone()
  validity={item['key'].removeprefix('profile.'):item['valid_until'] for item in c.execute('SELECT f.key,v.valid_until FROM facts f JOIN fact_validity v ON v.fact_id=f.id AND v.owner_id=f.owner_id WHERE f.owner_id=? AND f.case_id IS NULL',(user['id'],))}
 return data({'revision':row['revision'] if row else 0,'updated_at':row['updated_at'] if row else None,'source':'user_input','invalid_fields':[key for key,value in values.items() if not valid_value(key,value)],'field_valid_until':validity,'expired_fields':[key for key,value in validity.items() if expired(value)]})
@app.get('/api/v1/profile/completeness')
def profile_completeness(user=Depends(current_user)):
 fields=required_profile_fields(user['id']);values=profile_values(user['id'])
 completed=[field for field in fields if values.get(field) not in (None,'',[]) and valid_value(field,values.get(field))]
 missing=[field for field in fields if field not in completed]
 return data({'score':round(len(completed)*100/len(fields)) if fields else 100,'completed_fields':completed,'missing_fields':missing,'required_fields':fields})
@app.post('/api/v1/privacy/analyze')
def privacy_analyze(body:PrivacyIn):
 return data(analyze_privacy(body.text))
def account_settings_json(user):
 with conn() as c:settings=c.execute('SELECT * FROM account_settings WHERE owner_id=?',(user['id'],)).fetchone()
 return {'id':user['id'],'email':user['email'],'email_verified':bool(user['verified_at']),'display_name':settings['display_name'] if settings else None,'locale':settings['locale'] if settings else 'zh-CN','timezone':settings['timezone'] if settings else 'Asia/Shanghai','created_at':user['created_at'],'updated_at':settings['updated_at'] if settings else None}
@app.get('/api/v1/account/settings')
def get_account_settings(user=Depends(current_user)):
 database()
 return data(account_settings_json(user))
@app.patch('/api/v1/account/settings')
def patch_account_settings(body:AccountSettingsPatch,user=Depends(current_user)):
 database()
 fields=body.model_fields_set
 if not fields:raise HTTPException(422,'至少提供一个账户设置字段')
 if 'locale' in fields and body.locale and not re.fullmatch(r'[a-z]{2}(?:-[A-Z]{2})?',body.locale):raise HTTPException(422,'locale 格式无效')
 if 'timezone' in fields and body.timezone:
  if body.timezone!='Asia/Shanghai':
   try:ZoneInfo(body.timezone)
   except ZoneInfoNotFoundError:raise HTTPException(422,'timezone 无效')
 current=account_settings_json(user);now=stamp()
 display_name=body.display_name if 'display_name' in fields else current['display_name']
 locale=body.locale if 'locale' in fields else current['locale'];timezone_name=body.timezone if 'timezone' in fields else current['timezone']
 if not locale or not timezone_name:raise HTTPException(422,'locale 和 timezone 不能为 null')
 with conn() as c:c.execute('INSERT INTO account_settings(owner_id,display_name,locale,timezone,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(owner_id) DO UPDATE SET display_name=excluded.display_name,locale=excluded.locale,timezone=excluded.timezone,updated_at=excluded.updated_at',(user['id'],display_name,locale,timezone_name,now,now))
 return data(account_settings_json(user))

@app.get('/api/v1/dashboard')
def dashboard(user=Depends(current_user)):
 database()
 settings=account_settings_json(user);timezone_name=settings['timezone']
 try:tz=timezone_for(timezone_name)
 except ValueError:timezone_name='Asia/Shanghai';tz=timezone_for(timezone_name)
 today=datetime.now(tz).date();due_through=today+timedelta(days=7)
 day_start=utc_iso(datetime.combine(today,time.min,tzinfo=tz));day_end=utc_iso(datetime.combine(today+timedelta(days=1),time.min,tzinfo=tz))
 with conn() as c:
  case_rows=c.execute("""SELECT c.*,COUNT(t.id) task_count,COALESCE(SUM(CASE WHEN t.status='done' THEN 1 ELSE 0 END),0) done_task_count
   FROM cases c LEFT JOIN tasks t ON t.owner_id=c.owner_id AND t.case_id=c.id
   WHERE c.owner_id=? GROUP BY c.id""",(user['id'],)).fetchall()
  task_rows=c.execute("""SELECT t.*,c.title case_title,c.status case_status
   FROM tasks t JOIN cases c ON c.id=t.case_id AND c.owner_id=t.owner_id
   WHERE t.owner_id=? AND c.status NOT IN ('completed','archived','deleted')""",(user['id'],)).fetchall()
  edge_rows=c.execute('SELECT before_task_id,after_task_id FROM task_edges WHERE owner_id=?',(user['id'],)).fetchall()
  schedule_rows=c.execute("SELECT * FROM schedule_items WHERE owner_id=? AND kind='task' AND starts_at<? AND ends_at>? ORDER BY starts_at,id",(user['id'],day_end,day_start)).fetchall()
  material_rows=c.execute('SELECT l.task_id,m.* FROM task_material_links l JOIN materials m ON m.id=l.material_id AND m.owner_id=l.owner_id WHERE l.owner_id=? ORDER BY m.created_at',(user['id'],)).fetchall()
  file_rows=c.execute('SELECT l.task_id,v.id,v.name,v.category,v.mime,v.size,v.created_at,v.updated_at FROM vault_task_links l JOIN vault_items v ON v.id=l.vault_item_id AND v.owner_id=l.owner_id WHERE l.owner_id=? ORDER BY v.created_at',(user['id'],)).fetchall()
 case_items=[]
 for row in case_rows:
  item=case_json(row);total=int(item['task_count']);done=int(item['done_task_count']);item['progress']=round(done*100/total) if total else 0;case_items.append(item)
 active_cases=[item for item in case_items if item['status'] not in {'archived','deleted'}]
 recent_cases=sorted(active_cases,key=lambda item:(item['updated_at'],item['id']),reverse=True)[:5]
 schedule_by_task={row['task_id']:schedule_item_json(row) for row in schedule_rows if row['task_id']}
 statuses={row['id']:row['status'] for row in task_rows};predecessors={task_id:[] for task_id in statuses}
 for edge in edge_rows:predecessors.setdefault(edge['after_task_id'],[]).append(edge['before_task_id'])
 materials_by_task={task_id:[] for task_id in statuses};files_by_task={task_id:[] for task_id in statuses}
 for row in material_rows:
  item=dict(row);task_id=item.pop('task_id');item['evidence_ids']=json.loads(item.pop('evidence_ids_json'));materials_by_task.setdefault(task_id,[]).append(item)
 for row in file_rows:
  item=dict(row);task_id=item.pop('task_id');item['content_url']=f"/api/v1/vault/items/{item['id']}/content";files_by_task.setdefault(task_id,[]).append(item)
 today_tasks=[]
 for row in task_rows:
  if row['status'] not in {'todo','in_progress'}:continue
  schedule_item=schedule_by_task.get(row['id']);deadline_today=parse_date(row['deadline'])==today
  if not deadline_today and not schedule_item:continue
  item=dict(row);item.pop('case_status',None);item['evidence_ids']=json.loads(item.pop('evidence_ids_json'));item['materials']=materials_by_task.get(item['id'],[]);item['files']=files_by_task.get(item['id'],[])
  item['is_actionable']=all(statuses.get(parent) in {'done','skipped'} for parent in predecessors.get(item['id'],[]))
  item['sources']=[source for source,present in (('deadline',deadline_today),('schedule',bool(schedule_item))) if present]
  item['schedule_item']=schedule_item;item['scheduled_start']=schedule_item['starts_at'] if schedule_item else None;item['scheduled_end']=schedule_item['ends_at'] if schedule_item else None
  today_tasks.append(item)
 today_tasks.sort(key=lambda item:(item['scheduled_start'] is None,item['scheduled_start'] or '',item['deadline'] or '',item['id']))
 return data({'date':today.isoformat(),'timezone':timezone_name,'total_cases':len(active_cases),'in_progress_cases':sum(item['status']=='in_progress' for item in active_cases),'due_soon_cases':sum(item['status'] not in {'completed','archived','deleted'} and (deadline:=parse_date(item.get('deadline'))) is not None and today<=deadline<=due_through for item in case_items),'completed_cases':sum(item['status']=='completed' for item in case_items),'recent_cases':recent_cases,'today_tasks':today_tasks})

def validate_schedule_links(kind:str,case_id:str|None,task_id:str|None,owner_id:str):
 if kind not in SCHEDULE_KINDS:raise HTTPException(422,'无效日程类型')
 task=None
 if task_id:
  task=owned('tasks',task_id,owner_id)
  if case_id and task['case_id']!=case_id:raise HTTPException(422,'任务不属于关联事项')
  case_id=task['case_id']
 if case_id:owned('cases',case_id,owner_id)
 if kind=='task' and not task_id:raise HTTPException(422,'任务日程必须关联 task_id')
 if kind!='task' and task_id:raise HTTPException(422,'只有任务日程可以关联 task_id')
 if kind=='task':check_review(owner_id,case_id)
 return case_id

def check_review(owner_id:str,case_id:str):
 with conn() as c:
  try:require_confirmed(c,owner_id,case_id)
  except ReviewError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})

def normalize_schedule_range(starts_at:str,ends_at:str):
 try:start=parse_instant(starts_at);end=parse_instant(ends_at)
 except ValueError as exc:raise HTTPException(422,str(exc))
 if end<=start:raise HTTPException(422,'ends_at 必须晚于 starts_at')
 if end-start>timedelta(days=7):raise HTTPException(422,'单个日程不能超过 7 天')
 return utc_iso(start),utc_iso(end)

def ensure_schedule_slot(owner_id:str,starts_at:str,ends_at:str,exclude_id:str|None=None):
 sql='SELECT id FROM schedule_items WHERE owner_id=? AND starts_at<? AND ends_at>?'
 params:list[object]=[owner_id,ends_at,starts_at]
 if exclude_id:sql+=' AND id<>?';params.append(exclude_id)
 with conn() as c:conflict=c.execute(sql,params).fetchone()
 if conflict:raise HTTPException(409,'该时间段与已有安排冲突')

def ensure_task_schedule_unique(owner_id:str,task_id:str|None,exclude_id:str|None=None):
 if not task_id:return
 sql='SELECT id FROM schedule_items WHERE owner_id=? AND task_id=?';params:list[object]=[owner_id,task_id]
 if exclude_id:sql+=' AND id<>?';params.append(exclude_id)
 with conn() as c:
  existing=c.execute(sql,params).fetchone()
  planning=c.execute('SELECT splittable FROM task_planning WHERE task_id=? AND owner_id=?',(task_id,owner_id)).fetchone()
  own_item=c.execute('SELECT 1 FROM schedule_items WHERE id=? AND owner_id=? AND task_id=?',(exclude_id,owner_id,task_id)).fetchone() if exclude_id else None
 if existing and not (own_item and planning and planning['splittable']):raise HTTPException(409,'该任务已有日程安排')

def validate_schedule_write(c,owner_id,case_id,task_id,starts_at,ends_at,exclude_id=None,allow_split=False):
 if exclude_id:
  lock=c.execute('SELECT locked FROM schedule_locks WHERE item_id=? AND owner_id=?',(exclude_id,owner_id)).fetchone()
  if lock and lock['locked']:raise HTTPException(409,'安排已锁定，请先明确解锁')
 if task_id:
  try:require_confirmed(c,owner_id,case_id)
  except ReviewError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
  duplicate=c.execute('SELECT id FROM schedule_items WHERE owner_id=? AND task_id=? AND (? IS NULL OR id<>?)',(owner_id,task_id,exclude_id,exclude_id)).fetchone()
  options=c.execute('SELECT splittable FROM task_planning WHERE task_id=? AND owner_id=?',(task_id,owner_id)).fetchone()
  own_item=c.execute('SELECT 1 FROM schedule_items WHERE id=? AND owner_id=? AND task_id=?',(exclude_id,owner_id,task_id)).fetchone() if exclude_id else None
  if duplicate and not ((allow_split or own_item) and options and options['splittable']):raise HTTPException(409,'该任务已有日程安排')
  task=c.execute('SELECT * FROM tasks WHERE id=? AND owner_id=? AND case_id=?',(task_id,owner_id,case_id)).fetchone()
  if not task:raise HTTPException(404,'任务不存在')
  if task['deadline']:
   from .services.schedule import _deadline
   deadline=_deadline(task['deadline'],timezone_for('Asia/Shanghai'))
   if not deadline or parse_instant(ends_at)>deadline:raise HTTPException(409,'安排超出任务截止时间')
  for edge in c.execute('SELECT before_task_id FROM task_edges WHERE owner_id=? AND after_task_id=?',(owner_id,task_id)):
   predecessor=c.execute('SELECT status,duration_minutes FROM tasks WHERE id=? AND owner_id=?',(edge['before_task_id'],owner_id)).fetchone()
   if predecessor and predecessor['status'] in {'done','skipped'}:continue
   blocks=c.execute('SELECT starts_at,ends_at FROM schedule_items WHERE owner_id=? AND task_id=?',(owner_id,edge['before_task_id'])).fetchall()
   minutes=sum((parse_instant(block['ends_at'])-parse_instant(block['starts_at'])).total_seconds()/60 for block in blocks)
   if not blocks or not predecessor or minutes<(predecessor['duration_minutes'] or 30) or max(parse_instant(block['ends_at']) for block in blocks)>parse_instant(starts_at):raise HTTPException(409,'前置步骤尚未完成或未完整安排在此步骤之前')
  other=c.execute('SELECT starts_at,ends_at FROM schedule_items WHERE owner_id=? AND task_id=? AND (? IS NULL OR id<>?)',(owner_id,task_id,exclude_id,exclude_id)).fetchall()
  total_minutes=(parse_instant(ends_at)-parse_instant(starts_at)).total_seconds()/60+sum((parse_instant(block['ends_at'])-parse_instant(block['starts_at'])).total_seconds()/60 for block in other)
  latest=max([parse_instant(ends_at)]+[parse_instant(block['ends_at']) for block in other])
  for edge in c.execute('SELECT after_task_id FROM task_edges WHERE owner_id=? AND before_task_id=?',(owner_id,task_id)):
   next_blocks=c.execute('SELECT starts_at FROM schedule_items WHERE owner_id=? AND task_id=?',(owner_id,edge['after_task_id'])).fetchall()
   if next_blocks and (total_minutes<(task['duration_minutes'] or 30) or any(parse_instant(block['starts_at'])<latest for block in next_blocks)):raise HTTPException(409,'修改会破坏已安排后置步骤的依赖，请先移除后置安排')
 conflict=c.execute('SELECT id FROM schedule_items WHERE owner_id=? AND starts_at<? AND ends_at>? AND (? IS NULL OR id<>?)',(owner_id,ends_at,starts_at,exclude_id,exclude_id)).fetchone()
 if conflict:raise HTTPException(409,'该时间段与已有安排冲突')

@app.get('/api/v1/schedule')
def get_schedule(from_at:str|None=Query(default=None,alias='from'),to_at:str|None=Query(default=None,alias='to'),case_id:str|None=None,task_id:str|None=None,kind:str|None=None,user=Depends(current_user)):
 database()
 if kind and kind not in SCHEDULE_KINDS:raise HTTPException(422,'无效日程类型')
 if case_id:owned('cases',case_id,user['id'])
 if task_id:owned('tasks',task_id,user['id'])
 clauses=['owner_id=?'];params:list[object]=[user['id']]
 if from_at:
  try:from_value=utc_iso(parse_instant(from_at))
  except ValueError as exc:raise HTTPException(422,str(exc))
  clauses.append('ends_at>?');params.append(from_value)
 if to_at:
  try:to_value=utc_iso(parse_instant(to_at))
  except ValueError as exc:raise HTTPException(422,str(exc))
  clauses.append('starts_at<?');params.append(to_value)
 if case_id:clauses.append('case_id=?');params.append(case_id)
 if task_id:clauses.append('task_id=?');params.append(task_id)
 if kind:clauses.append('kind=?');params.append(kind)
 with conn() as c:rows=c.execute('SELECT * FROM schedule_items WHERE '+' AND '.join(clauses)+' ORDER BY starts_at,id',params).fetchall()
 return data([schedule_item_json(row) for row in rows])

@app.post('/api/v1/schedule/items')
def create_schedule_item(body:ScheduleItemIn,user=Depends(current_user)):
 database();case_id=validate_schedule_links(body.kind,body.case_id,body.task_id,user['id']);starts_at,ends_at=normalize_schedule_range(body.starts_at,body.ends_at);ensure_task_schedule_unique(user['id'],body.task_id);ensure_schedule_slot(user['id'],starts_at,ends_at)
 item_id=str(uuid.uuid4());now=stamp()
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  validate_schedule_write(c,user['id'],case_id,body.task_id,starts_at,ends_at)
  c.execute('INSERT INTO schedule_items(id,owner_id,case_id,task_id,title,kind,starts_at,ends_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(item_id,user['id'],case_id,body.task_id,body.title,body.kind,starts_at,ends_at,now,now))
 return data(schedule_item_json(owned('schedule_items',item_id,user['id'])))

@app.patch('/api/v1/schedule/items/{item_id}')
def patch_schedule_item(item_id:str,body:ScheduleItemPatch,user=Depends(current_user)):
 require_unlocked(item_id,user['id'])
 current=dict(owned('schedule_items',item_id,user['id']));fields=body.model_fields_set
 if not fields:raise HTTPException(422,'至少提供一个日程字段')
 merged={key:(getattr(body,key) if key in fields else current[key]) for key in ('title','kind','starts_at','ends_at','case_id','task_id')}
 if any(merged[key] is None for key in ('title','kind','starts_at','ends_at')):raise HTTPException(422,'title、kind、starts_at 和 ends_at 不能为 null')
 case_id=validate_schedule_links(merged['kind'],merged['case_id'],merged['task_id'],user['id']);starts_at,ends_at=normalize_schedule_range(merged['starts_at'],merged['ends_at']);ensure_task_schedule_unique(user['id'],merged['task_id'],item_id);ensure_schedule_slot(user['id'],starts_at,ends_at,item_id)
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  validate_schedule_write(c,user['id'],case_id,merged['task_id'],starts_at,ends_at,item_id)
  c.execute('UPDATE schedule_items SET title=?,kind=?,starts_at=?,ends_at=?,case_id=?,task_id=?,updated_at=? WHERE id=? AND owner_id=?',(merged['title'],merged['kind'],starts_at,ends_at,case_id,merged['task_id'],stamp(),item_id,user['id']))
 return data(schedule_item_json(owned('schedule_items',item_id,user['id'])))

@app.delete('/api/v1/schedule/items/{item_id}')
def delete_schedule_item(item_id:str,user=Depends(current_user)):
 require_unlocked(item_id,user['id'])
 owned('schedule_items',item_id,user['id'])
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  lock=c.execute('SELECT locked FROM schedule_locks WHERE item_id=? AND owner_id=?',(item_id,user['id'])).fetchone()
  if lock and lock['locked']:raise HTTPException(409,'安排已锁定，请先明确解锁')
  item=c.execute('SELECT task_id FROM schedule_items WHERE id=? AND owner_id=?',(item_id,user['id'])).fetchone()
  if item and item['task_id'] and c.execute('SELECT 1 FROM task_edges e JOIN schedule_items s ON s.task_id=e.after_task_id AND s.owner_id=e.owner_id WHERE e.owner_id=? AND e.before_task_id=?',(user['id'],item['task_id'])).fetchone():raise HTTPException(409,'前置步骤已有后置安排，请先移除后置安排')
  c.execute('DELETE FROM schedule_locks WHERE item_id=? AND owner_id=?',(item_id,user['id']))
  c.execute('DELETE FROM schedule_items WHERE id=? AND owner_id=?',(item_id,user['id']))
 return data({'id':item_id,'deleted':True})

def require_unlocked(item_id,owner_id):
 with conn() as c:lock=c.execute('SELECT locked FROM schedule_locks WHERE item_id=? AND owner_id=?',(item_id,owner_id)).fetchone()
 if lock and lock['locked']:raise HTTPException(409,'安排已锁定，请先明确解锁')

@app.post('/api/v1/schedule/items/{item_id}/lock')
def set_schedule_lock(item_id:str,body:ScheduleLockIn,user=Depends(current_user)):
 owned('schedule_items',item_id,user['id'])
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if not c.execute('SELECT 1 FROM schedule_items WHERE id=? AND owner_id=?',(item_id,user['id'])).fetchone():raise HTTPException(404,'安排不存在')
  c.execute('INSERT INTO schedule_locks VALUES(?,?,?) ON CONFLICT(item_id) DO UPDATE SET locked=excluded.locked',(item_id,user['id'],int(body.locked)))
 return data({'id':item_id,'locked':body.locked})

@app.post('/api/v1/schedule/series')
def create_schedule_series(body:ScheduleSeriesIn,user=Depends(current_user)):
 database()
 if body.kind not in {'course','busy'} or body.task_id:raise HTTPException(422,'周期安排仅支持课程或忙碌时段')
 case_id=validate_schedule_links(body.kind,body.case_id,None,user['id'])
 try:tz=timezone_for(body.timezone);start=parse_instant(body.starts_at).astimezone(tz);end=parse_instant(body.ends_at).astimezone(tz)
 except ValueError as exc:raise HTTPException(422,str(exc))
 ids=[];now=stamp()
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  for index in range(body.count):
   shift=timedelta(weeks=index*body.every_weeks);starts_at,ends_at=normalize_schedule_range((start+shift).isoformat(),(end+shift).isoformat())
   validate_schedule_write(c,user['id'],case_id,None,starts_at,ends_at)
   item_id=str(uuid.uuid4());ids.append(item_id)
   c.execute('INSERT INTO schedule_items VALUES(?,?,?,?,?,?,?,?,?,?)',(item_id,user['id'],case_id,None,body.title,body.kind,starts_at,ends_at,now,now))
 return data({'ids':ids,'count':len(ids),'timezone':body.timezone,'expanded':True})

@app.post('/api/v1/schedule/preview')
def schedule_preview(body:SchedulePreviewIn,user=Depends(current_user)):
 database()
 try:tz=timezone_for(body.timezone)
 except ValueError as exc:raise HTTPException(422,str(exc))
 now=datetime.now(tz)
 try:
  window_start=parse_instant(body.window_start) if body.window_start else now
  window_end=parse_instant(body.window_end) if body.window_end else window_start+timedelta(days=14)
 except ValueError as exc:raise HTTPException(422,str(exc))
 if body.case_id:
  owned('cases',body.case_id,user['id'])
  check_review(user['id'],body.case_id)
 if len(set(body.task_ids))!=len(body.task_ids):raise HTTPException(422,'task_ids 不能重复')
 if body.task_ids:
  tasks=[dict(owned('tasks',task_id,user['id'])) for task_id in body.task_ids]
  if body.case_id and any(task['case_id']!=body.case_id for task in tasks):raise HTTPException(422,'任务不属于指定事项')
 else:
  sql="SELECT * FROM tasks WHERE owner_id=? AND status IN ('todo','in_progress')";params:list[object]=[user['id']]
  if body.case_id:sql+=' AND case_id=?';params.append(body.case_id)
  with conn() as c:tasks=[dict(row) for row in c.execute(sql,params).fetchall()]
 tasks=[task for task in tasks if task['status'] in {'todo','in_progress'}]
 for case_id in {task['case_id'] for task in tasks}:check_review(user['id'],case_id)
 selected_ids={task['id'] for task in tasks}
 with conn() as c:
  planning={row['task_id']:dict(row) for row in c.execute('SELECT * FROM task_planning WHERE owner_id=?',(user['id'],))}
  for task in tasks:
   if task['id'] in planning:task.update({key:value for key,value in planning[task['id']].items() if key in {'splittable','min_chunk_minutes','max_chunk_minutes','importance','preference'}})
  edges=[dict(row) for row in c.execute('SELECT before_task_id,after_task_id FROM task_edges WHERE owner_id=?',(user['id'],)).fetchall() if row['after_task_id'] in selected_ids]
  existing=[dict(row) for row in c.execute('SELECT * FROM schedule_items WHERE owner_id=? ORDER BY starts_at,id',(user['id'],)).fetchall()]
  statuses={row['id']:row['status'] for row in c.execute('SELECT id,status FROM tasks WHERE owner_id=?',(user['id'],)).fetchall()}
 if body.calendar_blocks:
  if not body.calendar_consent or body.calendar_revision is None:raise HTTPException(422,'本机课表占用时段须明确确认发送并附资料版本')
  for block in body.calendar_blocks:
   starts_at,ends_at=normalize_schedule_range(block.starts_at,block.ends_at)
   if any(not re.fullmatch(r'block:client:[A-Za-z0-9-]+',ref) for ref in block.evidence_ids):raise HTTPException(422,'课表缺少有效本机证据')
   existing.append({'id':block.id,'title':'本机课表占用','kind':'course','starts_at':starts_at,'ends_at':ends_at})
 try:result=preview_schedule(tasks,edges,existing,window_start,window_end,body.timezone,statuses,body.preferences.model_dump())
 except ValueError as exc:raise HTTPException(422,str(exc))
 if body.calendar_revision is not None:result.update(calendar_revision=body.calendar_revision,calendar_blocks=[b.model_dump() for b in body.calendar_blocks])
 return data(result)

@app.put('/api/v1/tasks/{task_id}/planning')
def update_task_planning(task_id:str,body:TaskPlanningIn,user=Depends(current_user)):
 task=owned('tasks',task_id,user['id']);check_review(user['id'],task['case_id'])
 if body.min_chunk_minutes%30 or body.max_chunk_minutes%30 or body.min_chunk_minutes>body.max_chunk_minutes:raise HTTPException(422,'分段长度须为30分钟倍数且最小值不大于最大值')
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT 1 FROM schedule_items WHERE task_id=? AND owner_id=?',(task_id,user['id'])).fetchone():raise HTTPException(409,'任务已有安排，请先移除对应安排再修改耗时或拆分方式')
  ref='block:'+str(uuid.uuid4());now=stamp()
  c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,user['id'],task['case_id'],'用户排程偏好',f'用户估计步骤耗时{body.duration_minutes}分钟；可拆分={body.splittable}；最小片段{body.min_chunk_minutes}分钟；最大片段{body.max_chunk_minutes}分钟；重要性{body.importance}；偏好{body.preference}','用户填写，不代表官方通知',None,now))
  refs=sorted(set(json.loads(task['evidence_ids_json']))|{ref})
  c.execute('UPDATE tasks SET duration_minutes=?,evidence_ids_json=?,updated_at=? WHERE id=? AND owner_id=?',(body.duration_minutes,json.dumps(refs),now,task_id,user['id']))
  c.execute('INSERT INTO task_planning VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET splittable=excluded.splittable,min_chunk_minutes=excluded.min_chunk_minutes,max_chunk_minutes=excluded.max_chunk_minutes,importance=excluded.importance,preference=excluded.preference,evidence_id=excluded.evidence_id,updated_at=excluded.updated_at',(task_id,user['id'],int(body.splittable),body.min_chunk_minutes,body.max_chunk_minutes,body.importance,body.preference,ref,now))
 return data({'task_id':task_id,'planning':body.model_dump(),'evidence_ids':[ref]})

@app.post('/api/v1/schedule/drafts')
def schedule_draft(body:SchedulePreviewIn,user=Depends(current_user)):
 database()
 with conn() as c:before=schedule_snapshot(c,user['id'])
 result=schedule_preview(body,user)['data']
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if schedule_snapshot(c,user['id'])!=before:raise HTTPException(409,{'code':'DRAFT_STALE','message':'预览期间状态变化，请重试'})
  return data(create_draft(c,user['id'],result,before))

@app.post('/api/v1/schedule/drafts/{draft_id}/commit')
def schedule_draft_commit(draft_id:str,body:DraftCommitIn,user=Depends(current_user)):
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  try:return data(commit_draft(c,user['id'],draft_id,body.consent,validate_schedule_write,body.calendar_revision))
  except DraftError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})

@app.get('/api/v1/cases/{case_id}/knowledge-evidence')
def knowledge_evidence(case_id:str,user=Depends(current_user)):
 case=dict(owned('cases',case_id,user['id']))
 with conn() as c:
  evidence=[dict(row) for row in c.execute('SELECT id,text,source_name,locator FROM evidence WHERE owner_id=? AND case_id=? ORDER BY created_at',(user['id'],case_id)).fetchall()]
  rules=[dict(row) for row in c.execute('SELECT id,label FROM rules WHERE owner_id=? AND case_id=? ORDER BY created_at',(user['id'],case_id)).fetchall()]
 return data(get_knowledge_provider().search(case,evidence,rules))

@app.post('/api/v1/knowledge/text')
def import_knowledge_text(body:KnowledgeTextIn,user=Depends(current_user)):
 if not body.consent:raise HTTPException(422,{'code':'CONFIRMATION_REQUIRED','message':'请确认将资料保存到当前账户知识库'})
 database()
 with conn() as c:
  document=store_document(c,document_root(),user['id'],body.text.encode(),'text/plain',body.title+'.txt',parse_bytes)
  knowledge_id=index_document(c,user['id'],document['id'],body.title,body.category)
 return data({'id':knowledge_id,'document_id':document['id'],'status':'indexed','index_type':'local_tfidf_bigram'})

@app.post('/api/v1/knowledge/documents')
async def import_knowledge_file(file:UploadFile=File(...),consent:bool=Form(False),title:str=Form('知识资料'),user=Depends(current_user)):
 if not consent:raise HTTPException(422,{'code':'CONFIRMATION_REQUIRED','message':'请确认知识资料保存范围'})
 database()
 try:
  raw=await read_upload(file);mime=file.content_type or mimetypes.guess_type(file.filename or '')[0]
  with conn() as c:
   document=store_document(c,document_root(),user['id'],raw,mime,file.filename or '',parse_bytes)
   if document['status']=='failed':return data({'document_id':document['id'],'status':'indexing_failed','error_code':document['error_code']})
   knowledge_id=index_document(c,user['id'],document['id'],title[:300])
 except DocumentError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
 return data({'id':knowledge_id,'document_id':document['id'],'status':'indexed','index_type':'local_tfidf_bigram'})

@app.get('/api/v1/knowledge/documents')
def list_knowledge(user=Depends(current_user)):
 with conn() as c:rows=c.execute('SELECT id,document_id,title,category,publisher,effective_date,status,created_at FROM knowledge_documents WHERE owner_id=? ORDER BY created_at DESC,id',(user['id'],)).fetchall()
 return data([dict(row) for row in rows])

@app.post('/api/v1/knowledge/search')
def knowledge_search(body:KnowledgeSearchIn,user=Depends(current_user)):
 with conn() as c:return data(search_knowledge(c,user['id'],body.query,body.top_k,body.category))

@app.post('/api/v1/knowledge/ask')
def knowledge_ask(body:KnowledgeSearchIn,user=Depends(current_user)):
 with conn() as c:result=search_knowledge(c,user['id'],body.query,body.top_k,body.category)
 return data(answer_with_sources(result))

@app.delete('/api/v1/knowledge/documents/{knowledge_id}')
def delete_knowledge(knowledge_id:str,user=Depends(current_user)):
 owned('knowledge_documents',knowledge_id,user['id'])
 with conn() as c:
  c.execute('DELETE FROM knowledge_chunks WHERE owner_id=? AND knowledge_id=?',(user['id'],knowledge_id))
  c.execute('DELETE FROM knowledge_documents WHERE owner_id=? AND id=?',(user['id'],knowledge_id))
 return data({'id':knowledge_id,'deleted':True,'original_retained':True})

@app.post('/api/v1/cases/{case_id}/knowledge/{chunk_id}/attach')
def attach_knowledge(case_id:str,chunk_id:str,body:KnowledgeConsent,user=Depends(current_user)):
 owned('cases',case_id,user['id']);chunk=owned('knowledge_chunks',chunk_id,user['id'])
 if not body.consent:raise HTTPException(422,{'code':'CONFIRMATION_REQUIRED','message':'请核对该条款是否适用后明确确认'})
 evidence_id='block:'+str(uuid.uuid5(uuid.NAMESPACE_URL,f'knowledge:{case_id}:{chunk_id}'))
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  chunk=c.execute('SELECT * FROM knowledge_chunks WHERE id=? AND owner_id=?',(chunk_id,user['id'])).fetchone()
  if not chunk:raise HTTPException(404,'知识条款已失效，请重新检索')
  existing=c.execute('SELECT 1 FROM evidence WHERE owner_id=? AND id=?',(user['id'],evidence_id)).fetchone()
  if not existing:
   source=c.execute('SELECT title FROM knowledge_documents WHERE id=? AND owner_id=?',(chunk['knowledge_id'],user['id'])).fetchone()
   c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(evidence_id,user['id'],case_id,source['title'],chunk['text'],'用户确认关联知识条款',chunk['page'],stamp()))
   document_id=c.execute('SELECT document_id FROM knowledge_documents WHERE id=? AND owner_id=?',(chunk['knowledge_id'],user['id'])).fetchone()[0]
   c.execute('INSERT INTO knowledge_evidence_sources VALUES(?,?,?,?)',(user['id'],evidence_id,document_id,hashlib.sha256(chunk['text'].encode()).hexdigest()))
   for rule in extract_rules([(evidence_id,chunk['text'])]):
    rid=str(uuid.uuid4());c.execute('INSERT INTO rules VALUES(?,?,?,?,?,?,?)',(rid,user['id'],case_id,rule['label'],json.dumps(rule['ast']),json.dumps(rule['evidence_ids']),stamp()))
    c.execute('INSERT INTO rule_semantics VALUES(?,?,?)',(rid,user['id'],rule['kind']))
   invalidate_review(c,user['id'],case_id)
 evaluate_case(case_id,user['id'])
 return data({'evidence_id':evidence_id,'already_attached':bool(existing),'review_required':True})

@app.get('/api/v1/vault/items')
def list_vault_items(q:str|None=None,category:str|None=None,case_id:str|None=None,task_id:str|None=None,user=Depends(current_user)):
 database()
 if category and category not in VAULT_CATEGORIES:raise HTTPException(422,'无效材料分类')
 if case_id:owned('cases',case_id,user['id'])
 if task_id:owned('tasks',task_id,user['id'])
 clauses=['v.owner_id=?'];params:list[object]=[user['id']]
 if q:clauses.append('lower(v.name) LIKE ?');params.append('%'+q.casefold()+'%')
 if category:clauses.append('v.category=?');params.append(category)
 if case_id:clauses.append('EXISTS (SELECT 1 FROM vault_case_links c WHERE c.owner_id=v.owner_id AND c.vault_item_id=v.id AND c.case_id=?)');params.append(case_id)
 if task_id:clauses.append('EXISTS (SELECT 1 FROM vault_task_links t WHERE t.owner_id=v.owner_id AND t.vault_item_id=v.id AND t.task_id=?)');params.append(task_id)
 with conn() as c:rows=c.execute('SELECT v.* FROM vault_items v WHERE '+' AND '.join(clauses)+' ORDER BY v.created_at DESC,v.id',params).fetchall()
 return data([vault_item_json(row) for row in rows])

@app.post('/api/v1/vault/items')
async def create_vault_item(file:UploadFile=File(...),name:str|None=Form(default=None),category:str=Form(default='other'),case_ids:str=Form(default='[]'),task_ids:str=Form(default='[]'),consent:bool=Form(False),user=Depends(current_user)):
 if not consent:raise HTTPException(422,{'code':'CONFIRMATION_REQUIRED','message':'请先核对材料隐私并确认上传'})
 database()
 if category not in VAULT_CATEGORIES:raise HTTPException(422,'无效材料分类')
 linked_cases=parse_form_ids(case_ids,'case_ids');linked_tasks=parse_form_ids(task_ids,'task_ids');validate_vault_links(linked_cases,linked_tasks,user['id'])
 try:content=await read_upload(file)
 except DocumentError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
 item_name=(name or file.filename or '未命名材料').strip()
 if not item_name or len(item_name)>255:raise HTTPException(422,'材料名称无效')
 item_id=str(uuid.uuid4());provider=get_vault_content_provider();content_provider,content_key=provider.put(user['id'],item_id,content);now=stamp();mime=file.content_type or mimetypes.guess_type(item_name)[0] or 'application/octet-stream'
 try:
  with conn() as c:
   c.execute('INSERT INTO vault_items(id,owner_id,name,category,mime,size,content_provider,content_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(item_id,user['id'],item_name,category,mime,len(content),content_provider,content_key,now,now))
   for case_id in linked_cases:c.execute('INSERT INTO vault_case_links(owner_id,vault_item_id,case_id) VALUES(?,?,?)',(user['id'],item_id,case_id))
   for task_id in linked_tasks:c.execute('INSERT INTO vault_task_links(owner_id,vault_item_id,task_id) VALUES(?,?,?)',(user['id'],item_id,task_id))
 except Exception:
  provider.delete(user['id'],content_provider,content_key);raise
 return data(vault_item_json(owned('vault_items',item_id,user['id'])))

@app.get('/api/v1/vault/items/{item_id}')
def get_vault_item(item_id:str,user=Depends(current_user)):
 return data(vault_item_json(owned('vault_items',item_id,user['id'])))

@app.patch('/api/v1/vault/items/{item_id}')
def patch_vault_item(item_id:str,body:VaultPatch,user=Depends(current_user)):
 current=owned('vault_items',item_id,user['id']);fields=body.model_fields_set
 if not fields:raise HTTPException(422,'至少提供一个材料字段')
 category=body.category if 'category' in fields else current['category']
 if category not in VAULT_CATEGORIES:raise HTTPException(422,'无效材料分类')
 with conn() as c:
  current_cases=[row['case_id'] for row in c.execute('SELECT case_id FROM vault_case_links WHERE owner_id=? AND vault_item_id=?',(user['id'],item_id)).fetchall()]
  current_tasks=[row['task_id'] for row in c.execute('SELECT task_id FROM vault_task_links WHERE owner_id=? AND vault_item_id=?',(user['id'],item_id)).fetchall()]
 linked_cases=body.case_ids if body.case_ids is not None else current_cases;linked_tasks=body.task_ids if body.task_ids is not None else current_tasks;validate_vault_links(linked_cases,linked_tasks,user['id']);item_name=body.name if 'name' in fields else current['name']
 if item_name is None:raise HTTPException(422,'name 不能为 null')
 with conn() as c:
  c.execute('UPDATE vault_items SET name=?,category=?,updated_at=? WHERE id=? AND owner_id=?',(item_name,category,stamp(),item_id,user['id']))
  c.execute('DELETE FROM vault_case_links WHERE owner_id=? AND vault_item_id=?',(user['id'],item_id));c.execute('DELETE FROM vault_task_links WHERE owner_id=? AND vault_item_id=?',(user['id'],item_id))
  for case_id in linked_cases:c.execute('INSERT INTO vault_case_links(owner_id,vault_item_id,case_id) VALUES(?,?,?)',(user['id'],item_id,case_id))
  for task_id in linked_tasks:c.execute('INSERT INTO vault_task_links(owner_id,vault_item_id,task_id) VALUES(?,?,?)',(user['id'],item_id,task_id))
 return data(vault_item_json(owned('vault_items',item_id,user['id'])))

@app.delete('/api/v1/vault/items/{item_id}')
def delete_vault_item(item_id:str,user=Depends(current_user)):
 item=owned('vault_items',item_id,user['id']);get_vault_content_provider().delete(user['id'],item['content_provider'],item['content_key'])
 with conn() as c:
  c.execute('DELETE FROM vault_case_links WHERE owner_id=? AND vault_item_id=?',(user['id'],item_id));c.execute('DELETE FROM vault_task_links WHERE owner_id=? AND vault_item_id=?',(user['id'],item_id));c.execute('DELETE FROM vault_items WHERE id=? AND owner_id=?',(item_id,user['id']))
 return data({'id':item_id,'deleted':True})

@app.get('/api/v1/vault/items/{item_id}/content')
def get_vault_content(item_id:str,user=Depends(current_user)):
 item=owned('vault_items',item_id,user['id'])
 try:content=get_vault_content_provider().read(user['id'],item['content_provider'],item['content_key'])
 except FileNotFoundError:raise HTTPException(404,'材料内容不存在')
 filename=quote(item['name'],safe='')
 return Response(content=content,media_type=item['mime'],headers={'Content-Disposition':f"inline; filename*=UTF-8''{filename}",'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

@app.post('/api/v1/cases')
def create_case(body:CaseIn,user=Depends(current_user)):
 body.deadline=normalize_deadline(body.deadline)
 if body.category not in CASE_CATEGORIES:raise HTTPException(422,'无效事项分类')
 if body.status not in CASE_STATUSES:raise HTTPException(422,'无效事项状态')
 if body.deadline and not parse_date(body.deadline):raise HTTPException(422,'deadline 必须是 ISO 日期或带时区时间')
 database(); cid=str(uuid.uuid4())
 now=stamp()
 with conn() as c:
  c.execute('INSERT INTO cases(id,owner_id,title,category,status,relevance,deadline,created_at,updated_at,deadline_source,deadline_evidence_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,user['id'],body.title,body.category,body.status,'UNKNOWN',body.deadline,now,now,'user_input' if body.deadline else None,'[]'))
  if body.deadline:
   ref='block:'+str(uuid.uuid4());c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,user['id'],cid,'用户填写',f'用户填写截止时间为 {body.deadline}','用户填写记录，不代表官方文件',None,now))
   c.execute('UPDATE cases SET deadline_evidence_ids_json=? WHERE id=? AND owner_id=?',(json.dumps([ref]),cid,user['id']))
 return data(case_json(owned('cases',cid,user['id'])))
@app.get('/api/v1/cases')
def cases(q:str|None=None,status:str|None=None,category:str|None=None,deadline_from:str|None=None,deadline_to:str|None=None,sort:str='updated_at_desc',limit:int=Query(default=20,ge=1,le=100),cursor:str|None=None,user=Depends(current_user)):
 if status and status not in CASE_STATUSES:raise HTTPException(422,'无效事项状态')
 if category and category not in CASE_CATEGORIES:raise HTTPException(422,'无效事项分类')
 allowed_sorts={'updated_at_desc','updated_at_asc','deadline_asc','deadline_desc','title_asc','title_desc'}
 if sort not in allowed_sorts:raise HTTPException(422,'无效排序方式')
 start_date=parse_date(deadline_from) if deadline_from else None;end_date=parse_date(deadline_to) if deadline_to else None
 if deadline_from and not start_date:raise HTTPException(422,'deadline_from 必须是 ISO 日期')
 if deadline_to and not end_date:raise HTTPException(422,'deadline_to 必须是 ISO 日期')
 if start_date and end_date and start_date>end_date:raise HTTPException(422,'deadline_from 不能晚于 deadline_to')
 with conn() as c: rows=c.execute("SELECT * FROM cases WHERE owner_id=? AND status!='deleted' ORDER BY updated_at DESC",(user['id'],)).fetchall()
 with conn() as c:counts={r['case_id']:(r['task_count'],r['done_task_count']) for r in c.execute("SELECT case_id,COUNT(*) task_count,SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done_task_count FROM tasks WHERE owner_id=? GROUP BY case_id",(user['id'],)).fetchall()}
 items=[]
 for row in rows:
  item=case_json(row)
  if q and q.casefold() not in item['title'].casefold():continue
  if status and item['status']!=status:continue
  if category and item['category']!=category:continue
  item_date=parse_date(item.get('deadline'))
  if start_date and (not item_date or item_date<start_date):continue
  if end_date and (not item_date or item_date>end_date):continue
  outcome=evaluate_case(row['id'],user['id'],persist=False);item['relevance']=outcome['relevance'];item['relevance_reason']=outcome['reason']
  total,done=counts.get(row['id'],(0,0));item['task_count']=total;item['done_task_count']=done;item['progress']=round(done*100/total) if total else 0
  items.append(item)
 if sort.startswith('updated_at_'):items.sort(key=lambda x:(x['updated_at'],x['id']),reverse=sort.endswith('desc'))
 elif sort=='deadline_asc':items.sort(key=lambda x:(parse_date(x.get('deadline')) is None,parse_date(x.get('deadline')) or date.max,x['id']))
 elif sort=='deadline_desc':items.sort(key=lambda x:(parse_date(x.get('deadline')) is None,-(parse_date(x.get('deadline')).toordinal() if parse_date(x.get('deadline')) else 0),x['id']))
 else:items.sort(key=lambda x:(x['title'].casefold(),x['id']),reverse=sort.endswith('desc'))
 offset=decode_cursor(cursor,sort);page=items[offset:offset+limit];next_cursor=encode_cursor(offset+limit,sort) if offset+limit<len(items) else None
 return data(page,{'pagination':{'limit':limit,'next_cursor':next_cursor}})
@app.get('/api/v1/cases/{case_id}')
def get_case(case_id:str,user=Depends(current_user)):
 row=owned('cases',case_id,user['id']);outcome=evaluate_case(case_id,user['id'],persist=False);item=case_json(row);item['relevance']=outcome['relevance']
 item.update({key:outcome[key] for key in ('eligibility_truth','relevance_level','interest_match','interest_evidence_ids')})
 item['relevance_reason']=outcome['reason'];item['missing_profile_fields']=outcome['missing_profile_fields'];item['missing_case_fields']=outcome['missing_case_fields']
 with conn() as c:counts=c.execute("SELECT COUNT(*) task_count,SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done_task_count FROM tasks WHERE owner_id=? AND case_id=?",(user['id'],case_id)).fetchone()
 total=counts['task_count'];done=counts['done_task_count'] or 0;item.update({'task_count':total,'done_task_count':done,'progress':round(done*100/total) if total else 0})
 return data(item)
@app.patch('/api/v1/cases/{case_id}')
def patch_case(case_id:str,body:CasePatch,user=Depends(current_user)):
 if 'deadline' in body.model_fields_set:body.deadline=normalize_deadline(body.deadline)
 owned('cases',case_id,user['id']);fields=body.model_fields_set
 if not fields:raise HTTPException(422,'至少提供一个可修改字段')
 if 'title' in fields and body.title is None:raise HTTPException(422,'title 不能为 null')
 if 'category' in fields and body.category not in CASE_CATEGORIES:raise HTTPException(422,'无效事项分类')
 if 'status' in fields and body.status not in CASE_STATUSES:raise HTTPException(422,'无效事项状态')
 if 'deadline' in fields and body.deadline and not parse_date(body.deadline):raise HTTPException(422,'deadline 必须是 ISO 日期或带时区时间')
 assignments=[];values=[]
 for field in ('title','category','status'):
  if field in fields:assignments.append(field+'=?');values.append(getattr(body,field))
 if 'deadline' in fields:
  assignments+=['deadline=?','deadline_source=?','deadline_evidence_ids_json=?'];values += [body.deadline,'user_input' if body.deadline else None,'[]']
 assignments.append('updated_at=?');values.append(stamp());values += [case_id,user['id']]
 with conn() as c:
  c.execute(f"UPDATE cases SET {','.join(assignments)} WHERE id=? AND owner_id=?",values)
  if 'deadline' in fields:
   if body.deadline:
    eid='block:'+str(uuid.uuid4())
    c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(eid,user['id'],case_id,'用户填写',f'用户填写截止时间为 {body.deadline}','用户填写记录，不代表官方文件',None,stamp()))
    c.execute('UPDATE cases SET deadline_evidence_ids_json=? WHERE id=? AND owner_id=?',(json.dumps([eid]),case_id,user['id']))
   invalidate_review(c,user['id'],case_id)
 return get_case(case_id,user)

@app.get('/api/v1/cases/{case_id}/reviews')
def get_reviews(case_id:str,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 with conn() as c:review=read_review(c,user['id'],case_id)
 return data(review)

@app.post('/api/v1/cases/{case_id}/attachments')
async def upload_case_attachment(case_id:str,file:UploadFile=File(...),consent:bool=Form(False),user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 if not consent:raise HTTPException(422,'补充附件必须明确确认上传')
 try:
  raw=await read_upload(file);mime=file.content_type or mimetypes.guess_type(file.filename or '')[0] or ''
  if mime not in ALLOWED:raise HTTPException(415,'不支持的附件格式')
  with conn() as c:
   document=store_document(c,document_root(),user['id'],raw,mime,file.filename or '用户补充附件',parse_bytes)
   ref='block:'+str(uuid.uuid4())
   c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,user['id'],case_id,'用户补充附件记录',f'用户上传 {file.filename or "附件"}，处理状态：{document["status"]}','文件上传记录，不代表附件内容已核对',None,stamp()))
   c.execute('INSERT INTO case_attachment_documents VALUES(?,?,?,?)',(user['id'],case_id,document['id'],ref))
   if document['status']=='parsed':bind_document(c,user['id'],case_id,document['id'],file.filename or '用户补充附件')
   invalidate_review(c,user['id'],case_id)
 except DocumentError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
 return data({'document_id':document['id'],'status':document['status'],'error_code':document['error_code'],'requires_reanalysis':True,'warning':'附件需核对；旧确认已失效，请重新分析再确认任务'})

@app.post('/api/v1/cases/{case_id}/analysis/retry')
def retry_case_analysis(case_id:str,body:DraftCommitIn,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 if not body.consent:raise HTTPException(422,'请确认使用已上传证据和附件重新分析')
 with conn() as c:
  evidence=[(row['id'],row['text']) for row in c.execute('SELECT id,text FROM evidence WHERE owner_id=? AND case_id=? AND source_name<>?',(user['id'],case_id,'用户补充附件记录'))]
 if not evidence:raise HTTPException(422,'没有可重用的通知证据')
 return data(analyze_case(case_id,user['id'],evidence))

@app.post('/api/v1/cases/{case_id}/confirm')
def confirm_analysis(case_id:str,body:ReviewConfirmation,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 if not body.consent:raise HTTPException(422,{'code':'CONFIRMATION_REQUIRED','message':'请明确确认所选日期与行动步骤；资格未知仍保持待核对'})
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  try:review=confirm_review(c,user['id'],case_id,body.revision,body.action_ids,body.deadline_id,body.manual_deadline,body.no_deadline,body.task_deadlines)
  except ReviewError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
 return data(review)

@app.post('/api/v1/cases/{case_id}/reviews/prepare')
def prepare_legacy_review(case_id:str,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  existing=read_review(c,user['id'],case_id)
  if existing:return data(existing)
  evidence=[(row['id'],row['text']) for row in c.execute('SELECT id,text FROM evidence WHERE owner_id=? AND case_id=?',(user['id'],case_id))]
  tasks=c.execute('SELECT * FROM tasks WHERE owner_id=? AND case_id=? ORDER BY created_at,id',(user['id'],case_id)).fetchall()
  actions=[{'id':'legacy:'+task['id'],'existing_task_id':task['id'],'title':task['title'],'deadline':None,'proposed_deadline':task['deadline'],'duration_minutes':task['duration_minutes'],'evidence_ids':json.loads(task['evidence_ids_json']),'evidence_quotes':{}} for task in tasks]
  save_review(c,user['id'],case_id,{'actions':actions,'dates':extract_dates(evidence),'analysis_mode':'legacy_review','schema_version':'review-1','review_reasons':['历史步骤需要重新核对证据，保留原任务ID和完成状态']})
  result=read_review(c,user['id'],case_id)
 return data(result)
@app.get('/api/v1/cases/{case_id}/resources')
def case_resources(case_id:str,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 with conn() as c:
  evidence=[dict(x) for x in c.execute('SELECT * FROM evidence WHERE owner_id=? AND case_id=? ORDER BY created_at',(user['id'],case_id))]
  rules=[dict(x) for x in c.execute('SELECT * FROM rules WHERE owner_id=? AND case_id=? ORDER BY created_at',(user['id'],case_id))]
  tasks=[dict(x) for x in c.execute('SELECT * FROM tasks WHERE owner_id=? AND case_id=? ORDER BY created_at',(user['id'],case_id))]
  edges=dependency_dtos(c,user['id'],case_id)
  materials=[dict(x) for x in c.execute('SELECT * FROM materials WHERE owner_id=? AND case_id=? ORDER BY created_at',(user['id'],case_id))]
  conflicts=[dict(x) for x in c.execute('SELECT * FROM conflicts WHERE owner_id=? AND case_id=? ORDER BY id',(user['id'],case_id))]
  analysis_row=c.execute('SELECT * FROM analysis_metadata WHERE owner_id=? AND case_id=? ORDER BY created_at DESC LIMIT 1',(user['id'],case_id)).fetchone()
  for item in evidence:
   line=c.execute('SELECT l.*,d.mime FROM evidence_lines e JOIN document_lines l ON l.id=e.line_id AND l.owner_id=e.owner_id JOIN documents d ON d.id=e.document_id AND d.owner_id=e.owner_id WHERE e.evidence_id=? AND e.owner_id=?',(item['id'],user['id'])).fetchone()
   if line:item.update(document_id=line['document_id'],line_id=line['id'],bbox=json.loads(line['bbox_json'] or 'null'),coordinate_space=line['coordinate_space'],page_width=line['page_width'],page_height=line['page_height'],ocr_confidence=line['confidence'],preview_available=line['mime'] in {'application/pdf','image/png','image/jpeg'})
   else:
    source=c.execute('SELECT s.document_id,d.mime FROM knowledge_evidence_sources s JOIN documents d ON d.id=s.document_id AND d.owner_id=s.owner_id WHERE s.evidence_id=? AND s.owner_id=?',(item['id'],user['id'])).fetchone()
    if source:item.update(document_id=source['document_id'],bbox=None,preview_available=source['mime'] in {'application/pdf','image/png','image/jpeg'})
 facts=effective_fact_items(user['id'],case_id);evaluation=evaluate_case(case_id,user['id'],persist=False)
 semantic_kinds={r['id']:r['kind'] for r in evaluation['rules']}
 for x in rules:x['ast']=json.loads(x.pop('ast_json'));x['evidence_ids']=json.loads(x.pop('evidence_ids_json'));x['kind']=semantic_kinds.get(x['id'],'eligibility')
 for x in materials:x['evidence_ids']=json.loads(x.pop('evidence_ids_json'))
 tasks=task_dtos(tasks,edges,user['id'],case_id)
 analysis=None
 if analysis_row:
  analysis=dict(analysis_row)
  analysis['questions']=json.loads(analysis.pop('questions_json'))
  analysis['review_reasons']=json.loads(analysis.pop('review_reasons_json'))
  legacy_question='请在个人画像中补充规则所需字段；缺少字段会保持 UNKNOWN。'
  analysis['questions']=[question for question in analysis['questions'] if question!=legacy_question or evaluation['reason']=='missing_profile_fact']
 with conn() as c:file_rows=c.execute('SELECT v.* FROM vault_case_links l JOIN vault_items v ON v.id=l.vault_item_id AND v.owner_id=l.owner_id WHERE l.owner_id=? AND l.case_id=? ORDER BY v.created_at',(user['id'],case_id)).fetchall()
 files=[vault_item_json(row) for row in file_rows]
 with conn() as c:
  documents=[dict(row) for row in c.execute('SELECT DISTINCT d.* FROM evidence_lines e JOIN documents d ON d.id=e.document_id AND d.owner_id=e.owner_id JOIN evidence v ON v.id=e.evidence_id AND v.owner_id=e.owner_id WHERE e.owner_id=? AND v.case_id=?',(user['id'],case_id))]
  extra=[dict(row) for row in c.execute('SELECT d.* FROM case_attachment_documents a JOIN documents d ON d.id=a.document_id AND d.owner_id=a.owner_id WHERE a.owner_id=? AND a.case_id=?',(user['id'],case_id))]
  documents=list({d['id']:d for d in documents+extra}.values())
 with conn() as c:links=[{'url':r['url'],'title':r['title'],'evidence_ids':[r['evidence_id']],'quote':'网页附件引用：'+r['title']} for r in c.execute('SELECT * FROM case_attachment_links WHERE owner_id=? AND case_id=?',(user['id'],case_id))]
 attachment_status=attachment_inventory([e for e in evidence if e['source_name'] not in {'用户补充附件记录','网页附件链接'}],documents,links)
 return data({'facts':facts,'evidence':evidence,'rules':rules,'tasks':tasks,'materials':materials,'files':files,'conflicts':conflicts,'analysis':analysis,'evaluation':evaluation,'attachments':attachment_status})

@app.get('/api/v1/documents/{document_id}')
def get_document(document_id:str,user=Depends(current_user)):
 document=dict(owned('documents',document_id,user['id']));document.pop('owner_id')
 with conn() as c:rows=c.execute('SELECT * FROM document_lines WHERE document_id=? AND owner_id=? ORDER BY line_number',(document_id,user['id'])).fetchall()
 lines=[]
 for row in rows:
  line=dict(row);line.pop('owner_id');line['bbox']=json.loads(line.pop('bbox_json') or 'null');lines.append(line)
 return data({**document,'lines':lines})

@app.get('/api/v1/documents/{document_id}/content')
def get_document_content(document_id:str,user=Depends(current_user)):
 document=owned('documents',document_id,user['id'])
 try:raw=content_path(document_root(),user['id'],document_id).read_bytes()
 except FileNotFoundError:raise HTTPException(404,{'code':'DOCUMENT_CONTENT_MISSING','message':'原件不可用'})
 return Response(content=raw,media_type=document['mime'],headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Disposition':'attachment'})

@app.delete('/api/v1/documents/{document_id}')
def delete_unbound_document(document_id:str,user=Depends(current_user)):
 owned('documents',document_id,user['id'])
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  bound=c.execute('SELECT 1 FROM evidence_lines WHERE document_id=? UNION ALL SELECT 1 FROM source_documents WHERE document_id=? UNION ALL SELECT 1 FROM knowledge_documents WHERE document_id=? UNION ALL SELECT 1 FROM knowledge_evidence_sources WHERE document_id=? UNION ALL SELECT 1 FROM case_attachment_documents WHERE document_id=?',(document_id,document_id,document_id,document_id,document_id)).fetchone()
  if bound:raise HTTPException(409,{'code':'DOCUMENT_IN_USE','message':'原件仍关联来源或证据，请先解除来源；已作为事项证据的原件不能单独删除'})
  target=content_path(document_root(),user['id'],document_id)
  try:target.unlink(missing_ok=True)
  except OSError:raise HTTPException(503,{'code':'DOCUMENT_DELETE_FAILED','message':'原件删除失败，已保留记录，请重试'})
  c.execute('DELETE FROM document_lines WHERE document_id=? AND owner_id=?',(document_id,user['id']))
  c.execute('DELETE FROM document_privacy_findings WHERE document_id=? AND owner_id=?',(document_id,user['id']))
  for derivative in c.execute('SELECT id FROM document_derivatives WHERE document_id=? AND owner_id=?',(document_id,user['id'])).fetchall():content_path(document_root(),user['id'],derivative['id']).unlink(missing_ok=True)
  c.execute('DELETE FROM document_derivatives WHERE document_id=? AND owner_id=?',(document_id,user['id']))
  c.execute('DELETE FROM documents WHERE id=? AND owner_id=?',(document_id,user['id']))
 return data({'id':document_id,'deleted':True})

@app.post('/api/v1/documents/{document_id}/privacy/scan')
def scan_document_privacy(document_id:str,user=Depends(current_user)):
 owned('documents',document_id,user['id'])
 with conn() as c:return data(scan_document(c,user['id'],document_id))

@app.post('/api/v1/documents/{document_id}/redact')
def redact_document(document_id:str,body:RedactIn,user=Depends(current_user)):
 owned('documents',document_id,user['id'])
 if not body.consent:raise HTTPException(422,{'code':'CONFIRMATION_REQUIRED','message':'请确认所选敏感区域并同意生成副本'})
 try:
  with conn() as c:result=redact_copy(c,document_root(),user['id'],document_id,body.finding_ids,body.revision)
 except DocumentError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
 return data(result)

@app.get('/api/v1/document-copies/{copy_id}/content')
def get_redacted_copy(copy_id:str,user=Depends(current_user)):
 derivative=owned('document_derivatives',copy_id,user['id'])
 try:content=content_path(document_root(),user['id'],copy_id).read_bytes()
 except FileNotFoundError:raise HTTPException(404,'脱敏副本不可用')
 return Response(content=content,media_type=derivative['mime'],headers={'Cache-Control':'no-store','Content-Disposition':'attachment','X-Content-Type-Options':'nosniff'})

@app.get('/api/v1/documents/{document_id}/pages/{page}')
def get_document_page(document_id:str,page:int,user=Depends(current_user)):
 document=owned('documents',document_id,user['id'])
 try:
  raw=content_path(document_root(),user['id'],document_id).read_bytes()
  image=document_preview(raw,document['mime'],page)
 except FileNotFoundError:raise HTTPException(404,{'code':'DOCUMENT_CONTENT_MISSING','message':'原件不可用'})
 except DocumentError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
 return Response(content=image,media_type='image/png',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
@app.put('/api/v1/cases/{case_id}/facts')
def fact(case_id:str,body:FactIn,user=Depends(current_user)):
 owned('cases',case_id,user['id']); fid=str(uuid.uuid4())
 try:validated=validate_facts({body.key.removeprefix('profile.'):body.value})
 except ProfileError as exc:raise HTTPException(422,{'code':'PROFILE_INVALID','message':str(exc),'fields':exc.fields})
 if body.scope!='case':raise HTTPException(422,{'code':'FACT_SCOPE_INVALID','message':'事项事实只能保存到当前事项'})
 value=validated[body.key.removeprefix('profile.')]
 try:valid_until=normalize_validity(body.valid_until)
 except ValueError as exc:raise HTTPException(422,str(exc))
 with conn() as c:
  c.execute('INSERT INTO facts VALUES(?,?,?,?,?,?,?)',(fid,user['id'],case_id,body.key,json.dumps(value,ensure_ascii=False),'user_input',stamp()))
  record_fact(c,fid,user['id'],case_id,body.key,value,valid_until)
  c.execute('INSERT INTO profile_versions VALUES(?,1,?) ON CONFLICT(owner_id) DO UPDATE SET revision=revision+1,updated_at=excluded.updated_at',(user['id'],stamp()))
 evaluate_case(case_id,user['id'])
 return data({'id':fid,'key':body.key})
def evaluate_case(case_id:str,owner_id:str,persist=True):
 with conn() as c:
  rows=c.execute('SELECT * FROM rules WHERE owner_id=? AND case_id=?',(owner_id,case_id)).fetchall()
 facts=profile_values(owner_id,case_id)
 with conn() as c:
  kinds={row['rule_id']:row['kind'] for row in c.execute('SELECT * FROM rule_semantics WHERE owner_id=?',(owner_id,))}
  version=c.execute('SELECT revision FROM profile_versions WHERE owner_id=?',(owner_id,)).fetchone()
 rules=[{'id':r['id'],'label':r['label'],'ast':json.loads(r['ast_json']),'evidence_ids':json.loads(r['evidence_ids_json']),'kind':kinds.get(r['id'],'eligibility')} for r in rows]
 outcome=evaluate_rules(rules,facts);relevance=outcome['relevance']
 with conn() as c:review=c.execute('SELECT candidate_json FROM case_reviews WHERE owner_id=? AND case_id=?',(owner_id,case_id)).fetchone()
 unsupported=json.loads(review['candidate_json']).get('analysis',{}).get('unsupported_conditions',[]) if review else []
 if unsupported and relevance=='TRUE':
  relevance='UNKNOWN';outcome.update(relevance='UNKNOWN',eligibility_truth='UNKNOWN',reason='unmodeled_conditions',missing_case_fields=['unmodeled_conditions'])
 outcome['unsupported_conditions']=unsupported
 with conn() as c:
  if persist:bind_interest(c,owner_id,case_id)
  interest=soft_relevance(c,owner_id,case_id,relevance)
 if persist:
  with conn() as c:c.execute('UPDATE cases SET relevance=?,updated_at=? WHERE id=? AND owner_id=? AND relevance<>?',(relevance,stamp(),case_id,owner_id,relevance))
 return {**outcome,**interest,'profile_revision':version['revision'] if version else 0}
@app.get('/api/v1/cases/{case_id}/evaluate')
def reevaluate(case_id:str,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 return data(evaluate_case(case_id,user['id'],persist=False))
@app.post('/api/v1/cases/{case_id}/tasks')
def create_task(case_id:str,body:TaskIn,user=Depends(current_user)):
 body.deadline=normalize_deadline(body.deadline)
 owned('cases',case_id,user['id']); tid=str(uuid.uuid4())
 if not body.evidence_ids: raise HTTPException(422,'任务必须关联 EvidenceRef；没有证据请先标记待核对')
 validate_evidence_refs(body.evidence_ids,user['id'],case_id)
 check_review(user['id'],case_id)
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  try:require_confirmed(c,user['id'],case_id)
  except ReviewError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
  refs=list(body.evidence_ids)
  if body.deadline or body.duration_minutes:
   ref='block:'+str(uuid.uuid4());refs.append(ref)
   c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,user['id'],case_id,'用户填写任务安排',f'用户填写步骤截止={body.deadline or "未设置"}；估计耗时={body.duration_minutes or "未填写"}分钟','用户填写，不代表官方通知',None,stamp()))
  c.execute('INSERT INTO tasks(id,owner_id,case_id,title,status,deadline,evidence_ids_json,created_at,updated_at,duration_minutes) VALUES(?,?,?,?,?,?,?,?,?,?)',(tid,user['id'],case_id,body.title,'todo',body.deadline,json.dumps(refs),stamp(),stamp(),body.duration_minutes))
 with conn() as c:rows=c.execute('SELECT * FROM tasks WHERE owner_id=? AND case_id=?',(user['id'],case_id)).fetchall();edges=c.execute('SELECT before_task_id,after_task_id FROM task_edges WHERE owner_id=? AND case_id=?',(user['id'],case_id)).fetchall()
 return data(next(x for x in task_dtos(rows,edges,user['id'],case_id) if x['id']==tid))
@app.patch('/api/v1/tasks/{task_id}')
def patch_task(task_id:str,body:PatchTask,user=Depends(current_user)):
 if body.status not in {'todo','in_progress','done','skipped'}:raise HTTPException(422,'无效任务状态')
 owned('tasks',task_id,user['id'])
 check_review(user['id'],owned('tasks',task_id,user['id'])['case_id'])
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  try:require_confirmed(c,user['id'],owned_task_case:=c.execute('SELECT case_id FROM tasks WHERE id=? AND owner_id=?',(task_id,user['id'])).fetchone()['case_id'])
  except ReviewError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
  c.execute('UPDATE tasks SET status=?,updated_at=? WHERE id=? AND owner_id=?',(body.status,stamp(),task_id,user['id']))
 task=owned('tasks',task_id,user['id']);case_id=task['case_id']
 with conn() as c:rows=c.execute('SELECT * FROM tasks WHERE owner_id=? AND case_id=?',(user['id'],case_id)).fetchall();edges=c.execute('SELECT before_task_id,after_task_id FROM task_edges WHERE owner_id=? AND case_id=?',(user['id'],case_id)).fetchall()
 return data(next(x for x in task_dtos(rows,edges,user['id'],case_id) if x['id']==task_id))
@app.post('/api/v1/cases/{case_id}/materials')
def material(case_id:str,body:MaterialIn,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 if not body.evidence_ids:raise HTTPException(422,'材料必须关联 EvidenceRef')
 validate_evidence_refs(body.evidence_ids,user['id'],case_id)
 mid=str(uuid.uuid4())
 with conn() as c:c.execute('INSERT INTO materials VALUES(?,?,?,?,?,?,?)',(mid,user['id'],case_id,body.title,'missing',json.dumps(body.evidence_ids),stamp()))
 return data(dict(owned('materials',mid,user['id'])))
@app.post('/api/v1/cases/{case_id}/edges')
def edge(case_id:str,body:EdgeIn,user=Depends(current_user)):
 check_review(user['id'],case_id)
 owned('cases',case_id,user['id']); before=owned('tasks',body.before_task_id,user['id']); after=owned('tasks',body.after_task_id,user['id'])
 if before['case_id']!=case_id or after['case_id']!=case_id:raise HTTPException(422,'依赖任务必须属于当前事项')
 if body.before_task_id==body.after_task_id:raise HTTPException(422,'任务不能依赖自身')
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  rows=c.execute('SELECT before_task_id,after_task_id FROM task_edges WHERE owner_id=? AND case_id=?',(user['id'],case_id)).fetchall(); graph={}
  for r in rows:graph.setdefault(r['before_task_id'],[]).append(r['after_task_id'])
  graph.setdefault(body.before_task_id,[]).append(body.after_task_id)
  def reaches(a,target,seen=None):
   seen=seen or set()
   return a==target or any(reaches(x,target,seen|{a}) for x in graph.get(a,[]) if x not in seen)
  if reaches(body.after_task_id,body.before_task_id):raise HTTPException(422,'依赖图存在环')
  existing=c.execute('SELECT id FROM task_edges WHERE owner_id=? AND case_id=? AND before_task_id=? AND after_task_id=?',(user['id'],case_id,body.before_task_id,body.after_task_id)).fetchone()
  if existing:return data({'id':existing['id'],'idempotent':True})
  eid=str(uuid.uuid4());c.execute('INSERT INTO task_edges VALUES(?,?,?,?,?)',(eid,user['id'],case_id,body.before_task_id,body.after_task_id))
  ref='block:'+str(uuid.uuid4());c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,user['id'],case_id,'用户填写依赖',f'用户确认步骤“{before["title"]}”先于“{after["title"]}”','用户填写，不代表原文要求',None,stamp()))
  c.execute('INSERT INTO task_edge_evidence VALUES(?,?,?,?)',(eid,user['id'],json.dumps([ref]),'user_input'))
  for item in c.execute('SELECT * FROM schedule_items WHERE owner_id=? AND task_id=?',(user['id'],body.after_task_id)).fetchall():validate_schedule_write(c,user['id'],case_id,body.after_task_id,item['starts_at'],item['ends_at'],item['id'])
 return data({'id':eid})
@app.get('/api/v1/cases/{case_id}/plan')
def plan(case_id:str,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 with conn() as c:
  tasks=[dict(x) for x in c.execute('SELECT * FROM tasks WHERE owner_id=? AND case_id=?',(user['id'],case_id))];edges=dependency_dtos(c,user['id'],case_id)
 indeg={x['id']:0 for x in tasks};nexts={x['id']:[] for x in tasks}
 for e in edges:indeg[e['after_task_id']]+=1;nexts[e['before_task_id']].append(e['after_task_id'])
 order=[];ready=[x for x in indeg if indeg[x]==0]
 while ready:
  x=ready.pop(0);order.append(x)
  for y in nexts[x]:indeg[y]-=1;ready+= [y] if indeg[y]==0 else []
 if len(order)!=len(tasks):raise HTTPException(409,'依赖图损坏')
 enriched=task_dtos(tasks,edges,user['id'],case_id);by={x['id']:x for x in enriched};ordered=[by[x] for x in order]
 completed=sum(1 for x in ordered if x['status']=='done');pending=sum(1 for x in ordered if x['status'] in {'todo','in_progress'});total=len(ordered)
 return data({'ordered_tasks':ordered,'edges':edges,'overall_progress':round(completed*100/total) if total else 0,'current_tasks':[x for x in ordered if x['is_actionable']],'completed_tasks':completed,'pending_tasks':pending})
@app.get('/api/v1/cases/{case_id}/export.txt')
def export_txt(case_id:str,user=Depends(current_user)):
 c=owned('cases',case_id,user['id']); p=plan(case_id,user)['data']; lines=[c['title'],'执行计划']+[f"- {x['title']}：{x['status']}，截止 {x['deadline'] or '待核对'}" for x in p['ordered_tasks']]
 return {'content':'\n'.join(lines),'content_type':'text/plain; charset=utf-8'}
def title_from(text):
 first=next((x.strip() for x in text.splitlines() if x.strip()),'导入通知')
 return first[:120]
def category_from(text):
 lower=text.lower(); pairs=[('award',['奖学金','助学金','评优']),('competition',['竞赛','比赛']),('exam',['考试','准考证','报名']),('research',['科研','申报','导师']),('career',['实习','招聘','面试']),('academic',['选课','综测','转专业'])]
 return next((k for k,words in pairs if any(w in lower for w in words)),'other')
def get_llm_provider():
 return configured_provider()

def _local_candidates(evidence_rows:list[tuple[str,str]]):
 """Conservative extraction retained as the offline and failure-safe path."""
 combined='\n'.join(text for _,text in evidence_rows);all_evidence=[eid for eid,_ in evidence_rows]
 extracted_rules=extract_rules(evidence_rows)
 names=[name for name in ('身份证','成绩单','申请表','证明材料','个人简历','推荐信') if name in combined]
 return {
  'title':title_from(combined),
  'category':category_from(combined),
  'summary':'已完成本地文本规则抽取；更复杂的语义关系和例外条款仍需人工核对。',
  'rules':extracted_rules,
  'materials':[{'title':name,'state':'missing','evidence_ids':all_evidence,'evidence_quotes':{}} for name in names],
  'tasks':extract_actions(evidence_rows),
  'questions':[] if extracted_rules else ['现有通知信息不足，需要核对原文中的适用条件。'],
  'review_reasons':['当前未调用 AI 模型，仅使用本地规则抽取。'],
  'unsupported_conditions':extract_unsupported(evidence_rows),
 }

def _persist_analysis(owner_id:str,case_id:str,mode:str,model_id:str,input_hash:str,candidate:dict,review_reasons:list[str],job_id=None):
 now=stamp();metadata_id=str(uuid.uuid4())
 evidence_ids=[eid for eid,_ in candidate['_evidence_rows']]
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if job_id:
   job=c.execute('SELECT state FROM analysis_jobs WHERE id=? AND owner_id=?',(job_id,owner_id)).fetchone()
   if not job or job['state']=='cancelled':raise ReviewError('JOB_CANCELLED','分析已取消')
  for item in candidate.get('rules',[]):
   refs=sorted(set(item['evidence_ids']))
   ast={**item['ast'],'evidence':sorted(set(item['ast'].get('evidence',[])) or set(refs))}
   rule_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'rule:{owner_id}:{case_id}:'+json.dumps([item['label'],ast,refs,item.get('kind','eligibility')],sort_keys=True,ensure_ascii=False)))
   c.execute('INSERT OR IGNORE INTO rules VALUES(?,?,?,?,?,?,?)',(rule_id,owner_id,case_id,item['label'],json.dumps(ast,ensure_ascii=False),json.dumps(refs),now))
   c.execute('INSERT OR IGNORE INTO rule_semantics VALUES(?,?,?)',(rule_id,owner_id,item.get('kind','eligibility')))
  existing_tasks=c.execute('SELECT * FROM tasks WHERE owner_id=? AND case_id=?',(owner_id,case_id)).fetchall()
  actions=[];reused=set()
  for item in candidate.get('tasks',[]):
   action_id='action:'+hashlib.sha256(json.dumps([item['title'],sorted(item['evidence_ids']),item.get('origin','document')],ensure_ascii=False).encode()).hexdigest()[:24]
   action={**item,'id':action_id,'proposed_deadline':item.get('deadline'),'deadline':None}
   matches=[task for task in existing_tasks if task['title']==item['title'] and task['id'] not in reused]
   if len(matches)==1:action['existing_task_id']=matches[0]['id'];reused.add(matches[0]['id'])
   actions.append(action)
  for task in existing_tasks:
   if task['id'] not in reused:
    actions.append({'id':'previous:'+task['id'],'existing_task_id':task['id'],'title':task['title'],'origin':'previous','deadline':None,'duration_minutes':task['duration_minutes'],'evidence_ids':json.loads(task['evidence_ids_json']),'evidence_quotes':{}})
  version=c.execute('SELECT revision FROM profile_versions WHERE owner_id=?',(owner_id,)).fetchone()
  snapshot={key:value for key,value in candidate.items() if not key.startswith('_')}
  save_review(c,owner_id,case_id,{'actions':actions,'dependencies':extract_dependencies(actions,candidate['_evidence_rows']),'dates':extract_dates(candidate['_evidence_rows']),'analysis':snapshot,'profile_revision':version['revision'] if version else 0,'analysis_mode':mode,'input_hash':input_hash,'schema_version':'review-3','review_reasons':sorted(set(review_reasons+candidate.get('review_reasons',[])))})
  c.execute('INSERT INTO analysis_review_versions SELECT owner_id,case_id,revision,candidate_json,? FROM case_reviews WHERE owner_id=? AND case_id=?',(stamp(),owner_id,case_id))
  for item in candidate.get('materials',[]):
   refs=sorted(set(item['evidence_ids']))
   mid=str(uuid.uuid5(uuid.NAMESPACE_URL,f'material:{owner_id}:{case_id}:{item["title"]}'));c.execute('INSERT OR IGNORE INTO materials VALUES(?,?,?,?,?,?,?)',(mid,owner_id,case_id,item['title'],item.get('state','unknown'),json.dumps(refs),now))
  all_reviews=sorted(set(review_reasons+candidate.get('review_reasons',[])))
  c.execute('INSERT INTO analysis_metadata VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(metadata_id,owner_id,case_id,mode,model_id,PROMPT_VERSION,PARSER_VERSION,input_hash,'{}',candidate.get('summary',''),json.dumps(candidate.get('questions',[]),ensure_ascii=False),json.dumps(all_reviews,ensure_ascii=False),now))
 outcome=evaluate_case(case_id,owner_id)
 questions=list(candidate.get('questions',[]))
 legacy='请在个人画像中补充规则所需字段；缺少字段会保持 UNKNOWN。'
 if outcome['reason']!='missing_profile_fact':questions=[question for question in questions if question!=legacy]
 if outcome['reason']=='missing_profile_fact':questions.append('请补充个人画像：'+ '、'.join(field.removeprefix('profile.') for field in outcome['missing_profile_fields']))
 elif outcome['reason'] in {'missing_case_fact','insufficient_evidence'}:questions.append('现有通知信息不足，需要核对原文。')
 elif outcome['reason']=='rule_unknown':questions.append('规则条件暂时无法计算，请核对字段格式与原文。')
 questions=list(dict.fromkeys(question for question in questions if question))
 with conn() as c:c.execute('UPDATE analysis_metadata SET questions_json=? WHERE id=? AND owner_id=?',(json.dumps(questions,ensure_ascii=False),metadata_id,owner_id))
 return {'rules':len(candidate.get('rules',[])),'tasks':0,'suggested_tasks':len(actions),'review_status':'needs_confirmation','materials':len(candidate.get('materials',[])),'relevance':outcome['relevance'],'relevance_reason':outcome['reason'],'missing_profile_fields':outcome['missing_profile_fields'],'missing_case_fields':outcome['missing_case_fields'],'analysis_mode':mode,'model_id':model_id,'summary':candidate.get('summary',''),'questions':questions,'review_reasons':sorted(set(review_reasons+candidate.get('review_reasons',[])))}

def analyze_case(case_id:str,owner_id:str,evidence_rows:list[tuple[str,str]],job_id=None):
 """Use an optional LLM for candidates, while keeping final validation deterministic."""
 from .privacy import redact
 redacted={eid:redact(text)['redacted_text'] for eid,text in evidence_rows}
 input_hash=hashlib.sha256('\n'.join(f'{eid}:{redacted[eid]}' for eid,_ in evidence_rows).encode()).hexdigest()
 local=_local_candidates(evidence_rows);local['_evidence_rows']=evidence_rows
 provider=get_llm_provider();mode='local';model_id='none';review_reasons=[];candidate=local
 if provider.model_id!='none':
  try:
   ai=provider.analyze([{'id':eid,'text':redacted[eid],'locator':'证据块'} for eid,_ in evidence_rows])
   review_reasons=validate_candidates(ai,redacted)
   candidate=ai.model_dump();candidate['_evidence_rows']=evidence_rows
   candidate['unsupported_conditions'].extend(extract_unsupported(evidence_rows))
   mode='llm';model_id=provider.model_id
  except (AIUnavailable,AIInvalidOutput,ValidationError,ValueError) as exc:
   review_reasons=['AI 分析未完成（输出校验或服务调用失败），已回退本地规则抽取；请核对原文。']
   candidate=local
   mode='local_fallback'
 return _persist_analysis(owner_id,case_id,mode,model_id,input_hash,candidate,review_reasons,job_id)

def run_import_analysis(case_id,owner_id,evidence_rows,job_id):
 with conn() as c:c.execute("UPDATE analysis_jobs SET state='processing',stage='candidate_analysis',updated_at=? WHERE id=? AND owner_id=?",(stamp(),job_id,owner_id))
 try:
  result=analyze_case(case_id,owner_id,evidence_rows,job_id)
  with conn() as c:c.execute("UPDATE analysis_jobs SET state='completed',stage='review_required',updated_at=? WHERE id=? AND owner_id=? AND state<>'cancelled'",(stamp(),job_id,owner_id))
  return result
 except Exception as exc:
  state='cancelled' if isinstance(exc,ReviewError) and exc.code=='JOB_CANCELLED' else 'failed'
  with conn() as c:c.execute('UPDATE analysis_jobs SET state=?,stage=?,error=?,updated_at=? WHERE id=? AND owner_id=?',(state,'candidate_analysis',None if state=='cancelled' else 'ANALYSIS_FAILED',stamp(),job_id,owner_id))
  raise HTTPException(409 if state=='cancelled' else 502,{'code':'JOB_CANCELLED' if state=='cancelled' else 'ANALYSIS_FAILED','message':'分析已取消' if state=='cancelled' else '分析失败，原证据保留'})
def url_error(status:int,code:str,message:str):raise HTTPException(status,{'code':code,'message':message})
def validate_url_target(parsed):
 if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:url_error(422,'url_invalid','网址格式无效，仅支持公开 HTTP/HTTPS 地址')
 try:resolve_public_host(parsed.hostname,allow_proxy_synthetic=local_proxy_for(parsed.scheme))
 except HostResolutionError:url_error(502,'url_dns_failed','网址 DNS 解析失败')
 except UnsafeHostError:url_error(422,'url_unsafe_address','网址被安全策略拒绝：目标不是公网地址')
def validate_connected_peer(response,current_url:str):
 stream=response.extensions.get('network_stream');peer=None
 try:peer=stream.get_extra_info('server_addr') if stream else None
 except (AttributeError,NotImplementedError):return
 if not peer:return
 address=peer[0] if isinstance(peer,(tuple,list)) else str(peer)
 try:ip=ipaddress.ip_address(str(address).split('%',1)[0])
 except ValueError:return
 if ip.is_global:return
 scheme=urlparse(current_url).scheme
 if ip.is_loopback and local_proxy_for(scheme):return
 url_error(422,'url_unsafe_address','网址被安全策略拒绝：实际连接地址不是公网地址')
def parse_url_blocks(raw:bytes,mime:str,name:str):
 try:blocks=parse_bytes(raw,mime,name)
 except Exception as exc:url_error(422,'url_content_parse_failed','网页内容解析失败')
 if not any(str(block.get('text','')).strip() for block in blocks):url_error(422,'url_content_parse_failed','网页内容解析失败：没有可用正文')
 return blocks
def fetch_public(url:str,max_bytes:int=10*1024*1024,transport=None):
 current=url
 for _ in range(6):
  parsed=urlparse(current)
  validate_url_target(parsed)
  try:
   options={'timeout':15,'follow_redirects':False,'headers':{'User-Agent':'ZhishiRuleFlow/2.0'}}
   if transport is not None:options['transport']=transport
   with httpx.Client(**options) as client:
    with client.stream('GET',current) as response:
     validate_connected_peer(response,current)
     if response.status_code in {301,302,303,307,308}:
      location=response.headers.get('location')
      if not location:url_error(502,'url_redirect_invalid','网页重定向缺少地址')
      current=urljoin(current,location);continue
     response.raise_for_status();parts=[];size=0
     for chunk in response.iter_bytes():
      size+=len(chunk)
      if size>max_bytes:url_error(413,'url_content_too_large','网页或附件超过大小限制')
      parts.append(chunk)
     return b''.join(parts),response.headers.get('content-type','application/octet-stream').split(';')[0].lower(),current
  except HTTPException:raise
  except httpx.TimeoutException as exc:raise HTTPException(504,{'code':'url_timeout','message':'网页请求超时'}) from exc
  except httpx.HTTPStatusError as exc:raise HTTPException(502,{'code':'url_http_error','message':f'网页返回 HTTP {exc.response.status_code}'}) from exc
  except httpx.RequestError as exc:raise HTTPException(502,{'code':'url_request_failed','message':'网页连接失败'}) from exc
 url_error(508,'url_redirect_limit','网页重定向次数过多')

IMPORT_PROCESSING_DELAY=timedelta(milliseconds=350)
IMPORT_COMPLETION_DELAY=timedelta(milliseconds=1200)

def _batch_projected_state(batch):
 if not batch['started_at']:return 'draft'
 if not SETTINGS.demo_mode:return batch['state']
 now=datetime.now(timezone.utc)
 processing=parse_instant(batch['demo_processing_at']);completed=parse_instant(batch['demo_completed_at'])
 if now<processing:return 'queued'
 if now<completed:return 'processing'
 return batch['final_status'] or 'failed'

def _import_source_json(row):
 item=dict(row);item.pop('owner_id',None);item.pop('extracted_text',None);item['metadata']=json.loads(item.pop('metadata_json') or '{}');item['reason']='source_failed' if item['status']=='failed' else None
 return item

def _import_batch_json(batch):
 projected=_batch_projected_state(batch)
 with conn() as c:source_rows=c.execute('SELECT * FROM import_sources WHERE owner_id=? AND batch_id=? ORDER BY created_at,id',(batch['owner_id'],batch['id'])).fetchall()
 sources=[_import_source_json(row) for row in source_rows];successful=sum(source['status']=='completed' for source in sources);ready=sum(source['status']=='ready' for source in sources);failed=sum(source['status']=='failed' for source in sources)
 visible=projected in {'completed','partial_failure','failed'}
 return {'id':batch['id'],'title':batch['title'],'state':projected,'revision':batch['revision'],'created_at':batch['created_at'],'updated_at':batch['updated_at'],'started_at':batch['started_at'],'processing_at':batch['demo_processing_at'],'completed_at':batch['demo_completed_at'],'source_count':len(sources),'ready_source_count':ready,'analyzable_source_count':ready+successful,'successful_source_count':successful,'failed_source_count':failed,'sources':sources,'can_add_sources':not batch['case_id'] and projected not in {'queued','processing'},'case_id':batch['case_id'] if visible else None,'result':json.loads(batch['result_json']) if visible and batch['result_json'] else None}

def _batch_for_source_mutation(batch_id:str,owner_id:str):
 batch=owned('import_batches',batch_id,owner_id);state=_batch_projected_state(batch)
 if state in {'queued','processing'}:raise HTTPException(409,'批次正在分析，暂不能修改来源')
 if batch['case_id']:raise HTTPException(409,'已生成事项的批次只能删除失败来源后重新分析')
 with conn() as c:c.execute("UPDATE import_batches SET state='draft',revision=revision+1,analyzed_revision=NULL,started_at=NULL,demo_processing_at=NULL,demo_completed_at=NULL,final_status=NULL,result_json=NULL,updated_at=? WHERE id=? AND owner_id=?",(stamp(),batch_id,owner_id))
 return owned('import_batches',batch_id,owner_id)

def _store_import_source(owner_id:str,batch_id:str,kind:str,name:str,status:str,error:str|None,metadata:dict,extracted_text:str|None):
 source_id=str(uuid.uuid4());now=stamp()
 with conn() as c:c.execute('INSERT INTO import_sources(id,owner_id,batch_id,kind,name,status,error,metadata_json,extracted_text,evidence_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(source_id,owner_id,batch_id,kind,name,status,error,json.dumps(metadata,ensure_ascii=False),extracted_text,None,now,now))
 return _import_source_json(owned('import_sources',source_id,owner_id))

def _source_error(exc:Exception):
 if isinstance(exc,HTTPException):return str(exc.detail.get('message','来源处理失败') if isinstance(exc.detail,dict) else exc.detail)[:160]
 return '内容解析失败，请检查来源格式后重试'
def _source_error_code(exc:Exception):
 if isinstance(exc,HTTPException) and isinstance(exc.detail,dict):return str(exc.detail.get('code') or 'source_failed')
 return 'content_parse_failed'

def _existing_analysis_result(case_id:str,owner_id:str):
 with conn() as c:
  metadata=c.execute('SELECT * FROM analysis_metadata WHERE owner_id=? AND case_id=? ORDER BY created_at DESC LIMIT 1',(owner_id,case_id)).fetchone()
  counts=c.execute('SELECT (SELECT COUNT(*) FROM rules WHERE owner_id=? AND case_id=?) rules,(SELECT COUNT(*) FROM tasks WHERE owner_id=? AND case_id=?) tasks,(SELECT COUNT(*) FROM materials WHERE owner_id=? AND case_id=?) materials',(owner_id,case_id,owner_id,case_id,owner_id,case_id)).fetchone()
 if not metadata:return None
 outcome=evaluate_case(case_id,owner_id,persist=False)
 questions=json.loads(metadata['questions_json']);legacy='请在个人画像中补充规则所需字段；缺少字段会保持 UNKNOWN。'
 if outcome['reason']!='missing_profile_fact':questions=[question for question in questions if question!=legacy]
 return {'rules':counts['rules'],'tasks':counts['tasks'],'materials':counts['materials'],'relevance':outcome['relevance'],'relevance_reason':outcome['reason'],'missing_profile_fields':outcome['missing_profile_fields'],'missing_case_fields':outcome['missing_case_fields'],'analysis_mode':metadata['mode'],'model_id':metadata['model_id'],'summary':metadata['summary'],'questions':questions,'review_reasons':json.loads(metadata['review_reasons_json'])}

@app.post('/api/v1/import-batches')
def create_import_batch(body:ImportBatchIn,user=Depends(current_user)):
 database();batch_id=str(uuid.uuid4());now=stamp()
 with conn() as c:c.execute("INSERT INTO import_batches(id,owner_id,title,state,revision,created_at,updated_at) VALUES(?,?,?,'draft',0,?,?)",(batch_id,user['id'],body.title,now,now))
 return data(_import_batch_json(owned('import_batches',batch_id,user['id'])))

@app.get('/api/v1/import-batches/{batch_id}')
def get_import_batch(batch_id:str,user=Depends(current_user)):
 database();return data(_import_batch_json(owned('import_batches',batch_id,user['id'])))

@app.post('/api/v1/import-batches/{batch_id}/sources/text')
def add_import_text_source(batch_id:str,body:TextImport,user=Depends(current_user)):
 if not body.consent:raise HTTPException(422,'请先确认隐私处理范围')
 _batch_for_source_mutation(batch_id,user['id']);text=body.text.strip()
 return data(_store_import_source(user['id'],batch_id,'text',body.title or title_from(text),'ready',None,{'characters':len(text),'sha256':hashlib.sha256(text.encode()).hexdigest()},text))

@app.post('/api/v1/import-batches/{batch_id}/sources/url')
def add_import_url_source(batch_id:str,body:UrlImport,user=Depends(current_user)):
 if not body.consent:raise HTTPException(422,'请先确认隐私处理范围')
 _batch_for_source_mutation(batch_id,user['id']);parsed=urlparse(body.url);name=body.title or parsed.hostname or '网页通知'
 try:
  raw,mime,final_url=fetch_public(body.url);blocks=parse_url_blocks(raw,mime,final_url);extracted='\n\n'.join(block['text'] for block in blocks if block.get('text','').strip())
  if not extracted:raise ValueError('empty')
  suffix={'text/html':'.html','application/xhtml+xml':'.xhtml','application/pdf':'.pdf','text/plain':'.txt'}.get(mime,mimetypes.guess_extension(mime) or '')
  with conn() as c:document=store_document(c,document_root(),user['id'],raw,mime,'网页原件'+suffix,lambda *args:blocks)
  source=_store_import_source(user['id'],batch_id,'url',name,'ready',None,{'url':body.url,'final_url':final_url,'mime':mime,'blocks':len(blocks),'document_id':document['id'],'attachments':attachment_candidates(raw,mime,final_url)},extracted)
  with conn() as c:c.execute('INSERT INTO source_documents VALUES(?,?,?)',(user['id'],source['id'],document['id']))
  return data(source)
 except Exception as exc:
  return data(_store_import_source(user['id'],batch_id,'url',name,'failed',_source_error(exc),{'url':body.url,'error_code':_source_error_code(exc)},None))

@app.post('/api/v1/import-batches/{batch_id}/sources/{source_id}/attachments')
def import_attachment_candidate(batch_id:str,source_id:str,body:AttachmentImportIn,user=Depends(current_user)):
 if not body.consent:raise HTTPException(422,{'code':'CONFIRMATION_REQUIRED','message':'请单独确认此附件的隐私处理与获取范围'})
 source=owned('import_sources',source_id,user['id'])
 if source['batch_id']!=batch_id:raise HTTPException(404,'来源不属于当前批次')
 candidates=json.loads(source['metadata_json']).get('attachments',[])
 if body.index>=len(candidates):raise HTTPException(422,'附件候选不存在')
 result=add_import_url_source(batch_id,UrlImport(url=candidates[body.index]['url'],title=candidates[body.index]['title'],consent=True),user)
 with conn() as c:
  child=c.execute('SELECT metadata_json FROM import_sources WHERE id=? AND owner_id=?',(result['data']['id'],user['id'])).fetchone()
  metadata=json.loads(child['metadata_json']);metadata['parent_source_id']=source_id
  c.execute('UPDATE import_sources SET metadata_json=? WHERE id=? AND owner_id=?',(json.dumps(metadata,ensure_ascii=False),result['data']['id'],user['id']))
  result['data']['metadata']=metadata
 return result

@app.post('/api/v1/import-batches/{batch_id}/sources/files')
async def add_import_file_sources(batch_id:str,files:list[UploadFile]=File(...),consent:bool=Form(False),user=Depends(current_user)):
 if not consent:raise HTTPException(422,'请先确认隐私处理范围')
 if len(files)>10:raise HTTPException(422,'单次最多10个文件')
 _batch_for_source_mutation(batch_id,user['id']);result=[]
 for upload in files:
  name=upload.filename or '未命名';mime=upload.content_type or mimetypes.guess_type(name)[0] or 'application/octet-stream';metadata={'mime':mime}
  try:
   raw=await read_upload(upload);metadata.update(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
   with conn() as c:document=store_document(c,document_root(),user['id'],raw,mime,name,parse_bytes)
   metadata.update(document_id=document['id'],blocks=len(document['lines']))
   if document['status']=='failed':raise DocumentError(document['error_code'],'文件已保存，解析未完成；可查看原件')
   extracted='\n'.join(line['text'] for line in document['lines'])
   source=_store_import_source(user['id'],batch_id,'file',name,'ready',None,metadata,extracted)
   with conn() as c:c.execute('INSERT INTO source_documents VALUES(?,?,?)',(user['id'],source['id'],document['id']))
   result.append(source)
  except DocumentError as exc:
   metadata['error_code']=exc.code;result.append(_store_import_source(user['id'],batch_id,'file',name,'failed',str(exc),metadata,None))
  except Exception as exc:result.append(_store_import_source(user['id'],batch_id,'file',name,'failed',_source_error(exc),metadata,None))
 return data(result)

@app.delete('/api/v1/import-batches/{batch_id}/sources/{source_id}')
def delete_import_source(batch_id:str,source_id:str,user=Depends(current_user)):
 batch=owned('import_batches',batch_id,user['id'])
 with conn() as c:source=c.execute('SELECT * FROM import_sources WHERE id=? AND batch_id=? AND owner_id=?',(source_id,batch_id,user['id'])).fetchone()
 if not source:raise HTTPException(404,'导入来源不存在')
 state=_batch_projected_state(batch)
 if state in {'queued','processing'}:raise HTTPException(409,'批次正在分析，暂不能删除来源')
 if batch['case_id'] and source['status']!='failed':raise HTTPException(409,'已生成 Evidence 的来源不能删除')
 with conn() as c:
  c.execute('DELETE FROM source_documents WHERE source_id=? AND owner_id=?',(source_id,user['id']))
  c.execute('DELETE FROM import_sources WHERE id=? AND batch_id=? AND owner_id=?',(source_id,batch_id,user['id']))
  c.execute("UPDATE import_batches SET state='draft',revision=revision+1,analyzed_revision=NULL,started_at=NULL,demo_processing_at=NULL,demo_completed_at=NULL,final_status=NULL,result_json=NULL,updated_at=? WHERE id=? AND owner_id=?",(stamp(),batch_id,user['id']))
 return data({'id':source_id,'deleted':True})

@app.post('/api/v1/import-batches/{batch_id}/analyze')
def analyze_import_batch(batch_id:str,user=Depends(current_user)):
 batch=owned('import_batches',batch_id,user['id']);revision=int(batch['revision'])
 if batch['started_at'] and batch['analyzed_revision']==revision:return data(_import_batch_json(batch))
 execution_started=datetime.now(timezone.utc)
 with conn() as c:sources=c.execute('SELECT * FROM import_sources WHERE owner_id=? AND batch_id=? ORDER BY created_at,id',(user['id'],batch_id)).fetchall()
 successful=[row for row in sources if row['status'] in {'ready','completed'} and row['extracted_text']];failed=[row for row in sources if row['status']=='failed']
 case_id=batch['case_id'];evidence_rows=[];evidence_ids=[];analysis=None
 if successful:
  case_id=case_id or str(uuid.uuid5(uuid.NAMESPACE_URL,f'zhishi:import-batch:{user["id"]}:{batch_id}'));combined='\n'.join(row['extracted_text'] for row in successful);now=stamp()
  with conn() as c:c.execute('INSERT OR IGNORE INTO cases(id,owner_id,title,category,status,relevance,deadline,created_at,updated_at,deadline_source,deadline_evidence_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(case_id,user['id'],batch['title'] or title_from(successful[0]['extracted_text']),category_from(combined),'review','UNKNOWN',None,now,now,None,'[]'))
  for source in successful:
   evidence_id=source['evidence_id'] or 'block:'+str(uuid.uuid5(uuid.NAMESPACE_URL,f'zhishi:import-source:{user["id"]}:{source["id"]}'));source_meta=json.loads(source['metadata_json']);source_name=source_meta.get('final_url') or source['name']
   for link in source_meta.get('attachments',[]):
    ref='block:link:'+str(uuid.uuid5(uuid.NAMESPACE_URL,user['id']+case_id+link['url']))
    c.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,user['id'],case_id,'网页附件链接','网页附件引用：'+link['title'],'从已保存网页发现；未读取附件',None,stamp()))
    c.execute('INSERT OR IGNORE INTO case_attachment_links VALUES(?,?,?,?,?)',(user['id'],case_id,link['url'],link['title'],ref))
   with conn() as c:
    if source_meta.get('document_id'):
     bound=bind_document(c,user['id'],case_id,source_meta['document_id'],source_name)
     evidence_id=bound[0][0]
    else:
     c.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?)',(evidence_id,user['id'],case_id,source_name,source['extracted_text'],'批次来源全文',None,stamp()))
     bound=[(evidence_id,source['extracted_text'])]
    c.execute("UPDATE import_sources SET status='completed',evidence_id=?,updated_at=? WHERE id=? AND owner_id=? AND batch_id=?",(evidence_id,stamp(),source['id'],user['id'],batch_id))
   evidence_rows.extend(bound);evidence_ids.extend(ref for ref,_ in bound)
  analysis=_existing_analysis_result(case_id,user['id']) or analyze_case(case_id,user['id'],evidence_rows)
 final_status='completed' if successful and not failed else 'partial_failure' if successful else 'failed'
 result={'case_id':case_id,'source_count':len(sources),'successful_sources':len(successful),'failed_sources':len(failed),'evidence_ids':evidence_ids,'analysis':analysis,'reason':'source_failed' if failed else None,'error':None if successful else '没有可分析的成功来源'}
 started=execution_started;processing=started+IMPORT_PROCESSING_DELAY if SETTINGS.demo_mode else started;completed=started+IMPORT_COMPLETION_DELAY if SETTINGS.demo_mode else datetime.now(timezone.utc)
 started_at=started.isoformat();processing_at=processing.isoformat();completed_at=completed.isoformat();result_json=json.dumps(result,ensure_ascii=False)
 with conn() as c:
  c.execute("UPDATE import_batches SET state='queued',analyzed_revision=?,started_at=?,demo_processing_at=?,demo_completed_at=?,final_status=?,case_id=?,result_json=?,updated_at=? WHERE id=? AND owner_id=?",(revision,started_at,processing_at,completed_at,final_status,case_id,result_json,stamp(),batch_id,user['id']))
  if not SETTINGS.demo_mode:c.execute('UPDATE import_batches SET state=? WHERE id=? AND owner_id=?',(final_status,batch_id,user['id']))
  c.execute('INSERT OR IGNORE INTO import_analysis_runs(id,owner_id,batch_id,revision,final_status,result_json,started_at,processing_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),user['id'],batch_id,revision,final_status,result_json,started_at,processing_at,completed_at))
 return data(_import_batch_json(owned('import_batches',batch_id,user['id'])))

@app.post('/api/v1/imports/url')
def import_url(body:UrlImport,user=Depends(current_user)):
 database();parsed=urlparse(body.url);iid=str(uuid.uuid4());name=body.title or parsed.hostname or '网页通知'
 with conn() as c:c.execute('INSERT INTO imports VALUES(?,?,?,?,?,?,?,?,?)',(iid,user['id'],'url',name,'needs_confirmation',json.dumps({'url':body.url},ensure_ascii=False),None,stamp(),stamp()))
 if not body.consent:return data({'id':iid,'state':'needs_confirmation','privacy':{'url':body.url,'message':'确认后才会访问该网址'}})
 raw,mime,final_url=fetch_public(body.url);blocks=parse_url_blocks(raw,mime,final_url)
 cid=str(uuid.uuid4());jid=str(uuid.uuid4());attachments=[];evidence_rows=[]
 if mime in {'text/html','application/xhtml+xml'} and body.include_attachments:
  soup=BeautifulSoup(raw,'html.parser')
  for link in soup.select('a[href]'):
   absolute=urljoin(final_url,link.get('href',''))
   if re.search(r'\.(pdf|docx|xlsx|txt)(?:$|\?)',absolute,re.I) and absolute not in attachments:attachments.append(absolute)
 attachments=attachments[:10]
 with conn() as c:
  now=stamp();c.execute('INSERT INTO cases(id,owner_id,title,category,status,relevance,deadline,created_at,updated_at,deadline_source,deadline_evidence_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,user['id'],body.title or title_from(blocks[0]['text'] if blocks else name),category_from(' '.join(x['text'] for x in blocks)),'review','UNKNOWN',None,now,now,None,'[]'))
  suffix={'text/html':'.html','application/xhtml+xml':'.xhtml','application/pdf':'.pdf','text/plain':'.txt'}.get(mime,mimetypes.guess_extension(mime) or '')
  document=store_document(c,document_root(),user['id'],raw,mime,'网页原件'+suffix,lambda *args:blocks)
  evidence_rows=bind_document(c,user['id'],cid,document['id'],final_url)
  c.execute('INSERT INTO analysis_jobs VALUES(?,?,?,?,?,?,?,?)',(jid,user['id'],iid,'completed','blocks_created',None,stamp(),stamp()));c.execute('UPDATE imports SET state=?,updated_at=? WHERE id=? AND owner_id=?',('review',stamp(),iid,user['id']))
 with conn() as c:c.execute('INSERT INTO import_case_sources VALUES(?,?,?,?)',(user['id'],iid,cid,json.dumps([ref for ref,_ in evidence_rows])))
 analysis=run_import_analysis(cid,user['id'],evidence_rows,jid)
 return data({'id':iid,'job_id':jid,'case_id':cid,'document_id':document['id'],'state':'review','blocks':len(blocks),'final_url':final_url,'attachments':attachments,'analysis':analysis,'coverage':'网页正文已建立证据；附件链接需逐项确认后导入'})
@app.post('/api/v1/imports/text')
def import_text(body:TextImport,user=Depends(current_user)):
 # Strict mode stores only redacted text until the user has explicitly consented to processing.
 database(); iid=str(uuid.uuid4()); privacy=redact(body.text)
 with conn() as c:c.execute('INSERT INTO imports VALUES(?,?,?,?,?,?,?,?,?)',(iid,user['id'],'text',body.title or title_from(body.text),'needs_confirmation',json.dumps(privacy,ensure_ascii=False),None,stamp(),stamp()))
 if not body.consent:return data({'id':iid,'state':'needs_confirmation','privacy':privacy})
 jid=str(uuid.uuid4())
 with conn() as c:c.execute('INSERT INTO analysis_jobs VALUES(?,?,?,?,?,?,?,?)',(jid,user['id'],iid,'completed','evidence_created',None,stamp(),stamp()))
 cid=str(uuid.uuid4()); eid='block:'+str(uuid.uuid4())
 deadline=None
 with conn() as c:
  now=stamp();c.execute('INSERT INTO cases(id,owner_id,title,category,status,relevance,deadline,created_at,updated_at,deadline_source,deadline_evidence_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,user['id'],body.title or title_from(body.text),category_from(body.text),'review','UNKNOWN',deadline,now,now,'document' if deadline else None,json.dumps([eid]) if deadline else '[]'))
  c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(eid,user['id'],cid,'用户导入文本',body.text,'全文',None,stamp()))
  c.execute('UPDATE imports SET state=?,updated_at=? WHERE id=? AND owner_id=?',('review',stamp(),iid,user['id']))
 with conn() as c:c.execute('INSERT INTO import_case_sources VALUES(?,?,?,?)',(user['id'],iid,cid,json.dumps([eid])))
 analysis=run_import_analysis(cid,user['id'],[(eid,body.text)],jid)
 return data({'id':iid,'job_id':jid,'state':'review','case_id':cid,'coverage':'已抽取有原文依据的规则与步骤；个体事实不足时保持 UNKNOWN','evidence_id':eid,'analysis':analysis})
@app.get('/api/v1/imports/{import_id}/progress')
def progress(import_id:str,user=Depends(current_user)):
 owned('imports',import_id,user['id'])
 with conn() as c:r=c.execute('SELECT * FROM analysis_jobs WHERE import_id=? AND owner_id=? ORDER BY created_at DESC LIMIT 1',(import_id,user['id'])).fetchone()
 return data(dict(r) if r else {'state':'needs_confirmation','stage':'privacy_confirmation'})
@app.post('/api/v1/imports/{import_id}/cancel')
def cancel(import_id:str,user=Depends(current_user)):
 owned('imports',import_id,user['id'])
 with conn() as c:c.execute("UPDATE analysis_jobs SET state='cancelled',stage='cancelled',updated_at=? WHERE import_id=? AND owner_id=? AND state NOT IN ('completed','cancelled')",(stamp(),import_id,user['id']))
 return data({'id':import_id,'state':'cancelled'})
@app.post('/api/v1/imports/{import_id}/retry')
def retry(import_id:str,body:DraftCommitIn,user=Depends(current_user)):
 owned('imports',import_id,user['id'])
 if not body.consent:raise HTTPException(422,{'code':'CONFIRMATION_REQUIRED','message':'请确认使用已保存证据重新分析'})
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  source=c.execute('SELECT * FROM import_case_sources WHERE import_id=? AND owner_id=?',(import_id,user['id'])).fetchone()
  active=c.execute("SELECT 1 FROM analysis_jobs WHERE import_id=? AND owner_id=? AND state IN ('queued','processing')",(import_id,user['id'])).fetchone()
  if active:raise HTTPException(409,{'code':'RETRY_BUSY','message':'已有执行记录未完成，请先取消或检查服务状态'})
  if not source:raise HTTPException(409,{'code':'RETRY_SOURCE_MISSING','message':'没有可重用的授权证据，请重新导入原文件或链接'})
  evidence_rows=[]
  for ref in json.loads(source['evidence_ids_json']):
   row=c.execute('SELECT id,text FROM evidence WHERE id=? AND owner_id=? AND case_id=?',(ref,user['id'],source['case_id'])).fetchone()
   if not row:raise HTTPException(409,{'code':'RETRY_SOURCE_MISSING','message':'重试证据已失效，请重新导入'})
   evidence_rows.append((row['id'],row['text']))
  jid=str(uuid.uuid4());c.execute('INSERT INTO analysis_jobs VALUES(?,?,?,?,?,?,?,?)',(jid,user['id'],import_id,'processing','candidate_analysis',None,stamp(),stamp()))
 try:
  result=analyze_case(source['case_id'],user['id'],evidence_rows,jid)
  with conn() as c:
   row=c.execute('SELECT state FROM analysis_jobs WHERE id=? AND owner_id=?',(jid,user['id'])).fetchone()
   state='cancelled' if row['state']=='cancelled' else 'completed'
   c.execute('UPDATE analysis_jobs SET state=?,stage=?,updated_at=? WHERE id=? AND owner_id=?',(state,'review_required' if state=='completed' else 'cancelled',stamp(),jid,user['id']))
  return data({'id':import_id,'job_id':jid,'state':state,'case_id':source['case_id'],'analysis':result})
 except ReviewError as exc:
  if exc.code=='JOB_CANCELLED':return data({'id':import_id,'job_id':jid,'state':'cancelled'})
  raise
 except Exception:
  with conn() as c:c.execute("UPDATE analysis_jobs SET state='failed',stage='candidate_analysis',error='ANALYSIS_FAILED',updated_at=? WHERE id=? AND owner_id=?",(stamp(),jid,user['id']))
  raise HTTPException(502,{'code':'ANALYSIS_FAILED','message':'重新分析失败，原证据保留'})

@app.get('/api/v1/cases/{case_id}/analysis-history')
def analysis_history(case_id:str,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 with conn() as c:rows=c.execute('SELECT revision,candidate_json,created_at FROM analysis_review_versions WHERE owner_id=? AND case_id=? ORDER BY revision DESC',(user['id'],case_id)).fetchall()
 return data([{'revision':row['revision'],'created_at':row['created_at'],'candidate':json.loads(row['candidate_json'])} for row in rows])

@app.get('/api/v1/cases/{case_id}/analysis-inputs')
def analysis_inputs(case_id:str,user=Depends(current_user)):
 owned('cases',case_id,user['id'])
 with conn() as c:rows=c.execute('SELECT s.import_id,i.name,i.kind FROM import_case_sources s JOIN imports i ON i.id=s.import_id AND i.owner_id=s.owner_id WHERE s.owner_id=? AND s.case_id=?',(user['id'],case_id)).fetchall()
 return data([dict(row) for row in rows])
@app.get('/api/v1/cases/{case_id}/export.ics')
def export_ics(case_id:str,user=Depends(current_user)):
 c=owned('cases',case_id,user['id']);p=plan(case_id,user)['data'];rows=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Zhishi//RuleFlow//CN']
 for t in p['ordered_tasks']:
  if not t['deadline']:continue
  date=re.sub(r'[^0-9]','',t['deadline'])[:8]
  if len(date)!=8:continue
  rows += ['BEGIN:VEVENT','UID:'+t['id'],'DTSTART;VALUE=DATE:'+date,'SUMMARY:'+t['title'].replace('\\','\\\\').replace(',','\\,').replace(';','\\;'),'END:VEVENT']
 rows += ['END:VCALENDAR'];return {'content':'\r\n'.join(rows)+'\r\n','content_type':'text/calendar; charset=utf-8'}
@app.post('/api/v1/imports/files')
async def files(files:list[UploadFile]=File(...),consent:bool=Form(False),user=Depends(current_user)):
 database()
 if len(files)>10:raise HTTPException(422,'单次最多10个文件')
 result=[]
 for f in files:
  try:raw=await read_upload(f)
  except DocumentError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})
  mime=f.content_type or mimetypes.guess_type(f.filename or '')[0]
  if len(raw)>MAX_FILE_BYTES:raise HTTPException(413,'文件不得超过20MB')
  if mime not in ALLOWED:raise HTTPException(415,'不支持的文件类型')
  iid=str(uuid.uuid4())
  with conn() as c:c.execute('INSERT INTO imports VALUES(?,?,?,?,?,?,?,?,?)',(iid,user['id'],'file',f.filename or '未命名','needs_confirmation',json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'mime':mime}),None,stamp(),stamp()))
  if not consent: result.append({'id':iid,'name':f.filename,'state':'needs_confirmation'});continue
  jid=str(uuid.uuid4())
  document=None
  try:
   with conn() as c:document=store_document(c,document_root(),user['id'],raw,mime,f.filename or '',parse_bytes)
   if document['status']=='failed':raise DocumentError(document['error_code'],'文件已保存，但未获得有效文字')
   blocks=document['lines']
   cid=str(uuid.uuid4());evidence_rows=[]
   with conn() as c:
    now=stamp();c.execute('INSERT INTO cases(id,owner_id,title,category,status,relevance,deadline,created_at,updated_at,deadline_source,deadline_evidence_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,user['id'],f.filename or '导入文件','other','review','UNKNOWN',None,now,now,None,'[]'))
    evidence_rows=bind_document(c,user['id'],cid,document['id'],f.filename or '导入文件')
    c.execute('INSERT INTO analysis_jobs VALUES(?,?,?,?,?,?,?,?)',(jid,user['id'],iid,'completed','blocks_created',None,stamp(),stamp()));c.execute('UPDATE imports SET state=?,updated_at=? WHERE id=?',('review',stamp(),iid))
   with conn() as c:c.execute('INSERT INTO import_case_sources VALUES(?,?,?,?)',(user['id'],iid,cid,json.dumps([ref for ref,_ in evidence_rows])))
   analysis=run_import_analysis(cid,user['id'],evidence_rows,jid)
   result.append({'id':iid,'job_id':jid,'case_id':cid,'document_id':document['id'],'state':'review','blocks':len(blocks),'analysis':analysis})
  except Exception as e:
   code=e.code if isinstance(e,DocumentError) else 'DOCUMENT_PARSE_FAILED'
   with conn() as c:c.execute('INSERT OR REPLACE INTO analysis_jobs VALUES(?,?,?,?,?,?,?,?)',(jid,user['id'],iid,'partial_failure','parse',code,stamp(),stamp()));c.execute('UPDATE imports SET state=?,error=?,updated_at=? WHERE id=?',('failed',code,stamp(),iid))
   result.append({'id':iid,'job_id':jid,'document_id':document['id'] if document else None,'state':'partial_failure','error_code':code,'error':'解析失败，已保存的原件可查看'})
 return data(result)
