"""RF-043 characterization only: reports current gaps, not acceptance tests.

Run from repository root with the existing review virtual environment.
Uses synthetic accounts, temporary SQLite/uploads and no model endpoint.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT / 'server'), str(ROOT / 'server/tests')]

with tempfile.TemporaryDirectory(prefix='campusweave-d-probe-') as directory:
    os.environ.update(DATABASE_PATH=':memory:',
                      APP_ENV='development', DEMO_MODE='false',
                      LLM_BASE_URL='', LLM_MODEL='', LLM_API_KEY='',
                      VAULT_UPLOAD_ROOT=str(Path(directory) / 'vault'),
                      DEMO_UPLOAD_ROOT=str(Path(directory) / 'demo'),
                      DOCUMENT_UPLOAD_ROOT=str(Path(directory) / 'documents'))
    from fastapi.testclient import TestClient
    from app.main import app
    from helpers import client, head
    from test_schedule_drafts import setup_case

    with TestClient(app) as active:
        client.target = active
        results = []
        for scenario in ('external_predecessor', 'past_window', 'timezone_deadline'):
            account, case_id = setup_case(scenario + '@example.com')
            headers = head(account)
            tasks = client.get('/api/v1/cases/' + case_id + '/plan', headers=headers).json()['data']['ordered_tasks']
            before, after = [task['id'] for task in tasks]
            body = {'task_ids': [after], 'window_start': '2099-01-01T08:00:00+08:00',
                    'window_end': '2099-01-01T12:00:00+08:00'}
            if scenario == 'external_predecessor':
                assert client.put('/api/v1/tasks/' + before + '/planning', headers=headers,
                                  json={'duration_minutes': 90, 'splittable': True, 'max_chunk_minutes': 30}).status_code == 200
                assert client.post('/api/v1/cases/' + case_id + '/edges', headers=headers,
                                   json={'before_task_id': before, 'after_task_id': after}).status_code == 200
                assert client.post('/api/v1/schedule/items', headers=headers,
                                   json={'title': 'synthetic partial predecessor', 'kind': 'task', 'task_id': before,
                                         'starts_at': '2099-01-01T08:00:00+08:00', 'ends_at': '2099-01-01T08:30:00+08:00'}).status_code == 200
            elif scenario == 'past_window':
                body.update(window_start='2000-01-01T08:00:00+08:00', window_end='2000-01-01T12:00:00+08:00')
            else:
                evidence = client.get('/api/v1/cases/' + case_id + '/resources', headers=headers).json()['data']['evidence'][0]['id']
                created = client.post('/api/v1/cases/' + case_id + '/tasks', headers=headers,
                                      json={'title': 'synthetic UTC deadline', 'deadline': '2099-01-01', 'duration_minutes': 30, 'evidence_ids': [evidence]})
                assert created.status_code == 200, created.text
                body.update(task_ids=[created.json()['data']['id']], timezone='UTC',
                            window_start='2099-01-01T17:00:00Z', window_end='2099-01-01T20:00:00Z')
            draft = client.post('/api/v1/schedule/drafts', headers=headers, json=body)
            assert draft.status_code == 200, draft.text
            payload = draft.json()['data']
            count_before = len(client.get('/api/v1/schedule', headers=headers).json()['data'])
            committed = client.post('/api/v1/schedule/drafts/' + payload['draft_id'] + '/commit', headers=headers, json={'consent': True})
            count_after = len(client.get('/api/v1/schedule', headers=headers).json()['data'])
            results.append({'scenario': scenario, 'draft_status': draft.status_code,
                            'suggestion_count': len(payload['suggestions']),
                            'first_start': payload['suggestions'][0]['starts_at'] if payload['suggestions'] else None,
                            'commit_status': committed.status_code,
                            'error': committed.json().get('detail'),
                            'schedule_count_before': count_before, 'schedule_count_after': count_after})
        print(json.dumps(results, ensure_ascii=False, indent=2))
        client.target = None
    from app import auth
    if auth._memory_connection is not None:
        auth._memory_connection.close()
        auth._memory_connection = None
