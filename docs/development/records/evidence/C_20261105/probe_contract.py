"""RF-002 baseline experiments, not tests of the proposed candidate API.

Run with Python 3.12+ from any directory. Only stdlib and existing pure services
are used. SQL literals are read from the real auth/bootstrap files without
importing FastAPI or starting the app. Every test uses an in-memory database;
no user files, credentials, HTTP calls, OCR or live models are involved.
"""
import ast
import json
from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'server'))
from app.migrations import apply_migrations
from app.services.documents import bind_document, normalize_lines
from app.services.file_validation import DocumentError
from app.services.review import (ReviewError, save_review, read_review,
                                 confirm_review, require_confirmed, invalidate_review)


def schema_literal(path):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    literals = [node.args[0].value for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'executescript' and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)]
    if len(literals) != 1:
        raise RuntimeError('Schema layout changed; review experiment setup: ' + str(path))
    return literals[0]


class ExistingContractExperiments(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(schema_literal(ROOT / 'server/app/auth.py'))
        self.db.executescript(schema_literal(ROOT / 'server/app/bootstrap.py'))
        apply_migrations(self.db)
        for owner in ('owner-a', 'owner-b'):
            self.db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',
                            (owner, owner + '@example.com', 'unused-synthetic', 'now', 'now', None))
        for cid, owner in [('case-a', 'owner-a'), ('case-a2', 'owner-a'), ('case-b', 'owner-b')]:
            self.db.execute('INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (cid, owner, 'synthetic', 'other', 'review', 'UNKNOWN', None,
                             'now', 'now', None, '[]'))
        self.db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',
                        ('doc-a', 'owner-a', 'synthetic.txt', 'text/plain', 'synthetic-hash',
                         0, 'parsed', None, 'now', 1))
        for line in normalize_lines([{'text': '请填写申请表。\n请上传作品。', 'locator': '正文'}], 'doc-a'):
            self.db.execute('INSERT INTO document_lines VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                            (line['id'], 'owner-a', 'doc-a', line['line_number'], None,
                             line['text'], line['locator'], 'null', None, None, None, None))
        self.refs = bind_document(self.db, 'owner-a', 'case-a', 'doc-a', '合成原件')
        self.action = {'id': 'action-a', 'title': '填写申请表',
                       'evidence_ids': [self.refs[0][0]],
                       'evidence_quotes': {self.refs[0][0]: '填写申请表'}}
        save_review(self.db, 'owner-a', 'case-a', {'actions': [self.action], 'dates': []})
        self.db.commit()

    def confirm(self, revision=1):
        with self.db:
            return confirm_review(self.db, 'owner-a', 'case-a', revision,
                                  ['action-a'], None, None, True)

    def test_shared_document_has_case_scoped_idempotent_evidence(self):
        again = bind_document(self.db, 'owner-a', 'case-a', 'doc-a', '合成原件')
        other = bind_document(self.db, 'owner-a', 'case-a2', 'doc-a', '合成原件')
        self.assertEqual(again, self.refs)
        self.assertTrue(set(ref for ref, _ in other).isdisjoint(ref for ref, _ in self.refs))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM document_lines').fetchone()[0], 2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM evidence_lines').fetchone()[0], 4)

    def test_document_and_case_owner_checks(self):
        for owner, cid, code in [('owner-b', 'case-b', 'DOCUMENT_NOT_FOUND'),
                                 ('owner-b', 'case-a', 'CASE_NOT_FOUND')]:
            with self.assertRaises(DocumentError) as caught:
                bind_document(self.db, owner, cid, 'doc-a', '合成原件')
            self.assertEqual((caught.exception.status, caught.exception.code), (404, code))

    def test_review_gate_and_confirmation_idempotence(self):
        with self.assertRaises(ReviewError) as caught:
            require_confirmed(self.db, 'owner-a', 'case-a')
        self.assertEqual(caught.exception.code, 'REVIEW_REQUIRED')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 0)
        self.confirm()
        self.confirm()
        require_confirmed(self.db, 'owner-a', 'case-a')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 1)
        self.assertEqual(self.db.execute('SELECT relevance FROM cases WHERE id=?', ('case-a',)).fetchone()[0], 'UNKNOWN')

    def test_stale_confirmation_preserves_tasks(self):
        invalidate_review(self.db, 'owner-a', 'case-a')
        self.db.commit()
        with self.assertRaises(ReviewError) as caught:
            self.confirm()
        self.assertEqual(caught.exception.code, 'REVIEW_STALE')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 0)

    def test_cross_case_evidence_rejected_in_same_owner(self):
        save_review(self.db, 'owner-a', 'case-a2', {'actions': [self.action], 'dates': []})
        self.db.commit()
        with self.assertRaises(ReviewError) as caught:
            with self.db:
                confirm_review(self.db, 'owner-a', 'case-a2', 1, ['action-a'], None, None, True)
        self.assertEqual(caught.exception.code, 'EVIDENCE_INVALID')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 0)

    def test_legacy_existing_task_id_and_done_status_preserved(self):
        self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)',
                        ('legacy-task', 'owner-a', 'case-a', '填写申请表', 'done', None,
                         json.dumps([self.refs[0][0]]), 'now', 'now', None))
        save_review(self.db, 'owner-a', 'case-a',
                    {'actions': [{**self.action, 'existing_task_id': 'legacy-task'}], 'dates': []})
        self.db.commit()
        self.confirm(revision=2)
        rows = [tuple(row) for row in self.db.execute('SELECT id,status FROM tasks')]
        self.assertEqual(rows, [('legacy-task', 'done')])

    def test_existing_attachment_table_rejects_shared_document(self):
        self.db.execute('INSERT INTO case_attachment_documents VALUES(?,?,?,?)',
                        ('owner-a', 'case-a', 'doc-a', self.refs[0][0]))
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.db.execute('INSERT INTO case_attachment_documents VALUES(?,?,?,?)',
                                ('owner-a', 'case-a2', 'doc-a', self.refs[0][0]))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM case_attachment_documents').fetchone()[0], 1)

    def test_existing_migrations_replay_without_changing_ids(self):
        self.confirm()
        before = list(self.db.iterdump())
        apply_migrations(self.db)
        self.assertEqual(before, list(self.db.iterdump()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
