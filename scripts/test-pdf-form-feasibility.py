"""RF-037 local feasibility checks against three pinned, publicly issued PDFs."""
import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path

import pymupdf
from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, DictionaryObject, NameObject


SAMPLES = {
    "dartmouth-2.pdf": "9314feca3e5606db87a6209e95e3b8e0ed028cecbbdb94a6d76a64d17e466115",
    "xafu.pdf": "b5fb96112f709bbef7b6b487fa8a96cd36f55eac88a537f07644d49d62ad1fe1",
    "gdpt.pdf": "69d17e66112b2b3adbf0ef2d20e22dee89b6e35352d2fd990b39f1f561d67794",
}
APPLICANT_FIELDS = {"Name", "Net ID", "Class Year"}


def verify_originals(directory):
    for name, fingerprint in SAMPLES.items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == fingerprint, name


def widget_layout(document):
    return [
        [(item.field_name, item.field_type, tuple(item.rect)) for item in page.widgets()]
        for page in document
    ]


def field_values(reader):
    return {name: field.get("/V") for name, field in reader.get_fields().items()}


def applicant_writer(reader, values):
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF")
    form = reader.root_object.get("/AcroForm")
    fields = reader.get_fields() or {}
    if not form or not fields or "/XFA" in form.get_object():
        raise ValueError("No supported AcroForm")
    if reader.root_object.get("/Perms") or any(
        field.get("/FT") == "/Sig" and field.get("/V") for field in fields.values()
    ):
        raise ValueError("Signature or certification protection")
    if not values.keys() <= APPLICANT_FIELDS:
        raise ValueError("Only reviewed applicant fields can be written")
    for name in values:
        field = fields[name]
        if field.get("/FT") != "/Tx" or field.get("/Ff", 0) & 1:
            raise ValueError(f"Unsupported or read-only field: {name}")
        widgets = [
            ref.get_object()
            for page in reader.pages
            for ref in page.get("/Annots", [])
            if ref.get_object().get("/Subtype") == "/Widget"
            and ref.get_object().get("/T") == name
        ]
        if len(widgets) != 1 or widgets[0].get("/Ff", 0) & 1:
            raise ValueError(f"Expected one writable direct widget: {name}")
    writer = PdfWriter(clone_from=reader)
    writer.update_page_form_field_values(None, values, auto_regenerate=False)
    return writer


def expect_rejected(reader, values, message):
    try:
        applicant_writer(reader, values)
    except ValueError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("Invalid write was accepted")


def interactive_probe(original, output):
    values = {"Name": "Cheng Lin", "Net ID": "f031z42", "Class Year": "2027"}
    reader = PdfReader(original)
    expect_rejected(reader, {"Student Signature": "Cheng Lin"}, "reviewed applicant")
    # Synthetic protection marker only. The public template is unsigned.
    protected = PdfWriter(clone_from=reader)
    protected.root_object[NameObject("/Perms")] = DictionaryObject({
        NameObject("/DocMDP"): DictionaryObject(),
    })
    content = BytesIO()
    protected.write(content)
    expect_rejected(PdfReader(content), values, "certification protection")

    copy = output / "dartmouth-withdrawal-applicant-fields.pdf"
    applicant_writer(reader, values).write(copy)
    checked = PdfReader(copy)
    assert len(checked.pages) == len(reader.pages)
    assert field_values(checked) == (field_values(reader) | values)
    assert field_values(checked)["Student Signature"] is None
    assert checked.root_object["/AcroForm"]["/NeedAppearances"] == BooleanObject(False)
    seen = set()
    for before, after in zip(reader.pages, checked.pages, strict=True):
        assert before.get_contents().get_data() == after.get_contents().get_data()
        for ref in after.get("/Annots", []):
            widget = ref.get_object()
            name = widget.get("/T")
            if name in values:
                assert widget["/V"] == values[name]
                assert widget["/AP"]["/N"].get_data()
                seen.add(name)
    assert seen == values.keys()
    with pymupdf.open(original) as before, pymupdf.open(copy) as after:
        assert widget_layout(before) == widget_layout(after)
        for doc, label in ((before, "original"), (after, "filled")):
            doc[0].get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4)).save(
                output / f"dartmouth-{label}.png"
            )
    return {"type": "acroform", "widget_count": len(checked.get_fields()), "written": list(values),
            "protected": "Student Signature", "original_page_content_unchanged": True}


def ordinary_probe(original, output):
    assert not PdfReader(original).get_fields()
    with pymupdf.open(original) as document:
        page = document[1]
        assert not list(page.widgets())
        assert "学生证补办申请表" in page.get_text()
        labels = {}
        for label in ("姓名", "学号", "签字"):
            positions = page.search_for(label)
            assert len(positions) == (2 if label == "签字" else 1)
            labels[label] = [list(box) for box in positions]
        page.get_pixmap(matrix=pymupdf.Matrix(1.2, 1.2)).save(output / "xafu-form-page.png")
    return {"type": "ordinary", "page": 2, "label_boxes_pt": labels, "needs_review": True,
            "writeback": False}


def raster_probe(original):
    assert not PdfReader(original).get_fields()
    with pymupdf.open(original) as document:
        page = document[6]
        assert not list(page.widgets())
        assert "附件" in page.get_text()
        images = page.get_image_info()
        assert len(images) == 1
        bounds = pymupdf.Rect(images[0]["bbox"])
        fraction = (bounds & page.rect).get_area() / page.rect.get_area()
        assert fraction > 0.40
        assert page.get_text(clip=bounds).strip() == "广东职业技术学院"
        assert not page.search_for("学号")
    return {"type": "raster_form_in_mixed_pdf", "page": 7, "image_area_fraction": fraction,
            "form_text_extractable": False, "writeback": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    assert args.samples.resolve() != args.output.resolve()
    verify_originals(args.samples)
    args.output.mkdir(parents=True, exist_ok=True)
    results = {
        "interactive": interactive_probe(args.samples / "dartmouth-2.pdf", args.output),
        "ordinary": ordinary_probe(args.samples / "xafu.pdf", args.output),
        "raster": raster_probe(args.samples / "gdpt.pdf"),
    }
    verify_originals(args.samples)
    result = json.dumps(results, ensure_ascii=False, indent=2)
    (args.output / "results.json").write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
