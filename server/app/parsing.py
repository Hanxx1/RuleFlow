"""Bounded local parsers; callers persist only extracted blocks after consent."""
from __future__ import annotations
import io,ipaddress,socket,os
from urllib.parse import urlparse
from urllib.request import getproxies
from bs4 import BeautifulSoup
from docx import Document
from openpyxl import load_workbook

MAX_TEXT=500_000

def html_blocks(raw):
 soup=BeautifulSoup(raw,'html.parser')
 for element in soup.select('script,style,nav,footer,form'):element.decompose()
 content=None
 for selector in ('.v_news_content','.wp_articlecontent','.article-content','.news-content','.entry-content','article','main'):
  content=soup.select_one(selector)
  if content is not None:break
 content=content if content is not None else soup.body or soup
 for br in content.find_all('br'):br.replace_with('\n')
 tags={'p','li','tr','h1','h2','h3','h4','blockquote','pre'}
 out=[]
 for block in content.find_all(list(tags)):
  if any(parent.name in tags for parent in block.parents if parent is not content):continue
  text=block.get_text('',strip=False).strip()
  if block.name=='tr':text='\t'.join(cell.get_text('',strip=False).strip() for cell in block.find_all(['td','th']))
  if text:out.append({'text':_text(text),'locator':f'HTML正文段落 {len(out)+1}','page':None})
 if not out:
  text=content.get_text('',strip=False).strip()
  if text:out=[{'text':_text(text),'locator':'HTML 正文','page':None}]
 return out
def _text(x:str)->str:return x[:MAX_TEXT]
def _ocr(raw:bytes,locator='图片 OCR',page=None):
 from rapidocr_onnxruntime import RapidOCR
 import numpy as np
 from PIL import Image,ImageOps
 with Image.open(io.BytesIO(raw)) as original:image=np.array(ImageOps.exif_transpose(original).convert('RGB'))
 engine=RapidOCR(intra_op_num_threads=max(1,min(2,os.cpu_count() or 1)),inter_op_num_threads=1);result,_=engine(image)
 # Quarter-turn photographs need page orientation correction, not just EXIF handling.
 def vertical(row):
  points=np.asarray(row[0]);return np.ptp(points[:,1])>np.ptp(points[:,0])*1.5
 if result and sum(vertical(row) for row in result)>len(result)/2:
  def score(rows):return sum(len(str(row[1]))*float(row[2]) for row in rows or []) / max(1,len(rows or []))**.5
  best=result;best_score=score(result)
  for turns in (1,3):
   rotated=np.rot90(image,turns).copy();candidate,_=engine(rotated)
   if candidate and score(candidate)>best_score:
    mapped=[]
    for points,text,confidence in candidate:
     original_points=[([image.shape[1]-1-y,x] if turns==1 else [y,image.shape[0]-1-x]) for x,y in points]
     mapped.append([original_points,text,confidence])
    best=mapped;best_score=score(candidate)
  result=best
 dimensions={'coordinate_space':'image_pixels','page_width':int(image.shape[1]),'page_height':int(image.shape[0])}
 if not result:return [{'text':'','locator':locator,'page':page,'bbox':None,'confidence':None,**dimensions}]
 return [{'text':_text(str(row[1])),'locator':locator,'page':page or 1,'bbox':[[float(x),float(y)] for x,y in row[0]],'confidence':float(row[2]),**dimensions} for row in result if float(row[2])>=0.35]
