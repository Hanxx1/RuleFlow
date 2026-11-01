from test_api import client,account,head,confirm_import

def test_attachment_upload_is_owner_scoped_and_invalidates_old_review():
    a=account('case-attachment-a@example.com');b=account('case-attachment-b@example.com');h=head(a)
    imported=client.post('/api/v1/imports/text',headers=h,json={'text':'请填写附件1申请表。','consent':True}).json()['data'];cid=imported['case_id'];confirm_import(a,cid)
    before=client.get('/api/v1/cases/'+cid+'/resources',headers=h).json()['data'];assert before['attachments']['missing_count']==1
    files={'file':('附件1申请表.txt','申请表内容：请填写基本信息。'.encode(),'text/plain')}
    url='/api/v1/cases/'+cid+'/attachments'
    assert client.post(url,headers=head(b),files=files,data={'consent':'true'}).status_code==404
    assert client.post(url,headers=h,files=files).status_code==422
    assert client.post(url,headers=h,files=files,data={'consent':'true'}).status_code==200
    after=client.get('/api/v1/cases/'+cid+'/resources',headers=h).json()['data'];assert after['attachments']['missing_count']==0
    assert client.get('/api/v1/cases/'+cid+'/reviews',headers=h).json()['data']['status']=='needs_confirmation'
