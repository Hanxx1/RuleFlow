from test_api import client,account,head
from app.main import database
database()


def test_real_import_search_owner_citations_attach_and_delete(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT',str(tmp_path))
    a,b=account('knowledge-stage-a@example.com'),account('knowledge-stage-b@example.com')
    body={'title':'新奖学金细则','text':'本奖学金申请条件为专业排名前20%。请提交奖学金申请表。','consent':True}
    assert client.post('/api/v1/knowledge/text',headers=head(a),json={**body,'consent':False}).status_code==422
    imported=client.post('/api/v1/knowledge/text',headers=head(a),json=body).json()['data']
    searched=client.post('/api/v1/knowledge/search',headers=head(a),json={'query':'奖学金专业排名'}).json()['data']
    assert searched['items'] and searched['items'][0]['quote']==body['text']
    assert client.post('/api/v1/knowledge/search',headers=head(b),json={'query':'奖学金专业排名'}).json()['data']['items']==[]
    assert client.post('/api/v1/knowledge/ask',headers=head(a),json={'query':'火星飞船发动机'}).json()['data']['has_enough_evidence'] is False
    chunk=searched['items'][0];assert chunk['reference']['document_id']==imported['document_id']
    case_id=client.post('/api/v1/imports/text',headers=head(a),json={'text':'奖学金申请，请填写申请表，资格详见新奖学金细则。','consent':True}).json()['data']['case_id']
    url=f"/api/v1/cases/{case_id}/knowledge/{chunk['id']}/attach"
    assert client.post(url,headers=head(b),json={'consent':True}).status_code==404
    assert client.post(url,headers=head(a),json={'consent':False}).status_code==422
    assert client.post(url,headers=head(a),json={'consent':True}).json()['data']['already_attached'] is False
    assert client.post(url,headers=head(a),json={'consent':True}).json()['data']['already_attached'] is True
    outcome=client.get(f'/api/v1/cases/{case_id}/evaluate',headers=head(a)).json()['data']
    assert outcome['missing_profile_fields']==['profile.rank_percent']
    assert client.delete('/api/v1/knowledge/documents/'+imported['id'],headers=head(b)).status_code==404
    assert client.delete('/api/v1/knowledge/documents/'+imported['id'],headers=head(a)).status_code==200
    assert client.post('/api/v1/knowledge/search',headers=head(a),json={'query':'奖学金'}).json()['data']['items']==[]
    assert client.get(f'/api/v1/cases/{case_id}/resources',headers=head(a)).json()['data']['evidence'][-1]['text']==body['text']
    assert client.delete('/api/v1/documents/'+imported['document_id'],headers=head(a)).status_code==409
