"""Discover attachment candidates without fetching or executing linked content."""
import re
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup


def attachments(raw,mime,final_url):
    if mime not in {'text/html','application/xhtml+xml'}:return []
    result=[];seen=set()
    for link in BeautifulSoup(raw,'html.parser').select('a[href]'):
        url=urljoin(final_url,link.get('href',''));parsed=urlparse(url)
        label=link.get_text(' ',strip=True)[:200]
        if parsed.scheme not in {'http','https'} or parsed.username or parsed.password:continue
        if not (re.search(r'\.(pdf|docx|xlsx|txt)$',parsed.path,re.I) or re.search(r'\.(pdf|docx|xlsx|txt)(?:$|\s)',label,re.I)) or url in seen:continue
        seen.add(url);result.append({'url':url,'title':label or '附件待核对','state':'requires_confirmation'})
        if len(result)==10:break
    return result
