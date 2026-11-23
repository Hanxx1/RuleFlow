"""RF-015 pre-migration baseline; no new schema or candidate implementation."""
import hashlib
import shutil
import sqlite3
from contextlib import closing

from app import auth
from app.bootstrap import database
from app.services.documents import bind_document, content_path, document_root
from helpers import account, client, head


# Explicit scope: compare rows as well as FKs; JSON references have no SQL FK.
TABLES = (
    'imports', 'import_case_sources', 'import_batches', 'import_sources',
    'import_analysis_runs', 'source_documents', 'cases', 'evidence',
    'documents', 'document_lines', 'evidence_lines', 'rules', 'materials',
    'tasks', 'case_reviews', 'analysis_review_versions', 'review_events',
    'case_attachment_documents', 'case_attachment_links', 'schema_migrations',
)


def rows(path):
    with closing(sqlite3.connect(path)) as connection:
        return {table: sorted(connection.execute('SELECT * FROM ' + table).fetchall(), key=repr)
                for table in TABLES}


def test_existing_notice_links_and_originals_survive_backup_and_initialization(tmp_path, monkeypatch):
    original, restored = tmp_path / 'before.sqlite', tmp_path / 'restored.sqlite'
    monkeypatch.setattr(auth, 'DB', original)
    database()
    user, other = account('migration-notice@example.com'), account('migration-other@example.com')
    headers = head(user)
    raw = '请核对申请材料。\n提交前请填写申请表。'.encode()
    response = client.post('/api/v1/imports/files', headers=headers, data={'consent': 'true'},
                           files={'files': ('legacy.txt', raw, 'text/plain')})
    assert response.status_code == 200
    legacy, = response.json()['data']
    assert legacy['case_id'] and legacy['document_id'] and legacy['blocks'] == 2
    response = client.post('/api/v1/import-batches', headers=headers, json={})
    assert response.status_code == 200
    batch = '/api/v1/import-batches/' + response.json()['data']['id']
    text = client.post(batch + '/sources/text', headers=headers,
                       json={'text': '补充说明仅供人工核对。', 'consent': True})
    assert text.status_code == 200
    files = client.post(batch + '/sources/files', headers=headers, data={'consent': 'true'},
                        files={'files': ('batch.txt', raw, 'text/plain')})
    assert files.status_code == 200
    source, = files.json()['data']
    analyzed = client.post(batch + '/analyze', headers=headers)
    assert analyzed.status_code == 200
    case_id = analyzed.json()['data']['case_id']
    assert case_id
    document_ids = [legacy['document_id'], source['metadata']['document_id']]
    before = rows(original)
    assert before['import_case_sources'] and before['source_documents'] and before['evidence_lines']
    with auth.conn() as connection:
        # A Document has two lines; source.evidence_id represents only its first Evidence.
        mapped = connection.execute('SELECT evidence_id FROM evidence_lines WHERE document_id=?',
                                    (document_ids[1],)).fetchall()
        assert len(mapped) == 2
        assert {row[0] for row in mapped} <= set(analyzed.json()['data']['result']['evidence_ids'])
        stored = connection.execute('SELECT evidence_id FROM import_sources WHERE id=?', (source['id'],)).fetchone()
        assert stored[0] in {row[0] for row in mapped}
    original_root = document_root()
    hashes = {doc: hashlib.sha256(content_path(original_root, user['user']['id'], doc).read_bytes()).hexdigest()
              for doc in document_ids}
    with closing(sqlite3.connect(original)) as source_db, closing(sqlite3.connect(restored)) as target:
        source_db.backup(target)
    restored_root = tmp_path / 'restored-documents'
    shutil.copytree(original_root, restored_root)
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT', str(restored_root))
    monkeypatch.setattr(auth, 'DB', restored)
    database()  # Replay existing initialization only; no proposed RF-015 migration.
    database()
    assert rows(restored) == before
    assert rows(original) == before
    with closing(sqlite3.connect(restored)) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    restored_batch = client.get(batch, headers=headers)
    assert restored_batch.status_code == 200
    assert restored_batch.json()['data'] == analyzed.json()['data']
    for current_case in (legacy['case_id'], case_id):
        resources = '/api/v1/cases/' + current_case + '/resources'
        response = client.get(resources, headers=headers)
        assert response.status_code == 200 and response.json()['data']['evidence']
        assert client.get(resources, headers=head(other)).status_code == 404
        refs = [response.json()['data']['evidence'][0]['id']]
        denied = client.post('/api/v1/cases/' + current_case + '/tasks', headers=headers,
                             json={'title': 'Must remain behind Review', 'evidence_ids': refs})
        assert denied.status_code == 409
    for doc, expected in hashes.items():
        endpoint = '/api/v1/documents/' + doc + '/content'
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 200 and response.content == raw
        assert hashlib.sha256(response.content).hexdigest() == expected
        assert hashlib.sha256(content_path(original_root, user['user']['id'], doc).read_bytes()).hexdigest() == expected
        assert client.get(endpoint, headers=head(other)).status_code == 404
    assert rows(restored) == before


def test_shared_document_has_separate_case_evidence_and_idempotent_line_binding():
    user = account('migration-shared@example.com')
    headers = head(user)
    raw = b'Shared synthetic original\nSecond source line'
    response = client.post('/api/v1/imports/files', headers=headers, data={'consent': 'true'},
                           files={'files': ('shared.txt', raw, 'text/plain')})
    assert response.status_code == 200
    first, = response.json()['data']
    response = client.post('/api/v1/imports/text', headers=headers,
                           json={'text': 'Separate synthetic Case', 'consent': True})
    assert response.status_code == 200
    second_case = response.json()['data']['case_id']
    with auth.conn() as connection:
        second = bind_document(connection, user['user']['id'], second_case, first['document_id'], 'shared original')
        repeated = bind_document(connection, user['user']['id'], second_case, first['document_id'], 'shared original')
        assert repeated == second and len(second) == 2
        links = connection.execute('SELECT e.case_id,e.id,l.line_id FROM evidence e JOIN evidence_lines l '
                                   'ON e.id=l.evidence_id WHERE l.document_id=?', (first['document_id'],)).fetchall()
        first_links = {(row['id'], row['line_id']) for row in links if row['case_id'] == first['case_id']}
        second_links = {(row['id'], row['line_id']) for row in links if row['case_id'] == second_case}
        assert len(first_links) == len(second_links) == 2
        assert {ref for ref, _ in first_links}.isdisjoint(ref for ref, _ in second_links)
        assert {line for _, line in first_links} == {line for _, line in second_links}
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    assert client.get('/api/v1/documents/' + first['document_id'] + '/content', headers=headers).content == raw
