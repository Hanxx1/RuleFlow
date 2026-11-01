import io
from PIL import Image
from helpers import client,account,head


def test_batch_image_keeps_original_and_owner_scoped_line_evidence(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT',str(tmp_path))
    monkeypatch.setattr('app.parsing._ocr',lambda *args:[{'text':'请填写申请表。','locator':'图片 OCR','page':1,'bbox':[[10,10],[100,10],[100,30],[10,30]],'confidence':0.8,'coordinate_space':'image_pixels','page_width':120,'page_height':60}])
    out=io.BytesIO();Image.new('RGB',(120,60),'white').save(out,'PNG');original=out.getvalue()
    a,b=account('doc-image-a@example.com'),account('doc-image-b@example.com')
    batch=client.post('/api/v1/import-batches',headers=head(a),json={}).json()['data']
    path='/api/v1/import-batches/'+batch['id']+'/sources/files'
    denied=client.post(path,headers=head(a),files={'files':('notice.png',original,'image/png')})
    assert denied.status_code==422 and list(tmp_path.iterdir())==[]
    sources=client.post(path,headers=head(a),data={'consent':'true'},files={'files':('notice.png',original,'image/png')}).json()['data']
    document_id=sources[0]['metadata']['document_id']
    detail=client.get('/api/v1/documents/'+document_id,headers=head(a)).json()['data']
    assert detail['status']=='parsed' and len(detail['lines'])==1 and 'owner_id' not in detail
    assert client.get('/api/v1/documents/'+document_id+'/content',headers=head(a)).content==original
    assert client.delete('/api/v1/documents/'+document_id,headers=head(a)).status_code==409
    for suffix in ('','/content','/pages/1'):
        assert client.get('/api/v1/documents/'+document_id+suffix,headers=head(b)).status_code==404
    assert client.get('/api/v1/documents/'+document_id+'/pages/2',headers=head(a)).status_code==422
    client.post('/api/v1/import-batches/'+batch['id']+'/analyze',headers=head(a))
    from app.auth import conn
    with conn() as connection:case_id=connection.execute('SELECT case_id FROM import_batches WHERE id=?',(batch['id'],)).fetchone()[0]
    evidence=client.get('/api/v1/cases/'+case_id+'/resources',headers=head(a)).json()['data']['evidence'][0]
    assert evidence['document_id']==document_id and evidence['bbox'][0]==[10,10] and evidence['page']==1
    assert evidence['preview_available'] is True and evidence['ocr_confidence']==0.8
    preview=client.get('/api/v1/documents/'+document_id+'/pages/1',headers=head(a))
    assert preview.headers['cache-control']=='no-store' and preview.content.startswith(b'\x89PNG')


def test_failed_original_can_be_downloaded_and_explicitly_deleted(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT',str(tmp_path))
    monkeypatch.setattr('app.main.parse_bytes',lambda *args:[])
    a,b=account('doc-failed@example.com'),account('doc-failed-other@example.com')
    result=client.post('/api/v1/imports/files',headers=head(a),data={'consent':'true'},files={'files':('empty-text.txt',b'Original kept','text/plain')}).json()['data'][0]
    document_id=result['document_id'];url='/api/v1/documents/'+document_id
    assert result['error_code']=='OCR_EMPTY'
    assert client.get(url+'/content',headers=head(a)).content==b'Original kept'
    assert client.delete(url,headers=head(b)).status_code==404
    assert client.delete(url,headers=head(a)).status_code==200
    assert client.get(url,headers=head(a)).status_code==404
    assert not list(tmp_path.rglob(document_id))


def test_legacy_file_entry_also_binds_lines_and_rejects_disguised_files(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT',str(tmp_path))
    a=account('doc-file-entry@example.com')
    result=client.post('/api/v1/imports/files',headers=head(a),data={'consent':'true'},files={'files':('notice.txt','请填写申请表。\n请上传作品。'.encode(),'text/plain')}).json()['data'][0]
    assert result['blocks']==2 and result['document_id']
    evidence=client.get('/api/v1/cases/'+result['case_id']+'/resources',headers=head(a)).json()['data']['evidence']
    assert len(evidence)==2 and len({item['line_id'] for item in evidence})==2
    bad=client.post('/api/v1/imports/files',headers=head(a),data={'consent':'true'},files={'files':('fake.pdf',b'not PDF','application/pdf')}).json()['data'][0]
    assert bad['error_code']=='FILE_CORRUPTED' and bad['document_id'] is None
