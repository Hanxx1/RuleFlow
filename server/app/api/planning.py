"""Scheduling HTTP endpoints; existing SQL, validation and transactions preserved."""
from __future__ import annotations
import json, re, uuid
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Query
from ..auth import conn, current_user
from ..services.schedule import parse_instant, preview_schedule, timezone_for, utc_iso
from ..services.review import ReviewError, require_confirmed
from ..services.schedule_drafts import snapshot as schedule_snapshot, create_draft, commit_draft, DraftError
from fastapi import APIRouter
from ..bootstrap import database
from .common import data, stamp, owned, schedule_item_json
from ..schemas import ScheduleItemIn, ScheduleItemPatch, SchedulePreviewIn, DraftCommitIn, TaskPlanningIn, ScheduleSeriesIn, ScheduleLockIn

router = APIRouter()
SCHEDULE_KINDS = {"busy", "course", "task"}

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
   from ..services.schedule import task_deadline
   deadline=task_deadline(task['deadline'])
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

@router.get('/api/v1/schedule')
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

@router.post('/api/v1/schedule/items')
def create_schedule_item(body:ScheduleItemIn,user=Depends(current_user)):
 database();case_id=validate_schedule_links(body.kind,body.case_id,body.task_id,user['id']);starts_at,ends_at=normalize_schedule_range(body.starts_at,body.ends_at);ensure_task_schedule_unique(user['id'],body.task_id);ensure_schedule_slot(user['id'],starts_at,ends_at)
 item_id=str(uuid.uuid4());now=stamp()
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  validate_schedule_write(c,user['id'],case_id,body.task_id,starts_at,ends_at)
  c.execute('INSERT INTO schedule_items(id,owner_id,case_id,task_id,title,kind,starts_at,ends_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(item_id,user['id'],case_id,body.task_id,body.title,body.kind,starts_at,ends_at,now,now))
 return data(schedule_item_json(owned('schedule_items',item_id,user['id'])))

@router.patch('/api/v1/schedule/items/{item_id}')
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

@router.delete('/api/v1/schedule/items/{item_id}')
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

@router.post('/api/v1/schedule/items/{item_id}/lock')
def set_schedule_lock(item_id:str,body:ScheduleLockIn,user=Depends(current_user)):
 owned('schedule_items',item_id,user['id'])
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if not c.execute('SELECT 1 FROM schedule_items WHERE id=? AND owner_id=?',(item_id,user['id'])).fetchone():raise HTTPException(404,'安排不存在')
  c.execute('INSERT INTO schedule_locks VALUES(?,?,?) ON CONFLICT(item_id) DO UPDATE SET locked=excluded.locked',(item_id,user['id'],int(body.locked)))
 return data({'id':item_id,'locked':body.locked})

@router.post('/api/v1/schedule/series')
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

@router.post('/api/v1/schedule/preview')
def schedule_preview(body:SchedulePreviewIn,user=Depends(current_user)):
 database()
 try:tz=timezone_for(body.timezone)
 except ValueError as exc:raise HTTPException(422,str(exc))
 now=datetime.now(tz)
 try:
  window_start=parse_instant(body.window_start) if body.window_start else now
  window_end=parse_instant(body.window_end) if body.window_end else window_start+timedelta(days=14)
 except ValueError as exc:raise HTTPException(422,str(exc))
 if window_start<now:raise HTTPException(422,'排程窗口起点不能早于服务器当前时间，请重新选择时间')
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
  task_metadata=c.execute('SELECT id,status,duration_minutes FROM tasks WHERE owner_id=?',(user['id'],)).fetchall()
  statuses={row['id']:row['status'] for row in task_metadata}
  durations={row['id']:row['duration_minutes'] for row in task_metadata}
 if body.calendar_blocks:
  if not body.calendar_consent or body.calendar_revision is None:raise HTTPException(422,'本机课表占用时段须明确确认发送并附资料版本')
  for block in body.calendar_blocks:
   starts_at,ends_at=normalize_schedule_range(block.starts_at,block.ends_at)
   if any(not re.fullmatch(r'block:client:[A-Za-z0-9-]+',ref) for ref in block.evidence_ids):raise HTTPException(422,'课表缺少有效本机证据')
   existing.append({'id':block.id,'title':'本机课表占用','kind':'course','starts_at':starts_at,'ends_at':ends_at})
 try:result=preview_schedule(tasks,edges,existing,window_start,window_end,body.timezone,statuses,body.preferences.model_dump(),all_task_durations=durations)
 except ValueError as exc:raise HTTPException(422,str(exc))
 if body.calendar_revision is not None:result.update(calendar_revision=body.calendar_revision,calendar_blocks=[b.model_dump() for b in body.calendar_blocks])
 return data(result)

@router.put('/api/v1/tasks/{task_id}/planning')
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

@router.post('/api/v1/schedule/drafts')
def schedule_draft(body:SchedulePreviewIn,user=Depends(current_user)):
 database()
 with conn() as c:before=schedule_snapshot(c,user['id'])
 result=schedule_preview(body,user)['data']
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if schedule_snapshot(c,user['id'])!=before:raise HTTPException(409,{'code':'DRAFT_STALE','message':'预览期间状态变化，请重试'})
  return data(create_draft(c,user['id'],result,before))

@router.post('/api/v1/schedule/drafts/{draft_id}/commit')
def schedule_draft_commit(draft_id:str,body:DraftCommitIn,user=Depends(current_user)):
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  try:return data(commit_draft(c,user['id'],draft_id,body.consent,validate_schedule_write,body.calendar_revision))
  except DraftError as exc:raise HTTPException(exc.status,{'code':exc.code,'message':str(exc)})

