from helpers import client,account,head


def test_manual_deadlines_are_strict_and_have_user_assertion_evidence():
    a=account('manual-deadline@example.com')
    for value in ('2026-10-20garbage','2026-10-20T17:00:00','2026-02-30'):
        assert client.post('/api/v1/cases',headers=head(a),json={'title':'手工事项','deadline':value}).status_code==422
    case=client.post('/api/v1/cases',headers=head(a),json={'title':'手工事项','deadline':'2026-10-20T17:00:00+08:00'}).json()['data']
    assert case['deadline']=='2026-10-20T09:00:00Z' and case['deadline_evidence_ids']
    refs=client.get('/api/v1/cases/'+case['id']+'/resources',headers=head(a)).json()['data']['evidence']
    assert refs[0]['id']==case['deadline_evidence_ids'][0] and refs[0]['source_name']=='用户填写'
    assert client.patch('/api/v1/cases/'+case['id'],headers=head(a),json={'deadline':'2026-10-21bad'}).status_code==422
