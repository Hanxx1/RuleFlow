import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.migrations import apply_migrations
from app.settings import resolve_settings
from app.demo.bootstrap import bootstrap_owner
from app.providers.vault import get_vault_content_provider


def test_settings_select_demo_database_and_reject_collision(tmp_path):
    real = tmp_path / "real.db"
    demo = tmp_path / "demo.db"
    settings = resolve_settings(
        {
            "DEMO_MODE": "true",
            "DATABASE_PATH": str(real),
            "DEMO_DATABASE_PATH": str(demo),
        }
    )
    assert settings.demo_mode is True
    assert settings.database_path == demo.resolve()
    with pytest.raises(RuntimeError, match="must differ"):
        resolve_settings(
            {
                "DEMO_MODE": "true",
                "DATABASE_PATH": str(real),
                "DEMO_DATABASE_PATH": str(real),
            }
        )
    shared_uploads = tmp_path / "uploads"
    with pytest.raises(RuntimeError, match="DEMO_UPLOAD_ROOT must differ"):
        resolve_settings(
            {
                "DEMO_MODE": "true",
                "DATABASE_PATH": str(real),
                "DEMO_DATABASE_PATH": str(demo),
                "DEMO_UPLOAD_ROOT": str(shared_uploads),
                "VAULT_UPLOAD_ROOT": str(shared_uploads),
            }
        )


def test_real_mode_refuses_demo_bootstrap():
    with pytest.raises(RuntimeError, match="requires DEMO_MODE=true"):
        bootstrap_owner("not-a-demo-owner")


def test_real_mode_vault_provider_refuses_demo_fixture():
    with pytest.raises(FileNotFoundError):
        get_vault_content_provider().read(
            "not-a-demo-owner", "fixture", "德育加分申请表.txt"
        )


