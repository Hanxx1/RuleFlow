from test_api import client,account,head


def test_weekly_series_is_atomic_and_owner_scoped():
    a=account('series-owner@example.com')
    body={'title':'课程','kind':'course','starts_at':'2026-10-20T09:00:00+08:00','ends_at':'2026-10-20T10:00:00+08:00','count':3}
    result=client.post('/api/v1/schedule/series',headers=head(a),json=body)
    assert result.status_code==200 and result.json()['data']['count']==3
    items=client.get('/api/v1/schedule',headers=head(a)).json()['data']
    assert [item['starts_at'] for item in items]==['2026-10-20T01:00:00Z','2026-10-27T01:00:00Z','2026-11-03T01:00:00Z']
    # First occurrence is free, second conflicts: transaction must also roll back first.
    body.update(starts_at='2026-10-13T09:00:00+08:00',ends_at='2026-10-13T10:00:00+08:00')
    assert client.post('/api/v1/schedule/series',headers=head(a),json=body).status_code==409
    assert len(client.get('/api/v1/schedule',headers=head(a)).json()['data'])==3


def test_locked_item_requires_explicit_unlock_for_edit_delete():
    a,b=account('lock-owner@example.com'),account('lock-other@example.com')
    item=client.post('/api/v1/schedule/items',headers=head(a),json={'title':'固定课程','kind':'course','starts_at':'2026-10-20T09:00:00+08:00','ends_at':'2026-10-20T10:00:00+08:00'}).json()['data']
    url='/api/v1/schedule/items/'+item['id']
    assert client.post(url+'/lock',headers=head(b),json={'locked':True}).status_code==404
    assert client.post(url+'/lock',headers=head(a),json={'locked':True}).status_code==200
    assert client.patch(url,headers=head(a),json={'title':'changed'}).status_code==409
    assert client.delete(url,headers=head(a)).status_code==409
    assert client.get('/api/v1/schedule',headers=head(a)).json()['data'][0]['locked']
    assert client.post(url+'/lock',headers=head(a),json={'locked':False}).status_code==200
    assert client.delete(url,headers=head(a)).status_code==200
