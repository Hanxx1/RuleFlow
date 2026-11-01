"""Fact validity is explicit user metadata; expiry preserves UNKNOWN."""
import json
from datetime import datetime,timezone


def normalize_validity(value):
    if value is None:return None
    try:instant=datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError,AttributeError):raise ValueError('有效期必须为带时区的ISO-8601时间')
    if instant.tzinfo is None:raise ValueError('有效期必须包含时区')
    return instant.astimezone(timezone.utc).isoformat()


def record_fact(c,fact_id,owner_id,case_id,key,value,valid_until=None):
    now=datetime.now(timezone.utc).isoformat()
    c.execute('INSERT INTO fact_history VALUES(?,?,?,?,?,?,?,?)',(fact_id,owner_id,case_id,key,json.dumps(value,ensure_ascii=False),'user_input',now,valid_until))
    c.execute('INSERT INTO fact_validity VALUES(?,?,?)',(fact_id,owner_id,valid_until))


def expired(value,now=None):
    return bool(value and datetime.fromisoformat(value)<= (now or datetime.now(timezone.utc)))
