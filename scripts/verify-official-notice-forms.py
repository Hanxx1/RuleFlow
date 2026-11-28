"""Read back the two real-notice test downloads and compare the rest of each original."""
from argparse import ArgumentParser
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from lxml import etree
from openpyxl import load_workbook


WORKSHEET_FIELDS = {
    "B13": "程若宁", "C13": "韩国", "D13": "首尔市立大学寒假会计研修",
    "F13": "2019.01.07–2019.02.01", "G13": "经济管理学院", "H13": "会计学",
    "I13": "0000174206", "J13": "00000019980620000X", "K13": "0000000000000428371",
    "L13": "00000000802", "M13": "ruoning.cheng@example.com", "N13": "2000 元",
}
WORD_FIELDS = {
    (1, 2): "首尔市立大学（韩国）", (2, 2): "未申报排名加成",
    (4, 2): "程若宁", (4, 4): "女", (5, 2): "1998-06-20", (5, 4): "汉族",
    (6, 2): "0000174206", (6, 4): "2017级", (8, 2): "会计学", (8, 4): "88.6",
    (9, 2): "陕西省西安市长安区校内宿舍", (9, 4): "710127",
    (10, 2): "00000000802", (10, 4): "00000000803",
    (11, 2): "ruoning.cheng@example.com", (11, 4): "ruoning_campus",
    (12, 2): "2018年院级优秀志愿者", (12, 4): "摄影、篮球",
    (13, 4): "2018-10-20", (14, 4): "雅思 6.5",
}


def unchanged_parts(original, result, edited_part):
    with ZipFile(original) as left, ZipFile(result) as right:
        assert left.namelist() == right.namelist()
        assert right.testzip() is None
        assert [name for name in left.namelist() if left.read(name) != right.read(name)] == [edited_part]


def verify_xlsx(original, result):
    unchanged_parts(original, result, "xl/worksheets/sheet1.xml")
    source = load_workbook(original).active
    target = load_workbook(result).active
    assert set(source.merged_cells.ranges) == set(target.merged_cells.ranges)
    assert (source.max_row, source.max_column) == (target.max_row, target.max_column)
    for original_row, output_row in zip(source.iter_rows(), target.iter_rows(), strict=True):
        for before, after in zip(original_row, output_row, strict=True):
            assert before.coordinate == after.coordinate and before.style_id == after.style_id
            if before.coordinate in WORKSHEET_FIELDS:
                assert before.value is None and after.data_type == "s"
                assert after.value == WORKSHEET_FIELDS[before.coordinate], before.coordinate
            else:
                assert before.value == after.value and before.data_type == after.data_type, before.coordinate
    print("PASS XLSX entered 12 text cells in short-term row only; all examples, notes and styles preserved")


def canonical_status(element):
    return etree.tostring(element, method="c14n", exclusive=True)


def verify_docx(original, result):
    unchanged_parts(original, result, "word/document.xml")
    source = Document(original)
    target = Document(result)
    assert len(source.tables) == len(target.tables) == 1
    assert [p.text for p in source.paragraphs] == [p.text for p in target.paragraphs]
    original_rows = source.tables[0]._tbl.tr_lst
    output_rows = target.tables[0]._tbl.tr_lst
    for row, (left, right) in enumerate(zip(original_rows, output_rows, strict=True), 1):
        for column, (before, after) in enumerate(zip(left.tc_lst, right.tc_lst, strict=True), 1):
            assert canonical_status(before.tcPr) == canonical_status(after.tcPr)
            expected = WORD_FIELDS.get((row, column))
            if expected is None:
                assert canonical_status(before) == canonical_status(after), (row, column)
            else:
                assert "".join(before.xpath(".//w:t/text()")).strip() == ""
                assert "".join(after.xpath(".//w:t/text()")) == expected, (row, column)
    print("PASS DOCX entered 20 reviewed text cells; signature, school review and other original slots preserved")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("exports", type=Path)
    args = parser.parse_args()
    for pattern, verify in (("附件2*.xlsx", verify_xlsx), ("附件3*.docx", verify_docx)):
        result, = args.exports.glob(pattern)
        verify(args.samples / result.name, result)


if __name__ == "__main__":
    main()
