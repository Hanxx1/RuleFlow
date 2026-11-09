import json
import sqlite3
import pytest
from app.services.review import ReviewError,save_review,read_review,confirm_review,require_confirmed,invalidate_review


@pytest.fixture
def db():
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.executescript('''
      CREATE TABLE cases(id TEXT PRIMARY KEY,owner_id TEXT,status TEXT,deadline TEXT,deadline_source TEXT,deadline_evidence_ids_json TEXT,updated_at TEXT);
      CREATE TABLE evidence(id TEXT PRIMARY KEY,owner_id TEXT,case_id TEXT,source_name TEXT,text TEXT,locator TEXT,page INTEGER,created_at TEXT);
      CREATE TABLE analysis_metadata(owner_id TEXT,case_id TEXT);
      CREATE TABLE case_reviews(owner_id TEXT,case_id TEXT,revision INTEGER,status TEXT,candidate_json TEXT,decision_json TEXT,confirmed_at TEXT,PRIMARY KEY(owner_id,case_id));
      CREATE TABLE review_events(id TEXT,owner_id TEXT,case_id TEXT,revision INTEGER,action TEXT,details_json TEXT,created_at TEXT);
      CREATE TABLE tasks(id TEXT PRIMARY KEY,owner_id TEXT,case_id TEXT,title TEXT,status TEXT,deadline TEXT,evidence_ids_json TEXT,created_at TEXT,updated_at TEXT,duration_minutes INTEGER);
      CREATE TABLE materials(id TEXT,title TEXT,owner_id TEXT,case_id TEXT);
      CREATE TABLE task_material_links(owner_id TEXT,task_id TEXT,material_id TEXT,PRIMARY KEY(owner_id,task_id,material_id));
      CREATE TABLE schedule_items(owner_id TEXT,task_id TEXT,ends_at TEXT);
      CREATE TABLE task_planning(task_id TEXT,owner_id TEXT,evidence_id TEXT);
      INSERT INTO cases VALUES('c','a','review',NULL,NULL,'[]','now');
      INSERT INTO evidence VALUES('block:a','a','c','文档','请填写申请表。','正文',NULL,'now');
    ''')
    save_review(connection, 'a', 'c', {'actions': [{'id': 'action:0', 'title': '填写申请表', 'evidence_ids': ['block:a'], 'evidence_quotes': {'block:a': '填写申请表'}}], 'dates': []})
    connection.commit()
    yield connection
    connection.close()


def confirm(db, **kwargs):
    return confirm_review(db, 'a', 'c', kwargs.get('revision', 1), kwargs.get('action_ids', ['action:0']), kwargs.get('deadline_id'), kwargs.get('manual_deadline'), kwargs.get('no_deadline', True))


def test_gate_owner_scope_and_no_tasks_before_confirmation(db):
    assert read_review(db, 'b', 'c') is None
    with pytest.raises(ReviewError): require_confirmed(db, 'b', 'c')
    assert db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 0
    with pytest.raises(ReviewError, match='确认'): require_confirmed(db, 'a', 'c')
    assert confirm(db)['status'] == 'confirmed'
    require_confirmed(db, 'a', 'c')


def test_individual_task_dates_are_saved_with_evidence_and_idempotent(db):
    db.execute("INSERT INTO evidence VALUES('block:date','a','c','通知','2026年12月1日前提交','正文',NULL,'now')")
    candidate=read_review(db,'a','c')['candidate']
    candidate['actions'].append({'id':'action:1','title':'复核','evidence_ids':['block:a'],'evidence_quotes':{'block:a':'申请表'}})
    candidate['dates']=[{'id':'date:1','role':'deadline','value':'2026-12-01','evidence_ids':['block:date']}]
    save_review(db,'a','c',candidate)
    choices={'action:0':{'deadline_id':'date:1'},'action:1':{'manual_deadline':'2026-12-02'}}
    one=confirm_review(db,'a','c',2,['action:0','action:1'],None,None,True,choices)
    assert confirm_review(db,'a','c',2,['action:0','action:1'],None,None,True,choices)==one
    rows=db.execute('SELECT title,deadline,evidence_ids_json FROM tasks ORDER BY deadline').fetchall()
    assert [row['deadline'] for row in rows]==['2026-12-01','2026-12-02']
    assert 'block:date' in json.loads(rows[0]['evidence_ids_json'])
    assert len(json.loads(rows[1]['evidence_ids_json']))==2
    assert db.execute('SELECT deadline FROM cases').fetchone()[0] is None


