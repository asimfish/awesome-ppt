"""Native 16:9 slide authoring. All geometry is in inches."""

import io
import json
import math
import platform
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

from data import Sources, number, precision, required
from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

ASSETS = Path(__file__).resolve().parents[1] / "assets"
STYLES = json.loads((ASSETS / "styles.json").read_text(encoding="utf-8"))
MODES = json.loads((ASSETS / "modes.json").read_text(encoding="utf-8"))
W, H = 13.333333, 7.5
LAYOUTS = (
    "cover",
    "section",
    "argument",
    "contrast",
    "process",
    "figure",
    "video",
    "chart",
    "table",
    "equation",
    "decision",
    "dotplot",
    "unitgrid",
    "spotlight",
)
I = Inches


def rgb(value):
    return RGBColor.from_string(value)


def width_units(text):
    return sum(
        1 if unicodedata.east_asian_width(c) in "WF" else 0.85 if c.isupper() else 0.56
        for c in text
    )


def fit_size(text, w, h, preferred, minimum):
    for size in range(preferred, minimum - 1, -1):
        lines = sum(
            max(1, math.ceil(width_units(line) * size / (w * 72 * 0.96)))
            for line in text.split("\n")
        )
        if lines * size * 1.27 <= h * 72:
            return size
    raise ValueError(f"文字超过版面容量，请缩短或拆页：{text[:55]}")


def font(run, name, size, color, bold=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    props = run._r.get_or_add_rPr()
    ea = OxmlElement("a:ea")
    ea.set("typeface", name)
    props.append(ea)


def rectangle(slide, x, y, w, h, color):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, I(x), I(y), I(w), I(h))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(color)
    s.line.fill.background()
    for effect in s._element.xpath("./p:style/a:effectRef"):
        effect.set("idx", "0")
    return s


def text_box(
    slide,
    value,
    x,
    y,
    w,
    h,
    face,
    col,
    size,
    minimum=None,
    bold=False,
    align=PP_ALIGN.LEFT,
    name="Text",
):
    if not isinstance(value, str):
        raise TypeError(f"{name} 必须是文本")
    actual = fit_size(value, w, h, size, minimum or size)
    box = slide.shapes.add_textbox(I(x), I(y), I(w), I(h))
    box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, line in enumerate(value.split("\n")):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        para.space_after = Pt(0)
        run = para.add_run()
        run.text = line
        font(run, face, actual, col, bold)
    return box


def safe_figure(path, page):
    if path.suffix.lower() != ".pdf":
        with Image.open(path) as orig:
            image = orig.convert(
                "RGBA"
                if "A" in orig.getbands() or "transparency" in orig.info
                else "RGB"
            )
            buf = io.BytesIO()
            image.save(buf, format="PNG")
        buf.seek(0)
        return buf
    from pdf_api import fitz

    required(page, ["pdf_page", "crop"])
    with fitz.open(path) as doc:
        n = page["pdf_page"]
        if type(n) is not int or not 1 <= n <= len(doc):
            raise ValueError("PDF 页码超出范围")
        x0, y0, x1, y1 = page["crop"]
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("PDF crop 应为归一化左、上、右、下坐标")
        p = doc[n - 1]
        r = p.rect
        clip = (
            r.x0 + x0 * r.width,
            r.y0 + y0 * r.height,
            r.x0 + x1 * r.width,
            r.y0 + y1 * r.height,
        )
        return io.BytesIO(
            p.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip, alpha=False).tobytes(
                "png"
            )
        )


def contained_box(buf, x, y, w, h):
    with Image.open(buf) as img:
        iw, ih = img.size
    buf.seek(0)
    ratio = min(w / iw, h / ih)
    dw, dh = iw * ratio, ih * ratio
    return I(x + (w - dw) / 2), I(y + (h - dh) / 2), I(dw), I(dh)


def image_contain(slide, buf, x, y, w, h, alt):
    pic = slide.shapes.add_picture(buf, *contained_box(buf, x, y, w, h))
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    return pic


