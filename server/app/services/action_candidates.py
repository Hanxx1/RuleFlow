"""Pure, conservative extraction of explicitly written actions and their quotes."""
import re


def extract_actions(evidence: list[tuple[str, str]]) -> list[dict]:
    actions = []
    seen = set()
    for evidence_id, text in evidence:
        for clause in re.split(r"[。；;\n]|，?然后|，?并(?:且)?", text):
            match = re.search(r"(?:请|须|需|应|务必)?(?:于\s*[\d年月日/\- :]+\s*前)?\s*(准备|填写|提交|上传|下载|发送|报名|核对|查看)([^。；;\n]*)", clause)
            if not match:
                continue
            if re.search(r"无需|不必|不需要|不得|禁止|未在", clause[:match.start()+2]) or re.match(r"\s*(?:截止|截至|时间|日期|方式|指标|数量|情况|工作)", match.group(2)):
                continue
            quote = match.group().strip()
            title = (match.group(1) + match.group(2)).strip(" ，,：:")[:300]
            if title in seen or not quote:
                continue
            seen.add(title)
            actions.append({"title": title, "deadline": None, "origin": "document",
                            "evidence_ids": [evidence_id], "evidence_quotes": {evidence_id: quote}})
            if len(actions)>200:raise ValueError('行动候选超过200项处理预算，请拆分来源')
    return actions
