"""Existing source/Document guarantees for RF-013; no proposed handoff API."""
import hashlib

from helpers import account, client, head


def batch_for(user):
    response = client.post('/api/v1/import-batches', headers=head(user), json={})
    assert response.status_code == 200
    return '/api/v1/import-batches/' + response.json()['data']['id']


def upload(user, batch_url, files):
    response = client.post(batch_url + '/sources/files', headers=head(user),
                           data={'consent': 'true'}, files=files)
    assert response.status_code == 200
    return response.json()['data']


def test_same_filename_attachments_keep_distinct_originals_and_source_lines():
    user = account('handoff-files@example.com')
    other = account('handoff-files-other@example.com')
    url = batch_for(user)
    originals = ['申请表甲\n理由不超过100字。'.encode(), '申请表乙\n理由不超过200字。'.encode()]
    sources = upload(user, url, [('files', ('form.txt', raw, 'text/plain')) for raw in originals])
    assert len({source['id'] for source in sources}) == 2
    assert len({source['metadata']['document_id'] for source in sources}) == 2
    restored = client.get(url, headers=head(user)).json()['data']
    assert {s['id'] for s in restored['sources']} == {s['id'] for s in sources}
    assert restored['case_id'] is None
    line_sets = []
    for source, raw in zip(sources, originals):
        document_url = '/api/v1/documents/' + source['metadata']['document_id']
        document = client.get(document_url, headers=head(user)).json()['data']
        assert document['sha256'] == source['metadata']['sha256'] == hashlib.sha256(raw).hexdigest()
        assert [line['text'] for line in document['lines']] == raw.decode().splitlines()
        assert all(line['document_id'] == document['id'] for line in document['lines'])
        line_sets.append({line['id'] for line in document['lines']})
        content = client.get(document_url + '/content', headers=head(user))
        assert content.content == raw and content.headers['cache-control'] == 'no-store'
        assert client.get(document_url, headers=head(other)).status_code == 404
        assert client.get(document_url + '/content', headers=head(other)).status_code == 404
    assert line_sets[0].isdisjoint(line_sets[1])
    assert client.get(url, headers=head(other)).status_code == 404


def test_failed_source_replacement_preserves_successful_original_and_revision():
    user = account('handoff-recovery@example.com')
    url = batch_for(user)
    raw = '成功通知\n请人工核对后办理。'.encode()
    good, failed = upload(user, url, [
        ('files', ('notice.txt', raw, 'text/plain')),
        ('files', ('form.pdf', b'not a PDF', 'application/pdf')),
    ])
    assert good['status'] == 'ready' and failed['status'] == 'failed'
    assert failed['metadata']['error_code'] == 'FILE_CORRUPTED'
    before = client.get(url, headers=head(user)).json()['data']
    assert before['failed_source_count'] == 1 and before['analyzable_source_count'] == 1
    assert client.delete(url + '/sources/' + failed['id'], headers=head(user)).status_code == 200
    replacement = upload(user, url, [('files', ('form.txt', b'corrected original', 'text/plain'))])[0]
    after = client.get(url, headers=head(user)).json()['data']
    assert after['revision'] > before['revision']
    assert after['failed_source_count'] == 0 and after['analyzable_source_count'] == 2
    assert {s['id'] for s in after['sources']} == {good['id'], replacement['id']}
    assert client.get('/api/v1/documents/' + good['metadata']['document_id'] + '/content',
                      headers=head(user)).content == raw
    assert after['case_id'] is None


def test_missing_original_is_reported_even_when_document_metadata_survives():
    from app.services.documents import content_path, document_root

    user = account('handoff-missing@example.com')
    url = batch_for(user)
    source = upload(user, url, [('files', ('notice.txt', b'original notice', 'text/plain'))])[0]
    document_id = source['metadata']['document_id']
    document_url = '/api/v1/documents/' + document_id
    assert client.get(document_url + '/content', headers=head(user)).status_code == 200
    # Only this test's temporary original is removed; no real account files.
    content_path(document_root(), user['user']['id'], document_id).unlink()
    assert client.get(document_url, headers=head(user)).status_code == 200
    missing = client.get(document_url + '/content', headers=head(user))
    assert missing.status_code == 404
    assert missing.json()['detail']['code'] == 'DOCUMENT_CONTENT_MISSING'