def attach_formula(slide, latex, x, y, w, h, color):
    """Use the same Office Math expression for editing and the rendered fallback."""
    from pdf_api import fitz
    from PIL import ImageOps

    if not shutil.which("pandoc") or not shutil.which("soffice"):
        raise ValueError("公式页需要 pandoc 和 LibreOffice soffice")
    if not latex.strip() or "$" in latex or "\n" in latex:
        raise ValueError("latex 必须是单行公式，不含 $ 定界符")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        doc = work / "formula.docx"
        subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "docx", "-o", str(doc)],
            input="$$" + latex + "$$",
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        with ZipFile(doc) as z:
            root = etree.fromstring(z.read("word/document.xml"))
        subprocess.run(
            [
                "soffice",
                "-env:UserInstallation=" + (work / "profile").as_uri(),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp,
                str(doc),
            ],
            capture_output=True,
            check=True,
            timeout=90,
        )
        with fitz.open(work / "formula.pdf") as pdf:
            if len(pdf) != 1:
                raise ValueError("公式需要拆成单页表达式")
            pix = pdf[0].get_pixmap(
                matrix=fitz.Matrix(6, 6), colorspace=fitz.csGRAY, alpha=False
            )
    mask = ImageOps.invert(Image.frombytes("L", (pix.width, pix.height), pix.samples))
    bounds = mask.getbbox()
    if not bounds:
        raise ValueError(
            "公式预览为空，请核对表达式并检查 LibreOffice Writer 和 Math 组件"
        )
    mask = mask.crop(bounds)
    bitmap = Image.new("RGBA", mask.size, "#" + color)
    bitmap.putalpha(mask)
    buf = io.BytesIO()
    bitmap.save(buf, format="PNG")
    buf.seek(0)
    # Convert the 12 pt document preview to display size, bounded by the slide panel.
    scale = min(3.0 / 432, w / bitmap.width, h / bitmap.height)
    fw, fh = bitmap.width * scale, bitmap.height * scale
    pic = image_contain(slide, buf, x + (w - fw) / 2, y + (h - fh) / 2, fw, fh, latex)
    maths = root.xpath('//*[local-name()="oMathPara"]')
    if len(maths) != 1:
        raise ValueError("pandoc 未生成可编辑的 Office Math")
    box = slide.shapes.add_textbox(I(x), I(y), I(w), I(h))
    box.name = "Office Math"
    box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    para = box.text_frame.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    wrapper_ns = "http://schemas.microsoft.com/office/drawing/2010/main"
    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    math = etree.SubElement(para._p, "{" + wrapper_ns + "}m", nsmap={"a14": wrapper_ns})
    block = deepcopy(maths[0])
    for mrun in block.xpath(
        './/*[local-name()="r" and namespace-uri()="http://schemas.openxmlformats.org/officeDocument/2006/math"]'
    ):
        drawing_props = OxmlElement("a:rPr")
        drawing_props.set("sz", "3200")
        fill = OxmlElement("a:solidFill")
        srgb = OxmlElement("a:srgbClr")
        srgb.set("val", color)
        fill.append(srgb)
        drawing_props.append(fill)
        # A math run may contain m:rPr followed by DrawingML rPr, then m:t.
        mt_el = mrun.find(
            "{http://schemas.openxmlformats.org/officeDocument/2006/math}t"
        )
        if mt_el is not None:
            mrun.insert(mrun.index(mt_el), drawing_props)
    math.append(block)
    parent = pic._element.getparent()
    idx = parent.index(pic._element)
    ac = etree.Element(
        "{" + mc + "}AlternateContent", nsmap={"mc": mc, "a14": wrapper_ns}
    )
    etree.SubElement(ac, "{" + mc + "}Choice", Requires="a14").append(box._element)
    etree.SubElement(ac, "{" + mc + "}Fallback").append(pic._element)
    parent.insert(idx, ac)


