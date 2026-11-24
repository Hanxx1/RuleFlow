"""C-internal source inspection; not wired to an HTTP API or public DTO.

The caller supplies an authenticated owner, an existing SQLite connection and
the original-file root. No import, parser, model, write or download is invoked.
Public error/status mapping remains subject to the RF-011/013 contract review.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path

from .documents import content_path


class SourceSnapshotError(ValueError):
    """A content-free internal error; never includes resource IDs or paths."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _invalid():
    raise SourceSnapshotError('SOURCE_REFERENCE_INVALID')


def _code(value):
    # Do not forward free-form source errors or arbitrary metadata into a DTO.
    if isinstance(value, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}|source_failed', value):
        return value
    return None


def _metadata(source):
    try:
        result = json.loads(source['metadata_json'])
    except (TypeError, ValueError):
        _invalid()
    if not isinstance(result, dict):
        _invalid()
    return result


def _source_records(connection, owner_id, batch_id):
    records = []
    for row in connection.execute(
        'SELECT * FROM import_sources WHERE batch_id=? ORDER BY created_at,id', (batch_id,)
    ).fetchall():
        source = dict(row)
        if source['owner_id'] != owner_id:
            _invalid()
        metadata = _metadata(source)
        parent_id = metadata.get('parent_source_id')
        parent_state = 'none'
        if parent_id is not None:
            if not isinstance(parent_id, str) or not parent_id or parent_id == source['id']:
                _invalid()
            parent = connection.execute(
                'SELECT owner_id,batch_id FROM import_sources WHERE id=?', (parent_id,)
            ).fetchone()
            if parent is None:
                parent_id, parent_state = None, 'missing'
            elif parent['owner_id'] != owner_id or parent['batch_id'] != batch_id:
                _invalid()
            else:
                parent_state = 'valid'

        relation = connection.execute(
            'SELECT owner_id,document_id FROM source_documents WHERE source_id=?', (source['id'],)
        ).fetchone()
        document_id = metadata.get('document_id')
        document, lines = None, []
        if document_id is not None or relation is not None:
            if (not isinstance(document_id, str) or not document_id or relation is None
                    or relation['owner_id'] != owner_id or relation['document_id'] != document_id):
                _invalid()
            row = connection.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
            if row is None or row['owner_id'] != owner_id:
                _invalid()
            document = dict(row)
            rows = connection.execute(
                'SELECT * FROM document_lines WHERE document_id=? ORDER BY line_number,id',
                (document_id,),
            ).fetchall()
            for row in rows:
                if row['owner_id'] != owner_id:
                    _invalid()
                try:
                    bbox = json.loads(row['bbox_json'] or 'null')
                except (TypeError, ValueError):
                    _invalid()
                lines.append({
                    'line_id': row['id'], 'document_id': document_id,
                    'line_number': row['line_number'], 'text': row['text'],
                    'page': row['page'], 'locator': row['locator'],
                    'bbox': bbox, 'coordinate_space': row['coordinate_space'],
                    'page_width': row['page_width'], 'page_height': row['page_height'],
                    'confidence': row['confidence'],
                })
        records.append((source, metadata, parent_id, parent_state, document, lines))
    return records


def _original_state(root, owner_id, document_id):
    try:
        target = content_path(root, owner_id, document_id)
        if not stat.S_ISREG(target.stat().st_mode):
            return {'state': 'unverified', 'error_code': 'DOCUMENT_CONTENT_UNVERIFIED'}
    except FileNotFoundError:
        return {'state': 'missing', 'error_code': 'DOCUMENT_CONTENT_MISSING'}
    except OSError:
        return {'state': 'unverified', 'error_code': 'DOCUMENT_CONTENT_UNVERIFIED'}
    return {'state': 'present', 'error_code': None}


def read_source_snapshot(connection, owner_id: str, batch_id: str,
                         expected_revision: int, *, original_root: Path) -> dict:
    """Inspect one DB snapshot without committing a caller's outer transaction.

    File presence is advisory and observed afterwards; actual downloads still
    require authorization and byte-hash verification. A batch revision alone
    does not identify its current source set. No user export decision is made.
    """
    if type(expected_revision) is not int or expected_revision < 0:
        raise SourceSnapshotError('REVISION_REQUIRED')
    connection.execute('SAVEPOINT notice_source_snapshot')
    try:
        batch = connection.execute(
            'SELECT id,revision,case_id FROM import_batches WHERE id=? AND owner_id=?',
            (batch_id, owner_id),
        ).fetchone()
        if batch is None:
            raise SourceSnapshotError('BATCH_NOT_FOUND')
        if batch['revision'] != expected_revision:
            raise SourceSnapshotError('IMPORT_BATCH_STALE')
        result = {'batch_id': batch['id'], 'batch_revision': batch['revision'],
                  'case_id': batch['case_id'], 'sources': []}
        # Validate all ownership/relationships before any original-file probe.
        records = _source_records(connection, owner_id, batch_id)
    finally:
        connection.execute('RELEASE SAVEPOINT notice_source_snapshot')

    for source, metadata, parent_id, parent_state, document, lines in records:
        item = {
            'source_id': source['id'], 'name': source['name'], 'kind': source['kind'],
            'status': source['status'], 'error_code': _code(metadata.get('error_code')),
            'parent_source_id': parent_id, 'parent_reference_state': parent_state,
            'document_ref': None, 'text_origin': None, 'content_hash': None,
            'text': None, 'lines': lines,
        }
        if document is not None:
            item['document_ref'] = {
                'kind': 'document', 'id': document['id'], 'revision': document['revision'],
                'sha256': document['sha256'], 'name': document['name'],
                'mime': document['mime'], 'size': document['size'],
            }
            item['original'] = _original_state(original_root, owner_id, document['id'])
            item['text_origin'], item['content_hash'] = 'document_lines', document['sha256']
            if lines:
                item['text'] = '\n'.join(line['text'] for line in lines)
                item['extraction'] = {'state': 'available', 'error_code': None}
            else:
                error = _code(document['error_code'])
                item['extraction'] = {
                    'state': 'empty' if error == 'OCR_EMPTY' or document['status'] != 'failed' else 'failed',
                    'error_code': error,
                }
        elif source['kind'] == 'text':
            text = source['extracted_text']
            item['original'] = {'state': 'not_applicable', 'error_code': None}
            item['text_origin'], item['text'] = 'legacy_text', text
            if text is not None:
                item['content_hash'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
            item['extraction'] = {'state': 'available' if text else 'empty', 'error_code': None}
        else:
            item['original'] = {'state': 'not_acquired', 'error_code': item['error_code']}
            item['extraction'] = {'state': 'not_acquired', 'error_code': item['error_code']}
        result['sources'].append(item)
    return result
