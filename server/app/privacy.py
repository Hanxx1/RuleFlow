"""Deterministic privacy findings. Input and findings are never persisted here."""
from __future__ import annotations

import re


PATTERNS = [
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "id_card", "身份证号", lambda value: "*" * len(value)),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "phone", "手机号", lambda value: f"{value[:3]}****{value[-4:]}"),
    (re.compile(r"(?<!\d)\d{16,19}(?!\d)"), "bank_card", "银行卡号", lambda value: "*" * len(value)),
    (re.compile(r"[\w.+-]{1,64}@[\w.-]{1,253}\.[A-Za-z]{2,24}"), "email", "邮箱", lambda value: "[邮箱已遮盖]"),
    (re.compile(r"学号\s*[:：]?\s*\d{6,20}"), "student_id", "学号", lambda value: "[学号已遮盖]"),
    (re.compile(r"(?:姓名|名字)\s*[:：]\s*[\u4e00-\u9fff]{2,8}"), "name", "姓名", lambda value: "[姓名已遮盖]"),
    (re.compile(r"(?:地址|住址)\s*[:：]\s*[^\n。]{4,80}"), "address", "地址", lambda value: "[地址已遮盖]"),
]
UNSUPPORTED_PATTERNS = [
    (re.compile(r"(?<!\d)\d{8,12}(?!\d)"), "student_id"),
]


def analyze(text: str) -> dict:
    candidates = []
    for priority, (regex, finding_type, label, replacement) in enumerate(PATTERNS):
        for match in regex.finditer(text):
            candidates.append((match.start(), match.end(), priority, finding_type, label, match.group(), replacement(match.group())))
    candidates.sort(key=lambda item: (item[0], item[2], -(item[1] - item[0])))

    accepted = []
    for candidate in candidates:
        start, end = candidate[0], candidate[1]
        if any(start < prior[1] and end > prior[0] for prior in accepted):
            continue
        accepted.append(candidate)
    accepted.sort(key=lambda item: item[0])

    findings = []
    chunks = []
    cursor = 0
    for index, (start, end, _priority, finding_type, label, original, redacted) in enumerate(accepted, 1):
        chunks.extend((text[cursor:start], redacted))
        findings.append({"id": f"finding-{index}", "type": finding_type, "label": label, "start": start, "end": end, "original": original, "redacted": redacted})
        cursor = end
    chunks.append(text[cursor:])
    unsupported = []
    for regex, name in UNSUPPORTED_PATTERNS:
        matches = list(regex.finditer(text))
        if any(not any(match.start() < prior[1] and match.end() > prior[0] for prior in accepted) for match in matches):
            unsupported.append(name)
    return {"findings": findings, "redacted_text": "".join(chunks), "unsupported_types": unsupported, "offset_unit": "unicode_code_point", "engine_version": "privacy-regex-2", "persisted": False}


def redact(text: str) -> dict:
    result = analyze(text)
    counts: dict[str, int] = {}
    for finding in result["findings"]:
        counts[finding["label"]] = counts.get(finding["label"], 0) + 1
    matches = [{"type": label, "count": count} for label, count in counts.items()]
    return {"redacted_text": result["redacted_text"], "matches": matches, "count": len(result["findings"])}
