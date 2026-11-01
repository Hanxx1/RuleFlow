from app.services.knowledge import chunk_lines,tokens,answer_with_sources


def test_chunks_preserve_source_ids_and_overlap_without_invented_text():
    lines=[{'id':'a','text':'甲'*600,'page':1},{'id':'b','text':'乙'*600,'page':2}]
    chunks=chunk_lines(lines)
    assert len(chunks)>=2 and chunks[0]['line_ids']==['a']
    assert any('b' in chunk['line_ids'] for chunk in chunks)
    assert all(chunk['text'] in ('甲'*600+'\n'+'乙'*600+'\n') for chunk in chunks)


def test_no_sources_returns_no_evidence_and_excerpts_are_exact():
    assert answer_with_sources({'items':[]})['has_enough_evidence'] is False
    item={'id':'chunk:1','quote':'真实导入的原文条款'}
    answer=answer_with_sources({'items':[item]})
    assert answer['claims']==[{'text':item['quote'],'source_ids':[item['id']]}]
    assert tokens('专业排名前20%')['专业']==1
