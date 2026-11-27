"""RF-011/013 read-only source handoff; synthetic accounts and originals only."""
import hashlib
import json

import pytest

from app.auth import conn
from helpers import account, client, head


def batch_for(user):
    response = client.post('/api/v1/import-batches', headers=head(user), json={})
    assert response.status_code == 200
    return '/api/v1/import-batches/' + response.json()['data']['id']


def snapshot(user, batch):
    return client.get(batch, headers=head(user)).json()['data']


def context(user, batch, revision=None):
    if revision is None:
        revision = snapshot(user, batch)['revision']
    return client.get(batch + '/form-context', headers=head(user),
                      params={'expected_revision': revision})


def test_url_cms_form_body_reaches_saved_lines_and_preserves_original(monkeypatch):
    raw=('''<html><body><div><ul><li>学校导航</li></ul></div>
    <form name="_newscontent_fromname"><div id="vsb_content">
    <div class="v_news_content"><p>请提交申请表。</p><p>截止2026年12月1日。</p>
    <p><a href="form.docx">附件：申请表</a></p></div></div></form>
    <div><p>下一篇通知</p></div></body></html>''').encode()
    url='https://notice.example.edu/info/1/2.htm'
    monkeypatch.setattr('app.main.fetch_public', lambda target: (raw, 'text/html', url))
    user=account('context-html-form@example.com')
    batch=batch_for(user)
    response=client.post(batch+'/sources/url',headers=head(user),
                         json={'url':url,'consent':True})
    assert response.status_code==200
    source=response.json()['data']
    assert source['status']=='ready'
    assert source['metadata']['attachments'][0]['url']=='https://notice.example.edu/info/1/form.docx'
    result=context(user,batch)
    assert result.status_code==200
    item,=result.json()['data']['sources']
    expected=['请提交申请表。','截止2026年12月1日。','附件：申请表']
    assert [line['text'] for line in item['lines']]==expected
    assert item['text']=='\n'.join(expected)
    assert item['document_ref']['sha256']==hashlib.sha256(raw).hexdigest()
    document_id=item['document_ref']['id']
    document=client.get('/api/v1/documents/'+document_id,headers=head(user)).json()['data']
    assert [line['line_id'] for line in item['lines']]==[line['id'] for line in document['lines']]
    assert client.get('/api/v1/documents/'+document_id+'/content',headers=head(user)).content==raw


def upload(user, batch, raw=b'Synthetic notice\nSecond line', name='notice.txt'):
    response = client.post(batch + '/sources/files', headers=head(user), data={'consent': 'true'},
                           files=[('files', (name, raw, 'text/plain'))])
    assert response.status_code == 200
    return response.json()['data'][0]


def test_legacy_text_returns_exact_stored_text_and_hash_without_inventing_lines():
    user = account('context-text@example.com')
    batch = batch_for(user)
    text = 'Synthetic legacy notice\nVerify before submitting.'
    source = client.post(batch + '/sources/text', headers=head(user),
                         json={'text': text, 'consent': True}).json()['data']
    with conn() as connection:
        before = list(connection.iterdump())
    response = context(user, batch)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    result = response.json()['data']
    assert result['schema_version'] == 1 and result['case_id'] is None
    assert result['batch_id'] == batch.rsplit('/', 1)[1]
    item, = result['sources']
    assert item['source_id'] == source['id'] and item['text'] == text
    assert item['text_origin'] == 'legacy_text' and item['extraction']['state'] == 'available'
    assert item['lines'] == [] and item['document_ref'] is None
    assert item['content_hash'] == hashlib.sha256(text.encode()).hexdigest()
    assert 'evidence_ids' not in item and 'source_revision' not in item
    assert context(user, batch).json()['data'] == result
    with conn() as connection:
        assert list(connection.iterdump()) == before


