"""Explicit facts validation using the shared field contract. No type coercion."""
import json
import math
from pathlib import Path

PROFILE_SCHEMA=json.loads((Path(__file__).resolve().parents[3]/'shared'/'profile.schema.json').read_text(encoding='utf-8'))
PROFILE_FIELDS=set(PROFILE_SCHEMA['properties'])


class ProfileError(ValueError):
    def __init__(self,fields):
        self.fields=sorted(fields)
        super().__init__('画像字段格式或范围无效，请核对：'+ '、'.join(self.fields))


def valid_value(field,value):
    spec=PROFILE_SCHEMA['properties'].get(field)
    if not spec:return False
    if value is None:return True
    types=spec['type']
    if 'integer' in types:
        if type(value) not in (int,float) or not math.isfinite(value) or value!=int(value):return False
    elif 'number' in types:
        if type(value) not in (int,float) or not math.isfinite(value):return False
    elif 'string' in types:
        if not isinstance(value,str) or not value.strip() or len(value)>spec.get('maxLength',100):return False
    elif 'array' in types:
        if not isinstance(value,list) or len(value)>spec['maxItems'] or any(not isinstance(item,str) or not item.strip() or len(item)>100 for item in value):return False
        if len(set(value))!=len(value):return False
    if 'enum' in spec and value not in spec['enum']:return False
    if 'minimum' in spec and value<spec['minimum']:return False
    if 'maximum' in spec and value>spec['maximum']:return False
    return True


def validate_facts(changes):
    clean={key:(value.strip() if isinstance(value,str) else value) for key,value in changes.items()}
    invalid=[key for key,value in clean.items() if not valid_value(key,value)]
    if invalid:raise ProfileError(invalid)
    return clean
