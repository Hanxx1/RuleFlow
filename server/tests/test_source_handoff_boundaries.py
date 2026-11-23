"""RF-011/013 observed boundaries, not approval of a future read contract.

Synthetic sources only. The first two tests deliberately document limitations
that a future form-context consumer must handle, rather than desirable writes.
"""
import pytest

from app.auth import conn
from helpers import account, client, head


def batch_for(user):
    response = client.post('/api/v1/import-batches', headers=head(user), json={})
    assert response.status_code == 200
    return '/api/v1/import-batches/' + response.json()['data']['id']


def snapshot(user, batch):
    response = client.get(batch, headers=head(user))
    assert response.status_code == 200
    return response.json()['data']


def parent_and_attachment(user, batch, monkeypatch, during_fetch=None):
    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith('/notice'):
            return b'<article>Notice<a href="/form.txt">Form</a></article>', 'text/html', url
        assert url == 'https://example.com/form.txt'
        if during_fetch:
            during_fetch()
        return b'Synthetic form\nKeep this original', 'text/plain', url

    monkeypatch.setattr('app.main.fetch_public', fetch)
    response = client.post(batch + '/sources/url', headers=head(user),
                           json={'url': 'https://example.com/notice', 'consent': True})
    assert response.status_code == 200
    parent = response.json()['data']
    response = client.post(batch + '/sources/' + parent['id'] + '/attachments',
                           headers=head(user), json={'index': 0, 'consent': True})
    assert response.status_code == 200
    child = response.json()['data']
    assert parent['status'] == child['status'] == 'ready'
    assert child['metadata']['parent_source_id'] == parent['id']
    assert calls == ['https://example.com/notice', 'https://example.com/form.txt']
    return parent, child


def test_batch_revision_does_not_identify_a_frozen_source_set(monkeypatch):
    user = account('handoff-version@example.com')
    batch = batch_for(user)
    observed = []
    parent, child = parent_and_attachment(
        user, batch, monkeypatch, lambda: observed.append(snapshot(user, batch)))
    during, = observed
    after = snapshot(user, batch)
    assert during['revision'] == after['revision']
    assert {s['id'] for s in during['sources']} == {parent['id']}
    assert {s['id'] for s in after['sources']} == {parent['id'], child['id']}
    assert during['case_id'] is after['case_id'] is None


def test_deleted_parent_leaves_child_original_and_dangling_parent_metadata(monkeypatch):
    user, other = account('handoff-parent@example.com'), account('handoff-parent-other@example.com')
    batch = batch_for(user)
    parent, child = parent_and_attachment(user, batch, monkeypatch)
    before = snapshot(user, batch)
    response = client.delete(batch + '/sources/' + parent['id'], headers=head(user))
    assert response.status_code == 200
    after = snapshot(user, batch)
    assert after['revision'] > before['revision']
    remaining, = after['sources']
    assert remaining['id'] == child['id']
    assert remaining['metadata']['parent_source_id'] == parent['id']
    with conn() as connection:
        assert connection.execute('SELECT 1 FROM import_sources WHERE id=?', (parent['id'],)).fetchone() is None
        relation = connection.execute('SELECT document_id FROM source_documents WHERE source_id=? AND owner_id=?',
                                      (child['id'], user['user']['id'])).fetchone()
        assert relation['document_id'] == child['metadata']['document_id']
    document = '/api/v1/documents/' + child['metadata']['document_id']
    assert client.get(document + '/content', headers=head(user)).content == b'Synthetic form\nKeep this original'
    assert client.get(document + '/content', headers=head(other)).status_code == 404
    assert after['case_id'] is None


@pytest.mark.parametrize('reader', ['batch', 'document', 'original'])
def test_existing_source_reads_do_not_write_or_fetch_or_parse(monkeypatch, reader):
    user = account('handoff-readonly@example.com')
    batch = batch_for(user)
    _, child = parent_and_attachment(user, batch, monkeypatch)
    document = '/api/v1/documents/' + child['metadata']['document_id']
    endpoint = {'batch': batch, 'document': document, 'original': document + '/content'}[reader]

    def unexpected(*args, **kwargs):
        pytest.fail('Source read must not fetch, parse or analyze')

    for target in ('fetch_public', 'parse_bytes', 'parse_url_blocks', 'analyze_case'):
        monkeypatch.setattr('app.main.' + target, unexpected)
    with conn() as connection:
        before = list(connection.iterdump())
        changes = connection.total_changes
    first = client.get(endpoint, headers=head(user))
    second = client.get(endpoint, headers=head(user))
    assert first.status_code == second.status_code == 200
    if reader == 'original':
        assert first.content == second.content == b'Synthetic form\nKeep this original'
        assert first.headers['cache-control'] == second.headers['cache-control'] == 'no-store'
    else:
        # The response envelope deliberately assigns a fresh request_id.
        assert first.json()['data'] == second.json()['data']
    with conn() as connection:
        assert connection.total_changes == changes
        assert list(connection.iterdump()) == before