def test_document_lines_original_hash_and_same_named_files_remain_distinct():
    user = account('context-documents@example.com')
    batch = batch_for(user)
    sources = [upload(user, batch, raw) for raw in (b'Form A\nLimit 100', b'Form B\nLimit 200')]
    response = context(user, batch)
    assert response.status_code == 200
    items = {item['source_id']: item for item in response.json()['data']['sources']}
    assert len(items) == 2
    for source in sources:
        item = items[source['id']]
        document_id = source['metadata']['document_id']
        document = client.get('/api/v1/documents/' + document_id, headers=head(user)).json()['data']
        assert item['text_origin'] == 'document_lines' and item['extraction']['state'] == 'available'
        assert item['text'] == '\n'.join(line['text'] for line in document['lines'])
        assert [line['line_id'] for line in item['lines']] == [line['id'] for line in document['lines']]
        assert all(line['document_id'] == document_id for line in item['lines'])
        assert item['content_hash'] == document['sha256']
        assert item['document_ref'] == {'kind': 'document', 'id': document_id,
                'revision': document['revision'], 'sha256': document['sha256'],
                'name': document['name'], 'mime': document['mime'], 'size': document['size']}
    assert 'owner_id' not in response.text and 'upload_root' not in response.text


def test_expected_revision_is_required_and_stale_read_does_not_mutate():
    user = account('context-stale@example.com')
    batch = batch_for(user)
    old = snapshot(user, batch)['revision']
    upload(user, batch)
    before = snapshot(user, batch)
    assert client.get(batch + '/form-context', headers=head(user)).status_code == 422
    assert context(user, batch, -1).status_code == 422
    response = context(user, batch, old)
    assert response.status_code == 409 and response.json()['detail']['code'] == 'IMPORT_BATCH_STALE'
    assert snapshot(user, batch) == before


def test_foreign_and_missing_batches_do_not_disclose_content():
    user, other = account('context-owner@example.com'), account('context-other@example.com')
    batch = batch_for(user)
    upload(user, batch, b'PRIVATE_SYNTHETIC_CONTENT')
    for url in (batch, '/api/v1/import-batches/missing-batch'):
        response = context(other, url, 0)
        assert response.status_code == 404
        assert 'PRIVATE_SYNTHETIC_CONTENT' not in response.text
    assert client.get(batch + '/form-context', params={'expected_revision': 0}).status_code == 401


@pytest.mark.parametrize('tamper', ['metadata', 'foreign_relation', 'foreign_document', 'missing_relation'])
def test_forged_document_references_are_rejected_without_leaking_other_source(tamper):
    user, other = account('context-forge@example.com'), account('context-forge-other@example.com')
    batch, second_batch = batch_for(user), batch_for(user)
    own = upload(user, batch)
    # Same-owner document from another batch is not readable through this source's metadata.
    foreign = upload(user if tamper != 'foreign_document' else other,
                     second_batch if tamper != 'foreign_document' else batch_for(other),
                     b'PRIVATE_OTHER_BATCH')
    foreign_id = foreign['metadata']['document_id']
    with conn() as connection:
        if tamper in {'metadata', 'foreign_document'}:
            metadata = dict(own['metadata'], document_id=foreign_id)
            connection.execute('UPDATE import_sources SET metadata_json=? WHERE id=?',
                               (json.dumps(metadata), own['id']))
        if tamper == 'foreign_document':
            connection.execute('UPDATE source_documents SET document_id=? WHERE source_id=?',
                               (foreign_id, own['id']))
        if tamper == 'foreign_relation':
            connection.execute('UPDATE source_documents SET owner_id=? WHERE source_id=?',
                               (other['user']['id'], own['id']))
        if tamper == 'missing_relation':
            connection.execute('DELETE FROM source_documents WHERE source_id=?', (own['id'],))
    response = context(user, batch)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'SOURCE_REFERENCE_INVALID'
    assert 'PRIVATE_OTHER_BATCH' not in response.text and foreign_id not in response.text


def test_missing_original_is_visible_without_hiding_other_readable_sources():
    from app.services.documents import content_path, document_root

    user = account('context-missing-original@example.com')
    batch = batch_for(user)
    missing, good = upload(user, batch), upload(user, batch, b'Other preserved source')
    document_id = missing['metadata']['document_id']
    content_path(document_root(), user['user']['id'], document_id).unlink()
    response = context(user, batch)
    assert response.status_code == 200
    items = {item['source_id']: item for item in response.json()['data']['sources']}
    assert items[missing['id']]['original']['state'] == 'missing'
    assert items[missing['id']]['document_ref']['id'] == document_id
    assert items[good['id']]['original']['state'] == 'present'


