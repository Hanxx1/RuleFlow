"""Combine all hard conditions with Kleene logic; action triggers do not gate eligibility."""
from ..rules import evaluate


def evaluate_rules(rules,facts):
    results=[]
    for rule in rules:
        try:outcome=evaluate(rule['ast'],facts)
        except ValueError:outcome={'value':'UNKNOWN','missing_fields':[],'failed_conditions':[],'supporting_evidence':rule.get('evidence_ids',[]),'trace':[{'reason':'invalid_rule'}]}
        results.append({'id':rule['id'],'label':rule['label'],'kind':rule.get('kind','eligibility'),'evaluation':outcome,'evidence_ids':rule.get('evidence_ids',[])})
    hard=[item for item in results if item['kind']!='action_trigger']
    values=[item['evaluation']['value'] for item in hard]
    truth='FALSE' if 'FALSE' in values else 'TRUE' if values and all(value=='TRUE' for value in values) else 'UNKNOWN'
    missing=sorted({field for item in hard for field in item['evaluation']['missing_fields']})
    traces=[trace for item in hard for trace in item['evaluation']['trace']]
    if truth!='UNKNOWN':reason=None
    elif not hard:reason='insufficient_evidence'
    elif any(trace.get('reason') in {'unparseable_value','invalid_rule'} for trace in traces):reason='rule_unknown'
    elif missing:reason='missing_profile_fact'
    else:reason='rule_unknown'
    return {'relevance':truth,'eligibility_truth':truth,'reason':reason,'missing_profile_fields':missing,'missing_case_fields':[],
            'rules':results,'failed_rule_ids':[item['id'] for item in hard if item['evaluation']['value']=='FALSE'],
            'supporting_evidence':sorted({ref for item in hard for ref in item['evaluation']['supporting_evidence']})}
