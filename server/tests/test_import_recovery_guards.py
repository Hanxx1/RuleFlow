"""RF-013 target boundaries; four cases initially reproduce the shared gaps.

Synthetic input and isolated application fixtures only. These assertions express
the desired recovery behavior; do not weaken them to accept the existing gaps.
"""
import pytest
import sqlite3

from app.auth import conn
from helpers import account, client, head


def create_batch(user):
    response = client.post('/api/v1/import-batches', headers=head(user), json={})
    assert response.status_code == 200
    return '/api/v1/import-batches/' + response.json()['data']['id']


def install_fetch(monkeypatch, raw, mime, final_url):
    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith('/notice'):
            return b'<article>Notice<a href="/form.txt">form.txt</a></article>', 'text/html', url
        return raw, mime, final_url

    monkeypatch.setattr('app.main.fetch_public', fetch)
    return calls


def add_parent(user, batch):
    response = client.post(batch + '/sources/url', headers=head(user),
                           json={'url': 'https://example.com/notice', 'consent': True})
    assert response.status_code == 200
    parent = response.json()['data']
    assert parent['status'] == 'ready'
    return parent


@pytest.mark.parametrize('raw,mime,final_url', [
    (b'<html><body><h1>Sign in to download</h1></body></html>',
     'text/html', 'https://example.com/login'),
    (b'<html><body><p>File unavailable</p></body></html>',
     'text/html', 'https://example.com/form.txt'),
    (b'<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Sign in</p></body></html>',
     'application/xhtml+xml', 'https://example.com/login'),
])
def test_attachment_html_is_failed_without_document_or_analyzable_text(monkeypatch, raw, mime, final_url):
    install_fetch(monkeypatch, raw, mime, final_url)
    user = account('recovery-html@example.com')
    batch = create_batch(user)
    parent = add_parent(user, batch)
    response = client.post(batch + '/sources/' + parent['id'] + '/attachments',
                           headers=head(user), json={'index': 0, 'consent': True})
    assert response.status_code == 200
    child = response.json()['data']
    assert child['status'] == 'failed'
    assert child['metadata'].get('error_code')
    assert child['metadata']['parent_source_id'] == parent['id']
    assert 'document_id' not in child['metadata']
    restored = client.get(batch, headers=head(user)).json()['data']
    assert restored['analyzable_source_count'] == 1
    assert restored['failed_source_count'] == 1
    assert restored['case_id'] is None
    assert client.get('/api/v1/documents/' + parent['metadata']['document_id']
                      + '/content', headers=head(user)).status_code == 200
    with conn() as connection:
        assert connection.execute('SELECT COUNT(*) FROM documents WHERE owner_id=?',
                                  (user['user']['id'],)).fetchone()[0] == 1


def test_html_notice_and_valid_text_attachment_still_work(monkeypatch):
    calls = install_fetch(monkeypatch, b'Actual synthetic attachment', 'text/plain',
                          'https://example.com/form.txt')
    user = account('recovery-valid@example.com')
    batch = create_batch(user)
    parent = add_parent(user, batch)
    assert calls == ['https://example.com/notice']
    response = client.post(batch + '/sources/' + parent['id'] + '/attachments',
                           headers=head(user), json={'index': 0, 'consent': True})
    assert response.status_code == 200
    child = response.json()['data']
    assert child['status'] == 'ready'
    assert child['metadata']['parent_source_id'] == parent['id']
    assert calls == ['https://example.com/notice', 'https://example.com/form.txt']
    assert client.get('/api/v1/documents/' + child['metadata']['document_id']
                      + '/content', headers=head(user)).content == b'Actual synthetic attachment'
    with conn() as connection:
        assert connection.execute('SELECT COUNT(*) FROM source_documents WHERE source_id=? AND owner_id=?',
                                  (child['id'], user['user']['id'])).fetchone()[0] == 1


def test_attachment_rejections_do_not_fetch_or_mutate(monkeypatch):
    calls = install_fetch(monkeypatch, b'Attachment', 'text/plain', 'https://example.com/form.txt')
    user, other = account('recovery-consent@example.com'), account('recovery-foreign@example.com')
    batch = create_batch(user)
    parent = add_parent(user, batch)
    endpoint = batch + '/sources/' + parent['id'] + '/attachments'
    before = client.get(batch, headers=head(user)).json()['data']
    assert client.post(endpoint, headers=head(user), json={'index': 0}).status_code == 422
    assert client.post(endpoint, headers=head(other), json={'index': 0, 'consent': True}).status_code == 404
    assert client.post(create_batch(user) + '/sources/' + parent['id'] + '/attachments',
                       headers=head(user), json={'index': 0, 'consent': True}).status_code == 404
    assert client.post(endpoint, headers=head(user), json={'index': 9, 'consent': True}).status_code == 422
    after = client.get(batch, headers=head(user)).json()['data']
    assert calls == ['https://example.com/notice']
    assert after['source_count'] == before['source_count'] == 1
    assert after['revision'] == before['revision']


def test_parse_failure_keeps_original_and_formal_source_relation(monkeypatch):
    def fail(*args):
        raise RuntimeError('SYNTHETIC_PRIVATE_PARSER_ERROR')

    monkeypatch.setattr('app.main.parse_bytes', fail)
    user, other = account('recovery-parse@example.com'), account('recovery-parse-other@example.com')
    batch = create_batch(user)
    raw = b'Synthetic valid text with injected parser failure'
    response = client.post(batch + '/sources/files', headers=head(user), data={'consent': 'true'},
                           files=[('files', ('notice.txt', raw, 'text/plain'))])
    assert response.status_code == 200
    source = response.json()['data'][0]
    assert source['status'] == 'failed'
    assert source['metadata']['error_code'] == 'DOCUMENT_PARSE_FAILED'
    assert 'SYNTHETIC_PRIVATE_PARSER_ERROR' not in response.text
    document_id = source['metadata']['document_id']
    document_url = '/api/v1/documents/' + document_id
    assert client.get(document_url + '/content', headers=head(user)).content == raw
    assert client.get(document_url + '/content', headers=head(other)).status_code == 404
    with conn() as connection:
        assert connection.execute(
            'SELECT COUNT(*) FROM source_documents WHERE owner_id=? AND source_id=? AND document_id=?',
            (user['user']['id'], source['id'], document_id)).fetchone()[0] == 1
    restored = client.get(batch, headers=head(user)).json()['data']
    assert restored['analyzable_source_count'] == 0 and restored['case_id'] is None


