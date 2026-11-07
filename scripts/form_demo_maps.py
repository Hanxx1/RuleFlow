"""Maps for the verified campus forms added to the offline catalogue."""

import re

from docx import Document


HASHES = {
    "stay": "99d1bc18d5d6ff2e907bbd400b5e66d2bef9466ff5d803843ecbf459a118b537",
    "defer": "bab41dabfa8e5ccd1e4e283f83131d0a9eb1d4a66e3ead4e0da3cf37f12dab4b",
    "workstudy": "c9d6ff5cc0b0b537bd75ef8fba92f81eccb111341942efc53f54a9414e8178a7",
    "resume": "1e0cfd36b787b4a82ea98e621afb44d207520a0b791a0a840351a289ab6d315f",
    "major": "c4a885c0b963afa9853d6cc2ca5ffa0b0cf1587ca3e9f9420352b3ddc7b656fa",
    "review": "8bd850e2d9fcef00cf81ced2ec853e46213ffed0abca7d1f4e24a5e502a99486",
    "exemption": "1b0dd57ef171d8ffef5371a733250af0c84428f2670bb015dde4e19d2505b3fa",
}


def slot(field):
    return "{{CW:" + field + "}}"


def put_paragraph(paragraph, value):
    run = next((run for run in paragraph.runs if run.text.strip()), None)
    if run is None:
        run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
    for old in paragraph.runs:
        old.text = value if old._r == run._r else ""


def fill_blank(paragraph, value):
    if paragraph.text.strip():
        raise ValueError(f"Expected an empty applicant paragraph, found {paragraph.text!r}")
    put_paragraph(paragraph, value)


def replace_exact(paragraph, expected, value):
    if paragraph.text != expected:
        raise ValueError(f"Expected {expected!r}, found {paragraph.text!r}")
    put_paragraph(paragraph, value)


def cell(table, row, column):
    return table.rows[row].cells[column]


def fill_cells(table, mapping):
    for row, column, field in mapping:
        fill_blank(cell(table, row, column).paragraphs[0], slot(field))


def date_slot(paragraph, field="applicationDate"):
    value, count = re.subn(r"年[\s　]+月[\s　]+日", slot(field), paragraph.text)
    if count != 1:
        raise ValueError("Unexpected applicant date placeholder")
    put_paragraph(paragraph, value)


def select_paragraph(target, text):
    matches = [p for p in target.paragraphs if text in p.text]
    if len(matches) != 1:
        raise ValueError(f"Expected one paragraph for {text!r}")
    return matches[0]


def stay(doc):
    table = doc.tables[0]
    fill_cells(table, [(0,1,"name"),(0,3,"college"),(1,1,"gender"),(2,1,"room"),
                       (2,3,"phone"),(3,1,"guardian"),(3,3,"guardianPhone")])
    fill_blank(cell(table,1,3).paragraphs[0], slot("studentId")+"　"+slot("major"))
    target = cell(table,5,0)
    fill_blank(target.paragraphs[1], slot("reason"))
    timing = select_paragraph(target, "暑假留校时间")
    if "——" not in timing.text or len(re.findall(r"年[\s　]+月[\s　]+日", timing.text)) != 2:
        raise ValueError("Unexpected stay period fields")
    put_paragraph(timing, "暑假留校时间：" + slot("start") + "——" + slot("end"))
    date_slot(select_paragraph(target, "申请人签名"))


def defer(doc):
    coordinates = [(1,3,7,11,1,4,11), (1,3,6,8,1,4,8), (2,4,7,9,2,5,9)]
    for index, (college,group,name,student,course,mode,exam) in enumerate(coordinates):
        table = doc.tables[index]
        fill_cells(table, [(0,college,"college"),(0,name,"name"),(0,student,"studentId"),(1,course,"course")])
        fill_blank(cell(table,0,group).paragraphs[0], slot("major")+" "+slot("className"))
        replace_exact(cell(table,1,mode).paragraphs[0], "主修□ 重修□ 双学位、辅修□",
                      "主修"+slot("mainMode")+" 重修"+slot("retakeMode")+" 双学位、辅修"+slot("minorMode"))
        exam_paragraphs = cell(table,1,exam).paragraphs
        replace_exact(exam_paragraphs[0], "第   周周   ", "第"+slot("examWeek")+"周 周"+slot("weekday"))
        replace_exact(exam_paragraphs[1], "上□／下□午", "上"+slot("morning")+"／下"+slot("afternoon")+"午")
        if index < 2:
            target = cell(table,2,1)
            fill_blank(target.paragraphs[0], slot("reason"))
            sign = select_paragraph(target, "申请人签名")
            value, count = re.subn(r"(电话：)\s+", r"\1"+slot("phone")+" ", sign.text)
            if count != 1:
                raise ValueError("Unexpected defer telephone placeholder")
            put_paragraph(sign,value)
            date_slot(sign)


