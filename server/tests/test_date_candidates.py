from app.services.date_candidates import extract_dates


def test_publication_event_and_deadline_are_separate_and_never_final_values():
    candidates = extract_dates([('block:one', '发布于2026年10月1日。比赛2026-10-20举行。报名截止2026/10/15。')])
    assert [(item['role'], item['value']) for item in candidates] == [('publication', '2026-10-01'), ('event', '2026-10-20'), ('deadline', '2026-10-15')]
    assert all(item['evidence_ids'] == ['block:one'] and item['quote'] for item in candidates)
    assert candidates == extract_dates([('block:one', '发布于2026年10月1日。比赛2026-10-20举行。报名截止2026/10/15。')])


def test_missing_year_and_invalid_date_are_not_guessed():
    candidates = extract_dates([('block:a', '截止10月25日。截止2026-02-30。')])
    assert candidates[0]['value'] is None and 'missing_year' in candidates[0]['review_reasons']
    assert candidates[1]['value'] is None and 'invalid_date' in candidates[1]['review_reasons']
    assert not any(item['inferred'] for item in candidates)


def test_multiple_deadlines_and_unknown_role_require_review():
    candidates = extract_dates([('block:a', '报名截止2026-10-20。作品截止2026-10-25。记录2026-10-01。')])
    assert all('multiple_deadlines' in item['review_reasons'] for item in candidates[:2])
    assert candidates[2]['role'] == 'unknown'
    assert 'unknown_date_role' in candidates[2]['review_reasons']


def test_evidence_identity_does_not_mix_identical_dates_in_two_sources():
    candidates = extract_dates([('block:a', '截止2026-10-25'), ('block:b', '截止2026-10-25')])
    assert candidates[0]['id'] != candidates[1]['id']


def test_next_clause_does_not_change_an_event_date_into_a_deadline():
    candidates = extract_dates([('block:a', '比赛2026-10-20，报名截止2026-10-15。')])
    assert [item['role'] for item in candidates] == ['event', 'deadline']


def test_explicit_time_is_not_silently_replaced_with_end_of_day():
    candidates = extract_dates([('block:a', '截止2026-10-25下午5点。')])
    assert candidates[0]['value'] is None and 'time_requires_review' in candidates[0]['review_reasons']


def test_complete_clock_with_explicit_timezone_and_invalid_clock():
    values = extract_dates([('block:a','北京时间截止2026-10-25下午5点30分。UTC截止2026-10-26 09:45。北京时间截止2026-10-26 25:00。')])
    assert values[0]['value'] == '2026-10-25T17:30:00+08:00'
    assert values[1]['value'] == '2026-10-26T09:45:00+00:00'
    assert values[2]['value'] is None and 'invalid_time' in values[2]['review_reasons']


def test_spaces_and_date_first_stage_deadlines_in_public_notices():
    dates=extract_dates([('block:a','2026 年 1 月 15 日，网络报名截止。2026 年 1 月 31 日，研究综述上传截止。')])
    assert [(item['role'],item['value']) for item in dates]==[('deadline','2026-01-15'),('deadline','2026-01-31')]
    assert dates[0]['quote'].endswith('网络报名截止')
def test_table_date_cell_uses_full_action_cell_without_cross_date_inference():
    dates=extract_dates([('block:table','2026年5月31日\t实验记录、论文、查重报告、参赛承诺书上传截止。')])
    assert dates[0]['value']=='2026-05-31' and dates[0]['role']=='deadline'

def test_adjacent_clock_cannot_be_silently_dropped_from_date():
    dates=extract_dates([('block:clock','报送截止时间：2026年6月26日10点')])
    assert dates[0]['value'] is None and dates[0]['precision']=='datetime'
    assert 'time_requires_review' in dates[0]['review_reasons']

def test_fee_eligibility_table_period_is_not_an_action_deadline():
    dates=extract_dates([('block:fees','申请减免学费产生的学期\t2022年1月24日前\t2023年9月1日后')])
    assert all(date['role']=='unknown' for date in dates)

