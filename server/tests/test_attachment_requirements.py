from app.services.attachment_requirements import inventory

def test_missing_received_failed_attachments_retain_source():
    evidence=[{'id':'block:a','text':'请填写附件1申请表。按附件2实施细则执行。'}]
    result=inventory(evidence,[{'id':'d','name':'附件1申请表.pdf','status':'parsed'},{'id':'e','name':'附件2实施细则.pdf','status':'failed'}])
    assert [r['state'] for r in result['items']]==['obtained','failed']
    assert result['missing_count']==1 and not result['complete']
    assert all(r['evidence_ids']==['block:a'] for r in result['items'])

def test_link_discovery_is_not_attachment_content_and_generic_reference_reminds():
    result=inventory([{'id':'block:b','text':'具体要求见附件。'}],links=[{'title':'细则','url':'https://example.com/rules.pdf','evidence_ids':['block:b']}])
    assert result['missing_count']==2 and all(r['state']=='missing' for r in result['items'])