def test_application_import_fails_when_demo_and_real_database_paths_match(tmp_path):
    database = tmp_path / "same.db"
    environment = os.environ.copy()
    environment.update(
        {
            "DEMO_MODE": "true",
            "DATABASE_PATH": str(database),
            "DEMO_DATABASE_PATH": str(database),
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "DEMO_DATABASE_PATH must differ" in completed.stderr


def test_migration_backfills_legacy_session_token_types():
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE sessions(
          id TEXT PRIMARY KEY,user_id TEXT NOT NULL,family_id TEXT NOT NULL,
          token_hash TEXT NOT NULL,expires_at TEXT NOT NULL,revoked_at TEXT,
          device_name TEXT,created_at TEXT NOT NULL,last_used_at TEXT
        );
        INSERT INTO sessions VALUES
          ('a','u','fa','ha','2099',NULL,'access','now','now'),
          ('r','u','fr','hr','2099',NULL,'手机','now','now');
        """
    )
    apply_migrations(connection)
    rows = dict(connection.execute("SELECT id,token_type FROM sessions"))
    assert rows == {"a": "access", "r": "refresh"}
    versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert versions == [1, 2]


def test_demo_bootstrap_owner_isolation_and_reset(tmp_path):
    real_db = tmp_path / "real.db"
    demo_db = tmp_path / "demo.db"
    upload_root = tmp_path / "demo_uploads"
    result_file = tmp_path / "result.json"
    script = r'''
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.auth import conn
from app.demo.reset import reset_owner

client=TestClient(app)
def account(email):
    registered=client.post('/api/v1/auth/register',json={'email':email,'password':'correct horse battery staple'}).json()['data']
    client.post('/api/v1/auth/verify',json={'token':registered['development_verification_token']})
    return client.post('/api/v1/auth/login',json={'email':email,'password':'correct horse battery staple','device_name':'测试设备'}).json()['data']
def head(account):return {'Authorization':'Bearer '+account['access_token']}

first=account('demo-one@example.com')
second=account('demo-two@example.com')
first_cases=client.get('/api/v1/cases',headers=head(first)).json()['data']
second_cases=client.get('/api/v1/cases',headers=head(second)).json()['data']
assert len(first_cases)==13 and len(second_cases)==13
assert sum('公开通知演示' in c['title'] for c in first_cases)==12
assert {c['id'] for c in first_cases}.isdisjoint({c['id'] for c in second_cases})
assert first_cases[0]['id']!=second_cases[0]['id']
first_plan=client.get('/api/v1/cases/'+first_cases[0]['id']+'/plan',headers=head(first)).json()['data']
task_id=first_plan['ordered_tasks'][0]['id']
initial_schedule=client.get('/api/v1/schedule',headers=head(first)).json()['data']
initial_vault=client.get('/api/v1/vault/items',headers=head(first)).json()['data']
initial_dashboard=client.get('/api/v1/dashboard',headers=head(first)).json()['data']
assert len(initial_schedule)==3 and len(initial_vault)==2
knowledge=client.get('/api/v1/cases/'+first_cases[0]['id']+'/knowledge-evidence',headers=head(first)).json()['data']
assert knowledge['status']=='available' and knowledge['items'] and all(item['confidence'] is None for item in knowledge['items'])
assert client.get('/api/v1/vault/items/'+initial_vault[0]['id']+'/content',headers=head(first)).content
client.patch('/api/v1/tasks/'+task_id,headers=head(first),json={'status':'done'})
mutated_dashboard=client.get('/api/v1/dashboard',headers=head(first)).json()['data']
assert mutated_dashboard['recent_cases'][0]['progress']!=initial_dashboard['recent_cases'][0]['progress']
client.delete('/api/v1/schedule/items/'+initial_schedule[0]['id'],headers=head(first))
client.delete('/api/v1/vault/items/'+initial_vault[0]['id'],headers=head(first))
client.post('/api/v1/schedule/items',headers=head(first),json={'title':'运行时安排','kind':'busy','starts_at':'2099-01-01T08:00:00+08:00','ends_at':'2099-01-01T09:00:00+08:00'})
runtime_vault=client.post('/api/v1/vault/items',headers=head(first),data={'consent':'true','category':'proof','case_ids':json.dumps([first_cases[0]['id']]),'task_ids':json.dumps([task_id])},files={'file':('runtime.txt',b'runtime-content','text/plain')}).json()['data']
runtime_batch=client.post('/api/v1/import-batches',headers=head(first),json={'title':'运行时导入'}).json()['data']
client.post('/api/v1/import-batches/'+runtime_batch['id']+'/sources/text',headers=head(first),json={'text':'运行时批次通知，请准备申请表。','consent':True})
client.post('/api/v1/import-batches/'+runtime_batch['id']+'/analyze',headers=head(first))
with conn() as connection:
    owner=connection.execute("SELECT id FROM users WHERE email='demo-one@example.com'").fetchone()['id']
    assert connection.execute('SELECT COUNT(*) FROM import_batches WHERE owner_id=?',(owner,)).fetchone()[0]==1
    assert connection.execute('SELECT COUNT(*) FROM import_sources WHERE owner_id=?',(owner,)).fetchone()[0]==1
    assert connection.execute('SELECT COUNT(*) FROM import_analysis_runs WHERE owner_id=?',(owner,)).fetchone()[0]==1
owner_upload=Path(__import__('os').environ['DEMO_UPLOAD_ROOT'])/owner
assert (owner_upload/runtime_vault['id']).read_bytes()==b'runtime-content'
reset_owner(owner)
reset_cases=client.get('/api/v1/cases',headers=head(first)).json()['data']
reset_plan=client.get('/api/v1/cases/'+reset_cases[0]['id']+'/plan',headers=head(first)).json()['data']
reset_schedule=client.get('/api/v1/schedule',headers=head(first)).json()['data']
reset_vault=client.get('/api/v1/vault/items',headers=head(first)).json()['data']
reset_dashboard=client.get('/api/v1/dashboard',headers=head(first)).json()['data']
assert reset_cases[0]['id']==first_cases[0]['id']
assert reset_plan['ordered_tasks'][0]['status']=='todo'
assert {item['id'] for item in reset_schedule}=={item['id'] for item in initial_schedule}
assert {item['id'] for item in reset_vault}=={item['id'] for item in initial_vault}
assert {key:reset_dashboard[key] for key in ('total_cases','in_progress_cases','due_soon_cases','completed_cases')}=={key:initial_dashboard[key] for key in ('total_cases','in_progress_cases','due_soon_cases','completed_cases')}
assert [(item['id'],item['progress']) for item in reset_dashboard['recent_cases']]==[(item['id'],item['progress']) for item in initial_dashboard['recent_cases']]
assert not owner_upload.exists()
with conn() as connection:
    assert connection.execute('SELECT COUNT(*) FROM import_batches WHERE owner_id=?',(owner,)).fetchone()[0]==0
    assert connection.execute('SELECT COUNT(*) FROM import_sources WHERE owner_id=?',(owner,)).fetchone()[0]==0
    assert connection.execute('SELECT COUNT(*) FROM import_analysis_runs WHERE owner_id=?',(owner,)).fetchone()[0]==0
assert len(client.get('/api/v1/cases',headers=head(second)).json()['data'])==13
assert len(client.get('/api/v1/schedule',headers=head(second)).json()['data'])==3
assert len(client.get('/api/v1/vault/items',headers=head(second)).json()['data'])==2
Path(__import__('os').environ['RESULT_FILE']).write_text(json.dumps({'first':first_cases[0]['id'],'second':second_cases[0]['id']}),encoding='utf-8')
'''
    environment = os.environ.copy()
    environment.update(
        {
            "DEMO_MODE": "true",
            "DATABASE_PATH": str(real_db),
            "DEMO_DATABASE_PATH": str(demo_db),
            "DEMO_UPLOAD_ROOT": str(upload_root),
            "RESULT_FILE": str(result_file),
            "APP_ENV": "development",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert demo_db.exists()
    assert not real_db.exists()
    result = json.loads(result_file.read_text(encoding="utf-8"))
    assert result["first"] != result["second"]
