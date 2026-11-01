"""Document privacy scan and irreversible selected-region redaction of copies."""
import hashlib
import io
import json
import uuid
from datetime import datetime,timezone
from ..privacy import analyze
from .documents import content_path,document_root,preview
from .file_validation import DocumentError

WEIGHTS={'id_card':40,'bank_card':40,'phone':20,'student_id':15,'name':10,'email':10,'address':25,'qrcode':15}


def qr_regions(raw,mime):
    import cv2
    import numpy as np
    from PIL import Image
    pages=[1]
    if mime=='application/pdf':
        import fitz
        with fitz.open(stream=raw,filetype='pdf') as pdf:pages=list(range(1,len(pdf)+1))
    result=[]
    for page in pages:
        image=np.array(Image.open(io.BytesIO(preview(raw,mime,page))).convert('RGB'))
        found,points=cv2.QRCodeDetector().detectMulti(image)
        if found:
            for box in points:result.append({'page':page,'bbox':[[float(x),float(y)] for x,y in box]})
    return result


def scan_document(c,owner_id,document_id):
    document=c.execute('SELECT * FROM documents WHERE id=? AND owner_id=?',(document_id,owner_id)).fetchone()
    if not document:raise DocumentError('DOCUMENT_NOT_FOUND','文档不存在',404)
    findings=[]
    for line in c.execute('SELECT * FROM document_lines WHERE document_id=? AND owner_id=? ORDER BY line_number',(document_id,owner_id)):
        for finding in analyze(line['text'])['findings']:
            finding_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{document_id}:{line["id"]}:{finding["start"]}:{finding["type"]}'))
            box=json.loads(line['bbox_json'] or 'null')
            item={'id':finding_id,'type':finding['type'],'label':finding['label'],'page':line['page'],'bbox':box,'coordinate_space':line['coordinate_space'],'preview':finding['redacted'],'line_id':line['id'],'location_quality':'line' if box else 'text_only'}
            c.execute('INSERT OR REPLACE INTO document_privacy_findings VALUES(?,?,?,?,?,?,?,?,?)',(finding_id,owner_id,document_id,document['revision'],line['id'],finding['type'],line['page'],json.dumps(box),finding['redacted']))
            findings.append(item)
    unsupported=['unlabelled_name','unlabelled_address']
    if document['mime'] in {'image/png','image/jpeg','application/pdf'}:
        try:
            raw=content_path(document_root(),owner_id,document_id).read_bytes()
            for index,region in enumerate(qr_regions(raw,document['mime'])):
                finding_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{document_id}:qr:{index}'))
                box=region['bbox'];page=region['page']
                c.execute('INSERT OR REPLACE INTO document_privacy_findings VALUES(?,?,?,?,?,?,?,?,?)',(finding_id,owner_id,document_id,document['revision'],f'qr:{index}','qrcode',page,json.dumps(box),'[二维码区域]'))
                findings.append({'id':finding_id,'type':'qrcode','label':'二维码','page':page,'bbox':box,'coordinate_space':'pdf_points' if document['mime']=='application/pdf' else 'image_pixels','preview':'[二维码区域]','location_quality':'region'})
        except Exception:unsupported.append('qrcode')
    kinds={item['type'] for item in findings};risk=min(100,sum(WEIGHTS.get(item['type'],10) for item in findings)+(25 if {'name','id_card'}<=kinds else 10 if {'name','phone'}<=kinds else 0))
    return {'document_id':document_id,'revision':document['revision'],'findings':findings,'risk_score':risk,'score_type':'heuristic','unsupported_types':unsupported,'persisted':True}


def rectangle(box):
    if not box:return None
    if isinstance(box[0],(int,float)):return tuple(box)
    return min(point[0] for point in box),min(point[1] for point in box),max(point[0] for point in box),max(point[1] for point in box)


def redact_copy(c,root,owner_id,document_id,finding_ids,revision):
    document=c.execute('SELECT * FROM documents WHERE id=? AND owner_id=?',(document_id,owner_id)).fetchone()
    if not document:raise DocumentError('DOCUMENT_NOT_FOUND','文档不存在',404)
    if document['revision']!=revision:raise DocumentError('REDACT_STALE','原件版本变化，请重新扫描',409)
    if not finding_ids or len(finding_ids)!=len(set(finding_ids)):raise DocumentError('REDACT_INVALID','请选择不重复的敏感项')
    selected=[]
    for finding_id in finding_ids:
        finding=c.execute('SELECT * FROM document_privacy_findings WHERE id=? AND owner_id=? AND document_id=? AND revision=?',(finding_id,owner_id,document_id,revision)).fetchone()
        if not finding:raise DocumentError('REDACT_INVALID','敏感项不属于当前文档')
        box=rectangle(json.loads(finding['bbox_json'] or 'null'))
        if not box:raise DocumentError('REDACT_LOCATION_MISSING','敏感项没有可靠坐标，暂不能生成区域脱敏文件')
        selected.append((finding,box))
    original=content_path(root,owner_id,document_id).read_bytes();mime=document['mime']
    if mime in {'image/png','image/jpeg'}:
        from PIL import Image,ImageOps,ImageDraw
        with Image.open(io.BytesIO(original)) as source:
            image=ImageOps.exif_transpose(source).convert('RGB');draw=ImageDraw.Draw(image)
            for finding,box in selected:draw.rectangle(box,fill='black')
            out=io.BytesIO();image.save(out,format='PNG');result=out.getvalue();result_mime='image/png'
    elif mime=='application/pdf':
        import fitz
        with fitz.open(stream=original,filetype='pdf') as pdf:
            for finding,box in selected:
                page=pdf[finding['page']-1];region=fitz.Rect(box)*page.derotation_matrix
                page.add_redact_annot(region,fill=(0,0,0))
            for page in pdf:
                page.apply_redactions(images=2,graphics=2,text=0)
            pdf.set_metadata({});result=pdf.tobytes(garbage=4,deflate=True);result_mime='application/pdf'
    else:raise DocumentError('REDACT_FORMAT_UNSUPPORTED','该格式仅支持文本级处理，不能生成图像脱敏副本')
    derivative_id=str(uuid.uuid4());target=content_path(root,owner_id,derivative_id);target.write_bytes(result)
    c.execute('INSERT INTO document_derivatives VALUES(?,?,?,?,?,?,?,?)',(derivative_id,owner_id,document_id,revision,result_mime,json.dumps(finding_ids),hashlib.sha256(result).hexdigest(),datetime.now(timezone.utc).isoformat()))
    return {'id':derivative_id,'document_id':document_id,'mime':result_mime,'sha256':hashlib.sha256(result).hexdigest(),'selected_finding_ids':finding_ids,'original_preserved':True}
