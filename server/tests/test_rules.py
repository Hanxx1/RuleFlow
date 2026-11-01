from app.rules import Truth, evaluate
def atom(v): return {"op":"eq","field":"profile.team_size","value":v}
def test_unknown_on_missing():
    r=evaluate(atom(1), {})
    assert r["value"] == Truth.UNKNOWN and r["missing_fields"] == ["profile.team_size"]
def test_kleene_and_or():
    assert evaluate({"op":"and","args":[atom(1),atom(2)]},{"team_size":1})["value"] == Truth.FALSE
    assert evaluate({"op":"or","args":[atom(1),{"op":"eq","field":"profile.certificate_level","value":2}]},{"team_size":1})["value"] == Truth.TRUE
def test_scope():
    rule={"op":"gte","field":"profile.enrollment_year","value":2023}
    assert evaluate(rule,{"enrollment_year":2024})["value"] == Truth.TRUE
