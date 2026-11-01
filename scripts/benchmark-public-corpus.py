"""Resumable, bounded official-notice crawl and real provider evaluation."""
import concurrent.futures as cf
import hashlib,json,re,sys,time
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).parent))
from importlib.util import spec_from_file_location,module_from_spec
spec=spec_from_file_location('bench',Path(__file__).with_name('benchmark-public-notices.py'))
b=module_from_spec(spec);spec.loader.exec_module(b)
ROOT=b.ROOT;OUT=ROOT/'.runtime/public-corpus';OUT.mkdir(parents=True,exist_ok=True)
HOST='xsc.sicau.edu.cn'

def crawl():
 robots=RobotFileParser()
 try:
  raw,_,_=b.fetch_public('https://'+HOST+'/robots.txt')
  robots.parse(raw.decode('utf-8','replace').splitlines())
 except Exception as exc:
  if getattr(getattr(exc,'__cause__',None),'response',None) is None or exc.__cause__.response.status_code!=404:raise
  robots.parse([])  # Missing robots file; public pages only, paced requests.
 pending=['https://'+HOST+'/index/tzgg.htm','https://'+HOST+'/xszz/zzyr.htm','https://'+HOST+'/'];seen=set();articles={}
 while pending and len(seen)<400 and len(articles)<240:
  url=pending.pop(0)
  if url in seen or not robots.can_fetch('RuleFlowResearch',url):continue
  seen.add(url)
  try:
   raw,_,_=b.fetch_public(url);s=BeautifulSoup(raw.decode('utf-8','replace'),'html.parser')
   for a in s.select('a[href]'):
    target=urljoin(url,a['href']).split('#')[0]
    if urlparse(target).hostname!=HOST:continue
    if re.search(r'/info/\d+/\d+\.htm$',target):
     title=a.get_text('',strip=True)
     if re.search('通知|报名|申请|评选|申报|认定|征集|竞赛|考试|提醒',title) and not re.search('名单|公示|获奖结果',title):articles[target]=title
    elif target.endswith('.htm') and '/info/' not in target and target not in seen and target not in pending:
     if re.search(r'/\d+\.htm$',target):pending.insert(0,target)
     else:pending.append(target)
   print(json.dumps({'index_pages':len(seen),'article_links':len(articles)}),flush=True)
  except Exception as e:print(json.dumps({'crawl_error':type(e).__name__}),flush=True)
  time.sleep(.35)
 corpus=json.loads((OUT/'corpus.json').read_text(encoding='utf-8')) if (OUT/'corpus.json').exists() else []
 hashes={s['sha256'] for s in corpus};existing_urls={s['url'] for s in corpus}
 for url,title in articles.items():
  if len(corpus)>=210:break
  if url in existing_urls:continue
  if not robots.can_fetch('RuleFlowResearch',url):continue
  try:
   raw,_,final=b.fetch_public(url);s=BeautifulSoup(raw.decode('utf-8','replace'),'html.parser');node=s.select_one('.v_news_content')
   if node is None:continue
   lines=[]
   for block in b.html_blocks(str(node).encode('utf-8')):
    line=block['text'].strip()
    if not line or re.search('联系人|联系电话|联系老师|电话[：:]|地址[：:]|邮编',line):continue
    line=b.privacy_scan(line)['redacted_text']
    lines.append(line)
   text='\n'.join(lines);digest=hashlib.sha256(text.encode()).hexdigest()
   if len(text)<180 or len(text)>14000 or digest in hashes:continue
   hashes.add(digest);corpus.append({'id':'public-'+digest[:16],'url':final,'title':title,'sha256':digest,'lines':lines})
   (OUT/'corpus.json').write_text(json.dumps(corpus,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({'captured':len(corpus),'chars':len(text)}),flush=True)
  except Exception as e:print(json.dumps({'article_error':type(e).__name__}),flush=True)
  time.sleep(.4)
 if len(corpus)<200:raise RuntimeError('Insufficient distinct public documents: '+str(len(corpus)))

def run_one(sample):
 dest=OUT/(sample['id']+'.json')
 if dest.exists():
  cached=json.loads(dest.read_text(encoding='utf-8'))
  if '--retry-failed' not in sys.argv or cached['status']!='failed':return cached
  prior=OUT/(sample['id']+'.baseline.json')
  if not prior.exists():prior.write_text(dest.read_text(encoding='utf-8'),encoding='utf-8')
 evidence=[('block:'+sample['id']+':'+str(i),line) for i,line in enumerate(sample['lines'])]
 provider=b.configured_provider();start=time.perf_counter()
 result={'id':sample['id'],'url':sample['url'],'sha256':sample['sha256'],'title':sample['title']}
 try:
  candidate=provider.analyze([{'id':ref,'text':line,'locator':'public paragraph'} for ref,line in evidence])
  warnings=b.validate_candidates(candidate,dict(evidence))
  result.update(status='validated',candidate=candidate.model_dump(),summary=b.summarize(candidate.model_dump(),evidence),warnings=warnings)
 except Exception as e:result.update(status='failed',error_type=type(e).__name__)
 result.update(elapsed_seconds=round(time.perf_counter()-start,2),metrics=provider.request_metrics)
 dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 return result

def evaluate():
 b.load_config();samples=json.loads((OUT/'corpus.json').read_text(encoding='utf-8'))[:200];results=[]
 offset=int(sys.argv[sys.argv.index('--offset')+1]) if '--offset' in sys.argv else 0
 samples=samples[offset:]
 with cf.ThreadPoolExecutor(max_workers=3) as pool:
  for future in cf.as_completed([pool.submit(run_one,s) for s in samples]):
   r=future.result();results.append(r)
   print(json.dumps({'completed':len(results),'status':r['status'],'tasks':r.get('summary',{}).get('task_count'),'seconds':r['elapsed_seconds']}),flush=True)
 (OUT/('results-tail.json' if offset else 'results.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 if len(results)!=len(samples) or (not offset and len(results)!=200):raise RuntimeError('Incomplete benchmark')

if __name__=='__main__':
 if '--crawl' in sys.argv:crawl()
 if '--llm' in sys.argv:evaluate()
