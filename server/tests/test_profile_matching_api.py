from helpers import client,account,head
from app.main import database
database()  # TestClient without a lifespan context needs an explicit isolated schema initialization.


def test_typed_profile_rejects_invalid_values_atomically_and_versions_owner_changes():
    a,b=account('typed-profile@example.com'),account('typed-profile-other@example.com')
    path='/api/v1/profile'
    assert client.put(path,headers=head(a),json={'facts':{'enrollment_year':2024,'rank_percent':None}}).status_code==200
    version=client.get(path+'/meta',headers=head(a)).json()['data']['revision']
    result=client.put(path,headers=head(a),json={'facts':{'enrollment_year':2023,'rank_percent':'10'}})
    assert result.status_code==422 and result.json()['detail']['code']=='PROFILE_INVALID'
    assert client.get(path,headers=head(a)).json()['data']['enrollment_year']==2024
    assert client.get(path+'/meta',headers=head(a)).json()['data']['revision']==version
    assert client.get(path+'/meta',headers=head(b)).json()['data']['revision']==0


def test_new_notice_matches_all_user_conditions_and_case_facts_are_private():
    a,b=account('matching-profile@example.com'),account('matching-profile-other@example.com')
    client.put('/api/v1/profile',headers=head(a),json={'facts':{'enrollment_year':2024,'student_type':'undergraduate'}})
    case_id=client.post('/api/v1/imports/text',headers=head(a),json={'text':'面向2024级本科生。专业排名前20%。请提交申请表。','consent':True}).json()['data']['case_id']
    path='/api/v1/cases/'+case_id
    outcome=client.get(path+'/evaluate',headers=head(a)).json()['data']
    assert outcome['relevance']=='UNKNOWN' and outcome['missing_profile_fields']==['profile.rank_percent']
    assert client.put(path+'/facts',headers=head(a),json={'key':'profile.rank_percent','value':'10'}).status_code==422
    assert client.put(path+'/facts',headers=head(b),json={'key':'profile.rank_percent','value':10}).status_code==404
    assert client.put(path+'/facts',headers=head(a),json={'key':'profile.rank_percent','value':30}).status_code==200
    assert client.get(path+'/evaluate',headers=head(a)).json()['data']['relevance']=='FALSE'
    assert client.put(path+'/facts',headers=head(a),json={'key':'profile.rank_percent','value':10}).status_code==200
    assert client.get(path+'/evaluate',headers=head(a)).json()['data']['relevance']=='TRUE'
    review=client.get(path+'/reviews',headers=head(a)).json()['data']
    assert review['candidate']['profile_revision']>0 and review['candidate']['analysis']['rules']
    assert review['status']=='needs_confirmation'
