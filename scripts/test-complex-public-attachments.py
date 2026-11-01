"""Generated format stress cases using public text; not original attachments."""
import json,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageEnhance,ImageFilter
import fitz
from docx import Document
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'server'))
from app.parsing import parse_bytes
from app.services.date_candidates import extract_dates
out=ROOT/'.runtime/complex-attachments';out.mkdir(parents=True,exist_ok=True)
source=ROOT/'.runtime/public-notice-benchmark/multi_deadline.txt'
lines=[s for s in source.read_text(encoding='utf-8').splitlines() if s.startswith('2026 ')][:4]
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',32)
im=Image.new('RGB',(1600,400),'white');ImageDraw.Draw(im).multiline_text((30,30),'\n'.join(lines),font=font,fill='black',spacing=30)
cases=[]
for name,image in [('clear',im),('low-contrast',ImageEnhance.Contrast(im).enhance(.35)),('blur',im.filter(ImageFilter.GaussianBlur(1.1))),('skew',im.rotate(3,fillcolor='white')),('rotated',im.rotate(90,expand=True)),('small',im.resize((800,200)))]:
 p=out/(name+'.png');image.save(p);cases.append((p,'image/png'))
for kind in ['scanned','mixed']:
 pdf=fitz.open();page=pdf.new_page(width=800,height=400)
 if kind=='mixed':page.insert_text((30,30),'PUBLIC TEST ATTACHMENT',fontsize=12)
 page.insert_image(fitz.Rect(0,70,800,270),filename=str(out/'clear.png'))
 p=out/(kind+'.pdf');pdf.save(p);pdf.close();cases.append((p,'application/pdf'))
doc=Document();table=doc.add_table(rows=0,cols=2)
for line in lines:
 cells=table.add_row().cells;parts=line.split('，',1);cells[0].text=parts[0];cells[1].text=parts[1] if len(parts)>1 else ''
p=out/'table.docx';doc.save(p);cases.append((p,'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
results=[]
expected={'2026-01-15','2026-01-31','2026-03-31','2026-05-31'}
for path,mime in cases:
 try:
  blocks=parse_bytes(path.read_bytes(),mime,path.name)
  dates=extract_dates([('block:test:'+str(i),b['text']) for i,b in enumerate(blocks)])
  found={d['value'] for d in dates if d['role']=='deadline'}
  result={'case':path.name,'status':'complete' if expected<=found else 'needs_review','recognized_deadlines':sorted(d for d in found if d),'missing':sorted(expected-found),'located_blocks':sum(bool(b.get('bbox')) for b in blocks),'block_count':len(blocks)}
 except Exception as e:result={'case':path.name,'status':'failed','error_type':type(e).__name__}
 results.append(result);print(json.dumps(result),flush=True)
(out/'report.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
