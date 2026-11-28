"""Synthetic RF-014 content, isolation and legacy-validator regressions."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json

import pytest

from app.auth import conn
from app.services.documents import document_root
from app.services.notice_source_snapshot import read_source_snapshot
from app.services.notice_candidate_content import (
    candidate_content_sources, validate_candidate_content,
)
from app.services.notice_candidate_validation import CandidateValidationError, validate_candidate_output
from test_notice_candidate_validation import candidate, document_source
from helpers import account, client, head


@pytest.fixture
def content():
    source = document_source()
    text = '面向2023级及以后。请填写申请表。报名截止2026-12-10。'
    source['lines'][0]['text'] = text
    source['text'] = text + '\n' + source['lines'][1]['text']
    snapshot = {'batch_id': 'batch-one', 'batch_revision': 2, 'sources': [source]}
    output = {'batch_id': 'batch-one', 'batch_revision': 2,
              'candidates': [candidate(source)]}
    preview = validate_candidate_output(output, snapshot)[0]
    alias = candidate_content_sources(preview)[0].local_ref
    payload = {
        'title': '申请', 'category': 'award',
        'rules': [{'label': '入学年份', 'ast': {'op': 'gte', 'field': 'profile.enrollment_year',
                   'value': 2023, 'evidence': [alias]}, 'evidence_ids': [alias],
                   'evidence_quotes': {alias: '2023级及以后'}}],
        'materials': [{'title': '申请表', 'state': 'missing', 'evidence_ids': [alias],
                       'evidence_quotes': {alias: '申请表'}}],
        'tasks': [{'title': '填写申请表', 'evidence_ids': [alias],
                   'evidence_quotes': {alias: '填写申请表'}}],
    }
    return preview, payload, output, snapshot


def reject(preview, payload, code='CANDIDATE_CONTENT_INVALID'):
    before = deepcopy(payload)
    with pytest.raises(CandidateValidationError) as error:
        validate_candidate_content(preview, payload)
    assert str(error.value) == code
    assert payload == before


def test_grounded_content_reuses_analysis_and_dates_without_mutation_or_writes(content):
    preview, payload, _, _ = content
    before = deepcopy(payload)
    connection = conn()
    database = list(connection.iterdump())
    result = validate_candidate_content(preview, payload)
    assert json.loads(result.analysis_json)['tasks'][0]['deadline'] is None
    dates = json.loads(result.dates_json)
    assert dates[0]['value'] == '2026-12-10' and dates[0]['role'] == 'deadline'
    assert dates[0]['evidence_ids'] == [result.sources[0].local_ref]
    assert result.sources[0].source_ref_index == 0
    assert result.eligibility == 'UNKNOWN'
    assert result.review_reasons == ('DATE_REVIEW_REQUIRED', 'USER_REVIEW_REQUIRED')
    assert payload == before and list(connection.iterdump()) == database
    with pytest.raises(FrozenInstanceError):
        result.analysis_json = '{}'
    with pytest.raises(FrozenInstanceError):
        result.sources[0].text = 'changed'
    payload['tasks'][0]['title'] = 'later edit'
    assert json.loads(result.analysis_json)['tasks'][0]['title'] == '填写申请表'


@pytest.mark.parametrize('section', ['rules', 'materials', 'tasks'])
@pytest.mark.parametrize('change', ['empty', 'missing_quote', 'extra_quote', 'duplicate', 'foreign', 'fabricated'])
def test_every_item_requires_own_exact_declared_quotes(content, section, change):
    preview, payload, _, _ = content
    item = payload[section][0]
    alias = item['evidence_ids'][0]
    if change == 'empty':
        item.update(evidence_ids=[], evidence_quotes={})
    elif change == 'missing_quote':
        item['evidence_quotes'] = {}
    elif change == 'extra_quote':
        item['evidence_quotes']['block:foreign'] = '申请表'
    elif change == 'duplicate':
        item['evidence_ids'].append(alias)
    elif change == 'foreign':
        item.update(evidence_ids=['block:foreign'], evidence_quotes={'block:foreign': '申请表'})
    else:
        item['evidence_quotes'][alias] = '没有在当前候选短引中的断言'
    reject(preview, payload, 'CANDIDATE_CONTENT_REFERENCE_INVALID')


def test_candidate_cannot_borrow_other_candidate_content_even_with_same_quote(content):
    preview, payload, output, snapshot = content
    output['candidates'][0]['candidate_id'] = 'another-candidate'
    other = validate_candidate_output(output, snapshot)[0]
    assert candidate_content_sources(other) != candidate_content_sources(preview)
    reject(other, payload, 'CANDIDATE_CONTENT_REFERENCE_INVALID')


def test_shared_document_other_line_is_outside_candidate_content(content):
    preview, payload, _, snapshot = content
    alias = payload['tasks'][0]['evidence_ids'][0]
    payload['tasks'][0]['evidence_quotes'][alias] = snapshot['sources'][0]['lines'][1]['text']
    reject(preview, payload, 'CANDIDATE_CONTENT_REFERENCE_INVALID')


@pytest.mark.parametrize('update', [
    {'op': 'eval'}, {'field': 'profile.not_supported'}, {'value': '2023'},
    {'value': 2024}, {'unexpected': 'private text'},
])
def test_rule_schema_types_and_existing_semantic_checks_are_reused(content, update):
    preview, payload, _, _ = content
    payload['rules'][0]['ast'].update(update)
    reject(preview, payload)


def test_uncited_leaf_hidden_inside_cited_rule_is_rejected(content):
    preview, payload, _, _ = content
    rule = payload['rules'][0]
    child = deepcopy(rule['ast'])
    child.pop('evidence')
    rule['ast'] = {'op': 'and', 'args': [child], 'evidence': rule['evidence_ids']}
    reject(preview, payload, 'CANDIDATE_CONTENT_AST_INVALID')


@pytest.mark.parametrize('field,value', [('op', []), ('field', {}), ('evidence', [False])])
def test_malformed_ast_values_return_safe_errors(content, field, value):
    preview, payload, _, _ = content
    payload['rules'][0]['ast'][field] = value
    reject(preview, payload, 'CANDIDATE_CONTENT_AST_INVALID')


@pytest.mark.parametrize('wide', [False, True])
def test_ast_processing_budget_is_bounded_before_recursive_validator(content, wide):
    preview, payload, _, _ = content
    leaf = payload['rules'][0]['ast']
    node = leaf
    if wide:
        node = {'op': 'and', 'args': [deepcopy(leaf) for _ in range(257)]}
    else:
        for _ in range(34):
            node = {'op': 'and', 'args': [node]}
    payload['rules'][0]['ast'] = node
    reject(preview, payload, 'CANDIDATE_CONTENT_AST_INVALID')


@pytest.mark.parametrize('section,field,value', [
    ('materials', 'state', 'obtained'), ('tasks', 'origin', 'executed'),
    ('tasks', 'duration_minutes', True), ('tasks', 'duration_minutes', 0),
    ('tasks', 'title', '   '),
])
def test_model_cannot_claim_completion_or_supply_invalid_fields(content, section, field, value):
    preview, payload, _, _ = content
    payload[section][0][field] = value
    reject(preview, payload)


def test_duration_is_only_a_reviewable_suggestion_and_deadline_is_not_model_assigned(content):
    preview, payload, _, _ = content
    payload['tasks'][0]['duration_minutes'] = 45
    result = validate_candidate_content(preview, payload)
    assert 'DURATION_REVIEW_REQUIRED' in result.review_reasons
    payload['tasks'][0]['deadline'] = '2026-12-10'
    reject(preview, payload, 'CANDIDATE_CONTENT_DEADLINE_UNCONFIRMED')


@pytest.mark.parametrize('text,reason', [
    ('截止12月10日。', 'missing_year'),
    ('截止2026-02-30。', 'invalid_date'),
    ('截止2026-12-10下午5点。', 'time_requires_review'),
])
def test_unresolved_dates_remain_unresolved(content, text, reason):
    _, _, output, snapshot = content
    source = snapshot['sources'][0]
    source['text'] = text
    source['lines'][0]['text'] = text
    output['candidates'] = [candidate(source)]
    preview = validate_candidate_output(output, snapshot)[0]
    result = validate_candidate_content(preview, {})
    dates = json.loads(result.dates_json)
    assert dates[0]['value'] is None and reason in dates[0]['review_reasons']
    assert result.eligibility == 'UNKNOWN'


def test_changed_source_version_changes_local_alias(content):
    preview, payload, output, snapshot = content
    source = snapshot['sources'][0]
    source['document_ref']['revision'] = 2
    output['candidates'] = [candidate(source)]
    changed = validate_candidate_output(output, snapshot)[0]
    assert candidate_content_sources(changed) != candidate_content_sources(preview)
    reject(changed, payload, 'CANDIDATE_CONTENT_REFERENCE_INVALID')


def test_legacy_text_keeps_review_reasons(content):
    _, _, output, snapshot = content
    source = snapshot['sources'][0]
    source.update(text_origin='legacy_text', document_ref=None, lines=[])
    output['candidates'] = [candidate(source)]
    preview = validate_candidate_output(output, snapshot)[0]
    result = validate_candidate_content(preview, {})
    assert 'SOURCE_LOCATION_UNAVAILABLE' in result.review_reasons
    assert result.eligibility == 'UNKNOWN'


def test_empty_content_does_not_invent_actions(content):
    preview, _, _, _ = content
    result = validate_candidate_content(preview, {})
    assert json.loads(result.analysis_json)['tasks'] == []
    assert json.loads(result.analysis_json)['rules'] == []


def test_missing_original_and_parent_reasons_survive_content_validation(content):
    _, _, output, snapshot = content
    source = snapshot['sources'][0]
    source['original']['state'] = 'missing'
    source['parent_reference_state'] = 'missing'
    preview = validate_candidate_output(output, snapshot)[0]
    result = validate_candidate_content(preview, {})
    assert {'SOURCE_ORIGINAL_REVIEW_REQUIRED', 'SOURCE_PARENT_REVIEW_REQUIRED'} <= set(result.review_reasons)
    assert result.eligibility == 'UNKNOWN'


def test_dates_do_not_leak_from_another_candidate_in_the_same_document(content):
    _, _, output, snapshot = content
    output['candidates'] = [candidate(snapshot['sources'][0], line=1)]
    preview = validate_candidate_output(output, snapshot)[0]
    result = validate_candidate_content(preview, {})
    assert json.loads(result.dates_json) == []
    assert 'DATE_REVIEW_REQUIRED' not in result.review_reasons


def test_real_upload_snapshot_content_chain_is_read_only():
    user = account('content-owner@example.com')
    batch = client.post('/api/v1/import-batches', headers=head(user), json={}).json()['data']['id']
    uploaded = client.post(f'/api/v1/import-batches/{batch}/sources/files', headers=head(user),
                           data={'consent': 'true'},
                           files={'files': ('notice.txt', '请填写申请表。截止2026-12-10。'.encode(), 'text/plain')})
    assert uploaded.status_code == 200
    connection = conn()
    revision = connection.execute('SELECT revision FROM import_batches WHERE id=?', (batch,)).fetchone()[0]
    before = list(connection.iterdump())
    snapshot = read_source_snapshot(connection, user['user']['id'], batch, revision,
                                    original_root=document_root())
    output = {'batch_id': batch, 'batch_revision': revision,
              'candidates': [candidate(snapshot['sources'][0])]}
    preview = validate_candidate_output(output, snapshot)[0]
    alias = candidate_content_sources(preview)[0].local_ref
    content = {'tasks': [{'title': '填写申请表', 'evidence_ids': [alias],
                          'evidence_quotes': {alias: '填写申请表'}}]}
    result = validate_candidate_content(preview, content)
    assert result.eligibility == 'UNKNOWN'
    assert json.loads(result.analysis_json)['tasks'][0]['deadline'] is None
    assert json.loads(result.dates_json)[0]['value'] == '2026-12-10'
    assert list(connection.iterdump()) == before


@pytest.mark.parametrize('field', ['eligibility', 'dates', 'case_id', 'selected'])
def test_formal_decisions_and_model_dates_are_not_part_of_content_schema(content, field):
    preview, payload, _, _ = content
    payload[field] = 'private model output'
    reject(preview, payload)
