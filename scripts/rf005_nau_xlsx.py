"""RF-005: write synthetic values into the verified NAU XLSX, then check fidelity."""

import argparse
from hashlib import sha256
from pathlib import Path
import re
from xml.sax.saxutils import escape
from zipfile import ZipFile

from openpyxl import load_workbook


TEMPLATE_HASH = "f104c848d9a31c2f1eeacc86e98b1f1bd6f2c413848975acdc4b717eacda12fd"
SHEET = "xl/worksheets/sheet1.xml"
REASON = (
    "本人在本学年按照课程要求完成学习任务，主动复习重点内容，并及时整理课堂笔记。"
    "在小组作业中，我与同学分工协作，共同核对资料并完善展示。"
    "在课外学习中，我尝试把课堂方法用于练习，定期回顾错误和不足。"
    "今后我会继续加强专业学习，认真参与集体活动，主动听取老师和同学的意见，"
    "把改进计划落实到日常学习和生活中，努力提升自己的综合能力。"
)
VALUES = {"A9": "林示例", "J9": "00001234", "V9": "示例奖项·甲&乙", "Y9": None, "AG9": REASON}


def digest(data):
    return sha256(data).hexdigest()


def edit_sheet(xml, values):
    if values.keys() != VALUES.keys():
        raise ValueError("Unexpected target cells for this template")
    reason = values["AG9"]
    if not isinstance(reason, str) or not 100 <= len(reason) <= 200:
        raise ValueError("The visible template requires a reason of 100–200 characters")

    for address, value in values.items():
        blank = f'<c r="{address}" s="50"/>'.encode()
        if xml.count(blank) != 1:
            raise ValueError(f"{address} is missing or is not the expected blank cell")
        if value is not None:
            text = escape(value).encode()
            cell = blank[:-2] + b' t="inlineStr"><is><t xml:space="preserve">' + text + b"</t></is></c>"
            xml = xml.replace(blank, cell, 1)
    return xml


def verify(source, output):
    with ZipFile(source) as original, ZipFile(output) as exported:
        assert exported.testzip() is None
        assert original.namelist() == exported.namelist()
        for entry in original.namelist():
            before, after = original.read(entry), exported.read(entry)
            if entry == SHEET:
                for address, value in VALUES.items():
                    if value is None:
                        continue
                    pattern = rb'<c r="' + address.encode() + rb'" s="50" t="inlineStr">.*?</c>'
                    after, count = re.subn(pattern, f'<c r="{address}" s="50"/>'.encode(), after)
                    assert count == 1, address
            assert before == after, entry
    print("PASS: only four allowlisted cells changed; protected cells and all other package data match")

    workbook = load_workbook(output)
    try:
        sheet = workbook["申请审批表"]
        for address, expected in VALUES.items():
            assert sheet[address].value == expected, address
        assert sheet["J9"].data_type == "s"
        assert workbook["代码表"].sheet_state == "hidden"
    finally:
        workbook.close()
    print("PASS: read-back, leading zero, blank, XML special character and complete reason")


def check_rejection(xml):
    cases = [
        ({**VALUES, "AI9": "禁止写入"}, "target cells"),
        ({**VALUES, "AG9": "超" * 201}, "100–200"),
        ({**VALUES, "AG9": "短" * 99}, "100–200"),
    ]
    for values, expected in cases:
        try:
            edit_sheet(xml, values)
        except ValueError as error:
            assert expected in str(error), error
        else:
            raise AssertionError(f"Expected rejection: {expected}")
    print("PASS: protected address and reason lengths 99 / 201 rejected")


def run(source, output):
    with source.open("rb") as original:
        if digest(original.read()) != TEMPLATE_HASH:
            raise ValueError("Template SHA-256 does not match the RF-004 original")
        original.seek(0)
        with ZipFile(original) as package:
            xml = package.read(SHEET)
            check_rejection(xml)
            edited = edit_sheet(xml, VALUES)
            # Exclusive create also prevents overwriting the input or a previous export.
            with output.open("xb") as result, ZipFile(result, "w") as exported:
                for entry in package.infolist():
                    exported.writestr(entry, edited if entry.filename == SHEET else package.read(entry))
    verify(source, output)
    assert digest(source.read_bytes()) == TEMPLATE_HASH
    print("PASS: original SHA-256 unchanged")
    print(f"Reason length: {len(REASON)}. Output SHA-256: {digest(output.read_bytes())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    run(arguments.source, arguments.output)
