"""Evidence-backed attachment inventory; missing files block completeness claims."""
import re
from urllib.parse import urlparse

def inventory(evidence,documents=(),links=()):
    result=[];seen=set()
    for block in evidence:
        ref=block['id'];text=block['text']
        for clause in re.split(r'[。；\n]',text):
            if not re.search(r'附件|详见.{0,12}(?:细则|申请表)|以.{0,12}细则为准',clause):continue
            match=re.search(r'附件\s*(\d+)?\s*[：:、.\s]*([^，,]{0,60})',clause)
            number=match[1] if match else None
            title=(match[2].strip() if match else clause.strip()) or '附件名称待核对'
            if len(title)>60:title=title[:60]
            key=(number,title)
            if key in seen:continue
            seen.add(key)
            candidates=[]
            for doc in documents:
                name=doc['name'];indexed=number and re.search(r'附件\s*'+re.escape(number)+r'(?!\d)',name)
                named=title!='附件名称待核对' and len(title)>=3 and title in name
                if indexed or named:candidates.append(doc)
            state='obtained' if any(d['status']=='parsed' for d in candidates) else 'failed' if candidates else 'missing'
            result.append({'title':title,'number':number,'state':state,'evidence_ids':[ref],'quote':clause.strip(),'documents':[{'id':d['id'],'name':d['name'],'status':d['status']} for d in candidates],'warning':'文件名称匹配仅说明已取得，内容与适用范围仍需核对'})
    for link in links:
        title=link.get('title') or '网页附件';url=link.get('url','')
        if not any(item['title']==title for item in result):
            result.append({'title':title,'number':None,'state':'missing','evidence_ids':link.get('evidence_ids',[]),'quote':link.get('quote',title),'url':url,'documents':[],'warning':'只发现链接，不代表已读取附件'})
    missing=sum(r['state']!='obtained' for r in result)
    return {'status':'needs_attachments' if missing else 'attachments_obtained' if result else 'no_explicit_attachment_reference','missing_count':missing,'items':result,'complete':not missing,'warning':'附件齐备不代表资格条件或任务已全部识别'}
