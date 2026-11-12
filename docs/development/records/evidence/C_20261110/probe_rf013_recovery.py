"""RF-013 diagnostic probe, NOT acceptance of a new API or approved fix.

Uses the existing application, an in-memory DB, temporary originals, synthetic
accounts and a stub for external fetching/parser failure. No live HTTP, OCR,
model or real user data. Exit 0: all target boundaries met; 2: open product
gaps reproduced; 1: unexpected probe failure. Run with the project Python env.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT / 'server'), str(ROOT / 'server/tests')]


def run():
    results = []
    with tempfile.TemporaryDirectory(prefix='campusweave-rf013-') as folder:
        os.environ.update(
            DATABASE_PATH=':memory:', APP_ENV='development', DEMO_MODE='false',
            LLM_BASE_URL='', LLM_MODEL='', LLM_API_KEY='',
            VAULT_UPLOAD_ROOT=str(Path(folder) / 'vault'),
            DEMO_UPLOAD_ROOT=str(Path(folder) / 'demo'),
            DOCUMENT_UPLOAD_ROOT=str(Path(folder) / 'documents'),
        )
        from fastapi import HTTPException
        from fastapi.testclient import TestClient
        import app.main as main
        from app import auth
        from helpers import account, client, head

        def record(name, actual, meets_target):
            results.append({'scenario': name, 'status': 'PASS' if meets_target else 'OPEN_GAP',
                            'actual': actual})

        try:
            with TestClient(main.app) as active:
                client.target = active
                user = account('rf013-probe@example.com')
                other = account('rf013-probe-other@example.com')
                headers = head(user)
                calls = []
                reply = {}

                def fetch(url):
                    calls.append(url)
                    if url == 'https://example.com/notice':
                        return (b'<article><p>Public synthetic notice</p>'
                                b'<a href="/form.pdf">form.pdf</a></article>',
                                'text/html', url)
                    if reply.get('http_error'):
                        raise HTTPException(502, {'code': 'url_http_error',
                                                  'message': '网页返回 HTTP 403'})
                    return reply['raw'], reply['mime'], reply.get('final_url', url)

                def batch():
                    response = client.post('/api/v1/import-batches', headers=headers, json={})
                    assert response.status_code == 200
                    return '/api/v1/import-batches/' + response.json()['data']['id']

                def snapshot(url):
                    response = client.get(url, headers=headers)
                    assert response.status_code == 200
                    return response.json()['data']

                def parent(url):
                    response = client.post(url + '/sources/url', headers=headers,
                                           json={'url': 'https://example.com/notice', 'consent': True})
                    assert response.status_code == 200
                    source = response.json()['data']
                    assert source['status'] == 'ready'
                    return source

                def attach(url, source, body=None, request_headers=None):
                    return client.post(url + '/sources/' + source['id'] + '/attachments',
                                       headers=request_headers or headers,
                                       json=body or {'index': 0, 'consent': True})

                with patch.object(main, 'fetch_public', side_effect=fetch):
                    url = batch()
                    source = parent(url)
                    record('H07-discovery-only', {'fetch_count': len(calls),
                           'source_count': snapshot(url)['source_count']},
                           calls == ['https://example.com/notice'] and snapshot(url)['source_count'] == 1)

                    before = snapshot(url)
                    before_calls = len(calls)
                    no_consent = attach(url, source, {'index': 0})
                    foreign = attach(url, source, request_headers=head(other))
                    wrong_batch = attach(batch(), source)
                    missing_index = attach(url, source, {'index': 9, 'consent': True})
                    after = snapshot(url)
                    statuses = [r.status_code for r in (no_consent, foreign, wrong_batch, missing_index)]
                    record('H07-rejected-before-fetch', {'http_statuses': statuses,
                           'extra_fetches': len(calls) - before_calls,
                           'revision_unchanged': before['revision'] == after['revision'],
                           'source_count': after['source_count']},
                           statuses == [422, 404, 404, 422] and len(calls) == before_calls
                           and before['revision'] == after['revision'] and after['source_count'] == 1)

                    reply.update(http_error=True)
                    failed_response = attach(url, source)
                    assert failed_response.status_code == 200
                    failed = failed_response.json()['data']
                    original = client.get('/api/v1/documents/' + source['metadata']['document_id']
                                          + '/content', headers=headers)
                    record('H07-403-keeps-parent', {'source_status': failed['status'],
                           'error_code': failed['metadata'].get('error_code'),
                           'parent_link': failed['metadata'].get('parent_source_id') == source['id'],
                           'parent_content_http': original.status_code,
                           'case_id': snapshot(url)['case_id']},
                           failed['status'] == 'failed' and failed['metadata'].get('error_code') == 'url_http_error'
                           and failed['metadata'].get('parent_source_id') == source['id']
                           and original.status_code == 200 and snapshot(url)['case_id'] is None)

                    assert client.delete(url + '/sources/' + failed['id'], headers=headers).status_code == 200
                    replacement = client.post(url + '/sources/files', headers=headers,
                                              data={'consent': 'true'},
                                              files=[('files', ('corrected.txt', b'Corrected synthetic original', 'text/plain'))])
                    assert replacement.status_code == 200
                    restored = snapshot(url)
                    record('H07-manual-replacement', {'source_count': restored['source_count'],
                           'failed_count': restored['failed_source_count'],
                           'parent_preserved': any(s['id'] == source['id'] for s in restored['sources']),
                           'case_id': restored['case_id']},
                           restored['source_count'] == 2 and restored['failed_source_count'] == 0
                           and any(s['id'] == source['id'] for s in restored['sources'])
                           and restored['case_id'] is None)

                    for label, raw, final_url in [
                        ('login-html', b'<html><body><h1>Sign in to download</h1><form>Login</form></body></html>',
                         'https://example.com/login'),
                        ('error-html', b'<html><body><p>Download unavailable</p></body></html>',
                         'https://example.com/form.pdf'),
                    ]:
                        reply.clear()
                        reply.update(raw=raw, mime='text/html', final_url=final_url)
                        html_batch = batch()
                        html_parent = parent(html_batch)
                        response = attach(html_batch, html_parent)
                        assert response.status_code == 200
                        child = response.json()['data']
                        record('H07-' + label + '-not-an-attachment', {
                            'source_status': child['status'], 'stored_mime': child['metadata'].get('mime'),
                            'document_created': bool(child['metadata'].get('document_id')),
                            'analyzable_count': snapshot(html_batch)['analyzable_source_count'],
                        }, child['status'] == 'failed')

                file_batch = batch()
                raw = b'Valid synthetic TXT whose parser fails'
                with patch.object(main, 'parse_bytes', side_effect=RuntimeError('SYNTHETIC_PRIVATE_ERROR')):
                    response = client.post(file_batch + '/sources/files', headers=headers,
                                           data={'consent': 'true'},
                                           files=[('files', ('parse-failed.txt', raw, 'text/plain'))])
                assert response.status_code == 200
                file_source = response.json()['data'][0]
                doc_id = file_source['metadata'].get('document_id')
                content = client.get('/api/v1/documents/' + str(doc_id) + '/content', headers=headers)
                foreign = client.get('/api/v1/documents/' + str(doc_id) + '/content', headers=head(other))
                with auth.conn() as connection:
                    count = connection.execute(
                        'SELECT COUNT(*) FROM source_documents WHERE owner_id=? AND source_id=? AND document_id=?',
                        (user['user']['id'], file_source['id'], doc_id)).fetchone()[0]
                record('H07-parse-failure-original-protection', {
                    'status': file_source['status'], 'error_code': file_source['metadata'].get('error_code'),
                    'original_download_matches': content.content == raw,
                    'cross_owner_http': foreign.status_code,
                    'raw_error_hidden': 'SYNTHETIC_PRIVATE_ERROR' not in response.text,
                }, file_source['status'] == 'failed' and content.status_code == 200
                       and content.content == raw and foreign.status_code == 404
                       and 'SYNTHETIC_PRIVATE_ERROR' not in response.text)
                record('H07-parse-failure-source-document-relation', {
                    'metadata_has_document_id': bool(doc_id), 'source_documents_count': count,
                }, bool(doc_id) and count == 1)
        finally:
            client.target = None
            if auth._memory_connection is not None:
                auth._memory_connection.close()
                auth._memory_connection = None
    gaps = sum(row['status'] == 'OPEN_GAP' for row in results)
    print(json.dumps({'kind': 'diagnostic_not_acceptance', 'checks': results,
                      'passed_boundaries': len(results) - gaps, 'open_gaps': gaps},
                     ensure_ascii=False, indent=2))
    return 2 if gaps else 0


if __name__ == '__main__':
    sys.exit(run())
