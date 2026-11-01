import io
import fitz
from PIL import Image
from test_api import client,account,head
from app.main import database
database()


def test_pdf_redaction_removes_text_layer_keeps_original_and_rejects_foreign_findings(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT',str(tmp_path))
    pdf=fitz.open();pdf.new_page().insert_text((40,60),'Phone 13812345678');original=pdf.tobytes();pdf.close()
    a,b=account('redact-pdf@example.com'),account('redact-pdf-other@example.com')
    imported=client.post('/api/v1/imports/files',headers=head(a),data={'consent':'true'},files={'files':('notice.pdf',original,'application/pdf')}).json()['data'][0]
    document_id=imported['document_id'];path='/api/v1/documents/'+document_id
    scan=client.post(path+'/privacy/scan',headers=head(a)).json()['data']
    assert len(scan['findings'])==1 and 'original' not in scan['findings'][0]
    body={'revision':1,'finding_ids':[scan['findings'][0]['id']],'consent':True}
    assert client.post(path+'/redact',headers=head(a),json={**body,'consent':False}).status_code==422
    assert client.post(path+'/redact',headers=head(a),json={**body,'revision':99}).status_code==409
    assert client.post(path+'/redact',headers=head(b),json=body).status_code==404
    result=client.post(path+'/redact',headers=head(a),json=body).json()['data']
    content=client.get('/api/v1/document-copies/'+result['id']+'/content',headers=head(a)).content
    with fitz.open(stream=content,filetype='pdf') as redacted:assert '13812345678' not in ''.join(page.get_text() for page in redacted)
    assert client.get(path+'/content',headers=head(a)).content==original
    assert client.get('/api/v1/document-copies/'+result['id']+'/content',headers=head(b)).status_code==404


def test_image_copy_masks_selected_pixels_without_changing_original(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT',str(tmp_path))
    monkeypatch.setattr('app.parsing._ocr',lambda *args:[{'text':'电话13812345678','locator':'图片 OCR','page':1,'bbox':[[10,10],[90,10],[90,30],[10,30]],'confidence':.9,'coordinate_space':'image_pixels','page_width':100,'page_height':50}])
    out=io.BytesIO();Image.new('RGB',(100,50),'white').save(out,'PNG');original=out.getvalue()
    a=account('redact-image@example.com')
    document_id=client.post('/api/v1/imports/files',headers=head(a),data={'consent':'true'},files={'files':('notice.png',original,'image/png')}).json()['data'][0]['document_id']
    scan=client.post(f'/api/v1/documents/{document_id}/privacy/scan',headers=head(a)).json()['data']
    result=client.post(f'/api/v1/documents/{document_id}/redact',headers=head(a),json={'revision':1,'finding_ids':[scan['findings'][0]['id']],'consent':True}).json()['data']
    content=client.get('/api/v1/document-copies/'+result['id']+'/content',headers=head(a)).content
    image=Image.open(io.BytesIO(content));assert image.getpixel((20,20))==(0,0,0) and image.getpixel((0,0))==(255,255,255)
    assert client.get(f'/api/v1/documents/{document_id}/content',headers=head(a)).content==original


def test_text_only_locations_are_not_used_as_fake_image_coordinates(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT',str(tmp_path));a=account('redact-text@example.com')
    document_id=client.post('/api/v1/imports/files',headers=head(a),data={'consent':'true'},files={'files':('notice.txt',b'13812345678','text/plain')}).json()['data'][0]['document_id']
    scan=client.post(f'/api/v1/documents/{document_id}/privacy/scan',headers=head(a)).json()['data']
    response=client.post(f'/api/v1/documents/{document_id}/redact',headers=head(a),json={'revision':1,'finding_ids':[scan['findings'][0]['id']],'consent':True})
    assert response.status_code==422 and response.json()['detail']['code']=='REDACT_LOCATION_MISSING'


def test_vault_upload_requires_explicit_privacy_confirmation():
    a=account('vault-consent@example.com')
    result=client.post('/api/v1/vault/items',headers=head(a),files={'file':('test.txt',b'content','text/plain')})
    assert result.status_code==422 and result.json()['detail']['code']=='CONFIRMATION_REQUIRED'


def test_qr_detection_returns_regions_without_decoding_private_payload():
    import cv2
    from app.services.redaction import qr_regions
    qr=cv2.QRCodeEncoder_create().encode('https://example.com/private')
    image=cv2.copyMakeBorder(qr,8,8,8,8,cv2.BORDER_CONSTANT,value=255)
    image=cv2.resize(image,(300,300),interpolation=cv2.INTER_NEAREST)
    ok,encoded=cv2.imencode('.png',image)
    regions=qr_regions(bytes(encoded),'image/png')
    assert ok and regions and len(regions[0]['bbox'])==4
    assert 'private' not in str(regions)
