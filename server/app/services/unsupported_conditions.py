"""Retain explicit unmodeled hard conditions without inventing AST fields."""
import re

PATTERN=re.compile(r'德育(?:素质)?(?:成绩|分)|纪律处分|不诚信记录|必修课[^。]{0,50}合格|体育[^。]{0,50}合格|中华人民共和国国籍|每位学生[^。]{0,35}(?:一支|两次)|每位老师[^。]{0,60}(?:最多|超过)')

def extract_unsupported(evidence):
    result=[]
    for ref,text in evidence:
        for clause in re.split(r'[。；\n]',text):
            remaining=re.sub(r'德育(?:素质)?(?:成绩|分)[^。；\n]{0,12}?\d{1,3}\s*分(?:及以上|以上)|未受(?:过)?纪律处分','',clause)
            if PATTERN.search(remaining):
                quote=clause.strip()
                result.append({'value':quote,'inferred':False,'evidence_ids':[ref],'evidence_quotes':{ref:quote}})
    return result