def workstudy(doc):
    table = doc.tables[0]
    fill_cells(table, [(0,1,"name"),(0,4,"studentId"),(0,7,"college"),(1,1,"job"),(1,4,"politics"),
                       (1,7,"phone"),(3,0,"learnings"),(7,0,"suggestions")])
    fill_blank(cell(table,5,0).paragraphs[0], "见个人工作突出事迹总结附页")
    paragraphs = doc.paragraphs
    replace_exact(paragraphs[3], "示例", "")
    replace_exact(paragraphs[5], "所在部门-学号-姓名-就读学院",
                  "-".join(map(slot, ("department", "studentId", "name", "college"))))
    replace_exact(paragraphs[6], "（例如：学工部资助管理中心-1911111-张三-外国语学院）", "")
    replace_exact(paragraphs[7], "本人在担任学生助理期间XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX……（不少于200字）",
                  slot("achievement"))


def resume(doc):
    table = doc.tables[0]
    fill_cells(table, [(0,1,"name"),(0,4,"gender"),(0,6,"studentId"),(0,8,"phone"),(1,2,"address"),(1,8,"postalCode")])
    target = cell(table,2,2)
    replace_exact(target.paragraphs[0], "（如页面不够，可将详细申请附后）", slot("reason"))
    date_slot(select_paragraph(target,"签字(按手印)"))


def major(doc):
    table = doc.tables[0]
    fill_cells(table, [(0,1,"name"),(0,3,"gender"),(0,5,"applicationDate"),(1,1,"studentId"),
                       (1,5,"identity"),(2,1,"college"),(2,6,"phone"),(3,1,"targetMajor")])
    fill_blank(cell(table,2,3).paragraphs[0], slot("major")+" "+slot("className"))
    target = cell(table,4,1)
    fill_blank(target.paragraphs[0], slot("reason"))
    date_slot(target.paragraphs[-1])


def review(doc):
    table = doc.tables[0]
    fill_cells(table, [(0,1,"course"),(0,3,"courseCode"),(0,5,"assessment"),(1,1,"offeringUnit"),
                       (1,3,"teacher"),(1,5,"teacherPhone"),(2,1,"name"),(2,3,"college"),
                       (2,5,"className"),(3,1,"studentId"),(3,3,"phone")])
    replace_exact(doc.paragraphs[1], "       学年      学期                             年   月   日",
                  slot("academicYear")+" 学年 "+slot("term")+" 学期                  "+slot("applicationDate"))
    target = cell(table,4,1)
    fill_blank(target.paragraphs[0], slot("reason"))
    date_slot(select_paragraph(target,"申请人："))


def exemption(doc):
    table = doc.tables[0]
    fill_cells(table, [(0,1,"name"),(0,5,"studentId"),(0,12,"academicYear"),(1,1,"college"),
                       (1,5,"className"),(1,12,"term"),(3,2,"course"),(3,11,"courseCode"),(4,2,"credits"),
                       (4,6,"teacher"),(4,12,"hours"),(6,2,"completedCourse"),(6,11,"completedCode"),
                       (7,2,"completedCredits"),(7,6,"completedTeacher"),(7,12,"completedGrade")])
    options = cell(table,2,1).paragraphs
    for index, (text, field) in enumerate((("年级异动","yearChange"),("专业异动","majorChange"),("因病","illness"))):
        if options[index].text.strip() != "□  "+text:
            raise ValueError("Unexpected course exemption reason options")
        put_paragraph(options[index],slot(field)+"  "+text)
    if options[3].text.strip() != "其他":
        raise ValueError("Unexpected other reason placeholder")
    put_paragraph(options[3],"其他 "+slot("otherReason"))
    target = cell(table,5,1)
    fill_blank(target.paragraphs[1],slot("reason"))
    date_slot(select_paragraph(target,"申请人："))


MAPPERS = {"stay":stay, "defer":defer, "workstudy":workstudy, "resume":resume,
           "major":major, "review":review, "exemption":exemption}


def prepare_additional(key, source, output):
    document = Document(source)
    MAPPERS[key](document)
    document.save(output / (key+".docx"))
