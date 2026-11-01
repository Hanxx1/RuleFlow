from datetime import datetime,timezone
import pytest
from app.services.fact_history import normalize_validity,expired
from test_api import client,account,head


def test_validity_requires_timezone_and_expiry_boundary():
    assert normalize_validity('2026-10-20T08:00:00+08:00')=='2026-10-20T00:00:00+00:00'
    with pytest.raises(ValueError):normalize_validity('2026-10-20')
    assert expired('2026-10-20T00:00:00+00:00',datetime(2026,10,20,tzinfo=timezone.utc))


def test_fact_replacement_keeps_history_and_expired_profile_is_unknown():
    a,b=account('fact-history@example.com'),account('fact-history-other@example.com')
    imported=client.post('/api/v1/imports/text',headers=head(a),json={'text':'仅限2023级。','consent':True}).json()['data']
    payload={'facts':{'enrollment_year':2023},'valid_until':{'enrollment_year':'2000-01-01T00:00:00Z'}}
    assert client.put('/api/v1/profile',headers=head(a),json=payload).status_code==200
    outcome=client.get('/api/v1/cases/'+imported['case_id']+'/evaluate',headers=head(a)).json()['data']
    assert outcome['relevance']=='UNKNOWN' and 'profile.enrollment_year' in outcome['missing_profile_fields']
    assert client.get('/api/v1/profile',headers=head(a)).json()['data']['enrollment_year'] is None
    assert client.put('/api/v1/profile',headers=head(a),json={'facts':{'enrollment_year':2024}}).status_code==200
    history=client.get('/api/v1/profile/history',headers=head(a)).json()['data']
    assert [row['value'] for row in history]==[2024,2023]
    assert client.get('/api/v1/profile/history',headers=head(b)).json()['data']==[]
    assert client.get('/api/v1/cases/'+imported['case_id']+'/evaluate',headers=head(a)).json()['data']['relevance']=='FALSE'
