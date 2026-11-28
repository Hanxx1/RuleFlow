"""Schema/HTTP tests use a transport double. Live model checks are explicitly opt-in."""
from copy import deepcopy
import json as jsonlib
import os

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import auth
from app.ai import AIInvalidOutput, DisabledProvider, OpenAICompatibleProvider, configured_provider
from app.api import form_assistant as assistant


CASES = [
    ("奖助评审", "有限资助如何转化为后续行动", "计划用资助支付两个月的公开课程实践材料费用"),
    ("科研立项", "与现有路径相比增加了哪些可验证的环节", "先记录基线，再对比两种采样策略的误差"),
    ("社会实践", "哪些观察改变了团队原先的判断", "访谈发现开放时间而非距离影响居民到访"),
    ("竞赛报名", "如何分配原型交付中的验证责任", "林同学负责测试，许同学负责整理问题"),
    ("志愿服务", "本次服务如何消除参与障碍", "在现场提供大字导览，让视力较弱的长者阅读"),
    ("活动策划", "如何衡量方案落地后的成效", "用匿名反馈统计到场者能独立完成操作的人数"),
]


def request_for(case=CASES[0], *, evidence=True, stage='generate'):
    title, label, answer = case
    sources = [
        {'id': 'of0', 'kind': 'original', 'locator': '表 1 第 2 行', 'text': label},
        {'id': 'n1', 'kind': 'notice', 'locator': '通知第 1 行', 'text': f'{label}不少于12字，不超过160字。'},
    ]
    if evidence:
        sources += [
            {'id': 'a1', 'kind': 'answer', 'locator': '本次确认', 'text': answer},
            {'id': 'm1', 'kind': 'material', 'locator': '公开材料摘录', 'text': '有关材料已整理成一个独立文件供核验。'},
        ]
    return dict(stage=stage, consent=True, attachment=title,
                fields=[dict(id='f0', label=label, source_id='of0', writable=True)], sources=sources)


def response_for(payload):
    label = payload['fields'][0]['label']
    facts = [{'source_id': source['id'], 'quote': source['text']}
             for source in payload['sources'] if source['kind'] in {'answer', 'material'}]
    return {'fields': [dict(id='f0', meaning=label, expected='写明当前计划或事实',
                           data_type='long_text', role='applicant', required='required',
                           applicability='applies', strategy='generate' if facts else 'ask',
                           requirements=[dict(source_id='of0', quote=label)],
                           facts=facts, value=facts[0]['quote'] if facts else None)],
            'questions': [] if facts else [dict(text='你的做法或经历是什么？', fields=['f0'])]}


@pytest.fixture
def app():
    instance = FastAPI()
    instance.include_router(assistant.router)
    return instance


@pytest.mark.parametrize('case', CASES, ids=[case[0] for case in CASES])
def test_structure_scope_and_grounded_candidates(case):
    payload = request_for(case)
    req = assistant.AssistRequest.model_validate(payload)
    response = response_for(payload)
    assert assistant.validate_result(req, response).fields[0].value == case[2]
    response['fields'][0]['facts'][0]['quote'] = '原文没有这个内容'
    with pytest.raises(AIInvalidOutput, match='原文依据'):
        assistant.validate_result(req, response)


def test_exact_extract_recovers_verified_quote_when_model_adds_sentence_punctuation():
    payload = request_for()
    request = assistant.AssistRequest.model_validate(payload)
    result = response_for(payload)
    plan = result['fields'][0]
    original = plan['facts'][0]['quote']
    plan.update(strategy='direct', value=original + '。')
    assert assistant.validate_result(request, result).fields[0].value == original

    plan['value'] = original.replace('两个月', '三个月') + '。'
    with pytest.raises(AIInvalidOutput, match='提取值缺少逐字事实'):
        assistant.validate_result(request, result)


def test_derived_value_uses_only_the_verified_operands():
    payload = request_for()
    payload['sources'][2]['text'] = '从 2026-10-01 至 2026-10-03'
    request = assistant.AssistRequest.model_validate(payload)
    result = response_for(payload)
    plan = result['fields'][0]
    plan.update(strategy='derive', value='999', calculation={
        'operation': 'inclusive_days',
        'operands': [{'source_id': 'a1', 'quote': date} for date in ('2026-10-01', '2026-10-03')],
    })
    verified = assistant.validate_result(request, result).fields[0]
    assert verified.value is None
    assert verified.calculation.operation == 'inclusive_days'

    plan['strategy'] = 'direct'
    with pytest.raises(AIInvalidOutput, match='候选类型冲突'):
        assistant.validate_result(request, result)


