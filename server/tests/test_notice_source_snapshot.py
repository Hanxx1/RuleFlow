"""C-internal read service tests; no public form-context API is implemented."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.auth import conn
from app.services.documents import content_path, document_root
from app.services.file_validation import DocumentError
from app.services.notice_source_snapshot import SourceSnapshotError, read_source_snapshot
from helpers import account, client, head


def setup_batch(email='snapshot@example.com'):
    user = account(email)
    batch = client.post('/api/v1/import-batches', headers=head(user), json={}).json()['data']
    return user, batch['id']


def text_source(user, batch_id, text='Synthetic notice'):
    response = client.post('/api/v1/import-batches/' + batch_id + '/sources/text',
                          headers=head(user), json={'text': text, 'consent': True})
    assert response.status_code == 200
    return response.json()['data']


def file_source(user, batch_id, raw=b'Synthetic original\nSecond real line'):
    response = client.post('/api/v1/import-batches/' + batch_id + '/sources/files',
                          headers=head(user), data={'consent': 'true'},
                          files={'files': ('form.txt', raw, 'text/plain')})
    assert response.status_code == 200
    return response.json()['data'][0]


def revision(batch_id):
    return conn().execute('SELECT revision FROM import_batches WHERE id=?', (batch_id,)).fetchone()[0]


def read(user, batch_id, expected=None, connection=None):
    return read_source_snapshot(connection or conn(), user['user']['id'], batch_id,
                                revision(batch_id) if expected is None else expected,
                                original_root=document_root())


def set_metadata(source_id, **changes):
    with conn() as connection:
        current = json.loads(connection.execute(
            'SELECT metadata_json FROM import_sources WHERE id=?', (source_id,)
        ).fetchone()[0])
        current.update(changes)
        connection.execute('UPDATE import_sources SET metadata_json=? WHERE id=?',
                           (json.dumps(current), source_id))


def test_legacy_text_exact_hash_and_read_only_without_import_or_file_reads(monkeypatch):
    user, batch = setup_batch()
    text = 'Synthetic notice\nVerify the requirements.'
    source = text_source(user, batch, text)

    def forbidden(*args, **kwargs):
        pytest.fail('Source inspection must not fetch, parse, analyze or read original bytes')

    for name in ('fetch_public', 'parse_bytes', 'analyze_case'):
        monkeypatch.setattr('app.main.' + name, forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    before = list(conn().iterdump())
    connection = conn()
    writes = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
    connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY if action in writes else sqlite3.SQLITE_OK)
    try:
        result = read(user, batch)
        assert read(user, batch) == result
    finally:
        connection.set_authorizer(None)
    item, = result['sources']
    assert item['source_id'] == source['id'] and item['text'] == text
    assert item['content_hash'] == hashlib.sha256(text.encode()).hexdigest()
    assert item['original']['state'] == 'not_applicable'
    assert item['extraction']['state'] == 'available'
    assert item['lines'] == [] and item['document_ref'] is None
    assert result['case_id'] is None
    assert 'evidence_ids' not in item and 'source_revision' not in item
    assert list(connection.iterdump()) == before


def test_identical_files_keep_distinct_sources_documents_and_real_lines():
    user, batch = setup_batch()
    sources = [file_source(user, batch) for _ in range(2)]
    items = {item['source_id']: item for item in read(user, batch)['sources']}
    assert len(items) == 2
    assert len({item['document_ref']['id'] for item in items.values()}) == 2
    assert len({item['content_hash'] for item in items.values()}) == 1
    line_ids = []
    for source in sources:
        item = items[source['id']]
        document = client.get('/api/v1/documents/' + source['metadata']['document_id'],
                              headers=head(user)).json()['data']
        assert item['original']['state'] == 'present' and item['extraction']['state'] == 'available'
        assert [line['line_id'] for line in item['lines']] == [line['id'] for line in document['lines']]
        assert item['document_ref']['sha256'] == document['sha256']
        assert item['text'] == '\n'.join(line['text'] for line in document['lines'])
        line_ids.append({line['line_id'] for line in item['lines']})
    assert line_ids[0].isdisjoint(line_ids[1])
    encoded = json.dumps(items)
    assert 'owner_id' not in encoded and str(document_root()) not in encoded


def test_existing_page_coordinates_are_preserved_without_inventing_locator():
    user, batch = setup_batch()
    source = file_source(user, batch)
    with conn() as c:
        c.execute('UPDATE document_lines SET page=2,bbox_json=?,coordinate_space=?,page_width=600,'
                  'page_height=800,confidence=0.9 WHERE document_id=? AND line_number=1',
                  ('[10,20,100,40]', 'pixel', source['metadata']['document_id']))
    first = read(user, batch)['sources'][0]['lines'][0]
    assert first['page'] == 2 and first['bbox'] == [10, 20, 100, 40]
    assert (first['coordinate_space'], first['page_width'], first['page_height'], first['confidence']) == ('pixel', 600, 800, 0.9)


@pytest.mark.parametrize('empty', [False, True])
def test_parse_failure_or_empty_text_does_not_hide_original(monkeypatch, empty):
    user, batch = setup_batch()

    def parser(*args):
        if empty:
            return []
        raise DocumentError('DOCUMENT_PARSE_FAILED', 'Synthetic parser failure')

    monkeypatch.setattr('app.main.parse_bytes', parser)
    source = file_source(user, batch)
    item, = read(user, batch)['sources']
    assert source['status'] == 'failed'
    assert item['original']['state'] == 'present'
    assert item['extraction'] == {'state': 'empty' if empty else 'failed',
                                  'error_code': 'OCR_EMPTY' if empty else 'DOCUMENT_PARSE_FAILED'}
    assert item['document_ref'] and not item['lines']
    response = client.get('/api/v1/documents/' + item['document_ref']['id'] + '/content', headers=head(user))
    assert response.status_code == 200
    assert hashlib.sha256(response.content).hexdigest() == item['document_ref']['sha256']


def test_missing_original_keeps_history_and_unaffected_source():
    user, batch = setup_batch()
    source, good = file_source(user, batch), file_source(user, batch)
    content_path(document_root(), user['user']['id'], source['metadata']['document_id']).unlink()
    items = {item['source_id']: item for item in read(user, batch)['sources']}
    assert items[source['id']]['original'] == {'state': 'missing', 'error_code': 'DOCUMENT_CONTENT_MISSING'}
    assert items[source['id']]['extraction']['state'] == 'available'
    assert items[source['id']]['lines']
    assert items[good['id']]['original']['state'] == 'present'


def test_storage_error_is_unverified_instead_of_missing(monkeypatch):
    user, batch = setup_batch()
    source = file_source(user, batch)
    target = content_path(document_root(), user['user']['id'], source['metadata']['document_id'])
    original_stat = Path.stat

    def stat_with_failure(path, *args, **kwargs):
        if path == target:
            raise PermissionError('SENSITIVE_PATH_MUST_NOT_BE_RETURNED')
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', stat_with_failure)
    item, = read(user, batch)['sources']
    assert item['original'] == {'state': 'unverified', 'error_code': 'DOCUMENT_CONTENT_UNVERIFIED'}
    assert 'SENSITIVE_PATH' not in json.dumps(item)


def test_not_acquired_is_distinct_from_missing_and_keeps_good_source():
    user, batch = setup_batch()
    good = file_source(user, batch)
    response = client.post('/api/v1/import-batches/' + batch + '/sources/files', headers=head(user),
                           data={'consent': 'true'}, files={'files': ('bad.pdf', b'not a PDF', 'application/pdf')})
    failed, = response.json()['data']
    items = {item['source_id']: item for item in read(user, batch)['sources']}
    assert items[failed['id']]['original']['state'] == 'not_acquired'
    assert items[failed['id']]['document_ref'] is None
    assert items[good['id']]['original']['state'] == 'present'


@pytest.mark.parametrize('tamper', ['metadata', 'relation', 'missing_relation', 'document_owner', 'line_owner', 'invalid_json'])
def test_illegal_document_reference_rejects_entire_snapshot_before_file_probe(monkeypatch, tamper):
    user, batch = setup_batch()
    other, other_batch = setup_batch('snapshot-other@example.com')
    source, foreign = file_source(user, batch), file_source(other, other_batch)
    with conn() as c:
        if tamper == 'metadata':
            set_metadata(source['id'], document_id=foreign['metadata']['document_id'])
        elif tamper == 'relation':
            c.execute('UPDATE source_documents SET owner_id=? WHERE source_id=?', (other['user']['id'], source['id']))
        elif tamper == 'missing_relation':
            c.execute('DELETE FROM source_documents WHERE source_id=?', (source['id'],))
        elif tamper == 'document_owner':
            c.execute('UPDATE documents SET owner_id=? WHERE id=?', (other['user']['id'], source['metadata']['document_id']))
        elif tamper == 'line_owner':
            c.execute('UPDATE document_lines SET owner_id=? WHERE document_id=?', (other['user']['id'], source['metadata']['document_id']))
        else:
            c.execute("UPDATE import_sources SET metadata_json='[]' WHERE id=?", (source['id'],))
    monkeypatch.setattr('app.services.notice_source_snapshot._original_state',
                        lambda *args: pytest.fail('Invalid relationship must fail before file inspection'))
    before = list(conn().iterdump())
    with pytest.raises(SourceSnapshotError, match='^SOURCE_REFERENCE_INVALID$'):
        read(user, batch)
    assert list(conn().iterdump()) == before


@pytest.mark.parametrize('parent_kind', ['valid', 'deleted', 'cross_batch', 'cross_owner'])
def test_parent_relationship_is_separate_from_original_state(parent_kind):
    user, batch = setup_batch()
    child = file_source(user, batch)
    if parent_kind == 'cross_owner':
        parent_user, parent_batch = setup_batch('snapshot-parent@example.com')
    elif parent_kind == 'cross_batch':
        parent_user = user
        parent_batch = client.post('/api/v1/import-batches', headers=head(user), json={}).json()['data']['id']
    else:
        parent_user, parent_batch = user, batch
    parent = text_source(parent_user, parent_batch)
    set_metadata(child['id'], parent_source_id=parent['id'])
    if parent_kind == 'deleted':
        assert client.delete('/api/v1/import-batches/' + batch + '/sources/' + parent['id'], headers=head(user)).status_code == 200
    if parent_kind.startswith('cross_'):
        with pytest.raises(SourceSnapshotError, match='^SOURCE_REFERENCE_INVALID$'):
            read(user, batch)
    else:
        item = next(item for item in read(user, batch)['sources'] if item['source_id'] == child['id'])
        assert item['parent_reference_state'] == ('missing' if parent_kind == 'deleted' else 'valid')
        assert item['parent_source_id'] == (None if parent_kind == 'deleted' else parent['id'])
        assert item['original']['state'] == 'present'


def test_owner_precedes_version_check_and_stale_has_zero_writes():
    user, batch = setup_batch()
    other = account('snapshot-denied@example.com')
    old = revision(batch)
    file_source(user, batch)
    before = list(conn().iterdump())
    for denied_batch in (batch, 'missing-batch'):
        with pytest.raises(SourceSnapshotError, match='^BATCH_NOT_FOUND$'):
            read(other, denied_batch, old)
    with pytest.raises(SourceSnapshotError, match='^IMPORT_BATCH_STALE$'):
        read(user, batch, old)
    for invalid in (-1, None, True, '1'):
        with pytest.raises(SourceSnapshotError, match='^REVISION_REQUIRED$'):
            read_source_snapshot(conn(), user['user']['id'], batch, invalid, original_root=document_root())
    assert list(conn().iterdump()) == before


def test_read_does_not_commit_or_rollback_callers_pending_transaction():
    user, batch = setup_batch()
    text_source(user, batch)
    connection = conn()
    connection.execute("UPDATE import_batches SET title='Caller pending title' WHERE id=?", (batch,))
    assert connection.in_transaction
    read(user, batch)
    assert connection.in_transaction
    connection.rollback()
    assert connection.execute('SELECT title FROM import_batches WHERE id=?', (batch,)).fetchone()[0] != 'Caller pending title'


def test_database_snapshot_is_consistent_but_same_revision_can_gain_sources(tmp_path):
    user, batch = setup_batch()
    text_source(user, batch, 'Original text')
    database = tmp_path / 'snapshot.sqlite'
    with closing(sqlite3.connect(database)) as copy:
        conn().backup(copy)
        copy.execute('PRAGMA journal_mode=WAL')
    with closing(sqlite3.connect(database)) as reader, closing(sqlite3.connect(database)) as writer:
        reader.row_factory = writer.row_factory = sqlite3.Row
        inserted = []

        def concurrent_write(sql):
            if 'SELECT * FROM import_sources WHERE batch_id=' in sql and not inserted:
                inserted.append(True)
                row = dict(writer.execute('SELECT * FROM import_sources WHERE batch_id=?', (batch,)).fetchone())
                row['id'], row['extracted_text'] = 'concurrent-source', 'Later text'
                with writer:
                    writer.execute('INSERT INTO import_sources (' + ','.join(row) + ') VALUES (' + ','.join('?' for _ in row) + ')', tuple(row.values()))

        reader.set_trace_callback(concurrent_write)
        first = read(user, batch, connection=reader)
        reader.set_trace_callback(None)
        second = read(user, batch, connection=reader)
        assert inserted == [True]
        assert len(first['sources']) == 1 and len(second['sources']) == 2
        assert first['batch_revision'] == second['batch_revision']
        assert next(s for s in second['sources'] if s['source_id'] == 'concurrent-source')['text'] == 'Later text'
