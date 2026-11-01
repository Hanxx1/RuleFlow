from __future__ import annotations
from enum import StrEnum
from typing import Any
import json,re
from pathlib import Path
from .services.profile_facts import valid_value

RULE_SCHEMA=json.loads((Path(__file__).resolve().parents[2]/'shared'/'rule_ast.schema.json').read_text(encoding='utf-8'))
ALLOWED_FIELDS=set(RULE_SCHEMA['$defs']['field']['enum'])
ALLOWED_OPS={op for variant in RULE_SCHEMA['oneOf'] for op in variant['properties']['op'].get('enum',[variant['properties']['op'].get('const')])}

class Truth(StrEnum):
    TRUE = "TRUE"; FALSE = "FALSE"; UNKNOWN = "UNKNOWN"

def _field(profile: dict[str, Any], name: str):
    return profile.get(name.removeprefix("profile."))

def evaluate(ast: dict[str, Any], profile: dict[str, Any], _depth=0) -> dict[str, Any]:
    if _depth>32 or not isinstance(ast, dict) or ast.get("op") not in ALLOWED_OPS:
        raise ValueError("invalid Rule AST operator")
    op, evidence = ast["op"], ast.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(x, str) and re.fullmatch(r'block:[A-Za-z0-9._:-]+',x) for x in evidence):
        raise ValueError("invalid EvidenceRef")
    evidence=list(evidence)
    allowed={'op','evidence','args'} if op in {'and','or','not'} else {'op','evidence','field','value'}
    if set(ast)-allowed:raise ValueError('invalid Rule AST properties')
    missing: list[str] = []
    trace: list[dict[str, str]] = []
    if op in ("and", "or", "not"):
        if not isinstance(ast.get("args"), list) or not ast["args"] or (op == "not" and len(ast["args"]) != 1):
            raise ValueError("logical AST requires non-empty args; not requires one arg")
        children = [evaluate(x, profile, _depth+1) for x in ast.get("args", [])]
        values = [Truth(x["value"]) for x in children]
        missing = [m for x in children for m in x["missing_fields"]]
        evidence += [e for x in children for e in x["supporting_evidence"]]
        trace += [t for x in children for t in x['trace']]
        if op == "not": value = {Truth.TRUE: Truth.FALSE, Truth.FALSE: Truth.TRUE, Truth.UNKNOWN: Truth.UNKNOWN}[values[0]] if values else Truth.UNKNOWN
        elif op == "and": value = Truth.FALSE if Truth.FALSE in values else Truth.TRUE if values and all(v == Truth.TRUE for v in values) else Truth.UNKNOWN
        else: value = Truth.TRUE if Truth.TRUE in values else Truth.FALSE if values and all(v == Truth.FALSE for v in values) else Truth.UNKNOWN
    else:
        if ast.get("field") not in ALLOWED_FIELDS:
            raise ValueError("invalid profile field")
        field, actual = ast["field"], _field(profile, ast["field"])
        if actual is None or actual == "":
            value, missing = Truth.UNKNOWN, [field]
            trace.append({"node": op, "value": value, "reason": "field_missing"})
        elif not valid_value(field.removeprefix('profile.'),actual):
            value,missing=Truth.UNKNOWN,[field]
            trace.append({'node':op,'value':value,'reason':'unparseable_value'})
        elif op == "exists": value = Truth.TRUE
        else:
            expected = ast.get("value")
            try:
                key=field.removeprefix('profile.')
                if op=='in':
                    if isinstance(actual,list) or not isinstance(expected,list) or not expected or not all(valid_value(key,x) and x is not None for x in expected):raise ValueError()
                elif op=='contains':
                    if not isinstance(actual,(list,str)) or not isinstance(expected,str):raise ValueError()
                elif expected is None or not valid_value(key,expected):raise ValueError()
                if op in {'gte','lte','before','after'} and type(actual) not in (int,float):raise ValueError()
                match op:
                    case "eq": ok = actual == expected
                    case "in": ok = actual in expected
                    case "gte": ok = actual >= expected
                    case "lte": ok = actual <= expected
                    case "contains": ok = expected in actual
                    case "before": ok = actual < expected
                    case "after": ok = actual > expected
                    case _: raise ValueError("unsupported operator")
                value = Truth.TRUE if ok else Truth.FALSE
            except (TypeError, ValueError):
                value, missing = Truth.UNKNOWN, [field]
                trace.append({"node": op, "value": value, "reason": "unparseable_value"})
    return {"value": value, "missing_fields": sorted(set(missing)), "failed_conditions": [ast.get("field")] if value == Truth.FALSE and ast.get("field") else [], "supporting_evidence": sorted(set(evidence)), "trace": trace}

def status_for(scope: dict[str, Any]) -> str:
    return {Truth.TRUE: "相关", Truth.FALSE: "不相关", Truth.UNKNOWN: "待确认"}[Truth(scope["value"])]
