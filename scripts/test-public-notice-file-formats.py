"""Render already-captured public text into synthetic test files, then parse them."""
import json,math,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import fitz
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from app.parsing import parse_bytes
from app.services.date_candidates import extract_dates
root=ROOT/'.runtime/public-notice-benchmark'
text='\n'.join(line for line in (root/'multi_deadline.txt').read_text(encoding='utf-8').splitlines() if line.startswith('2026 '))
font_path='C:/Windows/Fonts/msyh.ttc';font=ImageFont.truetype(font_path,24)
width=math.ceil(max(font.getlength(line) for line in text.splitlines()))+60
height=len(text.splitlines())*48+60
assert width*height<20_000_000
image=Image.new('RGB',(width,height),'white');ImageDraw.Draw(image).multiline_text((30,30),text,font=font,fill='black',spacing=18)
image.save(root/'public-notice-test.png')
pdf_width=width+200  # PDF font metrics differ from Pillow; preserve complete source clauses.
pdf=fitz.open();page=pdf.new_page(width=pdf_width,height=height);page.insert_font(fontname='notice',fontfile=font_path)
assert page.insert_textbox(fitz.Rect(30,30,pdf_width-30,height-30),text,fontname='notice',fontsize=24)>=0
pdf.save(root/'public-notice-test.pdf');pdf.close()
result=[]
for name,mime in [('public-notice-test.png','image/png'),('public-notice-test.pdf','application/pdf')]:
 lines=parse_bytes((root/name).read_bytes(),mime,name)
 dates=extract_dates([('block:file:'+str(index),line['text']) for index,line in enumerate(lines)])
 found={date['value'] for date in dates if date['role']=='deadline'}
 assert {'2026-01-15','2026-01-31','2026-03-31','2026-05-31'}<=found
 assert all(line.get('bbox') for line in lines if line['text'].strip())
 result.append({'file':name,'source':'public text converted for test; not official attachment','line_count':len(lines),'located_lines':sum(bool(line.get('bbox')) for line in lines),'deadlines':sorted(found)})
(root/'file-format-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