class Deck:
    def __init__(self, spec, directory, style=None):
        required(spec, ["mode", "slides"])
        self.mode = MODES[spec["mode"]]
        self.style = STYLES[style or spec.get("style", self.mode["style"])]
        self.stationery = spec.get("stationery", {})
        if self.stationery and (
            not isinstance(self.stationery, dict)
            or set(self.stationery) - {"cover", "header_mark"}
            or self.style["treatment"] not in ("development", "quarterly")
        ):
            raise ValueError(
                "stationery 适用于 development / quarterly，可指定 cover、header_mark"
            )
        self.sources = Sources(spec, directory)
        self.pages = [self.sources.resolve(p) for p in spec["slides"]]
        if not self.pages:
            raise ValueError("至少需要一页")
        self.directory = directory
        self.lang = spec.get("language", "zh")
        if self.lang not in ("zh", "en"):
            raise ValueError("language 选 zh 或 en")
        mac = platform.system() == "Darwin"
        default_face = (
            ("Arial Unicode MS" if mac else "Noto Sans CJK SC")
            if self.lang == "zh"
            else "Arial"
        )
        self.face = spec.get("font", default_face)
        default_heading = self.face
        if self.style["treatment"] in ("folio", "atlas"):
            default_heading = (
                ("Songti SC" if mac else "Noto Serif CJK SC")
                if self.lang == "zh"
                else "Georgia"
            )
        self.heading = spec.get("heading_font", default_heading)
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = I(W), I(H)
        self.prs.core_properties.title = spec.get(
            "title", self.pages[0].get("title", "")
        )
        self.prs.core_properties.author = spec.get("presenter", "")
        self.sections = list(
            dict.fromkeys(p["section"] for p in self.pages if p.get("section"))
        )
        self.spec = spec

    def txt(
        self,
        value,
        x,
        y,
        w,
        h,
        size,
        minimum=None,
        key="ink",
        bold=False,
        head=False,
        **kwargs,
    ):
        return text_box(
            self.slide,
            value,
            x,
            y,
            w,
            h,
            self.heading if head else self.face,
            self.style[key],
            size,
            minimum,
            bold=bold,
            **kwargs,
        )

    def rect(self, x, y, w, h, key):
        return rectangle(self.slide, x, y, w, h, self.style[key])

    def build(self):
        for index, page in enumerate(self.pages, 1):
            self.index = index
            try:
                required(page, ["layout", "title"])
                layout = page["layout"]
                if layout not in LAYOUTS:
                    raise ValueError(f"未知页型 {layout}")
                self.slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
                self.slide.background.fill.solid()
                self.slide.background.fill.fore_color.rgb = rgb(self.style["paper"])
                if layout in ("cover", "section"):
                    self.opener(page)
                else:
                    self.frame(page)
                    getattr(self, layout)(page)
                notes = page.get("notes", "")
                if page["citations"]:
                    notes += (
                        "\n\n"
                        + ("资料来源" if self.lang == "zh" else "Sources")
                        + "\n"
                        + "\n".join(page["citations"])
                    )
                self.slide.notes_slide.notes_text_frame.text = notes.strip()
            except (
                ValueError,
                KeyError,
                IndexError,
                TypeError,
                OSError,
                subprocess.SubprocessError,
            ) as exc:
                raise ValueError(f"第 {self.index} 页：{exc}") from exc
        return self.prs

    def opener(self, p):
        t = self.style["treatment"]
        if "plate" in p or "metrics" in p:
            if ("plate" in p and "metrics" in p) or self.stationery:
                raise ValueError(
                    "分栏封面请选用一幅图版或一组指标，单位底图使用常规封面"
                )
            self.split_cover(p)
            return
        self.rect(0, 0, W, H, "hero")
        left, width = 0.95, 11.35
        label_y, title_y, sub_y, credit_y = 0.86, 2.12, 4.08, 6.35
        label_color = title_color = sub_color = credit_color = "onhero"
        if t == "rail":
            self.rect(0, 0, 0.32, H, "accent")
            left = 1.2
        elif t == "register":
            self.rect(0, 1.46, W, H - 1.46, "paper")
            self.rect(0.95, 5.86, 11.35, 0.025, "line")
            label_y, title_y, sub_y = 0.52, 2.28, 4.24
            title_color, sub_color, credit_color = "ink", "muted", "muted"
        elif t == "folio":
            self.rect(left, 1.5, width, 0.026, "accent")
            self.rect(left, 5.9, width, 0.015, "line")
        elif t in ("stage", "atlas", "briefing"):
            self.rect(left, 1.48, 2.0, 0.065, "accent")
        elif t == "band":
            self.rect(0, 4.0, W, 3.5, "paper")
            self.rect(0, 6.96, W, 0.12, "accent")
            title_y, sub_y = 1.54, 4.60
            sub_color = credit_color = "ink"
        elif t == "development":
            self.rect(0.73, 5.59, 1.12, 0.06, "onhero")
            self.rect(12.62, 2.00, 0.022, 3.5, "line")
            left, width, label_y, title_y, sub_y = 0.74, 11.1, 1.54, 2.43, 4.55
        elif t == "quarterly":
            self.rect(0, 0, W, H, "paper")
            self.rect(0, 1.68, W, 2.76, "hero")
            self.rect(left, 5.23, width, 0.02, "line")
            label_y, title_y, sub_y, credit_y = 0.60, 2.10, 4.70, 6.18
            label_color, sub_color, credit_color = "accent", "ink", "muted"
        else:
            self.rect(0, 0, W - 0.47, H, "paper")
            self.rect(left, 1.54, 1.35, 0.085, "accent")
            label_color, title_color, sub_color, credit_color = (
                "accent",
                "ink",
                "ink",
                "muted",
            )
        if "cover" in self.stationery:
            asset = safe_figure(self.directory / self.stationery["cover"], {})
            with Image.open(asset) as im:
                if abs(im.width / im.height - W / H) > 0.02:
                    raise ValueError("封面底图需要 16:9 宽屏比例")
            asset.seek(0)
            image_contain(self.slide, asset, 0, 0, W, H, "封面底图")
        label = (
            p.get("eyebrow")
            or p.get("section")
            or self.mode["name" if self.lang == "zh" else "en"]
        )
        self.txt(label, left, label_y, width, 0.5, 18, 14, label_color)
        self.txt(
            p["title"],
            left,
            title_y,
            width,
            1.75,
            50,
            30,
            title_color,
            True,
            True,
            name="Title",
        )
        if p.get("subtitle"):
            self.txt(p["subtitle"], left, sub_y, width, 0.9, 23, 15, sub_color)
        credit = p.get("credit") or self.spec.get("presenter", "")
        if credit:
            self.txt(credit, left, credit_y, width, 0.5, 15, 11, credit_color)
        if p["citations"]:
            self.txt(
                " · ".join(p["citations"]),
                left,
                6.90 if t != "band" else 7.12,
                width,
                0.34,
                10,
                8,
                credit_color,
            )

    def split_cover(self, p):
        self.rect(0, 0, W, H, "hero")
        left, divider = 0.72, 7.35
        self.txt(
            p.get("eyebrow") or self.mode["en" if self.lang == "en" else "name"],
            left,
            0.55,
            6.14,
            0.43,
            14,
            10,
            "onhero",
            True,
        )
        self.rect(left, 1.12, 5.92, 0.015, "line")
        self.txt(
            p["title"],
            left,
            1.60,
            6.15,
            2.65,
            56,
            28,
            "onhero",
            self.style["treatment"] != "atlas",
            True,
            name="Title",
        )
        if p.get("subtitle"):
            self.txt(p["subtitle"], left, 4.50, 5.94, 1.35, 22, 14, "onhero")
        credit = p.get("credit") or self.spec.get("presenter", "")
        self.txt(credit, left, 6.60, 6.12, 0.40, 13, 9, "onhero")
        self.rect(divider, 0, W - divider, H, "paper")
        x, w = divider + 0.46, W - divider - 0.92
        if "plate" in p:
            plate = p["plate"]
            required(plate, ["file", "alt", "caption", "source"])
            buf = safe_figure(self.directory / plate["file"], plate)
            image_contain(self.slide, buf, x, 0.26, w, 6.35, plate["alt"])
            self.rect(x, 6.73, w, 0.017, "line")
            self.txt(plate["caption"], x, 6.91, w, 0.34, 12, 9, "muted")
            return
        metrics = p["metrics"]
        if not isinstance(metrics, list) or not 2 <= len(metrics) <= 3:
            raise ValueError("分栏封面需要 2–3 项指标")
        pitch = 6.20 / len(metrics)
        for idx, item in enumerate(metrics):
            required(item, ["value", "label"])
            y = 0.64 + idx * pitch
            self.rect(x, y, w, 0.025, "line")
            self.txt(item["label"], x, y + 0.16, w, 0.52, 17, 12, "muted")
            self.txt(
                item["value"],
                x,
                y + 0.67,
                w,
                pitch - 0.72,
                57,
                24,
                "accent" if idx == 0 else "ink",
                True,
            )

    def frame(self, p):
        t = self.style["treatment"]
        self.x = 2.15 if t == "rail" else 0.70
        self.w = W - self.x - 0.70
        sec = p.get("section") or self.mode["name" if self.lang == "zh" else "en"]
        if t in ("atlas", "briefing"):
            self.rect(self.x, 0.63, self.w, 0.014, "line")
        if t == "rail":
            self.rect(0, 0, 1.8, H, "hero")
            for n, label in enumerate(self.sections[:8]):
                y = 0.96 + n * 0.62
                if label == sec:
                    self.rect(0.18, y, 0.055, 0.35, "line")
                self.txt(label, 0.32, y, 1.31, 0.46, 13, 9, "onhero", label == sec)
        if t == "band":
            self.rect(0, 0, W, 1.65, "hero")
            self.rect(0, 7.44, W * self.index / len(self.pages), 0.06, "accent")
        if t == "register":
            self.rect(0, 0, W, 0.115, "hero")
        if t == "stage":
            self.rect(self.x, 0.31, 0.06, 0.22, "accent")
        if t == "development":
            self.rect(self.x - 0.20, 0.78, 0.09, 0.46, "accent")
        if t == "quarterly":
            self.rect(0, 1.71, W, 0.045, "hero")
        if "header_mark" in self.stationery:
            x = 8.55 if t == "quarterly" else 10.09
            asset = safe_figure(self.directory / self.stationery["header_mark"], {})
            image_contain(self.slide, asset, x, 0.07, W - x - 0.45, 0.60, "机构标识")
        head_color = "onhero" if t == "band" else "ink"
        self.txt(
            sec,
            self.x + (0.2 if t == "stage" else 0),
            0.28,
            self.w if "header_mark" not in self.stationery else 7.45,
            0.35,
            14,
            11,
            "onhero" if t == "band" else "accent",
            True,
        )
        self.txt(
            p["title"],
            self.x,
            0.74,
            self.w,
            0.87,
            32,
            20,
            head_color,
            True,
            True,
            name="Title",
        )
        if t in ("folio", "rule", "register"):
            self.rect(
                self.x, 1.70, self.w, 0.026 if t != "register" else 0.047, "accent"
            )
        self.rect(self.x, 6.82, self.w, 0.012, "line")
        self.txt(
            " · ".join(p["citations"]),
            self.x,
            6.91,
            self.w - 0.66,
            0.37,
            11,
            8,
            "muted",
            name="Source",
        )
        self.txt(
            str(self.index),
            W - 1.25,
            6.9,
            0.55,
            0.36,
            12,
            10,
            "muted",
            align=PP_ALIGN.RIGHT,
        )

    def argument(self, p):
        required(p, ["lead", "points"])
        items = p["points"]
        if not isinstance(items, list) or not 1 <= len(items) <= 4:
            raise ValueError("points 需要 1–4 项")
        split = self.w * 0.39
        self.txt(
            p["lead"], self.x, 2.26, split - 0.3, 3.9, 31, 20, "accent", True, True
        )
        self.rect(self.x + split, 2.24, 0.025, 3.96, "line")
        step = 4.0 / len(items)
        for n, line in enumerate(items):
            self.txt(
                line,
                self.x + split + 0.40,
                2.26 + n * step,
                self.w - split - 0.45,
                step - 0.12,
                23,
                16,
            )
            if n + 1 < len(items):
                self.rect(
                    self.x + split + 0.4,
                    2.23 + (n + 1) * step,
                    self.w - split - 0.5,
                    0.015,
                    "line",
                )

    def contrast(self, p):
        for i, side in enumerate(("left", "right")):
            col = p[side]
            required(col, ["heading", "text"])
            w = (self.w - 0.45) / 2
            x = self.x + i * (w + 0.45)
            self.rect(x, 2.14, w, 4.20, "panel")
            self.rect(x, 2.14, w, 0.065, "accent" if i else "line")
            self.txt(
                col["heading"], x + 0.25, 2.48, w - 0.5, 0.74, 25, 17, "accent", True
            )
            self.txt(col["text"], x + 0.25, 3.39, w - 0.5, 2.68, 22, 15)

    def process(self, p):
        steps = p["steps"]
        if not isinstance(steps, list) or not 2 <= len(steps) <= 4:
            raise ValueError("steps 需要 2–4 项")
        active = p.get("active_step")
        if active is not None and (
            type(active) is not int or not 1 <= active <= len(steps)
        ):
            raise ValueError("active_step 是从 1 开始的本页节点编号")
        w = (self.w - 0.36 * (len(steps) - 1)) / len(steps)
        self.rect(self.x, 2.55, self.w, 0.035, "line")
        for i, s in enumerate(steps):
            required(s, ["heading", "text"])
            x = self.x + i * (w + 0.36)
            if active == i + 1:
                self.rect(x - 0.08, 2.93, w + 0.06, 3.23, "panel")
                self.rect(x, 6.20, w, 0.05, "accent")
                self.txt(
                    "本季节点" if self.lang == "zh" else "This quarter",
                    x + 0.59,
                    2.23,
                    w - 0.62,
                    0.44,
                    17,
                    12,
                    "accent",
                    True,
                )
            self.rect(x, 2.30, 0.49, 0.48, "accent")
            text_box(
                self.slide,
                str(i + 1),
                x,
                2.36,
                0.49,
                0.34,
                self.face,
                self.style["paper"],
                16,
                14,
                True,
                PP_ALIGN.CENTER,
            )
            self.txt(s["heading"], x, 3.09, w, 0.79, 24, 15, bold=True)
            self.txt(s["text"], x, 4.00, w, 2.10, 19, 14)

    def video(self, p):
        required(p, ["file", "poster"])
        movie = self.directory / p["file"]
        if movie.suffix.lower() != ".mp4" or not movie.is_file():
            raise ValueError("video 需要本地 MP4 演示片段")
        self.figure(p, movie)

    def figure(self, p, movie=None):
        required(p, ["file", "alt", "source"])
        buf = safe_figure(self.directory / p["poster" if movie else "file"], p)
        caption = p.get("caption")
        fw = self.w if not caption else self.w * 0.70
        if movie is None:
            image_contain(self.slide, buf, self.x, 1.95, fw, 4.55, p["alt"])
        else:
            shape = self.slide.shapes.add_movie(
                str(movie),
                *contained_box(buf, self.x, 1.95, fw, 4.55),
                poster_frame_image=buf,
                mime_type="video/mp4",
            )
            shape._element.nvPicPr.cNvPr.set("descr", p["alt"])
        if caption:
            self.rect(self.x + fw + 0.15, 2.27, 0.034, 3.72, "accent")
            self.txt(caption, self.x + fw + 0.42, 2.39, self.w - fw - 0.42, 3.5, 21, 14)

    def table(self, p):
        heads, rows = self.sources.select(p)
        if len(rows) > 9 or len(heads) > 6:
            raise ValueError("单页表格最多 9 行数据、6 列，请拆页或精选")
        widths = p.get("widths") or [1.3] + [1] * (len(heads) - 1)
        if len(widths) != len(heads) or any(
            type(v) not in (int, float) or not 0 < v <= 100 for v in widths
        ):
            raise ValueError("widths 应与列数一致且均为正数")
        h = min(3.73 if p.get("caption") else 4.46, 0.60 * (len(rows) + 1))
        y = 2.04 + (4.46 - h) * 0.28
        tab = self.slide.shapes.add_table(
            len(rows) + 1, len(heads), I(self.x), I(y), I(self.w), I(h)
        ).table
        highlights = set(p.get("highlight", []))
        if "highlight_where" in p:
            rule = p["highlight_where"]
            required(rule, ["column", "equals"])
            if rule["column"] not in heads:
                raise ValueError("highlight_where 使用的列必须出现在表格里")
            col_index = heads.index(rule["column"])
            highlights.update(
                row[0] for row in rows if row[col_index] == rule["equals"]
            )
        for i, v in enumerate(widths):
            tab.columns[i].width = I(self.w * v / sum(widths))
        for i, row in enumerate([heads, *rows]):
            for j, value in enumerate(row):
                c = tab.cell(i, j)
                c.margin_left = c.margin_right = I(0.10)
                c.margin_top = c.margin_bottom = I(0.025)
                c.vertical_anchor = MSO_ANCHOR.MIDDLE
                c.fill.solid()
                c.fill.fore_color.rgb = rgb(
                    self.style["hero" if i == 0 else "panel" if i % 2 else "paper"]
                )
                weight = i == 0 or row[0] in highlights
                col = "onhero" if i == 0 else "ink"
                size = fit_size(
                    str(value),
                    tab.columns[j].width / I(1) - 0.20,
                    h / (len(rows) + 1) - 0.06,
                    17,
                    10,
                )
                para = c.text_frame.paragraphs[0]
                run = para.add_run()
                run.text = str(value)
                font(run, self.face, size, self.style[col], weight)
        if p.get("caption"):
            self.txt(p["caption"], self.x, 6.06, self.w, 0.54, 17, 12, "muted")

    def chart(self, p):
        heads, rows = self.sources.select(p)
        if len(rows) > 8 or len(heads) > 4:
            raise ValueError("单页图表最多 8 个类别、3 个系列")
        dec = precision(p.get("decimals", 1))
        fmt = "0" + ("." + "0" * dec if dec else "")
        data = CategoryChartData()
        data.categories = [r[0] for r in rows]
        for j, h in enumerate(heads[1:], 1):
            data.add_series(h, [float(number(r[j])) for r in rows], number_format=fmt)
        kind = {
            "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
            "line": XL_CHART_TYPE.LINE_MARKERS,
        }[p.get("kind", "column")]
        reading = p.get("reading")
        cw = self.w * (0.70 if reading else 1)
        chart = self.slide.shapes.add_chart(
            kind, I(self.x), I(2.00), I(cw), I(4.40), data
        ).chart
        for auto_title in chart._chartSpace.xpath("./c:chart/c:autoTitleDeleted"):
            auto_title.set("val", "1")
        background = OxmlElement("c:spPr")
        fill = OxmlElement("a:solidFill")
        paint = OxmlElement("a:srgbClr")
        paint.set("val", self.style["paper"])
        fill.append(paint)
        background.append(fill)
        chart._chartSpace.insert_element_before(
            background, "c:txPr", "c:externalData", "c:printSettings", "c:extLst"
        )
        chart.has_legend = len(heads) > 2
        if chart.has_legend:
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.font.color.rgb = rgb(self.style["ink"])
            chart.legend.font.name = self.face
            chart.legend.font.size = Pt(12)
        for ax in (chart.category_axis, chart.value_axis):
            ax.tick_labels.font.name = self.face
            ax.tick_labels.font.color.rgb = rgb(self.style["ink"])
            ax.tick_labels.font.size = Pt(12)
        chart.value_axis.has_title = True
        axis_label = chart.value_axis.axis_title.text_frame.paragraphs[0].add_run()
        axis_label.text = p.get("axis_title", heads[1])
        font(axis_label, self.face, 12, self.style["muted"])
        if "min" in p:
            chart.value_axis.minimum_scale = float(number(p["min"]))
        if "max" in p:
            chart.value_axis.maximum_scale = float(number(p["max"]))
        if "min" in p and "max" in p and number(p["min"]) >= number(p["max"]):
            raise ValueError("轴范围 min 必须小于 max")
        if p.get("min") == 0 and p.get("max") == 100:
            chart.value_axis.major_unit = 20
            chart.value_axis.tick_labels.number_format = "0"
            chart.value_axis.tick_labels.number_format_is_linked = False
        if chart.value_axis.has_major_gridlines:
            chart.value_axis.major_gridlines.format.line.color.rgb = rgb(
                self.style["line"]
            )
            chart.value_axis.major_gridlines.format.line.width = Pt(0.6)
        plot = chart.plots[0]
        plot.has_data_labels = True
        labels = plot.data_labels
        labels.show_value = True
        labels.number_format = fmt
        labels.number_format_is_linked = False
        labels.font.name = self.face
        labels.font.size = Pt(13)
        labels.font.color.rgb = rgb(self.style["ink"])
        labels.position = (
            XL_LABEL_POSITION.ABOVE
            if p.get("kind") == "line"
            else XL_LABEL_POSITION.OUTSIDE_END
        )
        palette = [self.style["accent"], "759CC2", "CA8856"]
        for s, col in zip(chart.series, palette):
            s.format.fill.solid()
            s.format.fill.fore_color.rgb = rgb(col)
            s.format.line.color.rgb = rgb(col)
        if reading:
            self.rect(self.x + cw + 0.2, 2.35, 0.032, 3.3, "accent")
            self.txt(
                reading,
                self.x + cw + 0.45,
                2.45,
                self.w - cw - 0.45,
                3.1,
                23,
                15,
                "ink",
                True,
            )

    def equation(self, p):
        required(p, ["latex", "explanation", "source"])
        self.rect(self.x, 2.14, self.w, 2.58, "panel")
        attach_formula(
            self.slide,
            p["latex"],
            self.x + 0.25,
            2.35,
            self.w - 0.5,
            2.12,
            self.style["ink"],
        )
        self.txt(p["explanation"], self.x + 0.2, 5.10, self.w - 0.4, 1.02, 22, 15)

    def dotplot(self, p):
        """Stack equal measurements within each group. Each glyph remains editable."""
        heads, rows = self.sources.select(p)
        if len(heads) != 3 or len(rows) > 300:
            raise ValueError("dotplot 需要组别和数值两列，每页最多展示 300 条记录")
        groups = defaultdict(list)
        for record, group, value in rows:
            if not group.strip():
                raise ValueError("dotplot 组别不能为空")
            groups[group].append((record, number(value)))
        if len(groups) > 4:
            raise ValueError("dotplot 每页最多展示四组")
        values = [v for group in groups.values() for _, v in group]
        lo, hi = number(p.get("min", min(values))), number(p.get("max", max(values)))
        if lo >= hi or min(values) < lo or max(values) > hi:
            raise ValueError("dotplot 坐标范围需要包含全部观测值且 min 小于 max")
        plot_x, plot_w = self.x + 2.18, self.w - 2.43
        band = 3.60 / len(groups)
        max_count = max(
            max(Counter(v for _, v in group).values()) for group in groups.values()
        )
        distinct = sorted(set(values))
        min_gap = min(
            (distinct[i] - distinct[i - 1] for i in range(1, len(distinct))),
            default=hi - lo,
        )
        diameter = min(
            0.16, 0.88 * band / max_count, 0.94 * float(min_gap / (hi - lo)) * plot_w
        )
        if diameter < 0.045:
            raise ValueError("当前投影尺寸无法区分各点，请细分组别或拆页")
        self.txt(
            p.get("axis_title", heads[2]), plot_x, 1.74, plot_w, 0.43, 14, 11, "muted"
        )
        for tick in range(5):
            x = plot_x + plot_w * tick / 4
            value = lo + (hi - lo) * tick / 4
            self.rect(x, 2.25, 0.012, 3.60, "line")
            self.txt(
                format(value.normalize(), "f"),
                x - 0.29,
                5.92,
                0.58,
                0.32,
                13,
                9,
                "muted",
                align=PP_ALIGN.CENTER,
            )
        for idx, (group, records) in enumerate(groups.items()):
            baseline = 2.25 + (idx + 1) * band - 0.10
            self.txt(
                group, self.x, baseline - 0.48, 1.94, 0.46, 21, 12, "ink", True, True
            )
            self.rect(plot_x, baseline, plot_w, 0.014, "line")
            counts = Counter()
            for record, value in records:
                dx = plot_x + plot_w * float((value - lo) / (hi - lo))
                dy = baseline - (counts[value] + 1) * diameter
                counts[value] += 1
                dot = self.slide.shapes.add_shape(
                    MSO_SHAPE.OVAL,
                    I(dx - diameter / 2),
                    I(dy),
                    I(diameter),
                    I(diameter),
                )
                dot.name = f"{record} · {group} · {value}"
                dot.fill.solid()
                dot.fill.fore_color.rgb = rgb(self.style["accent"])
                dot.line.fill.background()
                for effect in dot._element.xpath("./p:style/a:effectRef"):
                    effect.set("idx", "0")
        if p.get("caption"):
            self.txt(p["caption"], self.x, 6.32, self.w, 0.36, 14, 10, "muted")

    def unitgrid(self, p):
        heads, rows = self.sources.select(p)
        required(p, ["legend"])
        if len(heads) != 3 or len(rows) != 2:
            raise ValueError("unitgrid 需要选择两行，以及命中数、总数两列")
        pairs = [(number(hit), number(total)) for _, hit, total in rows]
        if (
            any(
                hit % 1 or total % 1 or not 0 <= hit <= total <= 100 or total < 1
                for hit, total in pairs
            )
            or pairs[0][1] != pairs[1][1]
        ):
            raise ValueError("unitgrid 比较相同分母的两组整数计数，分母须在 1–100 之间")
        panel = (self.w - 0.68) / 2
        total = int(pairs[0][1])
        across = min(total, 10)
        down = math.ceil(total / across)
        pitch = min((panel - 0.32) / across, 2.64 / down, 0.44)
        column_pitch = min(panel / across, 0.65)
        for idx, ((label, _, _), (hit, _)) in enumerate(zip(rows, pairs)):
            x = self.x + idx * (panel + 0.68)
            tone = "accent" if idx else "muted"
            self.rect(x, 1.99, panel, 0.02, "line")
            self.txt(label, x, 2.16, panel * 0.45, 0.62, 20, 14, tone, True)
            self.txt(
                f"{int(hit)} / {total}",
                x + panel * 0.45,
                2.08,
                panel * 0.55,
                0.92,
                34,
                18,
                tone,
                True,
                align=PP_ALIGN.RIGHT,
            )
            for cell in range(total):
                box = self.rect(
                    x + cell % across * column_pitch,
                    3.12 + cell // across * pitch,
                    column_pitch * 0.85,
                    pitch * 0.81,
                    tone if cell < hit else "line",
                )
                box.name = f"{label} · {cell + 1}"
        self.txt(p["legend"], self.x, 6.08, self.w, 0.56, 17, 12, "ink")

    def spotlight(self, p):
        required(p, ["value", "label", "heading", "text"])
        panel = self.w * 0.49
        self.rect(self.x, 2.03, panel, 4.23, "hero")
        self.txt(p["label"], self.x + 0.34, 2.38, panel - 0.68, 0.64, 17, 12, "onhero")
        self.txt(
            p["value"],
            self.x + 0.34,
            3.47,
            panel - 0.68,
            1.75,
            58,
            25,
            "onhero",
            True,
            True,
        )
        x, w = self.x + panel + 0.46, self.w - panel - 0.52
        self.txt(p["heading"], x, 2.43, w, 1.32, 32, 19, "ink", True, True)
        self.rect(x, 3.91, w, 0.022, "line")
        self.txt(p["text"], x, 4.13, w, 1.89, 23, 14, "muted")

    def decision(self, p):
        required(p, ["takeaway", "items"])
        items = p["items"]
        if not isinstance(items, list) or not 1 <= len(items) <= 3:
            raise ValueError("items 需要 1–3 项")
        self.txt(
            p["takeaway"], self.x, 2.05, self.w, 1.22, 30, 20, "accent", True, True
        )
        h = 2.85 / len(items)
        for i, line in enumerate(items):
            top = 3.54 + i * h
            self.rect(self.x, top, self.w, 0.017, "line")
            self.txt(line, self.x + 0.12, top + 0.14, self.w - 0.24, h - 0.19, 20, 13)
