from __future__ import annotations

import copy
import hashlib
import os
import posixpath
import re
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"w": W_NS, "r": R_NS}
W = f"{{{W_NS}}}"
R = f"{{{R_NS}}}"




def qn(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def xml(data: bytes) -> etree._Element:
    return etree.fromstring(data)


def serialize(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def c14n_hash(elements: list[etree._Element]) -> str:
    payload = b"".join(etree.tostring(item, method="c14n") for item in elements)
    return hashlib.sha256(payload).hexdigest()


def load_zip(path: Path) -> tuple[dict[str, bytes], dict[str, ZipInfo]]:
    with ZipFile(path) as archive:
        return ({name: archive.read(name) for name in archive.namelist()},
                {name: archive.getinfo(name) for name in archive.namelist()})


def write_zip(path: Path, parts: dict[str, bytes], infos: dict[str, ZipInfo]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.stem + "_", suffix=".docx", dir=path.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with ZipFile(tmp, "w", compression=ZIP_DEFLATED) as archive:
            for name, data in parts.items():
                if name in infos:
                    old = infos[name]
                    info = ZipInfo(name, date_time=old.date_time)
                    info.compress_type = old.compress_type
                    info.comment = old.comment
                    info.extra = old.extra
                    info.internal_attr = old.internal_attr
                    info.external_attr = old.external_attr
                    info.create_system = old.create_system
                    archive.writestr(info, data)
                else:
                    archive.writestr(name, data)
        with ZipFile(tmp) as check:
            bad = check.testzip()
            if bad:
                raise RuntimeError(f"ZIP 校验失败：{bad}")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def next_rid(rels_root: etree._Element) -> str:
    nums = []
    for rel in rels_root:
        match = re.fullmatch(r"rId(\d+)", rel.get("Id", ""))
        if match:
            nums.append(int(match.group(1)))
    return f"rId{max(nums, default=0) + 1}"


def content_type_for(ct_root: etree._Element, part_name: str) -> str | None:
    query = f"./{{{CT_NS}}}Override[@PartName='/{part_name}']"
    found = ct_root.find(query)
    if found is not None:
        return found.get("ContentType")
    extension = Path(part_name).suffix.lstrip(".")
    query = f"./{{{CT_NS}}}Default[@Extension='{extension}']"
    found = ct_root.find(query)
    return found.get("ContentType") if found is not None else None


def ensure_override(ct_root: etree._Element, part_name: str, content_type: str) -> None:
    query = f"./{{{CT_NS}}}Override[@PartName='/{part_name}']"
    found = ct_root.find(query)
    if found is None:
        etree.SubElement(
            ct_root,
            qn(CT_NS, "Override"),
            PartName=f"/{part_name}",
            ContentType=content_type,
        )


def ensure_default(ct_root: etree._Element, extension: str, content_type: str) -> None:
    query = f"./{{{CT_NS}}}Default[@Extension='{extension}']"
    found = ct_root.find(query)
    if found is None:
        etree.SubElement(
            ct_root,
            qn(CT_NS, "Default"),
            Extension=extension,
            ContentType=content_type,
        )


def add_cover_styles(target_parts: dict[str, bytes], reference_parts: dict[str, bytes]) -> None:
    target = xml(target_parts["word/styles.xml"])
    reference = xml(reference_parts["word/styles.xml"])
    style_map = {"1": "RF_CoverNormal", "5": "RF_CoverTable"}

    for new_id in style_map.values():
        for old in target.xpath(f"./w:style[@w:styleId='{new_id}']", namespaces=NS):
            target.remove(old)

    for old_id, new_id in style_map.items():
        matches = reference.xpath(f"./w:style[@w:styleId='{old_id}']", namespaces=NS)
        if not matches:
            raise RuntimeError(f"参考文档缺少样式 {old_id}")
        item = copy.deepcopy(matches[0])
        item.set(W + "styleId", new_id)
        item.attrib.pop(W + "default", None)
        name = item.find("w:name", NS)
        if name is not None:
            name.set(W + "val", "RF Cover Normal" if old_id == "1" else "RF Cover Table")
        if old_id == "1":
            # The reference document has an empty paragraph default.  The target
            # document's global default adds 10 pt after each paragraph and 1.15
            # line spacing, so explicitly neutralize those inherited values for
            # cover-only paragraphs to preserve the original one-page layout.
            ppr = item.find("w:pPr", NS)
            if ppr is None:
                ppr = etree.SubElement(item, W + "pPr")
            spacing = ppr.find("w:spacing", NS)
            if spacing is None:
                spacing = etree.SubElement(ppr, W + "spacing")
            spacing.set(W + "before", "0")
            spacing.set(W + "after", "0")
            spacing.set(W + "line", "240")
            spacing.set(W + "lineRule", "auto")
        target.append(item)

    target_parts["word/styles.xml"] = serialize(target)


def apply_cover_styles(elements: list[etree._Element]) -> None:
    for element in elements:
        paragraphs = ([element] if element.tag == W + "p" else []) + element.xpath(".//w:p", namespaces=NS)
        for paragraph in paragraphs:
            ppr = paragraph.find("w:pPr", NS)
            if ppr is None:
                ppr = etree.Element(W + "pPr")
                paragraph.insert(0, ppr)
            pstyle = ppr.find("w:pStyle", NS)
            if pstyle is None:
                pstyle = etree.Element(W + "pStyle")
                ppr.insert(0, pstyle)
            pstyle.set(W + "val", "RF_CoverNormal")

        tables = ([element] if element.tag == W + "tbl" else []) + element.xpath(".//w:tbl", namespaces=NS)
        for table in tables:
            tblpr = table.find("w:tblPr", NS)
            if tblpr is None:
                tblpr = etree.Element(W + "tblPr")
                table.insert(0, tblpr)
            style = tblpr.find("w:tblStyle", NS)
            if style is None:
                style = etree.Element(W + "tblStyle")
                tblpr.insert(0, style)
            style.set(W + "val", "RF_CoverTable")


def style_cover_story_parts(parts: dict[str, bytes]) -> None:
    for name in list(parts):
        if not (
            name.startswith("word/cover_header_")
            or name.startswith("word/cover_footer_")
        ) or not name.endswith(".xml"):
            continue
        root = xml(parts[name])
        apply_cover_styles([root])
        parts[name] = serialize(root)


def resolve_part(base_part: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def relationship_part(part_name: str) -> str:
    return posixpath.join(posixpath.dirname(part_name), "_rels", posixpath.basename(part_name) + ".rels")


def import_related_part(
    ref_parts: dict[str, bytes],
    out_parts: dict[str, bytes],
    ref_ct: etree._Element,
    out_ct: etree._Element,
    source_part: str,
    destination_part: str,
) -> None:
    out_parts[destination_part] = ref_parts[source_part]
    ctype = content_type_for(ref_ct, source_part)
    if ctype:
        ensure_override(out_ct, destination_part, ctype)

    source_rels_name = relationship_part(source_part)
    if source_rels_name not in ref_parts:
        return

    rels = xml(ref_parts[source_rels_name])
    for rel in rels:
        if rel.get("TargetMode") == "External":
            continue
        source_related = resolve_part(source_part, rel.get("Target", ""))
        if source_related not in ref_parts:
            raise RuntimeError(f"参考部件关系目标不存在：{source_related}")
        extension = Path(source_related).suffix
        destination_related = posixpath.join(
            "word/media", f"cover_{Path(source_related).stem}{extension}"
        )
        suffix = 1
        while destination_related in out_parts and out_parts[destination_related] != ref_parts[source_related]:
            destination_related = posixpath.join(
                "word/media", f"cover_{Path(source_related).stem}_{suffix}{extension}"
            )
            suffix += 1
        out_parts[destination_related] = ref_parts[source_related]
        rel.set("Target", posixpath.relpath(destination_related, posixpath.dirname(destination_part)))
        ctype = content_type_for(ref_ct, source_related)
        if ctype:
            ensure_default(out_ct, extension.lstrip("."), ctype)

    out_parts[relationship_part(destination_part)] = serialize(rels)


def replace_cover(reference: Path, target: Path) -> dict[str, str]:
    ref_parts, _ = load_zip(reference)
    original_parts, original_infos = load_zip(target)
    out_parts = dict(original_parts)

    ref_doc = xml(ref_parts["word/document.xml"])
    out_doc = xml(out_parts["word/document.xml"])
    ref_body = ref_doc.find("w:body", NS)
    out_body = out_doc.find("w:body", NS)
    if ref_body is None or out_body is None:
        raise RuntimeError("文档缺少 w:body")

    ref_sect = ref_body.find("w:sectPr", NS)
    if ref_sect is None:
        raise RuntimeError("参考封面缺少节属性")

    break_index = None
    for index, element in enumerate(out_body):
        if element.xpath(".//w:br[@w:type='page']", namespaces=NS):
            break_index = index
            break
    if break_index is None:
        existing_sections = out_body.xpath("./w:p/w:pPr/w:sectPr", namespaces=NS)
        if len(existing_sections) != 1:
            raise RuntimeError("目标文档首页未找到显式分页符或既有封面分节")
        section_paragraph = existing_sections[0].getparent().getparent()
        cover_blocks = list(out_body).index(section_paragraph) + 1
        body_tail_hash = c14n_hash(list(out_body)[cover_blocks:])
        add_cover_styles(out_parts, ref_parts)
        style_cover_story_parts(out_parts)
        write_zip(target, out_parts, original_infos)
        return {
            "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "body_tail_sha256": body_tail_hash,
            "cover_blocks": str(cover_blocks),
        }

    original_tail = list(out_body)[break_index + 1:]
    before_tail_hash = c14n_hash(original_tail)
    for element in list(out_body)[:break_index + 1]:
        out_body.remove(element)

    cover_elements = [copy.deepcopy(item) for item in ref_body if item.tag != W + "sectPr"]
    apply_cover_styles(cover_elements)
    if not cover_elements or cover_elements[-1].tag != W + "p":
        cover_elements.append(etree.Element(W + "p"))
        apply_cover_styles([cover_elements[-1]])

    cover_section = copy.deepcopy(ref_sect)
    section_type = cover_section.find("w:type", NS)
    if section_type is None:
        section_type = etree.Element(W + "type")
        cover_section.insert(0, section_type)
    section_type.set(W + "val", "nextPage")

    ref_doc_rels = xml(ref_parts["word/_rels/document.xml.rels"])
    out_doc_rels = xml(out_parts["word/_rels/document.xml.rels"])
    ref_ct = xml(ref_parts["[Content_Types].xml"])
    out_ct = xml(out_parts["[Content_Types].xml"])

    ref_rel_by_id = {rel.get("Id"): rel for rel in ref_doc_rels}
    relationship_refs = cover_section.xpath("./w:headerReference | ./w:footerReference", namespaces=NS)
    for counter, reference_node in enumerate(relationship_refs, start=1):
        old_rid = reference_node.get(R + "id")
        source_rel = ref_rel_by_id.get(old_rid)
        if source_rel is None:
            raise RuntimeError(f"参考封面节关系不存在：{old_rid}")
        source_part = resolve_part("word/document.xml", source_rel.get("Target", ""))
        kind = "header" if reference_node.tag == W + "headerReference" else "footer"
        destination_part = f"word/cover_{kind}_{counter}.xml"
        import_related_part(ref_parts, out_parts, ref_ct, out_ct, source_part, destination_part)

        new_rid = next_rid(out_doc_rels)
        etree.SubElement(
            out_doc_rels,
            qn(PKG_REL_NS, "Relationship"),
            Id=new_rid,
            Type=source_rel.get("Type"),
            Target=posixpath.relpath(destination_part, "word"),
        )
        reference_node.set(R + "id", new_rid)

    last_paragraph = cover_elements[-1]
    ppr = last_paragraph.find("w:pPr", NS)
    if ppr is None:
        ppr = etree.Element(W + "pPr")
        last_paragraph.insert(0, ppr)
    old_section = ppr.find("w:sectPr", NS)
    if old_section is not None:
        ppr.remove(old_section)
    ppr.append(cover_section)

    for position, element in enumerate(cover_elements):
        out_body.insert(position, element)

    after_tail = list(out_body)[len(cover_elements):]
    after_tail_hash = c14n_hash(after_tail)
    if before_tail_hash != after_tail_hash:
        raise RuntimeError("正文结构发生变化，已中止写入")

    add_cover_styles(out_parts, ref_parts)
    style_cover_story_parts(out_parts)
    out_parts["word/document.xml"] = serialize(out_doc)
    out_parts["word/_rels/document.xml.rels"] = serialize(out_doc_rels)
    out_parts["[Content_Types].xml"] = serialize(out_ct)

    permitted_changes = {
        "word/document.xml",
        "word/_rels/document.xml.rels",
        "word/styles.xml",
        "[Content_Types].xml",
    }
    for name, data in original_parts.items():
        if name not in permitted_changes and out_parts.get(name) != data:
            raise RuntimeError(f"非封面部件被修改：{name}")

    write_zip(target, out_parts, original_infos)

    with ZipFile(target) as archive:
        final_parts = {name: archive.read(name) for name in archive.namelist()}
        final_doc = xml(final_parts["word/document.xml"])
        final_body = final_doc.find("w:body", NS)
        if final_body is None:
            raise RuntimeError("输出文档缺少正文")
        intermediate_sections = final_body.xpath("./w:p/w:pPr/w:sectPr", namespaces=NS)
        if len(intermediate_sections) != 1:
            raise RuntimeError(f"输出文档应仅有一个封面分节，实际为 {len(intermediate_sections)}")
        final_tail = list(final_body)[len(cover_elements):]
        if c14n_hash(final_tail) != before_tail_hash:
            raise RuntimeError("写入后正文结构校验失败")
        for name, data in original_parts.items():
            if name not in permitted_changes and final_parts.get(name) != data:
                raise RuntimeError(f"写入后非封面部件发生变化：{name}")

    return {
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "body_tail_sha256": before_tail_hash,
        "cover_blocks": str(len(cover_elements)),
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Replace a DOCX cover; both paths are explicit.')
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    for reference, target in [(args.reference.resolve(), args.target.resolve())]:
        result = replace_cover(reference, target)
        print(f"OK: {target}")
        for key, value in result.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
