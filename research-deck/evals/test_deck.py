"""Exercise data binding, starter generation, editability and safe output boundaries."""

import json
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
from pptx.util import Inches

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from data import Sources
from checks import video_parts
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
