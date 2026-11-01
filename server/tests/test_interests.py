from test_api import client,account,head


def test_interest_is_private_cited_and_cannot_upgrade_false_or_unknown():
    a,b=account('interests-owner@example.com'),account('interests-other@example.com')
    assert client.put('/api/v1/profile/interests',headers=head(a),json={'categories':['competition']}).status_code==200
    assert client.get('/api/v1/profile/interests',headers=head(b)).json()['data']['categories']==[]
    imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'创新竞赛仅限2023级。请上传作品。','consent':True}).json()['data']
    url='/api/v1/cases/'+imported['case_id']+'/evaluate'
    unknown=client.get(url,headers=head(a)).json()['data']
    assert unknown['interest_match'] is True and unknown['eligibility_truth']=='UNKNOWN' and unknown['relevance_level']=='needs_verification'
    resources=client.get('/api/v1/cases/'+imported['case_id']+'/resources',headers=head(a)).json()['data']
    assert set(unknown['interest_evidence_ids'])<={row['id'] for row in resources['evidence']}
    client.put('/api/v1/profile',headers=head(a),json={'facts':{'enrollment_year':2024}})
    failed=client.get(url,headers=head(a)).json()['data']
    assert failed['interest_match'] is True and failed['eligibility_truth']=='FALSE' and failed['relevance_level']=='not_eligible'
    client.put('/api/v1/profile',headers=head(a),json={'facts':{'enrollment_year':2023}})
    assert client.get(url,headers=head(a)).json()['data']['relevance_level']=='preferred'
