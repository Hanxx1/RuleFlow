"""Conservative hard-condition extraction with local verbatim evidence."""
import re


def extract_rules(evidence):
    result=[];seen=set()
    patterns=[
        (r'德育(?:素质)?(?:成绩|分)[^。；\n]{0,12}?(\d{1,3})\s*分(?:及以上|以上)', '德育成绩要求','eligibility','gte','moral_score',lambda m:int(m[1])),
        (r'(\d+)\s*[～~至—-]\s*(\d+)\s*名指导(?:老师|教师)', '指导教师人数上限','eligibility','lte','advisor_count',lambda m:int(m[2])),
        (r'(\d+)\s*[～~至—-]\s*(\d+)\s*名指导(?:老师|教师)', '指导教师人数下限','eligibility','gte','advisor_count',lambda m:int(m[1])),
        (r'未受(?:过)?纪律处分', '处分记录要求','eligibility','eq','disciplinary_status',lambda m:'clear'),
        (r'(20\d{2})\s*级(?:及以后|以后)', '入学年份要求','scope','gte','enrollment_year',lambda m:int(m[1])),
        (r'(?:仅限|限|面向)\s*(20\d{2})\s*级(?!及以后|以后)', '入学年份要求','scope','eq','enrollment_year',lambda m:int(m[1])),
        (r'(?:排名|成绩排名)[^。；\n]{0,40}?(?:前|不超过)\s*(\d{1,3})\s*%', '排名比例要求','eligibility','lte','rank_percent',lambda m:int(m[1])),
        (r'(?:团队|每队)[^。；\n]{0,45}?(?:不超过|至多)\s*(\d+)\s*(?:人|名(?:学生|队员|成员))','团队人数要求','eligibility','lte','team_size',lambda m:int(m[1])),
        (r'(?:仅限|限|面向)[^。；\n]{0,20}?本科生','培养层次要求','scope','eq','student_type',lambda m:'undergraduate'),
        (r'(?:面向|限)\s*(20\d{2})\s*[、,，和及]\s*(20\d{2})\s*届','毕业年份要求','scope','in','graduation_year',lambda m:[int(m[1]),int(m[2])]),
    ]
    for evidence_id,text in evidence:
        for pattern,label,kind,op,field,value in patterns:
            for match in re.finditer(pattern,text):
                expected=value(match);key=(op,field,str(expected))
                if key in seen:continue
                seen.add(key)
                result.append({'label':label,'kind':kind,'ast':{'op':op,'field':'profile.'+field,'value':expected,'evidence':[evidence_id]},'evidence_ids':[evidence_id],'evidence_quotes':{evidence_id:match.group()}})
    return result
