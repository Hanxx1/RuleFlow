"""Bounded public-notice benchmark; private configuration and outputs stay ignored."""
import argparse, hashlib, json, os, re, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.environ['DATABASE_PATH']=':memory:'
sys.path.insert(0,str(ROOT/'server'))
from bs4 import BeautifulSoup
from app.main import fetch_public,_local_candidates
from app.ai import configured_provider,validate_candidates
from app.privacy import analyze as privacy_scan
from app.services.date_candidates import extract_dates
from app.services.relevance import evaluate_rules
from app.services.schedule import preview_schedule
from app.parsing import html_blocks
from app.services.unsupported_conditions import extract_unsupported

SOURCES=[
 ('award','https://xsc.sicau.edu.cn/info/1013/14972.htm','.v_news_content'),
 ('registration','https://cxcy.cczu.edu.cn/2026/0810/c6900a420359/page.htm','.wp_articlecontent'),
 ('multi_deadline','https://jcsyzx.ntu.edu.cn/2026/0112/c6844a285330/page.htm','.wp_articlecontent'),
]

def load_config():
 config=json.loads((ROOT/'.runtime/deepseek/private.json').read_text(encoding='utf-8'))
 for key,value in config.items():
  if key.startswith('LLM_'):os.environ[key]=str(value)

def summarize(candidate,evidence):
 rules=[{**rule,'id':str(index)} for index,rule in enumerate(candidate.get('rules',[]))]
 facts={'student_type':'undergraduate','enrollment_year':2024,'team_size':3,'rank_percent':10}
 evaluation=evaluate_rules(rules,facts)
 unsupported=candidate.get('unsupported_conditions',[])+extract_unsupported(evidence)
 if unsupported and evaluation['relevance']=='TRUE':evaluation.update(relevance='UNKNOWN',eligibility_truth='UNKNOWN',reason='unmodeled_conditions')
 dates=extract_dates(evidence)
 return {'rule_count':len(rules),'material_count':len(candidate.get('materials',[])),
  'task_count':len(candidate.get('tasks',[])), 'tasks':candidate.get('tasks',[]),
  'rules':candidate.get('rules',[]),'questions':candidate.get('questions',[]),
  'review_reasons':candidate.get('review_reasons',[]),'dates':dates,'unsupported_conditions':unsupported,
  'synthetic_profile_evaluation':evaluation,
  'warning':'Eligibility over extracted supported rules is not proof that all original conditions are covered.'}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--llm',action='store_true');args=parser.parse_args()
 out=ROOT/'.runtime/public-notice-benchmark';out.mkdir(parents=True,exist_ok=True)
 if args.llm:load_config()
 provider=configured_provider() if args.llm else None
 report={'captured_at':datetime.now(timezone.utc).isoformat(),'model_id':provider.model_id if provider else 'not_called','samples':[]}
 for name,url,selector in SOURCES:
  sample={'id':name,'url':url};report['samples'].append(sample)
  try:
   raw,mime,final_url=fetch_public(url)
   soup=BeautifulSoup(raw,'html.parser');article=soup.select_one(selector)
   if article is None:raise ValueError('article_selector_missing')
   text='\n'.join(block['text'] for block in html_blocks(str(article).encode('utf-8')))
   lines=[line.strip() for line in text.splitlines() if line.strip()]
   # Remove contact sections before any external-model call; no real user data.
   cleaned=[]
   for line in lines:
    if re.search(r'联系人|联系电话|联系我们|联系老师|邮编|地址：|版权所有|CopyRight|电话：',line):continue
    cleaned.append(privacy_scan(line)['redacted_text'])
   text='\n'.join(cleaned)
   (out/(name+'.txt')).write_text(text,encoding='utf-8')
   evidence=[('block:'+name+':'+str(index),line) for index,line in enumerate(cleaned,1)]
   sample.update(final_url=final_url,input_chars=len(text),sha256=hashlib.sha256(text.encode()).hexdigest(),local=summarize(_local_candidates(evidence),evidence))
   if provider:
    started=time.perf_counter()
    try:
     candidate=provider.analyze([{'id':ref,'text':line,'locator':'public line'} for ref,line in evidence])
     warnings=validate_candidates(candidate,dict(evidence))
     sample['llm']={**summarize(candidate.model_dump(),evidence),'status':'validated','validation_warnings':warnings}
    except Exception as exc:
     sample['llm']={'status':'failed','error_type':type(exc).__name__}
    sample['llm']['elapsed_seconds']=round(time.perf_counter()-started,2)
    sample['llm']['request_metrics']=provider.request_metrics
   actions=sample.get('llm',{}).get('tasks') if sample.get('llm',{}).get('status')=='validated' else sample['local']['tasks']
   dates=sample['local']['dates'];complete=[item['value'] for item in dates if item['role']=='deadline' and item['value']]
   # Test-only replay. Do not claim automatic confirmation or set a user's deadline.
   selected=min(complete) if complete else None
   tasks=[{'id':f'task:{index}','case_id':name,'title':item['title'],'duration_minutes':30,'deadline':selected} for index,item in enumerate(actions)]
   start=datetime(2026,10,14,9,tzinfo=timezone(timedelta(hours=8)))
   schedule=preview_schedule(tasks,[],[],start,start+timedelta(days=14),'Asia/Shanghai',{item['id']:'todo' for item in tasks})
   sample['schedule_replay']={'explicit_test_choice':selected,'suggestions':schedule['suggestions'],'unscheduled':schedule['unscheduled'],'warning':'Test-only choice, no formal task saved, dependencies intentionally omitted.'}
   sample['status']='processed'
  except Exception as exc:sample.update(status='failed',error_type=type(exc).__name__)
  (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'sample':name,'status':sample['status'],'local_tasks':sample.get('local',{}).get('task_count'),'llm_status':sample.get('llm',{}).get('status'),'llm_tasks':sample.get('llm',{}).get('task_count'),'seconds':sample.get('llm',{}).get('elapsed_seconds')},ensure_ascii=False),flush=True)
 print('Report saved in ignored .runtime/public-notice-benchmark/report.json')

if __name__=='__main__':main()
