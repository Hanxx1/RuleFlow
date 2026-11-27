"""RF-014 internal experiment: synthetic output only, no public contract."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai import AIUnavailable
from app.auth import conn
from app.services.documents import document_root
from app.services.notice_source_snapshot import SourceSnapshotError, read_source_snapshot
from app.services.notice_candidate_validation import (
    CandidateValidationError, preview_candidate_output, validate_candidate_output,
)
from helpers import account, client, head


def document_source():
    texts=['请提交课程作业。', '请填写奖学金申请表。']
    digest=hashlib.sha256(b'Synthetic original bytes').hexdigest()
    return {
        'source_id':'source-one', 'content_hash':digest, 'text_origin':'document_lines',
        'document_ref':{'id':'document-one', 'revision':1, 'sha256':digest},
        'text':'\n'.join(texts),
        'lines':[{'line_id':f'line-{i}', 'document_id':'document-one', 'text':text}
                 for i,text in enumerate(texts)],
        'extraction':{'state':'available'}, 'original':{'state':'present'},
        'parent_reference_state':'none',
    }


def ref(source, line=0):
    document=source.get('document_ref')
    return {'source_id':source['source_id'], 'content_hash':source['content_hash'],
            'document_id':document['id'] if document else None,
            'document_revision':document['revision'] if document else None,
            'line_id':source['lines'][line]['line_id'] if document else None,
            'quote':source['lines'][line]['text'] if document else source['text']}


def candidate(source, identity='candidate-one', *, kind='case', course_id=None, line=0):
    return {'candidate_id':identity, 'kind':kind, 'title':'待用户核对的建议',
            'course_id':course_id, 'source_refs':[ref(source,line)]}


@pytest.fixture
def sample():
    source=document_source()
    snapshot={'batch_id':'batch-one', 'batch_revision':2, 'sources':[source]}
    payload={'batch_id':'batch-one', 'batch_revision':2, 'candidates':[candidate(source)]}
    return snapshot,payload


def assert_error(code, payload, snapshot, **kwargs):
    before=deepcopy((payload,snapshot))
    with pytest.raises(CandidateValidationError) as caught:
        validate_candidate_output(payload,snapshot,**kwargs)
    assert caught.value.code==code and str(caught.value)==code
    assert (payload,snapshot)==before


def test_one_source_two_cases_preserve_distinct_quotes_and_unknown(sample):
    snapshot,payload=sample
    payload['candidates'].append(candidate(snapshot['sources'][0],'candidate-two',line=1))
    before=deepcopy((payload,snapshot))
    result=validate_candidate_output(payload,snapshot)
    assert len(result)==2 and {item.candidate_id for item in result}=={'candidate-one','candidate-two'}
    assert [item.source_refs[0].line_id for item in result]==['line-0','line-1']
    assert all(item.eligibility=='UNKNOWN' and item.review_reasons==('USER_REVIEW_REQUIRED',) for item in result)
    assert (payload,snapshot)==before
    with pytest.raises(FrozenInstanceError):
        result[0].title='changed'
    with pytest.raises(ValidationError):
        result[0].source_refs[0].quote='changed'


def test_two_same_named_courses_and_campus_case_keep_explicit_targets(sample):
    snapshot,payload=sample
    source=snapshot['sources'][0]
    payload['candidates']=[candidate(source,'spring',kind='task',course_id='course-spring'),
                           candidate(source,'autumn',kind='task',course_id='course-autumn'),
                           candidate(source,'campus',line=1)]
    result=validate_candidate_output(payload,snapshot,
                                    allowed_course_ids=frozenset({'course-spring','course-autumn'}))
    assert [item.course_id for item in result]==['course-spring','course-autumn',None]
    assert len(result)==3  # Identical titles do not merge courses or suggestions.


@pytest.mark.parametrize('kind',['task','requirement','knowledge'])
def test_course_kinds_require_explicit_allowed_course_id(sample,kind):
    snapshot,payload=sample
    payload['candidates'][0]['kind']=kind
    for target in (None,'线性代数','foreign-course'):
        payload['candidates'][0]['course_id']=target
        assert_error('CANDIDATE_TARGET_INVALID',payload,snapshot,
                     allowed_course_ids=frozenset({'course-spring'}))
    payload['candidates'][0]['course_id']='course-spring'
    assert len(validate_candidate_output(payload,snapshot,
               allowed_course_ids=frozenset({'course-spring'})))==1


def test_case_cannot_silently_become_a_course_command(sample):
    snapshot,payload=sample
    payload['candidates'][0]['course_id']='course-spring'
    assert_error('CANDIDATE_TARGET_INVALID',payload,snapshot,
                 allowed_course_ids=frozenset({'course-spring'}))


@pytest.mark.parametrize('field,value,code',[
    ('source_id','other-source','CANDIDATE_SOURCE_INVALID'),
    ('content_hash','f'*64,'CANDIDATE_SOURCE_STALE'),
    ('document_id','other-document','CANDIDATE_SOURCE_INVALID'),
    ('document_revision',2,'CANDIDATE_SOURCE_STALE'),
    ('line_id','other-line','CANDIDATE_SOURCE_INVALID'),
    ('quote','原文中不存在的要求','CANDIDATE_QUOTE_INVALID'),
])
def test_reference_identity_version_and_verbatim_quote(sample,field,value,code):
    snapshot,payload=sample
    payload['candidates'][0]['source_refs'][0][field]=value
    assert_error(code,payload,snapshot)


def test_quote_from_other_real_line_does_not_ground_selected_line(sample):
    snapshot,payload=sample
    payload['candidates'][0]['source_refs'][0]['quote']=snapshot['sources'][0]['lines'][1]['text']
    assert_error('CANDIDATE_QUOTE_INVALID',payload,snapshot)


def test_new_source_identity_cannot_reuse_old_reference_even_with_same_hash(sample):
    snapshot,payload=sample
    snapshot['sources'][0]['source_id']='replacement-source'
    assert_error('CANDIDATE_SOURCE_INVALID',payload,snapshot)


def test_ambiguous_source_or_line_identity_is_rejected(sample):
    snapshot,payload=sample
    snapshot['sources'].append(deepcopy(snapshot['sources'][0]))
    assert_error('CANDIDATE_SOURCE_INVALID',payload,snapshot)
    snapshot['sources'].pop()
    snapshot['sources'][0]['lines'].append(deepcopy(snapshot['sources'][0]['lines'][0]))
    assert_error('CANDIDATE_SOURCE_INVALID',payload,snapshot)


@pytest.mark.parametrize('state',['failed','empty','not_acquired'])
def test_unreadable_sources_are_not_successful_candidates(sample,state):
    snapshot,payload=sample
    snapshot['sources'][0]['extraction']['state']=state
    assert_error('CANDIDATE_SOURCE_UNAVAILABLE',payload,snapshot)


def test_missing_original_and_parent_keep_historical_quote_under_review(sample):
    snapshot,payload=sample
    snapshot['sources'][0]['original']['state']='missing'
    snapshot['sources'][0]['parent_reference_state']='missing'
    item,=validate_candidate_output(payload,snapshot)
    assert item.eligibility=='UNKNOWN'
    assert item.review_reasons==('SOURCE_ORIGINAL_REVIEW_REQUIRED',
                                'SOURCE_PARENT_REVIEW_REQUIRED','USER_REVIEW_REQUIRED')


def test_legacy_text_does_not_invent_document_lines(sample):
    snapshot,payload=sample
    source={'source_id':'legacy', 'text':'请提交证明。', 'text_origin':'legacy_text',
            'content_hash':hashlib.sha256('请提交证明。'.encode()).hexdigest(),
            'document_ref':None, 'lines':[], 'extraction':{'state':'available'}}
    snapshot['sources']=[source]
    payload['candidates']=[candidate(source)]
    item,=validate_candidate_output(payload,snapshot)
    assert item.source_refs[0].line_id is None
    assert item.review_reasons==('SOURCE_LOCATION_UNAVAILABLE','USER_REVIEW_REQUIRED')
    payload['candidates'][0]['source_refs'][0]['line_id']='invented'
    assert_error('CANDIDATE_SOURCE_INVALID',payload,snapshot)


@pytest.mark.parametrize('field,value,code',[
    ('batch_id','other-batch','CANDIDATE_BATCH_INVALID'),
    ('batch_revision',1,'CANDIDATE_BATCH_STALE'),
])
def test_batch_identity_and_revision(sample,field,value,code):
    snapshot,payload=sample
    payload[field]=value
    assert_error(code,payload,snapshot)


def test_duplicate_candidates_or_references_and_late_invalid_item_reject_whole_output(sample):
    snapshot,payload=sample
    payload['candidates'].append(deepcopy(payload['candidates'][0]))
    assert_error('CANDIDATE_ID_DUPLICATE',payload,snapshot)
    payload['candidates'][1]['candidate_id']='second'
    payload['candidates'][1]['source_refs'][0]['quote']='invalid'
    assert_error('CANDIDATE_QUOTE_INVALID',payload,snapshot)
    payload['candidates'].pop()
    payload['candidates'][0]['source_refs']*=2
    assert_error('CANDIDATE_REFERENCE_DUPLICATE',payload,snapshot)


@pytest.mark.parametrize('field,value',[
    ('eligibility','TRUE'),('eligibility','FALSE'),('owner_id','foreign-owner'),
    ('case_id','invented-case'),('evidence_ids',['block:invented']),('selected',True),
])
def test_model_cannot_assert_eligibility_owner_or_formal_execution_fields(sample,field,value):
    snapshot,payload=sample
    payload['candidates'][0][field]=value
    assert_error('CANDIDATE_OUTPUT_INVALID',payload,snapshot)


@pytest.mark.parametrize('mutate',[
    lambda p:p.update(batch_revision=True),
    lambda p:p.update(candidates=None),
    lambda p:p.update(candidates=p['candidates']*21),
    lambda p:p['candidates'][0].update(source_refs=[]),
    lambda p:p['candidates'][0].update(title=' '*5),
    lambda p:p['candidates'][0]['source_refs'][0].update(quote='\n'),
    lambda p:p['candidates'][0]['source_refs'][0].update(document_revision=True),
    lambda p:p['candidates'][0]['source_refs'][0].update(line_id='x'*301),
    lambda p:p['candidates'][0].update(source_refs=p['candidates'][0]['source_refs']*21),
])
def test_malformed_or_unbounded_output_is_rejected_without_echo(sample,mutate):
    snapshot,payload=sample
    mutate(payload)
    assert_error('CANDIDATE_OUTPUT_INVALID',payload,snapshot)


@pytest.mark.parametrize('failure',[AIUnavailable('private provider detail'),TimeoutError('private URL')])
def test_fake_provider_failure_never_returns_demo_or_private_error(sample,failure):
    snapshot,_=sample
    def generate():
        raise failure
    with pytest.raises(CandidateValidationError) as caught:
        preview_candidate_output(generate,snapshot)
    assert str(caught.value)=='CANDIDATE_ANALYSIS_UNAVAILABLE'


def test_empty_fake_output_stays_empty(sample):
    snapshot,payload=sample
    payload['candidates']=[]
    assert preview_candidate_output(lambda:payload,snapshot)==()


def test_real_authorized_snapshot_and_validation_leave_database_unchanged():
    user=account('candidate-owner@example.com')
    other=account('candidate-other@example.com')
    batch=client.post('/api/v1/import-batches',headers=head(user),json={}).json()['data']['id']
    client.post(f'/api/v1/import-batches/{batch}/sources/files',headers=head(user),
                data={'consent':'true'},files={'files':('notice.txt','请提交申请表。'.encode(),'text/plain')})
    connection=conn()
    revision=connection.execute('SELECT revision FROM import_batches WHERE id=?',(batch,)).fetchone()[0]
    before=list(connection.iterdump())
    snapshot=read_source_snapshot(connection,user['user']['id'],batch,revision,original_root=document_root())
    payload={'batch_id':batch,'batch_revision':revision,'candidates':[candidate(snapshot['sources'][0])]}
    assert len(validate_candidate_output(payload,snapshot))==1
    with pytest.raises(SourceSnapshotError,match='BATCH_NOT_FOUND'):
        read_source_snapshot(connection,other['user']['id'],batch,revision,original_root=document_root())
    assert list(connection.iterdump())==before


def test_review_sample_file_matches_internal_validator():
    path=Path(__file__).resolve().parents[2]/'docs/development/records/evidence/C_20261128/rf014_preview_samples.json'
    sample=json.loads(path.read_text(encoding='utf-8'))
    result=validate_candidate_output(sample['output'],sample['snapshot'],
                                    allowed_course_ids=frozenset(sample['allowed_course_ids']))
    assert len(result)==3 and all(item.eligibility=='UNKNOWN' for item in result)
