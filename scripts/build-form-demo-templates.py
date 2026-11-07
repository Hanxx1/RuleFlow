"""Prepare verified public school templates for offline demonstration."""

import argparse
from base64 import b64encode
from hashlib import sha256
import json
from pathlib import Path
import re
from shutil import copyfile

from docx import Document
from docx.shared import Pt
from PIL import Image, ImageDraw

from form_demo_maps import HASHES, prepare_additional


OFFICIAL = {
    "scholarship": "f104c848d9a31c2f1eeacc86e98b1f1bd6f2c413848975acdc4b717eacda12fd",
    "leave": "d46c5a39ce1ca7208e4da627159253a279e6439bbaf033b82fdc3d9d682505c2",
    "proof": "430f8ba13773db00a3533010857c9f26e76e96683851b6bebdd10e3b167770b3",
    "photo": "b116c172005bae42da1b8371e6209e641bccd3317f4fa92de8676791b52367b5",
    **HASHES,
}


def slot(field):
    return "{{CW:" + field + "}}"


def put_blank_cell(table, row, column, field):
    paragraph = table.rows[row].cells[column].paragraphs[0]
    run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
    if paragraph.text.strip():
        raise ValueError(f"Expected a blank target for {field}")
    run.text = slot(field)


def replace_blanks(run, pattern, fields, padding=""):
    if len(re.findall(pattern, run.text)) != len(fields):
        raise ValueError(f"Unexpected blank positions for {fields}")
    markers = iter(map(slot, fields))
    run.text = re.sub(pattern, lambda _: padding + next(markers) + padding, run.text)


def leave_template(source, output):
    document = Document(source)
    # The school issues two copies, one for the faculty and one for the teacher.
    for start in (2, 14):
        paragraphs = document.paragraphs[start:start + 5]
        replace_blanks(paragraphs[0].runs[0], r"_{3,}", ("course", "teacher"))
        intro = paragraphs[1].runs
        intro[1].text, intro[3].text, intro[5].text = map(slot, ("major", "className", "reason"))
        replace_blanks(intro[4], r"_{3,}", ("name",))
        timing = paragraphs[2].runs
        timing[0].text = ""
        replace_blanks(
            timing[1], r"_{3,}年_{3,}月_{3,}日|_{3,}",
            ("start", "startPeriod", "end", "endPeriod", "days", "periodCount"),
        )
        replace_blanks(paragraphs[3].runs[0], r" {3,}", ("name", "phone", "studentId"), padding=" ")
        guardian = paragraphs[4].runs
        replace_blanks(guardian[0], r" {3,}", ("guardian", "guardianPhone"), padding=" ")
        for index, field in ((1, "awareYes"), (3, "awareNo")):
            guardian[index].text = slot(field)
            guardian[index].font.name = "Segoe UI Symbol"
    # Keep both filled copies on one page by compacting only blank separators.
    for paragraph in document.paragraphs[8:12]:
        if paragraph.text.strip():
            raise ValueError("Unexpected text between the two leave copies")
        paragraph.paragraph_format.line_spacing = Pt(6)
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
    document.save(output / "leave.docx")


def proof_template(source, output):
    document = Document(source)
    table = document.tables[0]
    mapping = {
        "name": (0, 1), "gender": (0, 5), "identity": (0, 10), "hometown": (1, 1),
        "ethnicity": (1, 5), "phone": (1, 10), "address": (2, 3), "start": (3, 2),
        "end": (3, 8), "degree": (3, 12), "major": (4, 2), "certificate": (4, 11),
        "degreeCertificate": (5, 11),
    }
    for field, (row, column) in mapping.items():
        put_blank_cell(table, row, column, field)
    reason = table.rows[6].cells[3]
    reason.paragraphs[0].add_run(slot("reason"))
    date = next(p for p in reason.paragraphs if "申请时间" in p.text)
    date_run = next(run for run in date.runs if run.text == "年   月   日")
    date_run.text = slot("applicationDate")
    document.save(output / "proof.docx")


def photo_template(source, output):
    image = Image.new("RGB", (250, 350), "#d6ebff")
    draw = ImageDraw.Draw(image)
    draw.ellipse((83, 60, 167, 144), fill="#305680")
    draw.rounded_rectangle((52, 150, 198, 290), radius=54, fill="#305680")
    draw.text((107, 311), "DEMO", fill="#234361")
    image.save(output / "avatar.png")

    document = Document(source)
    table = document.tables[0]
    mapping = {
        "name": (0, 1), "studentId": (1, 1), "gender": (2, 1), "ethnicity": (2, 3),
        "phone": (3, 1), "residentialCollege": (4, 1), "identity": (5, 1), "address": (6, 1),
        "railRoute": (7, 1),
    }
    for field, (row, column) in mapping.items():
        put_blank_cell(table, row, column, field)
    choices = table.rows[4].cells[5].paragraphs[0]
    if not choices.text.startswith("是□"):
        raise ValueError("Unexpected replacement history options")
    for run in choices.runs:
        run.text = ""
    choices.add_run("是" + slot("previousYes") + "　否" + slot("previousNo"))
    reason = table.rows[8].cells[0]
    reason.paragraphs[1].add_run(slot("reason"))
    date = reason.paragraphs[5]
    visible_date = re.sub(r"年[\s　]+月[\s　]+日", slot("applicationDate"), date.text)
    if visible_date == date.text:
        raise ValueError("Unexpected date slot")
    date.runs[0].text = visible_date
    for run in date.runs[1:]:
        run.text = ""
    document.save(output / "photo.docx")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in OFFICIAL:
        parser.add_argument(key, type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    for key, expected in OFFICIAL.items():
        path = getattr(args, key)
        suffix = "xlsx" if key == "scholarship" else "docx"
        if path.resolve() == (args.output / f"{key}.{suffix}").resolve():
            raise ValueError(f"The output directory would overwrite {key}")
        actual = sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Unexpected {key} template SHA-256: {actual}")
        print(f"{key}: {actual}")
    args.output.mkdir(parents=True, exist_ok=True)
    copyfile(args.scholarship, args.output / "scholarship.xlsx")
    leave_template(args.leave, args.output)
    proof_template(args.proof, args.output)
    photo_template(args.photo, args.output)
    for key in HASHES:
        prepare_additional(key, getattr(args, key), args.output)
    assets = ("scholarship.xlsx", "proof.docx", "leave.docx", "photo.docx", "avatar.png", *(key+".docx" for key in HASHES))
    data = {name: b64encode((args.output / name).read_bytes()).decode("ascii") for name in assets}
    (args.output / "templateData.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