def test_individual_task_dates_reject_foreign_actions_and_invalid_dates(db):
    for choices in ({'foreign':{'no_deadline':True}},{'action:0':{'manual_deadline':'2026-02-30'}},{'action:0':{'deadline_id':'foreign'}},{'action:0':{'no_deadline':True,'manual_deadline':'2026-12-02'}}):
        with pytest.raises(ReviewError):confirm_review(db,'a','c',1,['action:0'],None,None,True,choices)
    assert db.execute('SELECT count(*) FROM tasks').fetchone()[0]==0


def test_task_deadline_change_cannot_invalidate_existing_schedule(db):
    from app.services.review import compiled_task_id
    action=read_review(db,'a','c')['candidate']['actions'][0]
    task_id=compiled_task_id('a','c','action:0',action)
    db.execute('INSERT INTO schedule_items VALUES(?,?,?)',('a',task_id,'2026-12-03T10:00:00+08:00'))
    with pytest.raises(ReviewError,match='日程超出'):
        confirm_review(db,'a','c',1,['action:0'],None,None,True,{'action:0':{'manual_deadline':'2026-12-02'}})
    assert db.execute('SELECT count(*) FROM tasks').fetchone()[0]==0


def test_confirmation_is_idempotent_and_audits_no_original_text(db):
    one, two = confirm(db), confirm(db)
    assert one == two
    assert db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 1
    audit = db.execute("SELECT details_json FROM review_events WHERE action='analysis_confirmed'").fetchall()
    assert len(audit) == 1 and '填写申请表' not in audit[0][0]
    with pytest.raises(ReviewError): confirm(db, action_ids=[])


def test_revision_changed_invalidates_confirmation_without_duplicate_tasks(db):
    confirm(db)
    invalidate_review(db, 'a', 'c')
    with pytest.raises(ReviewError): confirm(db)
    with pytest.raises(ReviewError): require_confirmed(db, 'a', 'c')
    confirm(db, revision=2)
    assert db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 1


def test_invalid_actions_dates_and_foreign_evidence_are_rejected(db):
    for options in ({'action_ids': ['foreign']}, {'action_ids': ['action:0', 'action:0']}, {'no_deadline': False}, {'manual_deadline': '2026-02-30', 'no_deadline': False}):
        with pytest.raises(ReviewError): confirm(db, **options)
    db.execute("UPDATE evidence SET owner_id='b'")
    with pytest.raises(ReviewError): confirm(db)
    assert db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 0


def test_user_date_has_user_assertion_evidence_and_not_official_source(db):
    confirm(db, manual_deadline='2026-10-25', no_deadline=False)
    case = db.execute('SELECT * FROM cases').fetchone()
    assert case['deadline'] == '2026-10-25' and case['deadline_source'] == 'user_input'
    ref = json.loads(case['deadline_evidence_ids_json'])[0]
    assert db.execute('SELECT source_name FROM evidence WHERE id=?', (ref,)).fetchone()[0] == '用户确认'


def test_reconfirmation_keeps_user_estimate_reference(db):
    confirm(db)
    task_id=db.execute('SELECT id FROM tasks').fetchone()[0]
    db.execute("INSERT INTO evidence VALUES('block:estimate','a','c','用户估计','30分钟','用户填写',NULL,'now')")
    db.execute('INSERT INTO task_planning VALUES(?,?,?)',(task_id,'a','block:estimate'))
    invalidate_review(db,'a','c');confirm(db,revision=2)
    assert 'block:estimate' in json.loads(db.execute('SELECT evidence_ids_json FROM tasks').fetchone()[0])


@pytest.mark.parametrize('end,allowed', [('2099-01-01T15:59:59Z', True),
                                        ('2099-01-01T15:59:59.000001Z', False)])
def test_date_only_reconfirmation_uses_shanghai_exact_cutoff(db, end, allowed):
    from app.services.review import compiled_task_id
    action = read_review(db, 'a', 'c')['candidate']['actions'][0]
    task_id = compiled_task_id('a', 'c', 'action:0', action)
    db.execute('INSERT INTO schedule_items VALUES(?,?,?)', ('a', task_id, end))
    choices = {'action:0': {'manual_deadline': '2099-01-01'}}
    if allowed:
        assert confirm_review(db, 'a', 'c', 1, ['action:0'], None, None, True, choices)['status'] == 'confirmed'
        assert db.execute('SELECT deadline FROM tasks WHERE id=?', (task_id,)).fetchone()['deadline'] == '2099-01-01'
    else:
        with pytest.raises(ReviewError) as error:
            confirm_review(db, 'a', 'c', 1, ['action:0'], None, None, True, choices)
        assert error.value.code == 'REVIEW_SCHEDULE_CONFLICT'
        assert db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 0
