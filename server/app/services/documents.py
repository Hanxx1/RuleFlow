"""Original storage, normalized lines and owner-scoped evidence binding."""
import hashlib
import io
import json
import uuid
from datetime import datetime,timezone
from pathlib import Path
from .file_validation import DocumentError,validate_file


def document_root():
    from ..settings import SETTINGS
    import os
    real=Path(os.getenv('DOCUMENT_UPLOAD_ROOT',str(SETTINGS.vault_upload_root.parent/'document_uploads'))).resolve()
    demo=Path(os.getenv('DEMO_DOCUMENT_ROOT',str(SETTINGS.demo_upload_root/'documents'))).resolve()
    if real==demo or real in demo.parents or demo in real.parents:raise RuntimeError('Demo and Real document roots must be disjoint')
    return demo if SETTINGS.demo_mode else real


def content_path(root,owner_id,document_id):
    # Use only server-issued identifiers, never a filename or request path.
    if not owner_id or any(char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for char in owner_id+document_id):
        raise DocumentError('DOCUMENT_KEY_INVALID','文档标识无效')
    root=Path(root).resolve();target=(root/owner_id/document_id).resolve()
    if root not in target.parents:raise DocumentError('DOCUMENT_KEY_INVALID','文档路径无效')
    return target


def normalize_lines(blocks,document_id):
    lines=[];total=0
    for block in blocks:
        texts=[block.get('text','')] if block.get('bbox') else block.get('text','').splitlines()
        for text in texts:
            if not text.strip():continue
            index=len(lines)+1
            total+=len(text)
            if index>5000 or total>500000:
                raise DocumentError('DOCUMENT_TOO_COMPLEX','文档文字或行数超过处理预算')
            lines.append({**block,'id':str(uuid.uuid5(uuid.NAMESPACE_URL,f'{document_id}:line:{index}')),'line_number':index,'text':text.strip()})
    return lines


def store_document(c,root,owner_id,raw,mime,name,parser):
    validate_file(raw,mime,name)
    document_id=str(uuid.uuid4());target=content_path(root,owner_id,document_id)
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    now=datetime.now(timezone.utc).isoformat()
    try:
        lines=normalize_lines(parser(raw,mime,name),document_id)
        status,error=('parsed',None) if lines else ('failed','OCR_EMPTY')
    except DocumentError as exc:lines=[];status,error='failed',exc.code
    except Exception:lines=[];status,error='failed','DOCUMENT_PARSE_FAILED'
    try:
        c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',(document_id,owner_id,name,mime,hashlib.sha256(raw).hexdigest(),len(raw),status,error,now,1))
        for line in lines:
            c.execute('INSERT INTO document_lines VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(line['id'],owner_id,document_id,line['line_number'],line.get('page'),line['text'],line.get('locator'),json.dumps(line.get('bbox')),line.get('coordinate_space'),line.get('page_width'),line.get('page_height'),line.get('confidence')))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {'id':document_id,'status':status,'error_code':error,'lines':lines}


def bind_document(c,owner_id,case_id,document_id,source_name):
    if not c.execute('SELECT 1 FROM cases WHERE id=? AND owner_id=?',(case_id,owner_id)).fetchone():
        raise DocumentError('CASE_NOT_FOUND','事项不存在',404)
    rows=c.execute('SELECT * FROM document_lines WHERE owner_id=? AND document_id=? ORDER BY line_number',(owner_id,document_id)).fetchall()
    if not c.execute('SELECT 1 FROM documents WHERE id=? AND owner_id=?',(document_id,owner_id)).fetchone():
        raise DocumentError('DOCUMENT_NOT_FOUND','文档不存在',404)
    evidence=[]
    for row in rows:
        evidence_id='block:'+str(uuid.uuid5(uuid.NAMESPACE_URL,f'{case_id}:{row["id"]}'))
        c.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?)',(evidence_id,owner_id,case_id,source_name,row['text'],row['locator'],row['page'],datetime.now(timezone.utc).isoformat()))
        c.execute('INSERT OR IGNORE INTO evidence_lines VALUES(?,?,?,?)',(owner_id,evidence_id,document_id,row['id']))
        evidence.append((evidence_id,row['text']))
    return evidence


def preview(raw,mime,page=1):
    if mime.startswith('image/') and page==1:
        from PIL import Image,ImageOps
        with Image.open(io.BytesIO(raw)) as image:
            out=io.BytesIO();ImageOps.exif_transpose(image).convert('RGB').save(out,format='PNG');return out.getvalue()
    if mime=='application/pdf':
        import fitz
        with fitz.open(stream=raw,filetype='pdf') as document:
            if page<1 or page>len(document):raise DocumentError('DOCUMENT_PAGE_NOT_FOUND','页码不存在',404)
            return document[page-1].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).tobytes('png')
    raise DocumentError('DOCUMENT_PREVIEW_UNAVAILABLE','该格式提供文字定位，暂无图像预览',422)
