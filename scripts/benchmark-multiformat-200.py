from font_config import corpus_font
"""200 distinct public notices, format conversion clearly labelled, real OCR/LLM."""
import concurrent.futures as cf,hashlib,json,sys,time,textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import fitz
from docx import Document
from openpyxl import Workbook
from importlib.util import spec_from_file_location,module_from_spec
ROOT=Path(__file__).resolve().parents[1]
sp=spec_from_file_location('b',ROOT/'scripts/benchmark-public-notices.py');b=module_from_spec(sp);sp.loader.exec_module(b)
from app.parsing import parse_bytes
from app.services.attachment_requirements import inventory
OUT=ROOT/'.runtime/multiformat-200';OUT.mkdir(parents=True,exist_ok=True)
FONT=corpus_font()

def prepare():
 samples=json.loads((ROOT/'.runtime/public-corpus/corpus.json').read_text(encoding='utf-8'))[:200]
 manifest=[]
 for i,sample in enumerate(samples):
  kind='text' if i<60 else 'image' if i<110 else 'pdf' if i<160 else 'docx' if i<180 else 'xlsx'
  folder=OUT/sample['id'];folder.mkdir(exist_ok=True);paths=[]
  if kind=='text':
   p=folder/'notice.txt';p.write_text('\n'.join(sample['lines']),encoding='utf-8');paths=[{'path':str(p),'mime':'text/plain'}]
  elif kind in {'image','pdf'}:
   lines=[part for line in sample['lines'] for part in textwrap.wrap(line,width=40,replace_whitespace=False,drop_whitespace=False) or ['']]
   pages=[lines[j:j+40] for j in range(0,len(lines),40)];pdf=fitz.open() if kind=='pdf' else None
   for page_index,rows in enumerate(pages):
    image=Image.new('RGB',(1200,1600),'white');draw=ImageDraw.Draw(image);font=ImageFont.truetype(FONT,24)
    for n,line in enumerate(rows):draw.text((30,30+n*36),line,font=font,fill='black')
    if kind=='image' and i%10==0:image=image.rotate(90,expand=True)
    elif kind=='image' and i%10==1:image=image.filter(ImageFilter.GaussianBlur(.7))
    p=folder/('page-'+str(page_index)+'.png');image.save(p)
    if kind=='image':paths.append({'path':str(p),'mime':'image/png'})
    elif i%3==0:
     page=pdf.new_page(width=600,height=800);page.insert_image(page.rect,filename=str(p))
    else:
     page=pdf.new_page(width=650,height=850);page.insert_font(fontname='notice',fontfile=FONT)
     for n,line in enumerate(rows):page.insert_text((20,30+n*18),line,fontname='notice',fontsize=12)
   if pdf:
    p=folder/'notice.pdf';pdf.save(p);pdf.close();paths=[{'path':str(p),'mime':'application/pdf'}]
  elif kind=='docx':
   doc=Document();table=doc.add_table(rows=0,cols=1)
   for line in sample['lines']:table.add_row().cells[0].text=line
   p=folder/'notice.docx';doc.save(p);paths=[{'path':str(p),'mime':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}]
  else:
   book=Workbook();sheet=book.active
   for line in sample['lines']:sheet.append([line])
   p=folder/'notice.xlsx';book.save(p);paths=[{'path':str(p),'mime':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}]
  manifest.append({**sample,'format':kind,'paths':paths,'holdout':i%5==0,'provenance':'public HTML text converted for controlled format testing; not original attachment'})
 (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'prepared':len(manifest),'holdout':sum(s['holdout'] for s in manifest)}),flush=True)

def run_one(s):
 dest=OUT/(s['id']+'.json')
 if dest.exists():
  cached=json.loads(dest.read_text(encoding='utf-8'))
  if '--retry-failed' not in sys.argv or cached['status']!='failed':return cached
  prior=OUT/(s['id']+'.baseline.json')
  if not prior.exists():prior.write_text(dest.read_text(encoding='utf-8'),encoding='utf-8')
 started=time.perf_counter();result={k:s[k] for k in ['id','url','title','format','holdout','provenance']}
 try:
  blocks=[]
  for source in s['paths']:blocks+=parse_bytes(Path(source['path']).read_bytes(),source['mime'],Path(source['path']).name)
  rows=[]
  for block in blocks:
   for line in block['text'].splitlines():
    if line.strip():rows.append(line.strip())
  if not rows:raise ValueError('OCR_EMPTY')
  evidence=[('block:'+s['id']+':'+str(i),line) for i,line in enumerate(rows)]
  provider=b.configured_provider()
  try:
   candidate=provider.analyze([{'id':ref,'text':text,'locator':'parsed '+s['format']} for ref,text in evidence])
   b.validate_candidates(candidate,dict(evidence));result.update(status='validated',candidate=candidate.model_dump(),summary=b.summarize(candidate.model_dump(),evidence))
  except Exception as e:result.update(status='failed',error_type=type(e).__name__)
  result['metrics']=provider.request_metrics
  original_dates=b.extract_dates([('block:reference:'+str(i),line) for i,line in enumerate(s['lines'])]);parsed_dates=b.extract_dates(evidence)
  expected={d['value'] for d in original_dates if d['role']=='deadline' and d['value']}
  found={d['value'] for d in parsed_dates if d['role']=='deadline' and d['value']}
  result.update(reference_kind='automated paired original-text consistency, not independent manual gold',expected_deadlines=sorted(expected),parsed_deadlines=sorted(found),missing_deadlines=sorted(expected-found),extra_deadlines=sorted(found-expected),located_blocks=sum(bool(x.get('bbox')) for x in blocks),parsed_lines=len(rows),attachments=inventory([{'id':ref,'text':text} for ref,text in evidence]))
 except Exception as e:result.update(status='failed',error_type=type(e).__name__)
 result['seconds']=round(time.perf_counter()-started,2);dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

def run():
 b.load_config();samples=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'));results=[]
 with cf.ThreadPoolExecutor(max_workers=3) as pool:
  for future in cf.as_completed([pool.submit(run_one,s) for s in samples]):
   r=future.result();results.append(r);print(json.dumps({'completed':len(results),'format':r['format'],'status':r['status'],'seconds':r['seconds']}),flush=True)
 (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 assert len(results)==200

if __name__=='__main__':
 if '--prepare' in sys.argv:prepare()
 if '--run' in sys.argv:run()
