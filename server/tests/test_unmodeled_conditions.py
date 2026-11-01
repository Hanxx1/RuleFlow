from helpers import client,account,head


def test_supported_rule_cannot_prove_all_original_conditions():
    from app.main import database
    database()
    a=account('unmodeled-public-notice@example.com')
    client.put('/api/v1/profile',headers=head(a),json={'facts':{'team_size':3}})
    case_id=client.post('/api/v1/imports/text',headers=head(a),json={'text':'每支团队不超过5名学生。每位学生当届只可参加一支团队。','consent':True}).json()['data']['case_id']
    outcome=client.get('/api/v1/cases/'+case_id+'/evaluate',headers=head(a)).json()['data']
    assert outcome['relevance']=='UNKNOWN' and outcome['reason']=='unmodeled_conditions'
    assert outcome['unsupported_conditions'][0]['evidence_ids']
    client.put('/api/v1/profile',headers=head(a),json={'facts':{'team_size':6}})
    assert client.get('/api/v1/cases/'+case_id+'/evaluate',headers=head(a)).json()['data']['relevance']=='FALSE'
