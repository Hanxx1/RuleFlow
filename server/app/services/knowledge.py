"""Owner-filtered local retrieval over actual imported documents, with cited extractive answers."""
import json
import math
import re
import uuid
from collections import Counter
from datetime import datetime,timezone


def tokens(text):
    latin=re.findall(r'[a-z0-9_]{2,}',text.casefold())
    chinese=[]
    for run in re.findall(r'[\u4e00-\u9fff]+',text):
        chinese.extend(run[i:i+2] for i in range(len(run)-1))
    return Counter(latin+chinese)


def chunk_lines(lines,size=700,overlap=100):
    # Stable slices retain the IDs of every source line intersecting the chunk.
    text='';ranges=[]
    for line in lines:
        start=len(text);text+=line['text']+'\n';ranges.append((start,len(text),line['id'],line.get('page')))
    chunks=[];start=0
    while start<len(text):
        end=min(start+size,len(text))
        if end<len(text):
            split=text.rfind('\n',start+size//2,end)
            if split>start:end=split+1
        content=text[start:end].strip()
        if content:
            covered=[item for item in ranges if item[0]<end and item[1]>start]
            chunks.append({'text':content,'line_ids':[item[2] for item in covered],'page':next((item[3] for item in covered if item[3]),None)})
        if end==len(text):break
        start=max(start+1,end-overlap)
    return chunks


def index_document(c,owner_id,document_id,title,category='other',publisher='用户导入',effective_date=None):
    document=c.execute('SELECT * FROM documents WHERE id=? AND owner_id=?',(document_id,owner_id)).fetchone()
    if document is None or document['status']!='parsed':raise ValueError('资料文档不存在或解析尚未完成')
    existing=c.execute('SELECT id FROM knowledge_documents WHERE owner_id=? AND document_id=?',(owner_id,document_id)).fetchone()
    if existing:return existing['id']
    lines=[dict(row) for row in c.execute('SELECT * FROM document_lines WHERE owner_id=? AND document_id=? ORDER BY line_number',(owner_id,document_id))]
    knowledge_id=str(uuid.uuid4());chunks=chunk_lines(lines)
    if not chunks:raise ValueError('知识资料没有可索引文字')
    c.execute('INSERT INTO knowledge_documents VALUES(?,?,?,?,?,?,?,?,?)',(knowledge_id,owner_id,document_id,title,category,publisher,effective_date,'indexed',datetime.now(timezone.utc).isoformat()))
    for index,chunk in enumerate(chunks):
        chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{knowledge_id}:{index}'))
        c.execute('INSERT INTO knowledge_chunks VALUES(?,?,?,?,?,?,?,?)',(chunk_id,owner_id,knowledge_id,index,chunk['text'],json.dumps(chunk['line_ids']),chunk['page'],'local-tfidf-bigram-1'))
    return knowledge_id


def search(c,owner_id,query,top_k=5,category=None):
    # Authorization is applied before building the scoring corpus.
    rows=c.execute("SELECT k.*,d.title,d.publisher,d.effective_date,d.document_id,d.category FROM knowledge_chunks k JOIN knowledge_documents d ON d.id=k.knowledge_id AND d.owner_id=k.owner_id WHERE k.owner_id=? AND d.status='indexed' AND (? IS NULL OR d.category=?) ORDER BY k.id LIMIT 5001",(owner_id,category,category)).fetchall()
    if len(rows)>5000:return {'status':'unavailable','items':[],'reason':'knowledge_search_capacity_exceeded'}
    if not rows:return {'status':'unavailable','items':[],'reason':'knowledge_provider_not_configured'}
    counters=[tokens(row['title']+' '+row['text']) for row in rows];query_tokens=tokens(query)
    frequency=Counter(term for counter in counters for term in counter)
    weights={term:math.log((len(rows)+1)/(frequency[term]+1))+1 for term in set(query_tokens).union(frequency)}
    def vector(counter):return {term:(1+math.log(count))*weights.get(term,1) for term,count in counter.items()}
    q=vector(query_tokens);qnorm=math.sqrt(sum(value*value for value in q.values()))
    items=[]
    for row,counter in zip(rows,counters):
        v=vector(counter);norm=math.sqrt(sum(value*value for value in v.values()))
        score=sum(value*v.get(term,0) for term,value in q.items())/(qnorm*norm) if qnorm and norm else 0
        if score<0.08:continue
        items.append({'id':row['id'],'title':row['title'],'publisher':row['publisher'],'quote':row['text'],
                      'matched_section':f"片段 {row['chunk_index']+1}",'effective_date':row['effective_date'],
                      'confidence':None,'match_type':'local_tfidf_bigram','match_score':round(score,4),
                      'evidence_ids':[],'reference':{'document_id':row['document_id'],'knowledge_id':row['knowledge_id'],'chunk_id':row['id'],'line_ids':json.loads(row['line_ids_json']),'page':row['page'],'version':1,'locator':f"片段 {row['chunk_index']+1}"}})
    items.sort(key=lambda item:(-item['match_score'],item['id']))
    return {'status':'available','items':items[:top_k],'reason':None if items else 'RAG_NO_EVIDENCE'}


def answer_with_sources(result):
    sources=result['items']
    if not sources:return {'answer':'当前知识库中未找到足够依据','sources':[],'claims':[],'has_enough_evidence':False,'mode':'extractive','reason':'RAG_NO_EVIDENCE'}
    claims=[{'text':item['quote'],'source_ids':[item['id']]} for item in sources[:3]]
    return {'answer':'\n\n'.join(claim['text'] for claim in claims),'claims':claims,'sources':sources[:3],'has_enough_evidence':True,'mode':'extractive','reason':None}
