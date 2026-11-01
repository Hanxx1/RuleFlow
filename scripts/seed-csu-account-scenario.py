"""Idempotent owner-scoped scenario seed, only with an explicit --apply flag.

Official content retains original dates. Profile, timetable and progress are
synthetic, visibly labelled, and never claim attendance or official eligibility.
No credentials or personal account identifiers are included in this script.
"""
import argparse,hashlib,json,os,re,sqlite3,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import httpx
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.runtime/csu-account-scenario'
SELECT=[0,1,2,4,7,8,9,10,12,13,16,17,21,23,29,33,36,44,45,46,47,56,63,64]
COMPLETED={29,36,44,45,46,47}
CONFIRMED={0,1,2,4,7,8,9}

def identity(owner,key):return str(uuid.uuid5(uuid.NAMESPACE_URL,'zhishi-csu-scenario-20261014:'+owner+':'+key))

def workspace(owner):
    facts={'school':'中南大学','student_type':'undergraduate','college':'计算机学院','major':'软件工程','enrollment_year':2024,'graduation_year':2028,'class_name':'软件工程2403班（演示）','role':'学生（演示）','rank_percent':12,'moral_score':88,'disciplinary_status':'clear','coursework_status':'passed','fitness_status':'passed'}
    assertions=[{'id':'block:client:'+identity(owner,'profile:'+field),'field':field,'value':value,'quote':'用户授权演示画像设定：'+field+' = '+json.dumps(value,ensure_ascii=False)+'；未经学校核验，可随时修改','source':'form','scope':'','validUntil':'2027-07-04','confirmed':True} for field,value in facts.items()]
    courses=[]
    terms=[('2026-09-07','2027-01-10',[('软件工程',1,'08:00','09:40','all'),('操作系统',1,'14:00','15:40','all'),('数据库原理',2,'10:00','11:40','all'),('计算机网络',3,'08:00','09:40','all'),('软件工程实验',3,'14:00','17:00','odd'),('算法设计与分析',4,'10:00','11:40','all'),('大学体育',5,'14:00','15:40','all')]),('2027-03-01','2027-07-04',[('软件测试',1,'08:00','09:40','all'),('软件体系结构',2,'10:00','11:40','all'),('Web应用开发',3,'08:00','09:40','all'),('工程项目实践',3,'14:00','17:00','even'),('人工智能基础',4,'10:00','11:40','all'),('专业英语',5,'08:00','09:40','all')])]
    for start,end,rows in terms:
        for name,day,begin,finish,parity in rows:
            cid=identity(owner,'course:'+start+name)
            courses.append({'id':cid,'title':name+'（合成演示课表）','semesterStart':start,'semesterEnd':end,'weekday':day,'startTime':begin,'endTime':finish,'startWeek':1,'endWeek':18,'parity':parity,'evidence':{'id':'block:client:'+cid,'text':f'用户授权编写演示课表：{name}，{start}至{end}，周{day} {begin}-{finish}，第1-18周，{parity}；非学校正式课表'},'cancelledDates':[]})
    return {'version':2,'owner':owner,'revision':0,'form':facts,'assertions':assertions,'supplement':'演示画像：中南大学2024级软件工程本科生。班级、2028年毕业、排名12%、德育88、课程/体育合格、无处分为用户授权编写，未经学校核验。兴趣：后端开发、算法竞赛、开源项目和志愿服务。竞赛队伍、指导教师、参赛次数等须按具体赛事另行填写。2026秋与2027春课表为合成测试数据。','interests':['academic','competition','exam','award','career'],'history':[],'courses':courses}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--database',required=True);parser.add_argument('--email',required=True);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    dbpath=Path(args.database).resolve()
    if not dbpath.is_file():raise ValueError('Database must exist')
    connection=sqlite3.connect(dbpath);connection.row_factory=sqlite3.Row
    user=connection.execute('SELECT id FROM users WHERE email=? AND deleted_at IS NULL',(args.email,)).fetchone()
    if not user:raise ValueError('Requested active account does not exist')
    owner=user['id'];sources=json.loads((OUT/'notices.json').read_text(encoding='utf-8'))
    if len(sources)<65:raise ValueError('Expected reviewed source corpus')
    records=[sources[i] for i in SELECT]
    print(json.dumps({'cases':len(records),'completed':len(COMPLETED),'confirmed':len(CONFIRMED),'pending':len(SELECT)-len(COMPLETED)-len(CONFIRMED),'source_from':min(r['published'] for r in records),'source_to':max(r['published'] for r in records),'apply':args.apply}))
    if not args.apply:return
    backup=OUT/'before-seed.db'
    if not backup.exists():
        dest=sqlite3.connect(backup);connection.backup(dest);dest.close()
    other_before=connection.execute('SELECT id,owner_id,title,status,updated_at FROM cases WHERE owner_id<>? ORDER BY id',(owner,)).fetchall()
    connection.close()
    os.environ['DATABASE_PATH']=str(dbpath);os.environ['DEMO_MODE']='false'
    sys.path.insert(0,str(ROOT/'server'))
    from app.auth import conn
    from app.main import _local_candidates,_persist_analysis,category_from
    from app.services.review import confirm_review,read_review,compiled_task_id
    from app.parsing import parse_bytes
    previous_manifest={r['case_id']:r for r in json.loads((OUT/'seed-manifest.json').read_text(encoding='utf-8'))} if (OUT/'seed-manifest.json').exists() else {}
    manifest=[]
    client=httpx.Client(timeout=30,follow_redirects=True)
    for index in SELECT:
        sample=sources[index];case_id=identity(owner,'case:'+sample['url']);now=datetime.now(timezone.utc).isoformat()
        with conn() as c:
            if c.execute('SELECT 1 FROM cases WHERE id=? AND owner_id=?',(case_id,owner)).fetchone():
                manifest.append({**previous_manifest.get(case_id,{}),'case_id':case_id,'title':sample['title'],'source_url':sample['url'],'published':sample['published'],'seeded':False});continue
        rows=[{'text':line,'locator':'官网正文段落 '+str(i+1)+' '+sample['url'],'page':None} for i,line in enumerate(sample['lines']) if line.strip()]
        # Read actual embedded PDFs; refuse HTML masquerading as a PDF.
        response=client.get(sample['url']);response.raise_for_status()
        if urlparse(str(response.url)).hostname!='cse.csu.edu.cn' or len(response.content)>2_000_000:raise ValueError('Unsafe source response')
        soup=BeautifulSoup(response.content.decode('utf-8'),'html.parser');content=soup.select_one('.v_news_content')
        pdfs=list(dict.fromkeys(urljoin(sample['url'],p) for p in re.findall(r'[\"\']([^\"\']+\.pdf)[\"\']',str(content))))
        links=[]
        for link in soup.select('a[href]'):
            title=link.get_text(' ',strip=True);url=urljoin(sample['url'],link['href'].strip())
            if re.search(r'附件|\.(?:pdf|docx?|xlsx?)(?:$|\s)',title,re.I) and urlparse(url).scheme in {'http','https'}:
                links.append({'url':url,'title':title})
        formats=['html']
        for pdf in pdfs[:2]:
            if urlparse(pdf).hostname!='cse.csu.edu.cn':raise ValueError('Unexpected PDF host')
            raw=client.get(pdf);raw.raise_for_status()
            if urlparse(str(raw.url)).hostname!='cse.csu.edu.cn' or len(raw.content)>20_000_000:raise ValueError('Unsafe PDF response')
            blocks=parse_bytes(raw.content,'application/pdf',sample['title'])
            rows.extend({**b,'locator':b['locator']+' '+pdf} for b in blocks if b['text'].strip());formats.append('pdf')
        if not rows:raise ValueError('No source evidence')
        source_rows=[]
        with conn() as c:
            c.execute('INSERT INTO cases(id,owner_id,title,category,status,relevance,deadline,created_at,updated_at,deadline_source,deadline_evidence_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(case_id,owner,sample['title']+'【演示进度】',category_from(sample['title']),'review','UNKNOWN',None,now,now,None,'[]'))
            for i,block in enumerate(rows):
                ref='block:'+identity(owner,sample['id']+':evidence:'+str(i));source_rows.append((ref,block['text']))
                c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,owner,case_id,sample['title']+'（官方公开原文）',block['text'],block['locator'],block.get('page'),now))
            state_ref='block:'+identity(owner,'progress:'+sample['id'])
            progress='已完成' if index in COMPLETED else '已确认、进行中' if index in CONFIRMED else '待确认'
            c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(state_ref,owner,case_id,'用户授权演示设定',f'用户要求编写多种任务进度；本事项设为{progress}，仅用于演示，不证明真实报名、参加、获奖或办理。原通知发布于{sample["published"]}；原日期不改写。','2026-10-14 用户授权的模拟进度记录',None,now))
            for link in links[:10]:
                ref='block:'+identity(owner,'link:'+link['url']+sample['id'])
                c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,owner,case_id,'官网附件线索',link['title']+' '+link['url'],'附件链接仅发现，未上传或校验内容',None,now))
                c.execute('INSERT OR IGNORE INTO case_attachment_links VALUES(?,?,?,?,?)',(owner,case_id,link['url'],link['title'],ref))
        candidate=_local_candidates(source_rows)
        candidate['title']=sample['title'];candidate['summary']=f'中南大学官网公开通知，发布于{sample["published"]}。进度是用户授权的演示设定；仅抽取明确行动和条件，复杂资格、模糊日期、缺失附件保留待核对。'
        candidate['tasks']=[t for t in candidate['tasks'] if len(t['title'])<=100 and not re.search('学院|学校|各单位|各部门|审批|汇总|报送|推荐名单|QQ群|qq',t['title'],re.I)][:3]
        if not candidate['tasks']:
            with conn() as c:
                ref='block:'+identity(owner,'read-plan:'+sample['id'])
                quote='用户授权演示计划：阅读公开通知，核对个人资格、原日期及附件是否齐全。'
                c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ref,owner,case_id,'用户制定的阅读计划',quote,'用户计划，非官方要求',None,now))
            source_rows.append((ref,quote));candidate['tasks']=[{'title':'阅读通知并核对资格与附件（用户演示计划）','origin':'user_input','deadline':None,'evidence_ids':[ref],'evidence_quotes':{ref:quote}}]
        candidate['review_reasons'].append('模拟进度不代表真实办理；原文件中的复杂资格和附件需核对')
        candidate['_evidence_rows']=source_rows
        _persist_analysis(owner,case_id,'local','none',hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest(),candidate,[])
        with conn() as c:
            review=read_review(c,owner,case_id)
            if index in COMPLETED or index in CONFIRMED:
                dates=[d for d in review['candidate']['dates'] if d['role']=='deadline' and d['value']]
                choices={}
                for action in review['candidate']['actions']:
                    relevant=[d for d in dates if set(d['evidence_ids'])&set(action['evidence_ids'])]
                    choices[action['id']]={'deadline_id':relevant[0]['id']} if len(relevant)==1 else {'no_deadline':True}
                confirm_review(c,owner,case_id,review['revision'],[a['id'] for a in review['candidate']['actions']],None,None,True,choices)
                status='completed' if index in COMPLETED else 'in_progress'
                c.execute('UPDATE cases SET status=? WHERE owner_id=? AND id=?',(status,owner,case_id))
                for i,action in enumerate(review['candidate']['actions']):
                    tid=compiled_task_id(owner,case_id,action['id'],action)
                    task=c.execute('SELECT evidence_ids_json FROM tasks WHERE id=? AND owner_id=?',(tid,owner)).fetchone()
                    refs=json.loads(task[0]);refs.append(state_ref)
                    c.execute('UPDATE tasks SET status=?,evidence_ids_json=? WHERE id=? AND owner_id=?',('done' if index in COMPLETED else 'in_progress' if i==0 else 'todo',json.dumps(sorted(set(refs))),tid,owner))
            manifest.append({'case_id':case_id,'title':sample['title'],'source_url':sample['url'],'published':sample['published'],'progress':progress,'formats':formats,'attachment_links':len(links),'seeded':True})
    with conn() as c:
        after=c.execute('SELECT id,owner_id,title,status,updated_at FROM cases WHERE owner_id<>? ORDER BY id',(owner,)).fetchall()
        assert [tuple(r) for r in other_before]==[tuple(r) for r in after],'Other owner data changed'
        assert len(manifest)>=20
    (OUT/'client-workspace.json').write_text(json.dumps(workspace(owner),ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'seed-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'added':sum(r['seeded'] for r in manifest),'total_scenario':len(manifest),'other_owners_unchanged':True,'courses':13}))

if __name__=='__main__':main()
