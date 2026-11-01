"""Pure date extraction. Candidates never become a final deadline automatically."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone, timedelta

DATE = re.compile(r"(?<!\d)(?:(?P<year>20\d{2})\s*[-/年]\s*)?(?P<month>\d{1,2})\s*[-/月]\s*(?P<day>\d{1,2})(?:\s*日|(?!\d|\s*日))")
DEADLINE = re.compile(r"截止|截至|最迟|(?:提交|报名|申请|上传).{0,12}(?:前|之前)|(?:前|之前).{0,12}(?:提交|报名|申请|上传)")


def extract_dates(evidence: list[tuple[str, str]]) -> list[dict]:
    result = []
    for evidence_id, text in evidence:
        for match in DATE.finditer(text):
            start = max(text.rfind(char, 0, match.start()) for char in "。；;\n，,") + 1
            endings = [pos for char in "。；;\n，," if (pos := text.find(char, match.end())) >= 0]
            end = min(endings, default=len(text))
            context = text[start:end].strip()
            # A local clause avoids assigning a later clause's deadline to a publication date.
            left = text[max(start, match.start() - 16):match.start()]
            right = text[match.end():min(end, match.end() + 16)]
            # A table row explicitly pairs its date cell with the full action cell.
            row_tail=text[match.end():end]
            if '\t' in row_tail and not DATE.search(row_tail):right=row_tail
            if end<len(text) and text[end] in '，,':
                stops=[pos for char in '。；;\n' if (pos:=text.find(char,end+1))>=0]
                tail=text[end+1:min(stops,default=len(text))]
                if (DEADLINE.search(tail) or (re.match(r'\s*(?:前|之前)',right) and re.search(r'报名|申请|提交|公示|报送|完成',tail))) and not DATE.search(tail):
                    right=text[match.end():end]+tail
                    context=text[start:min(stops,default=len(text))].strip()
            if re.search(r"发布|公示|印发", left):
                role = "publication"
            elif DEADLINE.search(left + match.group() + right) or (re.match(r'\s*(?:前|之前)',right) and re.search(r'报名|申请|提交|公示|报送|完成',context)):
                role = "deadline"
            elif re.search(r"活动|比赛|考试|会议|举办", left + right):
                role = "event"
            else:
                role = "unknown"
            if '\t' in context and re.search(r'学费产生|奖励范围|统计期间|参评学年',context):role='unknown'
            year = match.group("year")
            try:
                checked = date(int(year or 2000), int(match.group("month")), int(match.group("day")))
                value = checked.isoformat() if year else None
                reasons = [] if year else ["missing_year"]
            except ValueError:
                value, reasons = None, ["invalid_date"]
            if role == "unknown":
                reasons.append("unknown_date_role")
            precision = 'date'
            clock = re.match(r"\s*(上午|下午|晚上)?\s*(\d{1,2})(?::(\d{2})|(?:点|时)(?:(\d{1,2})分?)?)", right)
            if clock:
                precision = 'datetime'
                hour, minute = int(clock[2]), int(clock[3] or clock[4] or 0)
                if clock[1] in {'下午','晚上'} and 1 <= hour < 12:hour += 12
                if clock[1] == '上午' and hour == 12:hour = 0
                explicit_zone = '北京时间' in context or '+08:00' in context or 'UTC' in context
                if value and explicit_zone and hour < 24 and minute < 60:
                    zone = timezone.utc if 'UTC' in context else timezone(timedelta(hours=8))
                    value = datetime(checked.year, checked.month, checked.day, hour, minute, tzinfo=zone).isoformat()
                else:
                    value = None
                    reasons.append('invalid_time' if hour >= 24 or minute >= 60 else 'time_requires_review')
            identity = f"{evidence_id}:{match.start()}:{match.group()}"
            result.append({"id": "date:" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                           "raw": match.group()+ (clock.group() if clock else ''), "value": value, "precision": precision, "role": role,
                           "inferred": False, "evidence_ids": [evidence_id], "quote": context,
                           "start": match.start(), "end": match.end(), "review_reasons": reasons})
    deadlines = {item["value"] or item["raw"] for item in result if item["role"] == "deadline"}
    if len(deadlines) > 1:
        for item in result:
            if item["role"] == "deadline":
                item["review_reasons"].append("multiple_deadlines")
    return result
