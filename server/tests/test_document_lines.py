import io
import sqlite3
import pytest
import fitz
from PIL import Image
from docx import Document
from app.parsing import parse_bytes
from app.services.file_validation import DocumentError,validate_file
from app.services.documents import content_path,store_document,normalize_lines,preview


def pdf_bytes(pages=1):
    document=fitz.open()
    for _ in range(pages):document.new_page().insert_text((40,60),'Submit form before 2026-10-25')
    raw=document.tobytes();document.close();return raw


def test_signature_extension_limits_and_pdf_pages_are_independent():
    for raw,mime,name in [(b'fake','application/pdf','notice.pdf'),(b'text','text/plain','notice.pdf'),(pdf_bytes(21),'application/pdf','notice.pdf')]:
        with pytest.raises(DocumentError):validate_file(raw,mime,name)
    validate_file(pdf_bytes(),'application/pdf','notice.pdf')
    with pytest.raises(DocumentError):content_path('/tmp/store','../other','file')
    document=fitz.open();document.new_page(width=10000,height=10000);raw=document.tobytes();document.close()
    with pytest.raises(DocumentError,match='像素'):validate_file(raw,'application/pdf','large.pdf')


def test_docx_tables_are_not_dropped():
    document=Document();document.add_paragraph('Notice');table=document.add_table(rows=1,cols=2)
    table.cell(0,0).text='Required form';table.cell(0,1).text='Deadline 2026-10-25'
    out=io.BytesIO();document.save(out)
    lines=parse_bytes(out.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    assert any('Required form' in line['text'] and '表格' in line['locator'] for line in lines)


def test_native_and_scanned_pdf_coordinates_use_display_page_points(monkeypatch):
    document=fitz.open();document.new_page().insert_text((40,60),'Native evidence');document.new_page()
    raw=document.tobytes();document.close()
    monkeypatch.setattr('app.parsing._ocr',lambda raw,locator,page:[{'text':'Scanned evidence','locator':locator,'page':page,'bbox':[[17,34],[51,34],[51,68],[17,68]],'confidence':0.8}])
    lines=parse_bytes(raw,'application/pdf')
    assert {line['page'] for line in lines}=={1,2}
    assert all(line['coordinate_space']=='pdf_points' and line['page_width']>0 for line in lines)
    scanned=next(line for line in lines if line['page']==2)
    assert scanned['bbox'][0][0]==pytest.approx(10,abs=.1)
    assert lines[0]['confidence'] is None
    assert preview(raw,'application/pdf',2).startswith(b'\x89PNG')


def test_rotated_pdf_boxes_are_in_preview_coordinate_space():
    document=fitz.open();page=document.new_page();page.insert_text((40,60),'Evidence');page.set_rotation(90)
    raw=document.tobytes();document.close()
    line=parse_bytes(raw,'application/pdf')[0]
    image=Image.open(io.BytesIO(preview(raw,'application/pdf')))
    assert (image.width,image.height)==(int(line['page_width']),int(line['page_height']))
    assert 0<=line['bbox'][0]<line['bbox'][2]<=line['page_width']


@pytest.mark.parametrize('rotation',[0,90])
def test_same_page_native_and_image_region_are_both_kept(monkeypatch,rotation):
    image=io.BytesIO();Image.new('RGB',(100,50),'white').save(image,format='PNG')
    document=fitz.open();page=document.new_page(width=300,height=400);page.insert_text((20,30),'Native title')
    page.insert_image(fitz.Rect(40,100,140,150),stream=image.getvalue());page.set_rotation(rotation)
    raw=document.tobytes();document.close()
    monkeypatch.setattr('app.parsing._ocr',lambda raw,locator,page:[{'text':'Image deadline','locator':locator,'page':page,'bbox':[[0,0],[10,0],[10,10],[0,10]],'confidence':.9}])
    lines=parse_bytes(raw,'application/pdf')
    assert {line['text'] for line in lines}=={'Native title','Image deadline'}
    scanned=next(line for line in lines if line['confidence'])
    assert '图片区域' in scanned['locator']
    assert all(0<=x<=scanned['page_width'] and 0<=y<=scanned['page_height'] for x,y in scanned['bbox'])


def test_normalization_keeps_stable_ids_and_does_not_fabricate_boxes():
    blocks=[{'text':'First\nSecond','locator':'正文','page':None}]
    one=normalize_lines(blocks,'doc');assert one==normalize_lines(blocks,'doc')
    assert len(one)==2 and one[0]['id']!=one[1]['id']
    assert not any(line.get('bbox') for line in one)


def test_parse_failure_keeps_original_without_sensitive_error_text(tmp_path):
    connection=sqlite3.connect(':memory:')
    connection.executescript('CREATE TABLE documents(id,owner_id,name,mime,sha256,size,status,error_code,created_at,revision); CREATE TABLE document_lines(id,owner_id,document_id,line_number,page,text,locator,bbox_json,coordinate_space,page_width,page_height,confidence);')
    def failing(*args):raise ValueError('private original content')
    result=store_document(connection,tmp_path,'owner',b'Original notice','text/plain','notice.txt',failing)
    assert result['status']=='failed' and result['error_code']=='DOCUMENT_PARSE_FAILED'
    assert content_path(tmp_path,'owner',result['id']).read_bytes()==b'Original notice'
    assert 'private' not in str(connection.execute('SELECT error_code FROM documents').fetchone())
    connection.close()


def test_demo_reset_deletes_only_the_selected_owners_originals(tmp_path,monkeypatch):
    from dataclasses import replace
    from app import settings
    from app.demo import reset
    demo=tmp_path/'demo';real=tmp_path/'real'
    configured=replace(settings.SETTINGS,demo_mode=True,demo_upload_root=demo,vault_upload_root=real/'vault')
    monkeypatch.setattr(settings,'SETTINGS',configured);monkeypatch.setattr(reset,'SETTINGS',configured)
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT',str(real/'documents'));monkeypatch.setenv('DEMO_DOCUMENT_ROOT',str(demo/'documents'))
    for root in (demo/'owner',demo/'documents'/'owner',demo/'documents'/'other',real/'documents'/'owner'):
        root.mkdir(parents=True);(root/'original').write_bytes(b'fixture')
    reset._delete_uploads('owner')
    assert not (demo/'documents'/'owner').exists()
    assert (demo/'documents'/'other'/'original').exists() and (real/'documents'/'owner'/'original').exists()
