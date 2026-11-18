"""Exercise data binding, starter generation, editability and safe output boundaries."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from data import Sources
from checks import compare_source, video_parts
from native import fill, inventory, ordered_parts
from pdf_api import fitz
from render import Deck


class DeckChecks(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.work = Path(self.workspace.name)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SKILL / "scripts/deck.py"), *map(str, args)],
            check=False,
            capture_output=True,
            text=True,
        )

    def start(self, mode):
        draft = self.work / mode
        run = self.cli("starter", mode, draft)
        self.assertEqual(run.returncode, 0, run.stderr)
        return draft, json.loads((draft / "deck.json").read_text())

    def test_observation_sequence_and_reading_links_survive_draft(self):
        images = self.work / "images"
        images.mkdir()
        frames = []
        for label, color in [("Start", "white"), ("End", "blue")]:
            path = images / (label + ".png")
            Image.new("RGB", (120, 80), color).save(path)
            frames.append({"file": str(path), "alt": label, "label": label})
        entry = {"byline": "Chen et al. · 2026", "title": "Flow measurements", "url": "https://example.org/flow"}
        spec = {"mode": "journal-club", "bibliography": {"flow": entry}, "slides": [
            {"title": "Flow changes", "source": "Fig. 1", "frames": frames, "cite": ["flow"]},
            {"title": "Reading", "layout": "bibliography", "cite": ["flow"]}]}
        draft = self.work / "draft"
        original = self.work / "talk.json"
        original.write_text(json.dumps(spec))
        self.assertEqual(self.cli("draft", original, draft).returncode, 0)
        shutil.rmtree(images)
        spec = json.loads((draft / "deck.json").read_text())
        deck = Deck(spec, draft)
        self.assertEqual(deck.pages[0]["layout"], "sequence")
        prs = deck.build()
        notes = prs.slides[0].notes_slide.notes_text_frame.text
        self.assertIn(entry["url"], notes)
        self.assertIn("Fig. 1", notes)
        if os.environ.get("AWESOMEPPT_RENDER_TESTS") == "1":
            clean = self.work / "reading.pptx"
            pdf = clean.with_suffix(".pdf")
            prs.save(clean)
            rendered = self.cli("preview", clean, pdf)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            checked = self.cli("check", clean, "--spec", draft / "deck.json", "--pdf", pdf)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertTrue(json.loads(checked.stdout)["pdf_fonts"])
        pictures = [s for s in prs.slides[0].shapes if s._element.xpath("./p:nvPicPr")]
        pictures[0].left, pictures[1].left = pictures[1].left, pictures[0].left
        link = next(s for s in prs.slides[1].shapes if s.name == "Reference title")
        self.assertEqual(link.click_action.hyperlink.address, entry["url"])
        link.click_action.hyperlink.address = "https://example.org/erratum"
        output = self.work / "changed.pptx"
        prs.save(output)
        findings = []
        compare_source(Deck(spec, draft), output, inventory(output), lambda *args: findings.append(args))
        self.assertEqual({f[2] for f in findings}, {"source_picture", "source_link"})
        spec["slides"][0]["cite"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "cite"):
            Deck(spec, draft)

    def test_storyboard_routes_measured_conditions_and_detects_swapped_photos(self):
        source = self.work / "optics"
        source.mkdir()
        for key, color in [("clear", "white"), ("filter", "blue")]:
            Image.new("RGB", (180, 100), color).save(source / (key + ".png"))
        (source / "readings.csv").write_text("condition,signal (mV)\nclear,90.2\nfilter,53.1\n")
        conditions = {
            key: {"file": key + ".png", "alt": key + " optical setup", "source": "Lab photo " + key}
            for key in ("clear", "filter")
        }
        spec = {
            "mode": "conference", "language": "en",
            "datasets": {"bench": {"file": "readings.csv", "key": "condition", "source": "Bench log 7"}},
            "slides": [
                {"title": "Optical bench", "subtitle": "Two observed conditions"},
                {"title": "Sample preparation and readout", "source": "Run sheet 7",
                 "stages": [{"owner": "Technician", "action": "Mount filter", "output": "Sample ID"},
                            {"owner": "Operator", "action": "Measure signal", "output": "Logged reading"}]},
                {"title": "Filter and clear reference", "dataset": "bench", "columns": ["signal (mV)"],
                 "rows": ["filter", "clear"], "conditions": conditions},
                {"title": "Signal under both conditions", "dataset": "bench", "columns": ["signal (mV)"]},
                {"layout": "table", "title": "Backup measurements", "dataset": "bench", "columns": ["signal (mV)"]},
            ],
        }
        path = source / "talk.json"
        path.write_text(json.dumps(spec))
        draft = self.work / "portable"
        self.assertEqual(self.cli("draft", path, draft).returncode, 0)
        shutil.rmtree(source)
        path = draft / "deck.json"
        result = self.cli("storyboard", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        pages = json.loads(result.stdout)["slides"]
        self.assertEqual([p["layout"] for p in pages], ["cover", "handoff", "condition_comparison", "chart", "table"])
        self.assertEqual(pages[2]["rows"], ["filter", "clear"])
        self.assertEqual(pages[2]["files"], ["filter.png", "clear.png"])
        self.assertEqual(pages[2]["sources"], ["Bench log 7", "Lab photo filter", "Lab photo clear"])
        self.assertNotIn("missing_files", pages[2])
        output = self.work / "optics.pptx"
        result = self.cli("build", path, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        if os.environ.get("AWESOMEPPT_RENDER_TESTS") == "1":
            pdf = output.with_suffix(".pdf")
            projected = self.cli("preview", output, pdf)
            self.assertEqual(projected.returncode, 0, projected.stderr)
            checked = self.cli("check", output, "--spec", path, "--pdf", pdf)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(json.loads(checked.stdout)["warnings"], [])
        prs = Presentation(output)
        page = prs.slides[2]
        table = next(shape.table for shape in page.shapes if shape.has_table)
        self.assertEqual([[c.text for c in row.cells] for row in table.rows],
                         [["condition", "filter", "clear"], ["signal (mV)", "53.1", "90.2"]])
        pictures = sorted((s for s in page.shapes if s._element.xpath("./p:nvPicPr")), key=lambda s: s.left)
        with Image.open(io.BytesIO(pictures[0].image.blob)) as first:
            self.assertEqual(first.convert("RGB").getpixel((0, 0)), (0, 0, 255))
        blips = [s._element.xpath("./p:blipFill/a:blip")[0] for s in pictures]
        ids = [b.get(qn("r:embed")) for b in blips]
        for blip, rid in zip(blips, reversed(ids)):
            blip.set(qn("r:embed"), rid)
        owners = [s for s in prs.slides[1].shapes if s.name.startswith("Handoff ") and s.name.endswith(" owner")]
        owners[0].top, owners[1].top = owners[1].top, owners[0].top
        swapped = self.work / "swapped.pptx"
        prs.save(swapped)
        findings = []
        copied = json.loads(path.read_text())
        compare_source(Deck(copied, draft), swapped, inventory(swapped), lambda *args: findings.append(args))
        self.assertEqual([(row[1], row[2]) for row in findings], [(2, "source_handoff"), (3, "source_picture")])
        copied["slides"][2].pop("rows")
        path.write_text(json.dumps(copied))
        readout = draft / "readings.csv"
        header, first_row, second_row = readout.read_text().splitlines()
        for records, expected in [([first_row, second_row], ["clear", "filter"]),
                                  ([second_row, first_row], ["filter", "clear"])]:
            readout.write_text("\n".join([header, *records]) + "\n")
            planned = json.loads(self.cli("storyboard", path).stdout)["slides"][2]
            self.assertEqual(planned["rows"], expected)
            self.assertEqual(planned["files"], [key + ".png" for key in expected])
        del copied["slides"][2]["conditions"]["clear"]
        path.write_text(json.dumps(copied))
        before = output.read_bytes()
        failed = self.cli("build", path, output, "--replace")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("第 3 页", failed.stderr)
        self.assertEqual(before, output.read_bytes())

    def test_storyboard_guides_ambiguous_pages_and_respects_the_audience(self):
        draft, spec = self.start("conference")
        chart = next(p for p in spec["slides"] if p["layout"] == "chart")
        page = {k: chart[k] for k in ("title", "dataset", "columns")}
        path = draft / "deck.json"
        for mode, layout in [("conference", "chart"), ("acceptance", "table")]:
            spec.update(mode=mode, slides=[page])
            path.write_text(json.dumps(spec))
            self.assertEqual(json.loads(self.cli("storyboard", path).stdout)["slides"][0]["layout"], layout)
        page.update(file="field.png", alt="Field", source="Log", layout="auto")
        path.write_text(json.dumps(spec))
        failure = self.cli("storyboard", path)
        self.assertNotEqual(failure.returncode, 0)
        self.assertIn("第 1 页", failure.stderr)
        page["layout"] = "figure"
        path.write_text(json.dumps(spec))
        planned = json.loads(self.cli("storyboard", path).stdout)["slides"][0]
        self.assertEqual(planned["layout"], "figure")
        self.assertEqual(planned["missing_files"], ["field.png"])

    def test_layout_compare_uses_selected_pages_and_preserves_output_on_error(self):
        left, right, output = [self.work / name for name in ("old.pdf", "new.pdf", "pair.pdf")]
        for path, prefix, width in [(left, "old", 960), (right, "new", 720)]:
            with fitz.open() as doc:
                for i in range(1, 3):
                    pg = doc.new_page(width=width, height=540)
                    pg.insert_text((40, 80), f"{prefix}-{i}")
                doc.save(path)
        run = self.cli("compare", left, right, output, "--pairs", "2:1", "1:2")
        self.assertEqual(run.returncode, 0, run.stderr)
        with fitz.open(output) as comparison:
            self.assertEqual(len(comparison), 2)
            for i, pair in enumerate([("old-2", "new-1"), ("old-1", "new-2")]):
                left_box = comparison[i].search_for(pair[0])[0]
                right_box = comparison[i].search_for(pair[1])[0]
                self.assertLess(left_box.x1, right_box.x0)
        saved = output.read_bytes()
        for pair in ("0:1", "1:3", "1-1"):
            failed = self.cli("compare", left, right, output, "--pairs", pair, "--replace")
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(output.read_bytes(), saved)

    def test_video_draft_embeds_both_assets(self):
        src, spec = self.start("conference")
        frame = src / "frame.png"
        Image.new("RGB", (64, 36), "green").save(frame)
        clip = src / "demo.mp4"
        # Only package identity is under test. Playback is checked with an actual clip.
        clip.write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes(12))
        spec["slides"] = [{
            "layout": "video", "title": "Replay", "file": "demo.mp4",
            "poster": "frame.png", "alt": "Recorded view", "source": "Team demo",
        }]
        (src / "deck.json").write_text(json.dumps(spec))
        dest = self.work / "reusable"
        copied = self.cli("draft", src / "deck.json", dest)
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual((dest / clip.name).read_bytes(), clip.read_bytes())
        self.assertEqual((dest / frame.name).read_bytes(), frame.read_bytes())
        output = self.work / "replay.pptx"
        built = self.cli("build", dest / "deck.json", output)
        self.assertEqual(built.returncode, 0, built.stderr)
        with ZipFile(output) as package:
            media = video_parts(package, ordered_parts(package)[0])
            self.assertEqual({item[0] for item in media}, {"image", "video"})
            movie = next(name for name in package.namelist() if name.endswith(".mp4"))
            self.assertEqual(package.read(movie), clip.read_bytes())

    def test_projection_caption_leaves_space_for_wide_media_and_chart_labels(self):
        src, spec = self.start("conference")
        chart = next(p for p in spec["slides"] if p["layout"] == "chart")
        Image.new("RGB", (600, 160), "green").save(src / "wide.png")
        (src / "demo.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes(12))
        figure = dict(layout="figure", title="Figure", file="wide.png",
                      alt="Wide view", source="Lab", caption="Visible event")
        video = dict(figure, layout="video", file="demo.mp4", poster="wide.png")
        pages = []
        for content in (figure, video, chart):
            legacy = dict(content)
            legacy.pop("caption_position", None)
            pages.extend([legacy, dict(content, caption_position="below")])
        spec["slides"] = pages
        path = src / "deck.json"
        path.write_text(json.dumps(spec))
        output = self.work / "projection.pptx"
        result = self.cli("build", path, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        slides = list(Presentation(output).slides)
        def evidence(slide):
            return next(s for s in slide.shapes if s.has_chart or
                        s._element.xpath('./p:nvPicPr/p:cNvPr[@descr="Wide view"]'))

        for idx in (0, 2, 4):
            side, wide = evidence(slides[idx]), evidence(slides[idx + 1])
            self.assertGreater(wide.width, side.width)
            line = next(s for s in slides[idx + 1].shapes if s.has_text_frame and
                        (s.text == "Visible event" or s.text.startswith("比向量检索高")))
            self.assertGreater(line.top, wide.top + wide.height)
            self.assertGreaterEqual(line.text_frame.paragraphs[0].runs[0].font.size.pt, 18)
            if wide.has_chart:
                self.assertEqual(wide.chart.category_axis.tick_labels.font.size.pt, 17)
                self.assertEqual(wide.chart.plots[0].data_labels.font.size.pt, 18)
            else:
                self.assertAlmostEqual(wide.width / wide.height, 600 / 160, places=4)
        pages[0]["caption_position"] = "unknown"
        path.write_text(json.dumps(spec))
        self.assertNotEqual(self.cli("build", path, self.work / "bad.pptx").returncode, 0)

    def test_visual_evidence_preserves_picture_regions_and_panel_sources(self):
        src, spec = self.start("demo")
        wide = src / "view.png"
        tall = self.work / "second.png"
        Image.new("RGB", (360, 160), "green").save(wide)
        Image.new("RGB", (100, 240), "blue").save(tall)
        spec["slides"] = [
            {"title": "Locate the field", "file": wide.name,
             "alt": "Complete view", "source": "Trial A", "region": [0.25, 0.1, 0.75, 0.6],
             "detail_label": "Selected field"},
            {"layout": "auto", "title": "Compare observations",
             "left": {"file": wide.name, "alt": "Overview", "heading": "First", "source": "Trial A"},
             "right": {"file": str(tall), "alt": "Second view", "heading": "Second", "source": "Trial B"}},
        ]
        path = src / "deck.json"
        path.write_text(json.dumps(spec))
        draft = self.work / "copy"
        self.assertEqual(self.cli("draft", path, draft).returncode, 0)
        tall.unlink()
        output = self.work / "visual.pptx"
        result = self.cli("build", draft / "deck.json", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        prs = Presentation(output)
        zoom, pair = list(prs.slides)
        whole, inset = [s for s in zoom.shapes if s._element.xpath("./p:nvPicPr")]
        self.assertEqual(whole.image.sha1, inset.image.sha1)
        self.assertEqual((inset.crop_left, inset.crop_top, inset.crop_right, inset.crop_bottom),
                         (0.25, 0.1, 0.25, 0.4))
        frame = next(s for s in zoom.shapes if s.name == "Detail region")
        self.assertAlmostEqual(frame.left, whole.left + whole.width / 4, delta=1)
        self.assertAlmostEqual(frame.top, whole.top + whole.height / 10, delta=1)
        self.assertAlmostEqual(inset.width / inset.height, frame.width / frame.height, places=5)
        self.assertGreater(inset.width, frame.width)
        left, right = [s for s in pair.shapes if s._element.xpath("./p:nvPicPr")]
        self.assertLess(left.left + left.width, right.left)
        self.assertAlmostEqual(left.width / left.height, 360 / 160, places=5)
        self.assertAlmostEqual(right.width / right.height, 100 / 240, places=5)
        self.assertIn("Trial A", pair.notes_slide.notes_text_frame.text)
        self.assertIn("Trial B", pair.notes_slide.notes_text_frame.text)
        copied = draft / "deck.json"
        inset.crop_top += 0.1
        drifted = self.work / "drifted-detail.pptx"
        prs.save(drifted)
        findings = []
        compare_source(Deck(json.loads(copied.read_text()), draft), drifted, inventory(drifted),
                       lambda *args: findings.append(args))
        self.assertEqual([(row[1], row[2]) for row in findings], [(1, "source_picture")])
        invalid = json.loads(copied.read_text())
        for rect in ([0, 0.5, 1, 0.5], [0, 0, 1.1, 1], [0, 1, 1], [0, 0, 1, 1]):
            invalid["slides"][0]["region"] = rect
            copied.write_text(json.dumps(invalid))
            self.assertNotEqual(self.cli("build", copied, self.work / "bad.pptx").returncode, 0)

    def test_portable_draft_carries_external_and_nested_assets(self):
        src, spec = self.start("conference")
        local = src / "art" / "plate.png"
        local.parent.mkdir()
        Image.new("RGB", (12, 20), "red").save(local)
        external = self.work / "plate.png"
        Image.new("RGB", (12, 20), "blue").save(external)
        spec["slides"] = [
            {
                "layout": "cover",
                "title": "Test",
                "plate": {
                    "file": "art/plate.png",
                    "alt": "A",
                    "caption": "Local",
                    "source": "A",
                },
            },
            {
                "layout": "figure",
                "title": "Other",
                "file": "../plate.png",
                "alt": "B",
                "source": "B",
            },
            {
                "layout": "figure",
                "title": "Again",
                "file": str(external),
                "alt": "B",
                "source": "B",
            },
        ]
        source = src / "deck.json"
        source.write_text(json.dumps(spec))
        dest = self.work / "portable"
        copied = self.cli("draft", source, dest)
        self.assertEqual(copied.returncode, 0, copied.stderr)
        draft = json.loads((dest / "deck.json").read_text())
        self.assertEqual((dest / "art/plate.png").read_bytes(), local.read_bytes())
        fig = draft["slides"][1]["file"]
        self.assertEqual(fig, draft["slides"][2]["file"])
        self.assertEqual((dest / fig).read_bytes(), external.read_bytes())
        external.unlink()
        self.assertNotEqual(
            self.cli("draft", source, self.work / "broken").returncode, 0
        )
        self.assertFalse((self.work / "broken").exists())
        shutil.rmtree(src)
        built = self.cli("build", dest / "deck.json", dest / "portable.pptx")
        self.assertEqual(built.returncode, 0, built.stderr)

    def test_add_text_preserves_blank_native_slide_and_rejects_replay(self):
        prs = Presentation()
        prs.slide_width, prs.slide_height = Inches(10), Inches(7.5)
        prs.slides.add_slide(prs.slide_layouts[6])
        src, dest = self.work / "blank.pptx", self.work / "edited.pptx"
        prs.save(src)
        edit = {
            "slide": 1,
            "op": "add_text",
            "name": "Research title",
            "text": "Editable title",
            "box": [0.1, 0.2, 0.8, 0.3],
            "align": "center",
            "bold": True,
        }
        fill(src, [edit], dest)
        with ZipFile(src) as before, ZipFile(dest) as after:
            self.assertEqual(before.namelist(), after.namelist())
            self.assertEqual(
                [p for p in before.namelist() if before.read(p) != after.read(p)],
                [ordered_parts(before)[0]],
            )
        shape = Presentation(dest).slides[0].shapes[0]
        self.assertEqual(
            (shape.left, shape.top, shape.width, shape.height),
            (Inches(1), Inches(1.5), Inches(8), Inches(2.25)),
        )
        self.assertEqual(shape.text, edit["text"])
        with self.assertRaisesRegex(ValueError, "已存在"):
            fill(dest, [edit], self.work / "duplicate.pptx")
        with self.assertRaisesRegex(ValueError, "画布"):
            fill(src, [dict(edit, box=[0.8, 0, 0.7, 1])], self.work / "outside.pptx")

    def test_projection_reports_source_drift_and_invisible_ink(self):
        path = self.work / "deck.json"
        spec = {
            "mode": "conference",
            "language": "en",
            "slides": [
                {
                    "layout": "cover",
                    "title": "Current title",
                    "eyebrow": "Study",
                    "notes": "Source record",
                }
            ],
        }
        path.write_text(json.dumps(spec))
        deck = self.work / "talk.pptx"
        run = self.cli("build", path, deck)
        self.assertEqual(run.returncode, 0, run.stderr)
        pdf = self.work / "projection.pdf"
        with fitz.open() as doc:
            page = doc.new_page(width=960, height=540)
            page.insert_text((60, 60), "Current title", color=(1, 1, 1))
            page.insert_text((60, 110), "Study")
            doc.save(pdf)
        args = ["check", deck, "--pdf", pdf, "--spec", path]
        run = self.cli(*args, "--overview", self.work / "overview.pdf")
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertIn("possible_low_contrast", [i["code"] for i in result["warnings"]])
        with fitz.open(self.work / "overview.pdf") as overview:
            self.assertIn("Review", overview[0].get_text())
        spec["slides"][0]["title"] = "Updated title"
        path.write_text(json.dumps(spec))
        drift = self.cli(*args)
        self.assertEqual(drift.returncode, 1, drift.stderr)
        self.assertIn(
            "source_text", [i["code"] for i in json.loads(drift.stdout)["errors"]]
        )
        with fitz.open() as doc:
            doc.new_page(width=960, height=540).insert_text((60, 60), "Stale title")
            stale = self.work / "stale.pdf"
            doc.save(stale)
        run = self.cli("check", deck, "--pdf", stale, "--spec", path)
        self.assertIn(
            "pdf_text_missing", [i["code"] for i in json.loads(run.stdout)["errors"]]
        )
        self.assertNotEqual(
            self.cli(*args, "--overview", pdf, "--replace").returncode, 0
        )

    def test_campus_preserves_native_master_or_uses_its_own_starter(self):
        draft = self.work / "quarter"
        self.assertEqual(self.cli("campus", "bza", draft).returncode, 0)
        spec = json.loads((draft / "deck.json").read_text())
        self.assertEqual(spec["slides"][1]["steps"], spec["slides"][2]["steps"])
        self.assertEqual(spec["slides"][2]["active_step"], 2)
        source = draft / "quarter.pptx"
        Deck(spec, draft).build().save(source)
        imported = self.work / "native"
        self.assertEqual(
            self.cli("campus", "tsinghua", imported, "--template", source).returncode, 0
        )
        self.assertEqual((imported / "template.pptx").read_bytes(), source.read_bytes())
        self.assertEqual(
            json.loads((imported / "objects.json").read_text()), inventory(source)
        )
        self.assertNotEqual(self.cli("campus", "bza", draft).returncode, 0)
        fail = self.work / "invalid"
        self.assertNotEqual(
            self.cli(
                "campus", "pku", fail, "--template", draft / "deck.json"
            ).returncode,
            0,
        )
        self.assertFalse(fail.exists())
        spec["slides"][2]["active_step"] = 4
        with self.assertRaisesRegex(ValueError, "active_step"):
            Deck(spec, draft).build()

    def test_reordering_rows_preserves_named_facts_and_chart(self):
        draft, spec = self.start("conference")
        csv_path = draft / "results.csv"
        lines = csv_path.read_text().splitlines()
        csv_path.write_text("\n".join([lines[0], *reversed(lines[1:])]) + "\n")
        out = draft / "talk.pptx"
        Deck(spec, draft).build().save(out)
        page = inventory(out)[3]
        chart = next(obj for obj in page["objects"] if obj["kind"] == "chart")
        series = chart["series"][0]
        pairs = [
            (c["value"], v["value"])
            for c, v in zip(series["categories"], series["values"])
        ]
        self.assertEqual(
            pairs, [("混合检索", "68.5"), ("向量检索", "55.5"), ("关键词", "42.0")]
        )
        labels = " ".join(
            t for obj in page["objects"] for t in obj.get("paragraphs", [])
        )
        self.assertIn("68.5%", labels)
        self.assertIn("13.0 个百分点", labels)
        self.assertIn("results.csv", page["notes"])
        with ZipFile(out) as z:
            xml = etree.fromstring(z.read("ppt/charts/chart1.xml"))
            self.assertEqual(
                xml.xpath(
                    '//*[local-name()="dLbls"]/*[local-name()="numFmt"]/@formatCode'
                ),
                ["0.0"],
            )
            self.assertTrue(any(f.endswith(".xlsx") for f in z.namelist()))

    def test_acceptance_fails_for_missing_evidence_in_passing_row(self):
        draft, spec = self.start("acceptance")
        file = draft / "tests.csv"
        file.write_text(
            file.read_text().replace("待补演练记录,待验证", "待补演练记录,达到")
        )
        with self.assertRaisesRegex(ValueError, "T-03"):
            Sources(spec, draft)
        del spec["datasets"]["tests"]["evidence_rule"]
        with self.assertRaisesRegex(ValueError, "T-03"):
            Sources(spec, draft)

    def test_status_count_and_highlight_follow_replaced_ledger(self):
        draft, spec = self.start("acceptance")
        (draft / "tests.csv").write_text(
            "测试编号,要求,实测记录,证据位置,判定\nR1,成功率 ≥ 70%,72.5%,L1,达到\nR2,耗时 ≤ 20 min,无记录,待补日志,待验证\n"
        )
        out = draft / "report.pptx"
        Deck(spec, draft).build().save(out)
        result = json.dumps(inventory(out), ensure_ascii=False)
        self.assertIn("1 项指标达到要求，1 项待验证", result)
        self.assertIn("72.5%", result)
        self.assertNotIn("T-03", result)
        spec["slides"][4]["highlight"] = ["no-such-row"]
        with self.assertRaisesRegex(ValueError, "no-such-row"):
            Deck(spec, draft).build()

    def test_wrong_keys_and_duplicate_csv_rows(self):
        draft, spec = self.start("conference")
        spec["facts"]["best"]["row"] = "未找到的方法"
        with self.assertRaisesRegex(ValueError, "scores.*未找到的方法"):
            Sources(spec, draft)
        p = draft / "results.csv"
        with p.open("a") as f:
            f.write("关键词,91,92\n")
        with self.assertRaisesRegex(ValueError, "重复"):
            Sources(spec, draft)

    def test_fill_preserves_unchanged_zip_parts_and_checks_expected_text(self):
        draft, spec = self.start("acceptance")
        original = draft / "old.pptx"
        revised = draft / "new.pptx"
        Deck(spec, draft).build().save(original)
        tab = next(
            obj for obj in inventory(original)[4]["objects"] if obj["kind"] == "table"
        )
        edit = {
            "slide": 5,
            "id": tab["id"],
            "cell": [1, 0],
            "expect": "T-01",
            "text": "R1",
        }
        fill(original, [edit], revised)
        result = next(
            obj for obj in inventory(revised)[4]["objects"] if obj["kind"] == "table"
        )
        self.assertEqual(result["cells"][1][0], "R1")
        with ZipFile(original) as before, ZipFile(revised) as after:
            self.assertEqual(before.namelist(), after.namelist())
            changed = [
                name
                for name in before.namelist()
                if before.read(name) != after.read(name)
            ]
            self.assertEqual(changed, [ordered_parts(before)[4]])
        with self.assertRaisesRegex(ValueError, "expect"):
            fill(revised, [edit], draft / "failure.pptx")
        self.assertFalse((draft / "failure.pptx").exists())

    def test_output_protection_and_failed_build(self):
        draft, spec = self.start("progress")
        inp = draft / "deck.json"
        out = draft / "report.pptx"
        out.write_bytes(b"existing")
        self.assertNotEqual(self.cli("build", inp, out).returncode, 0)
        self.assertEqual(out.read_bytes(), b"existing")
        spec["slides"][1]["title"] = "{{unknown_fact}}"
        inp.write_text(json.dumps(spec))
        run = self.cli("build", inp, out, "--replace")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("unknown_fact", run.stderr)
        self.assertEqual(out.read_bytes(), b"existing")
        self.assertNotEqual(self.cli("starter", "progress", draft).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