def parse_bytes(raw:bytes,mime:str,name:str='') -> list[dict]:
 if mime=='text/plain': return [{'text':_text(raw.decode('utf-8','replace')),'locator':'全文','page':None}]
 if mime=='application/pdf':
  import fitz
  from .services.file_validation import validate_file
  validate_file(raw,mime)
  out=[]
  with fitz.open(stream=raw,filetype='pdf') as doc:
   for i,p in enumerate(doc):
    native=[]
    for block in p.get_text('dict')['blocks']:
     for line in block.get('lines',[]):
      text=''.join(span['text'] for span in line['spans']).strip()
      if text:
       box=fitz.Rect(line['bbox'])*p.rotation_matrix
       native.append({'text':_text(text),'locator':f'第 {i+1} 页','page':i+1,'bbox':list(box),'confidence':None,'coordinate_space':'pdf_points','page_width':p.rect.width,'page_height':p.rect.height})
    if native:
     out.extend(sorted(native,key=lambda line:(line['bbox'][1],line['bbox'][0])))
     regions=p.get_image_info()
     if len(regions)>16:raise ValueError('PDF_IMAGE_REGION_BUDGET')
     for image in regions:
      region=(fitz.Rect(image['bbox'])*p.rotation_matrix)&p.rect
      if region.is_empty or region.width<20 or region.height<20:continue
      pix=p.get_pixmap(matrix=fitz.Matrix(1.7,1.7),clip=region,alpha=False)
      for line in _ocr(pix.tobytes('png'),f'第 {i+1} 页图片区域 OCR',i+1):
       if not line.get('text','').strip():continue
       if line.get('bbox'):line['bbox']=[[region.x0+x*region.width/pix.width,region.y0+y*region.height/pix.height] for x,y in line['bbox']]
       line.update(coordinate_space='pdf_points',page_width=p.rect.width,page_height=p.rect.height)
       out.append(line)
    else:
     pix=p.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False)
     for line in _ocr(pix.tobytes('png'),f'第 {i+1} 页 OCR',i+1):
      if line.get('bbox'):line['bbox']=[[x*p.rect.width/pix.width,y*p.rect.height/pix.height] for x,y in line['bbox']]
      line.update(coordinate_space='pdf_points',page_width=p.rect.width,page_height=p.rect.height)
      out.append(line)
  return out
 if mime.endswith('wordprocessingml.document'):
  d=Document(io.BytesIO(raw));out=[{'text':_text(p.text),'locator':f'段落 {index+1}','page':None} for index,p in enumerate(d.paragraphs) if p.text.strip()]
  for index,table in enumerate(d.tables):
   for row_index,row in enumerate(table.rows):
    out.append({'text':_text('\t'.join(cell.text for cell in row.cells)),'locator':f'表格 {index+1} 行 {row_index+1}','page':None})
  return out
 if mime.endswith('spreadsheetml.sheet'):
  wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True);out=[]
  for ws in wb.worksheets:out.append({'text':_text('\n'.join('\t'.join('' if v is None else str(v) for v in row) for row in ws.iter_rows(values_only=True))),'locator':ws.title,'page':None})
  return out
 if mime=='application/vnd.ms-excel' or name.lower().endswith('.xls'):
  import xlrd
  book=xlrd.open_workbook(file_contents=raw);out=[]
  for sheet in book.sheets():out.append({'text':_text('\n'.join('\t'.join(str(sheet.cell_value(r,c)) for c in range(sheet.ncols)) for r in range(sheet.nrows))),'locator':sheet.name,'page':None})
  return out
 if mime in {'text/html','application/xhtml+xml'}:return html_blocks(raw)
 if mime in {'image/png','image/jpeg'}:return _ocr(raw)
 raise ValueError('unsupported_format')
class HostResolutionError(ValueError):pass
class UnsafeHostError(ValueError):pass

_PROXY_SYNTHETIC=ipaddress.ip_network('198.18.0.0/15')

def local_proxy_for(scheme:str)->bool:
 """Return whether requests for this scheme go through a loopback proxy.

 Some mobile-development proxy tools deliberately return RFC 2544 benchmark
 addresses for public hostnames and resolve the real address inside the local
 proxy. This is not equivalent to allowing a reserved IP literal: only a DNS
 name, an all-synthetic answer and an active loopback proxy qualify.
 """
 proxies=getproxies();value=proxies.get(scheme) or proxies.get('all')
 if not value:return False
 host=(urlparse(value).hostname or '').lower()
 if host=='localhost':return True
 try:return ipaddress.ip_address(host).is_loopback
 except ValueError:return False

def resolve_public_host(host:str,allow_proxy_synthetic:bool=False):
 normalized=host.strip().rstrip('.').lower()
 if not normalized or normalized=='localhost' or normalized.endswith('.localhost') or normalized.endswith('.local'):raise UnsafeHostError('local hostname')
 try:
  literal=ipaddress.ip_address(normalized)
 except ValueError:literal=None
 if literal is not None:
  if not literal.is_global:raise UnsafeHostError(str(literal))
  return [literal]
 try:rows=socket.getaddrinfo(normalized,None,type=socket.SOCK_STREAM)
 except OSError as exc:raise HostResolutionError(normalized) from exc
 addresses=[]
 for row in rows:
  try:address=ipaddress.ip_address(row[4][0].split('%',1)[0])
  except ValueError:continue
  if address not in addresses:addresses.append(address)
 if not addresses:raise HostResolutionError(normalized)
 if all(address.is_global for address in addresses):return addresses
 if allow_proxy_synthetic and all(address.version==4 and address in _PROXY_SYNTHETIC for address in addresses):return addresses
 raise UnsafeHostError(','.join(str(address) for address in addresses if not address.is_global))

def safe_host(host:str):
 try:resolve_public_host(host)
 except (HostResolutionError,UnsafeHostError):return False
 return True
