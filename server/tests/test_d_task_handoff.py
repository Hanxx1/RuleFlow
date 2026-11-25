from helpers import account, client, confirm_import, head


def task_pair():
    user = account('task-handoff@example.com')
    headers = head(user)
    imported = client.post('/api/v1/imports/text', headers=headers, json={
        'text': '请准备申请表，并于 2026-10-01 前提交。', 'consent': True
    }).json()['data']
    case = imported['case_id']
    confirm_import(user, case)
    tasks = client.get(f'/api/v1/cases/{case}/plan', headers=headers).json()['data']['ordered_tasks']
    return headers, case, tasks[0]['id'], tasks[1]['id']


def test_skip_reopen_recomputes_pending_and_preserves_done():
    headers, case, first, second = task_pair()
    url = f'/api/v1/cases/{case}'
    assert client.post(url+'/edges', headers=headers, json={
        'before_task_id': first, 'after_task_id': second
    }).status_code == 200

    def status(task, value):
        assert client.patch('/api/v1/tasks/'+task, headers=headers, json={'status':value}).status_code == 200

    def successor():
        tasks = client.get(url+'/plan', headers=headers).json()['data']['ordered_tasks']
        return next(t for t in tasks if t['id'] == second)

    assert not successor()['is_actionable']
    status(first, 'skipped')
    assert successor()['is_actionable']
    status(first, 'todo')
    assert not successor()['is_actionable']
    status(first, 'skipped')
    status(second, 'done')
    status(first, 'todo')
    assert successor()['status'] == 'done'