def test_invalid_file_does_not_invent_document_or_relation():
    user = account('recovery-invalid@example.com')
    batch = create_batch(user)
    response = client.post(batch + '/sources/files', headers=head(user), data={'consent': 'true'},
                           files=[('files', ('invalid.pdf', b'not a pdf', 'application/pdf'))])
    assert response.status_code == 200
    source = response.json()['data'][0]
    assert source['status'] == 'failed' and source['metadata']['error_code'] == 'FILE_CORRUPTED'
    assert 'document_id' not in source['metadata']
    with conn() as connection:
        assert connection.execute('SELECT COUNT(*) FROM source_documents WHERE owner_id=?',
                                  (user['user']['id'],)).fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM documents WHERE owner_id=?',
                                  (user['user']['id'],)).fetchone()[0] == 0


@pytest.mark.parametrize('parser_mode,error_code', [
    ('empty', 'OCR_EMPTY'),
    ('error', 'DOCUMENT_PARSE_FAILED'),
])
def test_failed_original_is_protected_until_source_is_removed(monkeypatch, parser_mode, error_code):
    import app.main as main

    original_parser = main.parse_bytes

    def parse(raw, mime, name):
        if name == 'failed.txt':
            if parser_mode == 'empty':
                return []
            raise RuntimeError('SYNTHETIC_PRIVATE_PARSER_ERROR')
        return original_parser(raw, mime, name)

    monkeypatch.setattr(main, 'parse_bytes', parse)
    user = account('recovery-lifecycle@example.com')
    batch = create_batch(user)
    response = client.post(batch + '/sources/files', headers=head(user), data={'consent': 'true'},
                           files=[('files', ('failed.txt', b'Kept original', 'text/plain')),
                                  ('files', ('good.txt', b'Other successful original', 'text/plain'))])
    assert response.status_code == 200
    failed, good = response.json()['data']
    assert failed['status'] == 'failed' and failed['metadata']['error_code'] == error_code
    assert good['status'] == 'ready'
    document_url = '/api/v1/documents/' + failed['metadata']['document_id']
    assert client.get(document_url + '/content', headers=head(user)).content == b'Kept original'
    assert client.delete(document_url, headers=head(user)).status_code == 409
    assert client.delete(batch + '/sources/' + failed['id'], headers=head(user)).status_code == 200
    with conn() as connection:
        assert connection.execute('SELECT COUNT(*) FROM source_documents WHERE source_id=?',
                                  (failed['id'],)).fetchone()[0] == 0
    assert client.delete(document_url, headers=head(user)).status_code == 200
    assert client.get(document_url + '/content', headers=head(user)).status_code == 404
    assert client.get('/api/v1/documents/' + good['metadata']['document_id'] + '/content',
                      headers=head(user)).content == b'Other successful original'
    restored = client.get(batch, headers=head(user)).json()['data']
    assert restored['analyzable_source_count'] == 1 and restored['failed_source_count'] == 0
    assert restored['case_id'] is None


def test_source_insert_rolls_back_when_formal_document_relation_fails():
    from app.main import _store_import_source

    user = account('recovery-atomic@example.com')
    batch = create_batch(user)
    with pytest.raises(sqlite3.IntegrityError):
        _store_import_source(user['user']['id'], batch.rsplit('/', 1)[1], 'file', 'failed.txt',
                             'failed', 'Synthetic failure', {'document_id': 'missing-document'},
                             None, 'missing-document')
    restored = client.get(batch, headers=head(user)).json()['data']
    assert restored['source_count'] == 0 and restored['case_id'] is None
    with conn() as connection:
        assert connection.execute('SELECT COUNT(*) FROM source_documents').fetchone()[0] == 0


def test_html_attachment_failure_can_be_replaced_without_touching_parent(monkeypatch):
    calls = install_fetch(monkeypatch, b'<html>Private login page</html>', 'text/html',
                          'https://example.com/login')
    user = account('recovery-html-replacement@example.com')
    batch = create_batch(user)
    parent = add_parent(user, batch)
    endpoint = batch + '/sources/' + parent['id'] + '/attachments'
    failed = client.post(endpoint, headers=head(user), json={'index': 0, 'consent': True}).json()['data']
    assert failed['status'] == 'failed'
    assert failed['metadata']['error_code'] == 'ATTACHMENT_HTML_RESPONSE'
    assert 'Private login page' not in str(failed)
    assert client.delete(batch + '/sources/' + failed['id'], headers=head(user)).status_code == 200
    replacement = client.post(batch + '/sources/files', headers=head(user), data={'consent': 'true'},
                              files=[('files', ('form.txt', b'Actual replacement', 'text/plain'))])
    assert replacement.status_code == 200 and replacement.json()['data'][0]['status'] == 'ready'
    restored = client.get(batch, headers=head(user)).json()['data']
    assert restored['analyzable_source_count'] == 2 and restored['failed_source_count'] == 0
    assert parent in restored['sources'] and restored['case_id'] is None
    assert calls == ['https://example.com/notice', 'https://example.com/form.txt']
