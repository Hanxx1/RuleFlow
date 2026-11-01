import pytest
from app.services.profile_facts import validate_facts,valid_value,ProfileError


def test_profile_rejects_type_coercion_booleans_ranges_and_unknown_fields():
    for value in [{'enrollment_year':'2024'},{'enrollment_year':True},{'rank_percent':101},{'rank_percent':float('nan')},{'team_size':1.5},{'student_type':'invented'},{'unknown':1},{'moral_bonus_items':['same','same']}]:
        with pytest.raises(ProfileError):validate_facts(value)


def test_explicit_null_and_zero_are_not_conflated_with_missing():
    assert validate_facts({'rank_percent':0,'team_size':None,'college':'  学院  '})=={'rank_percent':0,'team_size':None,'college':'学院'}
    assert valid_value('enrollment_year',2024.0)
    assert not valid_value('enrollment_year','2024')


def test_error_exposes_only_field_names_and_not_sensitive_values():
    with pytest.raises(ProfileError) as error:validate_facts({'college':'private-value'*30})
    assert error.value.fields==['college'] and 'private-value' not in str(error.value)
