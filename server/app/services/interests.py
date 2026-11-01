"""Soft interests never change hard-rule eligibility."""
import json
import uuid
from datetime import datetime,timezone


def bind_interest(c,owner_id,case_id):
    preference=c.execute('SELECT * FROM profile_interests WHERE owner_id=?',(owner_id,)).fetchone()
    if not preference:return
    ref='block:'+str(uuid.uuid5(uuid.NAMESPACE_URL,f'interest:{owner_id}:{case_id}:{preference["revision"]}'))
    c.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,owner_id,case_id,'用户关注分类','用户关注的事项分类：'+', '.join(json.loads(preference['categories_json'])),'用户填写，只用于软偏好，不代表资格条件',None,datetime.now(timezone.utc).isoformat()))
    c.execute('INSERT INTO case_interest_evidence VALUES(?,?,?,?) ON CONFLICT(owner_id,case_id) DO UPDATE SET revision=excluded.revision,evidence_id=excluded.evidence_id',(owner_id,case_id,preference['revision'],ref))


def soft_relevance(c,owner_id,case_id,truth):
    preference=c.execute('SELECT * FROM profile_interests WHERE owner_id=?',(owner_id,)).fetchone()
    case=c.execute('SELECT category FROM cases WHERE id=? AND owner_id=?',(case_id,owner_id)).fetchone()
    source=c.execute('SELECT evidence_id,revision FROM case_interest_evidence WHERE owner_id=? AND case_id=?',(owner_id,case_id)).fetchone()
    configured=bool(preference and source and source['revision']==preference['revision'])
    match=case['category'] in json.loads(preference['categories_json']) if configured and case else None
    level='not_eligible' if truth=='FALSE' else 'needs_verification' if truth=='UNKNOWN' else 'preferred' if match else 'eligible'
    return {'relevance_level':level,'interest_match':match,'interest_evidence_ids':[source['evidence_id']] if configured else [],'interest_source':'user_input' if configured else None}
