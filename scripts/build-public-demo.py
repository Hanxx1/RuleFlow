"""Build read-only, reviewed public excerpts, separated from account data."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];runtime=ROOT/'.runtime/public-corpus'
samples=json.loads((runtime/'corpus.json').read_text(encoding='utf-8'))
bundles=[]
for sample in samples:
 path=runtime/(sample['id']+'.json')
 if not path.exists():continue
 result=json.loads(path.read_text(encoding='utf-8'))
 if result['status']!='validated':continue
 selected=[]
 for task in result['candidate']['tasks']:
  if task.get('origin')!='document' or re.search('学院|学校|各单位|各部门|评审|审批|汇总|公示|QQ|qq|群|报送|推荐名单',task['title']):continue
  quotes=task.get('evidence_quotes',{})
  if not quotes or any(len(quote)>100 or not quote.strip() for quote in quotes.values()):continue
  if not re.search('申请|提交|填写|上传|报名|参加|准备|缴纳|核对',task['title']):continue
  selected.append(task)
 if not selected:continue
 selected=selected[:2];blocks={};tasks=[]
 for index,task in enumerate(selected):
  for ref,quote in task['evidence_quotes'].items():
   original=sample['lines'][int(ref.rsplit(':',1)[1])]
   assert quote in original
   if ref in blocks and quote not in blocks[ref]['text']:blocks[ref]['text']+='\n'+quote
   elif ref not in blocks:blocks[ref]={'id':ref,'text':quote,'source_name':sample['title']+'（公开原文节选）','source_url':sample['url'],'locator':'官网原文节选；历史通知，仅供演示','confidence':1}
  tasks.append({'id':'demo-'+sample['id']+'-task-'+str(index),'title':task['title'],'status':'todo','deadline':None,'duration_minutes':None,'origin':'document','evidence_ids':list(task['evidence_quotes'])})
 case_id='demo-'+sample['id']
 bundles.append({'id':case_id,'notice':{'id':case_id,'title':sample['title']+'（公开通知演示）','category':result['candidate'].get('category','other'),'status':'demo','relevance':'UNKNOWN','deadline':None,'deadline_evidence_ids':[],'source_name':sample['title'],'source_url':sample['url']},'blocks':list(blocks.values()),'tasks':{'nodes':tasks,'edges':[]},'materials':[],'rules':[],'facts':[],'analysis':{'summary':'公开通知的行动节选；已核对任务短引，未替演示用户认定资格或确认截止时间。','questions':['请在真实使用时核对个人资格、具体日期及通知完整上下文。'],'review_reasons':['历史公开通知，只读演示，任务状态与真实账户隔离。']}})
 if len(bundles)>=12:break
assert len(bundles)>=10,'Not enough grounded public excerpts'
for target in [ROOT/'shared/demo/public-cases.json',ROOT/'mobile/public/demo/public-cases.json']:
 target.write_text(json.dumps(bundles,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'public_demo_cases':len(bundles),'task_count':sum(len(b['tasks']['nodes']) for b in bundles)}))
