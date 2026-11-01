from app.services.link_candidates import attachments
from helpers import client, account, head


def test_link_discovery_is_bounded_and_does_not_fetch():
    raw = b'<a href="/a.pdf?download=1">Form</a><a href="/a.pdf?download=1">duplicate</a><a href="javascript:alert(1)">X</a><a href="https://user:pw@example.com/b.docx">private</a>'
    assert attachments(raw,'text/html','https://example.com/news') == [{'url':'https://example.com/a.pdf?download=1','title':'Form','state':'requires_confirmation'}]


def test_attachment_requires_separate_consent_and_records_parent(monkeypatch):
    calls=[]
    def fetch(url):
        calls.append(url)
        return (b'<a href="/form.txt">application form</a>notice' if url.endswith('/news') else b'please submit form','text/html' if url.endswith('/news') else 'text/plain',url)
    monkeypatch.setattr('app.main.fetch_public',fetch)
    a,b=account('link-parent@example.com'),account('link-other@example.com')
    batch=client.post('/api/v1/import-batches',headers=head(a),json={}).json()['data']
    source=client.post('/api/v1/import-batches/'+batch['id']+'/sources/url',headers=head(a),json={'url':'https://example.com/news','consent':True}).json()['data']
    assert calls==['https://example.com/news'] and source['metadata']['document_id']
    url='/api/v1/import-batches/'+batch['id']+'/sources/'+source['id']+'/attachments'
    assert client.post(url,headers=head(a),json={'index':0}).status_code==422
    assert client.post(url,headers=head(b),json={'index':0,'consent':True}).status_code==404
    result=client.post(url,headers=head(a),json={'index':0,'consent':True}).json()['data']
    assert result['metadata']['parent_source_id']==source['id'] and result['metadata']['document_id']
    assert calls==['https://example.com/news','https://example.com/form.txt']
def test_dynamic_download_endpoint_is_discovered_from_attachment_filename():
    result=attachments(b'<a href="/download.jsp?id=5">policy.pdf</a><a href="javascript:alert(1)">bad.pdf</a>','text/html','https://example.com/notice')
    assert len(result)==1 and result[0]['url']=='https://example.com/download.jsp?id=5'
