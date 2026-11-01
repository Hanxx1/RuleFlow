"""Replay forty distinct notice tasks against explicit synthetic user calendars."""
import json,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'server'))
from app.services.schedule import preview_schedule,parse_instant
out=ROOT/'.runtime/multiformat-200';records=[]
for path in out.glob('public-*.json'):
 r=json.loads(path.read_text(encoding='utf-8'))
 if r['status']=='validated' and r['candidate']['tasks']:records.append(r)
records=sorted(records,key=lambda r:r['id'])[:40]
assert len(records)==40,'Wait for at least forty analyzed actionable notices'
results=[];tz=timezone(timedelta(hours=8))
for i,r in enumerate(records):
 start=datetime(2026,10,12,8,tzinfo=tz);end=start+timedelta(days=2)
 calendar=[{'id':'course:'+str(i),'title':'合成课程占用','kind':'course','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=2)).isoformat()}]
 if i%4==1:calendar=[{'id':'blocked:'+str(i),'title':'合成全天课程','kind':'course','starts_at':start.isoformat(),'ends_at':end.isoformat()}]
 tasks=[{'id':f'task:{i}:{j}','case_id':r['id'],'title':t['title'],'duration_minutes':30,'deadline':'2026-10-30','evidence_ids':t['evidence_ids']+['block:client:benchmark']} for j,t in enumerate(r['candidate']['tasks'][:2])]
 if i%4==2:
  for t in tasks:t['deadline']='2026-10-01'
 edges=[{'before_task_id':tasks[0]['id'],'after_task_id':tasks[1]['id']}] if len(tasks)>1 else []
 preview=preview_schedule(tasks,edges,calendar,start,end,'Asia/Shanghai',{t['id']:'todo' for t in tasks},{'buffer_minutes':15,'daily_max_minutes':120})
 overlaps=sum(parse_instant(c['starts_at'])<parse_instant(b['ends_at']) and parse_instant(b['starts_at'])<parse_instant(c['ends_at']) for b in preview['suggestions'] for c in calendar)
 assert overlaps==0
 results.append({'id':r['id'],'source':r['url'],'scenario':i%4,'suggestions':len(preview['suggestions']),'unscheduled':[u['reason'] for u in preview['unscheduled']],'course_overlap_count':overlaps,'assumptions':{'duration_minutes':30,'deadline':'synthetic user confirmed date, not original notice deadline','dependencies':'synthetic user-selected ordering','evidence':'block:client:benchmark: user selected a synthetic calendar, duration, deadline and order'}})
(out/'calendar-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'distinct_notice_scenarios':len(results),'course_overlaps':sum(r['course_overlap_count'] for r in results)}))
