"""Compare editable content with a fresh build and inspect the projected pages."""

import hashlib
import io
import json
import unicodedata
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal, localcontext
from zipfile import ZipFile

from lxml import etree
from PIL import Image
from native import inventory, ordered_parts, query, related_parts
from pdf_api import fitz
from render import Deck


def compact(value):
    return "".join(unicodedata.normalize("NFKC", value).split())


def contents(page):
    fields = {"text": [], "table": [], "chart": [], "notes": [page["notes"]]}
    for obj in page["objects"]:
        kind = obj["kind"]
        if kind == "text":
            fields[kind].extend(line for line in obj["paragraphs"] if line.strip())
        elif kind in ("table", "chart"):
            fields[kind].append(
                json.dumps(
                    obj.get("cells" if kind == "table" else "series"),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
    return {key: Counter(items) for key, items in fields.items()}


def projected_strings(page):
    for obj in page["objects"]:
        if obj["kind"] == "text":
            yield from obj["paragraphs"]
        elif obj["kind"] == "table":
            for row in obj["cells"]:
                yield from row


def data_marks(package, part):
    root = etree.fromstring(package.read(part))
    marks = Counter()
    for shape in query(root, "./p:cSld/p:spTree/p:sp"):
        name = query(shape, "./p:nvSpPr/p:cNvPr/@name")[0]
        if " · " not in name:
            continue
        transform = query(shape, "./p:spPr/a:xfrm/*")
        marks[
            (
                name,
                tuple(tuple(sorted(el.attrib.items())) for el in transform),
                tuple(query(shape, "./p:spPr/a:solidFill/a:srgbClr/@val")),
            )
        ] += 1
    return marks


def blends_into_background(span, rect, raster, scale):
    """Flag near-identical ink and surrounding pixels, as a visual review hint."""
    ink = tuple(span["color"] >> shift & 255 for shift in (16, 8, 0))
    samples = []
    for fraction in (0.05, 0.25, 0.50, 0.75, 0.95):
        x = int((rect.x0 + rect.width * fraction) * scale) - raster.x
        for y in (
            int(rect.y0 * scale) - raster.y - 1,
            int(rect.y1 * scale) - raster.y + 1,
        ):
            if 0 <= x < raster.width and 0 <= y < raster.height:
                samples.append(raster.pixel(x, y))
    return len(samples) >= 5 and sum(
        max(abs(a - b) for a, b in zip(ink, pixel)) <= 22 for pixel in samples
    ) >= 0.8 * len(samples)


def projection_issues(page):
    data = page.get_text(
        "dict",
        clip=fitz.INFINITE_RECT(),
        flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES,
    )
    scale = min(1, 1100 / max(page.rect.width, page.rect.height))
    raster = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False, annots=False
    )
    lines, faint, fonts = [], [], set()
    for block_id, block in enumerate(data["blocks"]):
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"])
            rect = fitz.Rect(line["bbox"]) * page.rotation_matrix
            if abs(rect) and text.strip():
                lines.append((block_id, rect, text))
            for span in line["spans"]:
                if span["text"].strip():
                    fonts.add(span["font"])
                if len(compact(span["text"])) >= 2 and blends_into_background(
                    span, fitz.Rect(span["bbox"]) * page.rotation_matrix, raster, scale
                ):
                    faint.append(span["text"])
    canvas = page.rect + (-1.5, -1.5, 1.5, 1.5)
    outside = [text for _, rect, text in lines if not canvas.contains(rect)]
    overlaps = []
    active = []
    for block, rect, text in sorted(lines, key=lambda line: line[1].y0):
        active = [(b, r, t) for b, r, t in active if r.y1 > rect.y0]
        for other_block, other, other_text in active:
            if block == other_block or text == other_text:
                continue
            overlap = abs(rect & other)
            if overlap > 0.55 * min(abs(rect), abs(other)):
                overlaps.append(f"{other_text[:45]} / {text[:45]}")
        active.append((block, rect, text))
    issues = []
    if faint:
        issues.append(("possible_low_contrast", faint[:3]))
    if outside:
        issues.append(("text_outside_canvas", outside[:3]))
    if overlaps:
        issues.append(("possible_text_overlap", overlaps[:3]))
    return lines, issues, fonts


def video_parts(package, part):
    slide = etree.fromstring(package.read(part))
    links = related_parts(package, part)
    result = []
    for pic in query(slide, ".//p:pic[.//a:videoFile]"):
        for rid in query(pic, ".//a:videoFile/@r:link|.//a:blip/@r:embed"):
            target = links.get(rid)
            if target is None or target[1] not in package.namelist():
                result.append(None)
            else:
                info = package.getinfo(target[1])
                result.append((target[0], info.file_size, info.CRC))
    return result


def evidence_pictures(package, part, layout, cache):
    """Compare pixels and source crop independently of PNG encoding and ZIP part names."""
    slide = etree.fromstring(package.read(part))
    links = related_parts(package, part)
    result = Counter()
    for pic in query(slide, "./p:cSld/p:spTree/p:pic"):
        rid = query(pic, "./p:blipFill/a:blip/@r:embed")
        target = links.get(rid[0]) if rid else None
        key = target[1] if target else None
        if key not in cache:
            if key is None or key not in package.namelist():
                cache[key] = None
            else:
                blob = package.read(key)
                try:
                    with Image.open(io.BytesIO(blob)) as image:
                        pixels = image.convert("RGBA")
                        cache[key] = (pixels.size, hashlib.sha256(pixels.tobytes()).digest())
                except OSError:
                    # A replacement can be a vector format without a Pillow decoder.
                    cache[key] = ("encoded", hashlib.sha256(blob).digest())
        crop = query(pic, "./p:blipFill/a:srcRect")
        bounds = tuple(int(crop[0].get(k, 0)) if crop else 0 for k in ("l", "t", "r", "b"))
        placement = ()
        if layout in ("detail", "evidence_pair", "condition_comparison", "sequence"):
            placement = tuple(tuple(sorted(el.attrib.items())) for el in query(pic, "./p:spPr/a:xfrm/*"))
        alt = tuple(query(pic, "./p:nvPicPr/p:cNvPr/@descr"))
        result[(cache[key], alt, bounds, placement)] += 1
    if layout == "detail":
        for frame in query(slide, './p:cSld/p:spTree/p:sp[p:nvSpPr/p:cNvPr[@name="Detail region"]]'):
            transform = query(frame, "./p:spPr/a:xfrm/*")
            result[("frame", tuple(tuple(sorted(el.attrib.items())) for el in transform))] += 1
    return result


def handoff_cells(package, part):
    slide = etree.fromstring(package.read(part))
    cells = []
    for shape in query(slide, './p:cSld/p:spTree/p:sp[starts-with(p:nvSpPr/p:cNvPr/@name,"Handoff ")]'):
        position = query(shape, "./p:spPr/a:xfrm/a:off")[0]
        value = "".join(query(shape, "./p:txBody/a:p/a:r/a:t/text()"))
        cells.append((int(position.get("x")), int(position.get("y")), value))
    cells.sort()
    # Read the three columns top to bottom; small per-cell nudges preserve the association.
    rows = max(1, (len(cells) + 2) // 3)
    return [
        tuple(v for _, _, v in sorted(cells[i:i + rows], key=lambda cell: cell[1]))
        for i in range(0, len(cells), rows)
    ]


def bibliography_links(package, part):
    folder, filename = part.rsplit("/", 1)
    rels = etree.fromstring(package.read(f"{folder}/_rels/{filename}.rels"))
    urls = {r.get("Id"): r.get("Target") for r in rels
            if r.get("TargetMode") == "External" and r.get("Type", "").endswith("/hyperlink")}
    slide = etree.fromstring(package.read(part))
    result = []
    for shape in query(slide, './/p:sp[p:nvSpPr/p:cNvPr[@name="Reference title"]]'):
        title = "".join(query(shape, ".//a:t/text()"))
        links = query(shape, "./p:nvSpPr/p:cNvPr/a:hlinkClick/@r:id")
        result.append((title, [urls.get(link) for link in links]))
    return result


def compare_source(reference, source, actual, record):
    buf = io.BytesIO()
    reference.build().save(buf)
    expected = inventory(buf)
    with ZipFile(buf) as expected_package, ZipFile(source) as actual_package:
        expected_pixels, actual_pixels = {}, {}
        for i, (lhs, rhs) in enumerate(
            zip(ordered_parts(expected_package), ordered_parts(actual_package)), 1
        ):
            if reference.pages[i - 1]["layout"] == "video" and (
                video_parts(expected_package, lhs) != video_parts(actual_package, rhs)
            ):
                record("errors", i, "source_video", "内嵌视频或静态预览帧与工作稿不一致")
            layout = reference.pages[i - 1]["layout"]
            if layout == "bibliography" and bibliography_links(expected_package, lhs) != bibliography_links(actual_package, rhs):
                record("errors", i, "source_link", "文献标题或链接目标与逐页稿不一致")
            if layout == "handoff" and handoff_cells(expected_package, lhs) != handoff_cells(actual_package, rhs):
                record("errors", i, "source_handoff", "责任方、操作与交付物的对应关系与逐页稿不一致")
            if layout in ("figure", "detail", "evidence_pair", "condition_comparison", "sequence"):
                if evidence_pictures(expected_package, lhs, layout, expected_pixels) != evidence_pictures(
                    actual_package, rhs, layout, actual_pixels
                ):
                    record("errors", i, "source_picture", "图像内容、裁切区域或对照位置与逐页稿不一致")
            if reference.pages[i - 1]["layout"] in ("dotplot", "unitgrid") and (
                data_marks(expected_package, lhs) != data_marks(actual_package, rhs)
            ):
                record(
                    "errors",
                    i,
                    "source_data_marks",
                    "数据标记的数量、位置或填色与逐页稿不同",
                )
    if len(actual) != len(expected):
        record(
            "errors",
            None,
            "source_page_count",
            {"pptx": len(actual), "spec": len(expected)},
        )
    for i, (before, after) in enumerate(zip(expected, actual), 1):
        wanted, got = contents(before), contents(after)
        for field, values in wanted.items():
            if values != got[field]:
                record(
                    "errors",
                    i,
                    "source_" + field,
                    {
                        "expected": list((values - got[field]).elements())[:1],
                        "found": list((got[field] - values).elements())[:1],
                    },
                )


def chart_findings(reference, slide, projected, visible_lines):
    heads, rows = reference.sources.select(slide)
    decimals = slide.get("decimals", 1)
    low = Decimal(str(slide["min"])) if "min" in slide else None
    high = Decimal(str(slide["max"])) if "max" in slide else None
    labels, clipped = set(), []
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_UP
        for row in rows:
            for column, raw in zip(heads[1:], row[1:]):
                value = Decimal(raw)
                labels.add(format(value, f".{decimals}f"))
                if (low is not None and value < low) or (
                    high is not None and value > high
                ):
                    clipped.append(f"{row[0]} / {column} = {raw}")
    text = visible_lines + [word[4] for word in projected.get_text("words")]
    tokens = {compact(s).replace(",", ".").replace("−", "-") for s in text}
    return clipped, sorted(labels - tokens)


def check(source, preview, spec=None, directory=None, style=None):
    actual = inventory(source)
    report = {"slides": len(actual), "errors": [], "warnings": []}

    def record(level, number, code, detail):
        report[level].append({"slide": number, "code": code, "detail": detail})

    reference = None
    projected_fonts = set()
    if spec is not None:
        reference = Deck(spec, directory, style)
        report["requested_fonts"] = {"body": reference.face, "heading": reference.heading}
        compare_source(reference, source, actual, record)
    with ZipFile(source) as package:
        size = query(
            etree.fromstring(package.read("ppt/presentation.xml")), "./p:sldSz"
        )[0]
        ratio = int(size.get("cx")) / int(size.get("cy"))
        visible = [
            i
            for i, name in enumerate(ordered_parts(package))
            if etree.fromstring(package.read(name)).get("show", "1")
            not in ("0", "false")
        ]
    try:
        rendered = fitz.open(preview)
    except (RuntimeError, ValueError) as exc:
        raise ValueError(f"无法读取 PDF 预览：{preview}") from exc
    with rendered as document:
        order = list(range(len(actual))) if len(document) == len(actual) else visible
        report["pdf_slides"] = (
            [i + 1 for i in order]
            if len(document) == len(order)
            else [None] * len(document)
        )
        if len(document) != len(order):
            record(
                "errors",
                None,
                "pdf_page_count",
                {"pdf": len(document), "pptx": len(actual), "visible": len(visible)},
            )
        else:
            for index, projected in zip(order, document):
                page = actual[index]
                if (
                    abs((projected.rect.width / projected.rect.height) / ratio - 1)
                    > 0.01
                ):
                    record(
                        "errors",
                        index + 1,
                        "pdf_aspect_ratio",
                        "PDF 画布比例与 PPTX 不匹配",
                    )
                lines, issues, fonts = projection_issues(projected)
                projected_fonts.update(fonts)
                for code, examples in issues:
                    record("warnings", index + 1, code, examples)
                visible_lines = [
                    s for _, rect, s in lines if rect.intersects(projected.rect)
                ]
                projected_text = compact("".join(visible_lines))
                missing = [
                    s
                    for s in projected_strings(page)
                    if compact(s) and compact(s) not in projected_text
                ]
                if missing:
                    record(
                        "errors" if spec is not None else "warnings",
                        index + 1,
                        "pdf_text_missing",
                        {"count": len(missing), "examples": missing[:3]},
                    )
                if reference and index < len(reference.pages):
                    slide = reference.pages[index]
                    if slide["layout"] == "bibliography":
                        expected_links = Counter(ref["url"] for ref in slide["references"])
                        projected_links = Counter(link.get("uri") for link in projected.get_links())
                        missing_links = list((expected_links - projected_links).elements())
                        if missing_links:
                            record("errors", index + 1, "pdf_reference_link_missing", missing_links)
                    if slide["layout"] == "chart":
                        clipped, absent = chart_findings(
                            reference, slide, projected, visible_lines
                        )
                        if clipped:
                            record(
                                "warnings", index + 1, "chart_axis_clips_data", clipped
                            )
                        if absent:
                            record("errors", index + 1, "pdf_chart_labels", absent)
    report["pdf_fonts"] = sorted(projected_fonts)
    report["ok"] = not report["errors"]
    return report


def compare_layouts(original, revision, pairs, dest):
    """Compare the actual projection of corresponding pages at equal frame sizes."""
    with fitz.open(original) as left, fitz.open(revision) as right, fitz.open() as result:
        for pair in pairs:
            values = pair.split(":")
            if len(values) != 2 or not all(v.isascii() and v.isdigit() for v in values):
                raise ValueError(f"页码对应须写成 原页:新页，例如 3:5，收到 {pair}")
            before, after = map(int, values)
            if not (1 <= before <= len(left) and 1 <= after <= len(right)):
                raise ValueError(f"对应页 {pair} 超出范围：原稿 {len(left)} 页，新稿 {len(right)} 页")
            frame_width = 720
            frame_height = max(
                frame_width * doc[num - 1].rect.height / doc[num - 1].rect.width
                for doc, num in ((left, before), (right, after))
            )
            page = result.new_page(width=1500, height=frame_height + 78)
            for x, doc, number, label in (
                (20, left, before, "原版"),
                (760, right, after, "修订版"),
            ):
                page.insert_text(
                    (x, 32), f"{label}  /  第 {number} 页", fontname="china-s",
                    fontsize=17, color=(0.12, 0.20, 0.23),
                )
                frame = fitz.Rect(x, 56, x + frame_width, 56 + frame_height)
                if doc[number - 1].get_contents():
                    page.show_pdf_page(frame, doc, number - 1)
                page.draw_rect(frame, color=(0.75, 0.79, 0.79), width=0.5)
        result.save(dest, garbage=4, deflate=True)


def overview(preview, dest, slide_numbers, findings):
    """Six vector slide previews per page, retaining the source aspect ratios."""
    flagged = {entry["slide"] for entry in findings}
    with fitz.open(preview) as pdf, fitz.open() as sheet:
        for i, source_page in enumerate(pdf):
            row, col = divmod(i % 6, 2)
            if i % 6 == 0:
                page = sheet.new_page(width=1000, height=920)
            x, y = 26 + col * 485, 20 + row * 300
            n = slide_numbers[i]
            label = f"Slide {n}" if n is not None else f"PDF page {i + 1}"
            if n in flagged and n is not None:
                label += "  /  Review"
            page.insert_text(
                (x, y + 14),
                label,
                fontsize=12,
                color=(0.56, 0.16, 0.13) if n in flagged else (0.12, 0.20, 0.23),
            )
            if source_page.get_contents():
                page.show_pdf_page(fitz.Rect(x, y + 24, x + 462, y + 284), pdf, i)
        sheet.save(dest, garbage=4, deflate=True)
