from app.services.action_candidates import extract_actions
from app.services.dependency_candidates import extract_dependencies


def edges(text):
    evidence = [('block:a', text)]
    actions = [{**item,'id':str(index)} for index,item in enumerate(extract_actions(evidence))]
    return extract_dependencies(actions,evidence)


def test_only_explicit_ordering_and_local_evidence():
    result = edges('请先下载申请表，然后填写申请表。')
    assert len(result) == 1 and result[0]['before_action_id'] == '0' and result[0]['after_action_id'] == '1'
    assert result[0]['evidence_ids'] == ['block:a']
    assert edges('请下载申请表。请填写申请表。') == []
    assert edges('请下载申请表，并填写申请表。') == []