def test_failed_original_with_formal_relation_is_distinct_from_file_never_received(monkeypatch):
    user = account('context-failed-original@example.com')
    batch = batch_for(user)
    monkeypatch.setattr('app.main.parse_bytes', lambda *args: [])
    failed = upload(user, batch)
    assert failed['status'] == 'failed'
    document_id = failed['metadata']['document_id']
    # Use the formal link created by the current import API after H07.
    with conn() as connection:
        assert connection.execute(
            'SELECT document_id FROM source_documents WHERE owner_id=? AND source_id=?',
            (user['user']['id'], failed['id']),
        ).fetchone()['document_id'] == document_id
    invalid = client.post(batch + '/sources/files', headers=head(user), data={'consent': 'true'},
                          files=[('files', ('bad.pdf', b'not pdf', 'application/pdf'))]).json()['data'][0]
    assert invalid['status'] == 'failed' and 'document_id' not in invalid['metadata']
    response = context(user, batch)
    assert response.status_code == 200
    items = {item['source_id']: item for item in response.json()['data']['sources']}
    assert items[failed['id']]['extraction']['state'] == 'empty'
    assert items[failed['id']]['extraction']['error_code'] == 'OCR_EMPTY'
    assert items[failed['id']]['text'] is None and items[failed['id']]['lines'] == []
    assert items[failed['id']]['document_ref']['id'] == document_id
    assert items[invalid['id']]['original']['state'] == 'not_acquired'
    assert items[invalid['id']]['document_ref'] is None


@pytest.mark.parametrize('scenario', ['anonymous', 'missing', 'negative', 'invalid', 'foreign', 'stale'])
def test_error_responses_are_not_cached(scenario):
    user = account('context-cache@example.com')
    batch = batch_for(user)
    upload(user, batch)
    headers = head(user)
    params = {'expected_revision': snapshot(user, batch)['revision']}
    expected = 422
    if scenario == 'anonymous':
        headers, expected = {}, 401
    elif scenario == 'missing':
        params = {}
    elif scenario == 'negative':
        params['expected_revision'] = -1
    elif scenario == 'invalid':
        params['expected_revision'] = 'not-an-integer'
    elif scenario == 'foreign':
        headers, expected = head(account('context-cache-other@example.com')), 404
    else:
        params['expected_revision'], expected = 0, 409
    response = client.get(batch + '/form-context', headers=headers, params=params)
    assert response.status_code == expected
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('parent_kind', ['valid', 'missing', 'cross_batch'])
def test_http_parent_reference_states_and_illegal_reference(parent_kind):
    user = account('context-parent@example.com')
    batch = batch_for(user)
    child = upload(user, batch)
    parent_batch = batch_for(user) if parent_kind == 'cross_batch' else batch
    parent = client.post(parent_batch + '/sources/text', headers=head(user),
                         json={'text': 'Synthetic parent', 'consent': True}).json()['data']
    with conn() as c:
        metadata = dict(child['metadata'], parent_source_id=parent['id'])
        c.execute('UPDATE import_sources SET metadata_json=? WHERE id=?',
                  (json.dumps(metadata), child['id']))
    if parent_kind == 'missing':
        assert client.delete(batch + '/sources/' + parent['id'], headers=head(user)).status_code == 200
    response = context(user, batch)
    if parent_kind == 'cross_batch':
        assert response.status_code == 409
        assert response.headers['cache-control'] == 'no-store'
        assert parent['id'] not in response.text
    else:
        item = next(x for x in response.json()['data']['sources'] if x['source_id'] == child['id'])
        assert item['parent_reference_state'] == parent_kind
        assert item['parent_source_id'] == (parent['id'] if parent_kind == 'valid' else None)
        assert item['original']['state'] == 'present'


def test_http_read_never_initializes_writes_fetches_parses_or_analyzes(monkeypatch):
    import sqlite3
    user = account('context-no-side-effects@example.com')
    batch = batch_for(user)
    upload(user, batch)
    revision = snapshot(user, batch)['revision']

    def forbidden(*args, **kwargs):
        pytest.fail('Read endpoint must not initialize, fetch, parse or analyze')

    for name in ('database', 'fetch_public', 'parse_bytes', 'analyze_case'):
        monkeypatch.setattr('app.main.' + name, forbidden)
    connection = conn()
    before = list(connection.iterdump())
    writes = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
    connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY if action in writes else sqlite3.SQLITE_OK)
    try:
        response = context(user, batch, revision)
        assert response.status_code == 200
        assert list(connection.iterdump()) == before
    finally:
        connection.set_authorizer(None)
