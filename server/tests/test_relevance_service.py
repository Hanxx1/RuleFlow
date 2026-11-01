import json
from pathlib import Path
from app.rules import evaluate,ALLOWED_FIELDS
from app.services.profile_facts import PROFILE_FIELDS
from app.services.relevance import evaluate_rules
from app.services.rule_candidates import extract_rules


def rule(id,field,op,value,kind='eligibility'):
    return {'id':id,'label':id,'kind':kind,'ast':{'op':op,'field':'profile.'+field,'value':value,'evidence':['block:'+id]},'evidence_ids':['block:'+id]}


def test_every_hard_condition_is_combined_instead_of_first_rule_only():
    rules=[rule('year','enrollment_year','eq',2024),rule('rank','rank_percent','lte',20)]
    unknown=evaluate_rules(rules,{'enrollment_year':2024})
    assert unknown['relevance']=='UNKNOWN' and unknown['missing_profile_fields']==['profile.rank_percent']
    assert evaluate_rules(rules,{'enrollment_year':2024,'rank_percent':30})['relevance']=='FALSE'
    assert evaluate_rules(rules,{'enrollment_year':2024,'rank_percent':10})['relevance']=='TRUE'


def test_optional_action_does_not_affect_eligibility_but_hard_conflict_dominates():
    rules=[rule('year','enrollment_year','eq',2024),rule('bonus','moral_bonus_items','contains','volunteer','action_trigger')]
    assert evaluate_rules(rules,{'enrollment_year':2024})['relevance']=='TRUE'
    rules.append(rule('rank','rank_percent','lte',20))
    assert evaluate_rules(rules,{'enrollment_year':2023})['relevance']=='FALSE'


def test_invalid_legacy_profile_values_remain_unknown_with_trace():
    outcome=evaluate_rules([rule('rank','rank_percent','lte',20)],{'rank_percent':'15'})
    assert outcome['relevance']=='UNKNOWN' and outcome['reason']=='rule_unknown'
    assert outcome['rules'][0]['evaluation']['trace'][0]['reason']=='unparseable_value'


def test_shared_vectors_match_python_and_schema_field_contract():
    vectors=json.loads((Path(__file__).resolve().parents[2]/'shared/test-vectors/rule-engine.json').read_text(encoding='utf-8'))
    for vector in vectors:assert evaluate(vector['ast'],vector['profile'])['value']==vector['value'],vector['name']
    assert ALLOWED_FIELDS=={'profile.'+key for key in PROFILE_FIELDS}


def test_local_conditions_use_only_their_matching_evidence():
    evidence=[('block:year','仅限2023级本科生。'),('block:rank','专业排名前20%。'),('block:other','请填写申请表。')]
    rules=extract_rules(evidence)
    assert len(rules)==3
    assert all('block:other' not in item['evidence_ids'] for item in rules)
    assert all(quote in dict(evidence)[ref] for item in rules for ref,quote in item['evidence_quotes'].items())
