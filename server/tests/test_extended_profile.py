import pytest
from app.services.profile_facts import validate_facts,ProfileError
from app.services.rule_candidates import extract_rules
from app.rules import evaluate

def test_explicit_score_advisor_and_disciplinary_rules():
    rules=extract_rules([('block:test','德育成绩达到80分及以上；1～2名指导教师；未受纪律处分')])
    assert len(rules)==4
    for rule in rules:
        assert evaluate(rule['ast'],{'moral_score':85,'advisor_count':2,'disciplinary_status':'clear'})["value"]=='TRUE'
    assert evaluate(rules[0]['ast'],{})["value"]=='UNKNOWN'

def test_new_profile_ranges_and_enums():
    assert validate_facts({'moral_score':80,'disciplinary_status':'clear','advisor_count':2})['advisor_count']==2
    for facts in ({'moral_score':101},{'advisor_count':1.5},{'disciplinary_status':'yes'},{'participation_count':-1}):
        with pytest.raises(ProfileError):validate_facts(facts)
