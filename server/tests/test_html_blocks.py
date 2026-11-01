from app.parsing import html_blocks


def test_inline_tags_do_not_split_years_words_or_clauses():
 raw='<nav>报名指标说明</nav><div class="v_news_content"><p>截止<span>202</span><b>6</b>年10月<span>19</span>日，请<span>提交</span>申请表。</p><p>下一段<br>第二行</p></div><footer>电话</footer>'.encode()
 lines=html_blocks(raw)
 assert lines[0]['text']=='截止2026年10月19日，请提交申请表。'
 assert lines[1]['text']=='下一段\n第二行'
 assert len(lines)==2


def test_table_cells_keep_separators_and_nested_blocks_are_not_duplicated():
 lines=html_blocks(b'<main><ul><li><p>Submit form</p></li></ul><table><tr><td>Rank</td><td>20%</td></tr></table></main>')
 assert [line['text'] for line in lines]==['Submit form','Rank\t20%']
