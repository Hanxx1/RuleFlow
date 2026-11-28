import pytest

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


@pytest.mark.parametrize('container', [
 '<div class="v_news_content">{}</div>',
 '<div class="wp_articlecontent">{}</div>',
 '<div class="article-content">{}</div>',
 '<div class="news-content">{}</div>',
 '<div class="entry-content">{}</div>',
 '<article>{}</article>',
 '<main>{}</main>',
])
def test_cms_form_wrapper_keeps_article_and_excludes_page_navigation(container):
 # Synthetic structure from the NWU notice: form > #vsb_content > .v_news_content.
 article=container.format('<p>截止<span>202</span>6年，请提交申请表。</p><p>第二条<br>保留原句</p>')
 raw=('<body><div><ul><li>学校导航</li></ul></div>'
      '<form><p>搜索提示</p><input value="搜索"></form>'
      '<form name="_newscontent_fromname"><h2>通知标题</h2>'
      '<div id="vsb_content">'+article+'</div></form>'
      '<div><p>上一篇与下一篇</p></div></body>').encode()
 assert [row['text'] for row in html_blocks(raw)]==[
  '截止2026年，请提交申请表。','第二条\n保留原句',
 ]


def test_article_wrapper_controls_are_excluded_without_removing_prose_or_table():
 raw=('''<form name="_newscontent_fromname"><div class="v_news_content">
 <p>请按原表填写。<input value="private"><button>提交按钮</button><select><option>选项</option></select><textarea>输入框</textarea></p>
 <script>tracking()</script><style>.x{}</style>
 <table><tr><td>申请表</td><td>一份</td></tr></table>
 <p><a href="form.docx">下载原表</a></p></div></form>''').encode()
 assert [row['text'] for row in html_blocks(raw)]==[
  '请按原表填写。','申请表\t一份','下载原表',
 ]


def test_unrelated_forms_still_do_not_become_fallback_notice_text():
 raw=b'<body><form><p>Search prompt</p></form><div><p>Plain notice</p></div></body>'
 assert [row['text'] for row in html_blocks(raw)]==['Plain notice']


def test_search_form_body_selector_does_not_hide_later_article():
 raw=('<form role="search"><div class="entry-content"><p>搜索帮助</p></div></form>'
      '<article><p>报名截止2026-12-10。</p></article>').encode()
 assert [row['text'] for row in html_blocks(raw)]==['报名截止2026-12-10。']
