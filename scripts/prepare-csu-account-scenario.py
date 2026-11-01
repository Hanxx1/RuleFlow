"""Collect official CSU notices for an explicitly requested account scenario.

Public corpus only; personal account selection is supplied separately at seed time.
"""
import json,re,time,hashlib
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.runtime/csu-account-scenario'
OUT.mkdir(parents=True,exist_ok=True)
client=httpx.Client(timeout=25,follow_redirects=True,headers={'User-Agent':'ZhiShi-PublicNoticeReview/1.0'})
robots=RobotFileParser()
rr=client.get('https://cse.csu.edu.cn/robots.txt')
if rr.status_code==200:robots.parse(rr.text.splitlines())
elif rr.status_code==404:robots.parse([])
else:raise RuntimeError('Cannot establish crawl policy')

def fetch(url):
    if urlparse(url).hostname!='cse.csu.edu.cn' or not robots.can_fetch('*',url):raise ValueError('Source not allowed')
    r=client.get(url);r.raise_for_status()
    if urlparse(str(r.url)).hostname!='cse.csu.edu.cn':raise ValueError('Unexpected redirect')
    if len(r.content)>2_000_000:raise ValueError('Oversized page')
    return BeautifulSoup(r.content.decode('utf-8'),'html.parser')

items=[];seen=set();url='https://cse.csu.edu.cn/index/tzgg.htm'
for page in range(18):
    s=fetch(url)
    for a in s.select('a[href]'):
        title=a.get_text(' ',strip=True);href=urljoin(url,a['href'])
        if '/info/1040/' not in href or href in seen:continue
        seen.add(href)
        # Exclude named lists, personnel decisions and graduate-only notices.
        if re.search('公示|名单|研究生|博士|硕士|辅导员|教师|党|聘|通报|退学',title):continue
        if not re.search('本科|竞赛|大赛|综合测评|创新|辅修|程序|选拔|考试|实践|志愿',title):continue
        try:
            body=fetch(href)
            content=body.select_one('.v_news_content')
            if not content:continue
            lines=[p.get_text(' ',strip=True) for p in content.select('p,tr')]
            lines=list(dict.fromkeys(x for x in lines if x))
            if not lines:lines=[content.get_text('\n',strip=True)]
            heading=body.select_one('h1')
            title=heading.get_text(' ',strip=True) if heading else title
            date_match=re.search(r'时间[：:]\s*(20\d{2})年(\d{2})月(\d{2})日',body.get_text(' ',strip=True))
            published='-'.join(date_match.groups()) if date_match else None
            if published and published<'2024-01-01':continue
            links=[{'title':a.get_text(' ',strip=True),'url':urljoin(href,a['href'])} for a in body.select('a[href]') if re.search(r'附件|\.(?:pdf|docx?|xlsx?)(?:$|\s)|download',a.get_text()+a['href'],re.I)]
            for embedded in re.findall(r'[\"\']([^\"\']+\.pdf)[\"\']',str(content)):
                links.append({'title':title+'（官网PDF）','url':urljoin(href,embedded)})
            items.append({'id':hashlib.sha256(href.encode()).hexdigest()[:24],'title':title,'url':href,'published':published,'lines':lines,'attachment_links':links})
            print(json.dumps({'count':len(items),'title':title,'published':published},ensure_ascii=True),flush=True)
        except Exception as e:print(json.dumps({'skipped':href,'error':type(e).__name__}),flush=True)
        time.sleep(.15)
    nxt=next((a for a in s.select('a[href]') if a.get_text(strip=True)=='下页'),None)
    if not nxt or len(items)>=65:break
    url=urljoin(url,nxt['href'])
    time.sleep(.2)
for href in ['https://cse.csu.edu.cn/info/1041/11541.htm','https://cse.csu.edu.cn/info/1041/11538.htm']:
    try:
        body=fetch(href);content=body.select_one('.v_news_content');heading=body.select_one('h1')
        if not content or not heading:continue
        lines=list(dict.fromkeys(p.get_text(' ',strip=True) for p in content.select('p') if p.get_text(strip=True)))
        dm=re.search(r'时间[：:]\s*(20\d{2})年(\d{2})月(\d{2})日',body.get_text(' ',strip=True))
        items.append({'id':hashlib.sha256(href.encode()).hexdigest()[:24],'title':heading.get_text(' ',strip=True),'url':href,'published':'-'.join(dm.groups()) if dm else None,'lines':lines,'attachment_links':[]})
    except Exception as exc:print(json.dumps({'lecture_skipped':href,'error':type(exc).__name__}),flush=True)
(OUT/'notices.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
if len(items)<20:raise RuntimeError(f'Only {len(items)} qualifying sources')
print(json.dumps({'collected':len(items),'from':min(x['published'] or '9999' for x in items),'to':max(x['published'] or '' for x in items)}))