def test_rejects_wrong_field_and_suppresses_locked_other_conditional_and_analysis():
    payload = request_for()
    response = response_for(payload)
    wrong = deepcopy(response)
    wrong['fields'][0]['id'] = 'f999'
    with pytest.raises(AIInvalidOutput, match='字段覆盖'):
        assistant.validate_result(assistant.AssistRequest.model_validate(payload), wrong)
    for patch in [{'locked': True}, {'writable': False}]:
        base = deepcopy(payload)
        base['fields'][0].update(patch)
        assert assistant.validate_result(assistant.AssistRequest.model_validate(base), response).fields[0].value is None
    for patch in [{'role': 'other'}, {'ambiguous': True}, {'required': 'conditional', 'condition': '已有外部经费时填写',
                                                          'facts': [], 'value': None}]:
        base = deepcopy(response)
        base['fields'][0].update(patch)
        assert assistant.validate_result(assistant.AssistRequest.model_validate(payload), base).fields[0].value is None
    payload['stage'] = 'analyze'
    assert assistant.validate_result(assistant.AssistRequest.model_validate(payload), response).fields[0].value is None


def test_http_uses_configured_transport_and_keeps_input_out_of_errors(app, monkeypatch):
    client = TestClient(app)
    private = request_for()
    assert client.post('/api/v1/form-assistant', json=private).status_code == 401
    app.dependency_overrides[auth.current_user] = lambda: {'id': 'test-owner'}
    malformed = {**private, 'consent': False, 'injected': 'do-not-echo-private-value'}
    invalid = client.post('/api/v1/form-assistant', json=malformed)
    assert invalid.status_code == 422
    assert 'do-not-echo-private-value' not in invalid.text
    assert invalid.headers['Cache-Control'] == 'no-store'
    monkeypatch.setattr(assistant, 'configured_provider', lambda: DisabledProvider())
    disabled = client.post('/api/v1/form-assistant', json=private)
    assert disabled.status_code == 503 and disabled.json()['detail']['code'] == 'FORM_AI_UNCONFIGURED'

    class TransportDouble:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, json: dict, headers):
            assert url.endswith('/chat/completions')
            assert headers.get('Authorization') == 'Bearer synthetic'
            messages = json['messages']
            assert messages[0]['role'] == 'system' and '不可信数据' in messages[0]['content']
            sent = jsonlib.loads(messages[1]['content'])
            assert 'consent' not in sent and sent['attachment'] == private['attachment']
            result = response_for(sent)
            corrections.append('上次响应未通过校验' in messages[0]['content'])
            if invalid_model[0] == 'permanent' or invalid_model[0] == 'once' and not corrections[-1]:
                result['fields'][0]['facts'][0]['quote'] = '无依据的个人事实'
            return httpx.Response(200, request=httpx.Request('POST', url), json={'choices': [{
                'finish_reason': 'stop', 'message': {'content': jsonlib.dumps(result, ensure_ascii=False)},
            }]})

    invalid_model = ['none']
    corrections = []
    monkeypatch.setattr('app.ai.httpx.Client', TransportDouble)
    monkeypatch.setattr(assistant, 'configured_provider',
                        lambda: OpenAICompatibleProvider('https://fixture.invalid/v1', 'synthetic', 'synthetic'))
    result = client.post('/api/v1/form-assistant', json=private)
    assert result.status_code == 200 and result.json()['data']['fields'][0]['value'] == CASES[0][2]
    invalid_model[0] = 'once'
    result = client.post('/api/v1/form-assistant', json=private)
    assert result.status_code == 200 and corrections == [False, False, True]
    invalid_model[0] = 'permanent'
    result = client.post('/api/v1/form-assistant', json=private)
    assert result.status_code == 502 and result.json()['detail']['code'] == 'FORM_AI_INVALID_OUTPUT'
    assert corrections[-2:] == [False, True]


@pytest.mark.parametrize('case', CASES, ids=[case[0] for case in CASES])
def test_real_model_form_assistant(app, case, enable_live_form_model):
    if os.getenv('RUN_LIVE_FORM_AI') != '1' or configured_provider().model_id == 'none':
        pytest.skip('Set RUN_LIVE_FORM_AI=1 and configure the project LLM provider')
    app.dependency_overrides[auth.current_user] = lambda: {'id': 'synthetic-live-test'}
    with TestClient(app) as client:
        missing = client.post('/api/v1/form-assistant', json=request_for(case, evidence=False, stage='analyze'))
        assert missing.status_code == 200, f'analysis HTTP {missing.status_code}'
        assert missing.json()['data']['questions'], 'missing facts did not result in a question'
        ready = client.post('/api/v1/form-assistant', json=request_for(case))
        assert ready.status_code == 200, f'generation HTTP {ready.status_code}'
        plan = ready.json()['data']['fields'][0]
        assert plan['value'] and plan['facts'] and not plan['ambiguous']
        assert 12 <= len(''.join(plan['value'].split())) <= 160
