import pytest

from app.ai import AIAnalysis, AIInvalidOutput, AIUnavailable, validate_ai_payload, validate_candidates


def valid_payload(evidence_id='block:one'):
    return {
        'title': '奖助通知',
        'category': 'award',
        'summary': '符合条件后准备申请材料。',
        'rules': [{
            'label': '入学年份要求',
            'ast': {'op': 'gte', 'field': 'profile.enrollment_year', 'value': 2023, 'evidence': [evidence_id]},
            'evidence_ids': [evidence_id],
            'evidence_quotes': {evidence_id: '2023级及以后'},
        }],
        'materials': [],
        'tasks': [{'title': '准备申请表', 'deadline': None, 'evidence_ids': [evidence_id], 'evidence_quotes': {evidence_id: '申请表'}}],
        'questions': [],
        'review_reasons': [],
    }


def test_ai_payload_is_structured_and_ast_is_restricted():
    result = validate_ai_payload(valid_payload())
    assert isinstance(result, AIAnalysis)
    bad = valid_payload()
    bad['rules'][0]['ast']['op'] = 'eval'
    with pytest.raises(AIInvalidOutput):
        validate_ai_payload(bad)


def test_ai_payload_rejects_unknown_evidence_reference():
    bad = valid_payload('block:missing')
    bad['rules'][0]['ast']['evidence'] = ['block:missing']
    result = validate_ai_payload(bad)
    with pytest.raises(AIInvalidOutput):
        validate_candidates(result, {'block:real': '有证据'})


def test_disabled_provider_does_not_claim_ai():
    from app.ai import DisabledProvider
    with pytest.raises(AIUnavailable):
        DisabledProvider().analyze([])


def test_semantic_fields_require_verbatim_evidence_and_typed_rule_values():
    payload=valid_payload();payload['audience']={'value':'本科生','evidence_ids':['block:one'],'evidence_quotes':{'block:one':'本科生'}}
    result=validate_ai_payload(payload)
    assert validate_candidates(result,{'block:one':'2023级及以后本科生，请准备申请表'})==[]
    with pytest.raises(AIInvalidOutput):validate_candidates(result,{'block:one':'2023级及以后，请准备申请表'})
    payload['rules'][0]['ast']['value']='2023'
    with pytest.raises(AIInvalidOutput):validate_ai_payload(payload)


def test_model_cannot_disguise_a_hard_rule_as_optional_without_evidence():
    payload=valid_payload();payload['rules'][0]['kind']='action_trigger'
    result=validate_ai_payload(payload)
    with pytest.raises(AIInvalidOutput):validate_candidates(result,{'block:one':'2023级及以后，请准备申请表'})


def test_model_cannot_use_team_size_for_participation_count():
    payload=valid_payload();payload['rules']=[{'label':'每位学生只可参加一支团队','ast':{'op':'lte','field':'profile.team_size','value':1,'evidence':['block:one']},'evidence_ids':['block:one'],'evidence_quotes':{'block:one':'每位学生当届只可参加一支团队'}}]
    result=validate_ai_payload(payload)
    with pytest.raises(AIInvalidOutput,match='语义|没有对应'):validate_candidates(result,{'block:one':'每位学生当届只可参加一支团队。请准备申请表'})
    payload['rules'][0].update(label='团队学生人数不超过5名',ast={'op':'lte','field':'profile.team_size','value':5,'evidence':['block:one']},evidence_quotes={'block:one':'每支参赛团队由1～2名指导老师和不超过5名学生组成'})
    assert validate_candidates(validate_ai_payload(payload),{'block:one':'每支参赛团队由1～2名指导老师和不超过5名学生组成。请准备申请表'})==[]


def test_provider_quarantines_cited_invalid_rule_and_retains_valid_actions():
    from app.ai import validate_provider_payload
    payload=valid_payload();payload['rules'][0].update(label='年级',ast={'op':'gte','field':'profile.enrollment_year','value':2,'evidence':['block:one']},evidence_quotes={'block:one':'二年级及以上'})
    result=validate_provider_payload(payload,{'block:one':'二年级及以上，请填写申请表'})
    assert result.rules==[] and len(result.tasks)==1
    assert result.unsupported_conditions[0].value=='二年级及以上'
    assert result._rejected_rule_count==1


def test_discipline_record_cannot_be_replaced_with_bonus_item_presence():
    payload=valid_payload();payload['rules']=[{'label':'无处分','ast':{'op':'exists','field':'profile.moral_bonus_items','evidence':['block:one']},'evidence_ids':['block:one'],'evidence_quotes':{'block:one':'未受纪律处分，无不诚信记录'}}]
    with pytest.raises(AIInvalidOutput,match='没有对应'):validate_candidates(validate_ai_payload(payload),{'block:one':'未受纪律处分，无不诚信记录。申请表'})
def test_provider_quote_alignment_only_restores_unique_original_whitespace():
    from app.ai import validate_provider_payload
    payload=valid_payload();payload['rules']=[];payload['tasks'][0]['evidence_quotes']={'block:one':'准备 申请表'}
    result=validate_provider_payload(payload,{'block:one':'请准备\t申请表。'})
    assert result.tasks[0].evidence_quotes['block:one']=='准备\t申请表'
    payload['tasks'][0]['evidence_quotes']={'block:one':'无需申请表'}
    with pytest.raises(AIInvalidOutput):validate_provider_payload(payload,{'block:one':'请准备\t申请表。'})
    payload['tasks'][0]['evidence_quotes']={'block:one':'准备 申请表'}
    with pytest.raises(AIInvalidOutput):validate_provider_payload(payload,{'block:one':'准备\t申请表，准备\t申请表'})
