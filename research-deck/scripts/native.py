"""Inspect and patch a native PPTX without round-tripping unrelated parts."""

import posixpath
from copy import copy
from shutil import copyfileobj
from zipfile import ZipFile

from lxml import etree as E

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS = {"p": P, "a": A, "r": R, "c": C}


def query(root, path):
    return root.xpath(path, namespaces=NS)


def ordered_parts(z):
    root = E.fromstring(z.read("ppt/presentation.xml"))
    rel = E.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
    parts = {
        el.get("Id"): posixpath.normpath(
            posixpath.join("ppt", el.get("Target"))
        ).lstrip("/")
        for el in rel
        if el.get("TargetMode") != "External"
    }
    return [parts[key] for key in query(root, "./p:sldIdLst/p:sldId/@r:id")]


def shapes(slide):
    tree = query(slide, "./p:cSld/p:spTree")[0]
    return query(tree, ".//p:sp|.//p:graphicFrame|.//p:pic")


def identity(shape):
    return query(shape, "./*/p:cNvPr")[0]


def paragraphs(body):
    return query(body, "./a:p")


def content(paragraph):
    return "".join(query(paragraph, "./a:r/a:t/text()|./a:fld/a:t/text()"))


def related_parts(z, part):
    folder, file = posixpath.split(part)
    relfile = posixpath.join(folder, "_rels", file + ".rels")
    if relfile not in z.namelist():
        return {}
    links = E.fromstring(z.read(relfile))
    return {
        r.get("Id"): (
            r.get("Type").rsplit("/", 1)[-1],
            posixpath.normpath(posixpath.join(folder, r.get("Target"))).lstrip("/"),
        )
        for r in links
        if r.get("TargetMode") != "External"
    }


def chart_inventory(z, part):
    root = E.fromstring(z.read(part))
    series = []
    for s in query(root, ".//c:plotArea/*/c:ser"):
        names = query(s, "./c:tx//c:v/text()")
        item = {"name": names[0] if names else ""}
        for field, element in (
            ("categories", "cat"),
            ("values", "val"),
            ("x", "xVal"),
            ("y", "yVal"),
        ):
            pts = query(
                s,
                "./c:"
                + element
                + "//*[self::c:strCache or self::c:numCache or self::c:strLit or self::c:numLit]/c:pt",
            )
            if pts:
                item[field] = [
                    {
                        "index": int(pt.get("idx")),
                        "value": "".join(query(pt, "./c:v/text()")),
                    }
                    for pt in pts
                ]
        series.append(item)
    return series


def inventory(file):
    output = []
    with ZipFile(file) as z:
        for index, part in enumerate(ordered_parts(z), 1):
            slide = E.fromstring(z.read(part))
            related = related_parts(z, part)
            objects = []
            for sh in shapes(slide):
                obj = identity(sh)
                record = {"id": int(obj.get("id")), "name": obj.get("name", "")}
                texts = query(sh, "./p:txBody/a:p")
                tables = query(sh, ".//a:tbl")
                if texts:
                    record.update(kind="text", paragraphs=[content(p) for p in texts])
                elif tables:
                    rows = query(tables[0], "./a:tr")
                    record.update(
                        kind="table",
                        cells=[
                            [
                                "\n".join(
                                    content(p) for p in query(c, "./a:txBody/a:p")
                                )
                                for c in query(row, "./a:tc")
                            ]
                            for row in rows
                        ],
                    )
                elif query(sh, ".//c:chart"):
                    record["kind"] = "chart"
                    rel_id = query(sh, ".//c:chart/@r:id")[0]
                    if rel_id in related:
                        record["series"] = chart_inventory(z, related[rel_id][1])
                elif sh.tag == "{" + P + "}pic":
                    record["kind"] = "picture"
                    record["alt"] = obj.get("descr", "")
                else:
                    continue
                objects.append(record)
            note_text = []
            for kind, target in related.values():
                if kind == "notesSlide":
                    note = E.fromstring(z.read(target))
                    note_text = [
                        content(p)
                        for p in query(
                            note,
                            './/p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]/p:txBody/a:p',
                        )
                    ]
            output.append(
                {"slide": index, "objects": objects, "notes": "\n".join(note_text)}
            )
    return output


def at(items, index):
    if type(index) is not int or not 0 <= index < len(items):
        raise ValueError(f"索引 {index} 超出范围")
    return items[index]


def patch_slide(root, edit):
    match = [s for s in shapes(root) if identity(s).get("id") == str(edit["id"])]
    if len(match) != 1:
        raise ValueError(f"无法唯一定位对象 {edit['id']}")
    sh = match[0]
    if "cell" in edit:
        r, c = edit["cell"]
        table = at(query(sh, ".//a:tbl"), 0)
        row = at(query(table, "./a:tr"), r)
        cell = at(query(row, "./a:tc"), c)
        bodies = query(cell, "./a:txBody")
    else:
        bodies = query(sh, "./p:txBody")
    para = at(paragraphs(at(bodies, 0)), edit.get("paragraph", 0))
    old = content(para)
    if old != edit["expect"]:
        raise ValueError(f"对象 {edit['id']} 的原文与 expect 不一致")
    if query(para, "./a:fld|./a:br|./*[local-name()='m']") or any(
        c in edit["text"] for c in "\r\n"
    ):
        raise ValueError("模板编辑只替换单段纯文本，请分段指定")
    runs = query(para, "./a:r/a:t")
    if not runs:
        run = E.Element("{" + A + "}r")
        end = query(para, "./a:endParaRPr")
        para.insert(para.index(end[0]) if end else len(para), run)
        runs = [E.SubElement(run, "{" + A + "}t")]
    runs[0].text = edit["text"]
    for t in runs[1:]:
        t.text = ""


def fill(source, edits, dest):
    if not isinstance(edits, list) or not edits:
        raise ValueError("edits 需要非空数组")
    with ZipFile(source) as z:
        parts = ordered_parts(z)
        changed = {}
        seen = set()
        for edit in edits:
            if (
                type(edit.get("id")) is not int
                or type(edit.get("text")) is not str
                or type(edit.get("expect")) is not str
            ):
                raise ValueError("编辑项需要整数 id 和字符串 expect、text")
            if set(edit) - {"slide", "id", "cell", "paragraph", "expect", "text"}:
                raise ValueError("编辑项包含未知字段")
            n = edit["slide"]
            if type(n) is not int or not 1 <= n <= len(parts):
                raise ValueError(f"页码 {n} 无效")
            key = (n, edit["id"], tuple(edit.get("cell", [])), edit.get("paragraph", 0))
            if key in seen:
                raise ValueError(f"重复修改目标 {key}")
            seen.add(key)
            part = parts[n - 1]
            if part not in changed:
                changed[part] = E.fromstring(z.read(part))
            patch_slide(changed[part], edit)
        with ZipFile(dest, "w") as out:
            out.comment = z.comment
            for info in z.infolist():
                # Stream large embedded videos, preserving their uncompressed content.
                if info.filename in changed:
                    out.writestr(
                        copy(info),
                        E.tostring(
                            changed[info.filename],
                            encoding="UTF-8",
                            xml_declaration=True,
                            standalone=True,
                        ),
                    )
                else:
                    with (
                        z.open(info) as reader,
                        out.open(
                            copy(info), "w", force_zip64=info.file_size >= 2**31
                        ) as writer,
                    ):
                        copyfileobj(reader, writer, 1024 * 1024)
