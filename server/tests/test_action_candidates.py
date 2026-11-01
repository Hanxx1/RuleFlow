from app.services.action_candidates import extract_actions


def test_plain_announcement_does_not_invent_a_submission_task():
    assert extract_actions([('block:a', '本周校园活动安排公布。申请表供参考。')]) == []
    assert extract_actions([('block:a', '报名截止2026-10-25。无需准备申请表。不得上传材料。')]) == []


def test_explicit_actions_have_local_verbatim_quotes_without_invented_edges():
    evidence = [('block:a', '请填写申请表。'), ('block:b', '请上传作品。')]
    actions = extract_actions(evidence)
    assert [item['title'] for item in actions] == ['填写申请表', '上传作品']
    assert [item['evidence_ids'] for item in actions] == [['block:a'], ['block:b']]
    assert all(item['evidence_quotes'][item['evidence_ids'][0]] in dict(evidence)[item['evidence_ids'][0]] for item in actions)
    assert all(item['deadline'] is None and 'dependencies' not in item for item in actions)


def test_actions_in_one_sentence_split_and_duplicate_titles_are_not_repeated():
    actions = extract_actions([('block:a', '请准备申请表，并于2026-10-25前提交。请准备申请表。')])
    assert len(actions) == 2
    assert actions[0]['title'] == '准备申请表'
    assert actions[1]['title'] == '提交'
