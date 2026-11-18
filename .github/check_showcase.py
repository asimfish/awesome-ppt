"""Check that the published talk, the source table and a fresh build agree."""

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "research-deck"
sys.path.insert(0, str(SKILL / "scripts"))
from native import inventory


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], check=True)


def verify_talk(deck, expected, observations):
    pages = inventory(deck)
    assert len(pages) == 5 and all(p["notes"] for p in pages), deck
    series = next(o["series"][0] for o in pages[2]["objects"] if o["kind"] == "chart")
    actual = [
        (k["value"], float(v["value"]))
        for k, v in zip(series["categories"], series["values"])
    ]
    assert actual == expected, (deck, actual)
    assert any(o["kind"] == "table" for o in pages[3]["objects"]), deck
    assert "10.24432/C56C76" in pages[2]["notes"], deck
    names = {o["name"] for o in pages[1]["objects"] if " · " in o["name"]}
    assert names == {
        f"{r['Specimen']} · {r['Species']} · {r['Petal length (cm)']}"
        for r in observations
    }, deck
    assert "The Botanical Magazine" in pages[0]["notes"]


def verify_project(work, cli):
    source = ROOT / "examples/project-review"
    pptx, pdf = work / "project-review.pptx", work / "project-review.pdf"
    run(cli, "build", source / "deck.json", pptx)
    assert inventory(pptx) == inventory(ROOT / "docs/decks" / pptx.name)
    with (source / "pilot.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for deck in (pptx, ROOT / "docs/decks" / pptx.name):
        grid = Presentation(deck).slides[1]
        for row in rows:
            cells = [s for s in grid.shapes if s.name.startswith(row["轮次"] + " · ")]
            assert len(cells) == int(row["任务总数"])
            colors = [s.fill.fore_color.rgb for s in cells]
            assert len(set(colors)) == 2 and colors.count(colors[0]) == int(
                row["命中任务"]
            )
    run(cli, "preview", pptx, pdf)
    for path in (pdf, ROOT / "docs/decks" / pdf.name):
        with fitz.open(path) as document:
            assert len(document) == 5
            for idx, labels in (
                (0, ["74/80"]),
                (1, ["66/80", "74/80"]),
                (4, ["90", "R-04"]),
            ):
                projected = "".join(document[idx].get_text().split())
                assert all(label in projected for label in labels), (
                    path,
                    idx,
                    projected,
                )


def verify_pdf(path):
    with fitz.open(path) as pdf:
        assert len(pdf) == 5, path
        chart = " ".join(pdf[2].get_text().split())
        for label in ("5.55", "4.26", "1.46", "1.29", "10.24432/C56C76"):
            assert label in chart, (path, label, chart)


def main():
    iris = ROOT / "examples/iris"
    cli = SKILL / "scripts/deck.py"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        summary = work / "summary.csv"
        specimens = work / "observations.csv"
        run(iris / "summarize.py", summary, "--observations", specimens)
        assert specimens.read_bytes() == (iris / "observations.csv").read_bytes()
        with specimens.open(encoding="utf-8", newline="") as stream:
            observations = list(csv.DictReader(stream))
        assert summary.read_bytes() == (iris / "summary.csv").read_bytes()
        with summary.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert sum(int(row["Plants"]) for row in rows) == 150
        expected = [(r["Species"], float(r["Mean (cm)"])) for r in rows]
        result = work / "iris.pptx"
        run(cli, "build", iris / "deck.json", result)
        verify_talk(result, expected, observations)
        verify_talk(ROOT / "docs/decks/iris.pptx", expected, observations)
        run(cli, "preview", result, work / "iris.pdf")
        verify_pdf(work / "iris.pdf")
        verify_pdf(ROOT / "docs/decks/iris.pdf")
        verify_project(work, cli)
        # Rebuild every advertised starter and compare its native contents to the shipped slide deck.
        for spec in sorted((SKILL / "assets/starters").glob("*.json")):
            outputs = work / (spec.stem + ".pptx")
            run(cli, "build", spec, outputs)
            assert inventory(outputs) == inventory(
                ROOT / "docs/decks" / outputs.name
            ), spec.stem
        for campus, name in (("sjtu", "sjtu-review"), ("bza", "bza-quarterly")):
            draft = work / campus
            run(cli, "campus", campus, draft)
            output = draft / "talk.pptx"
            run(cli, "build", draft / "deck.json", output)
            assert inventory(output) == inventory(
                ROOT / "docs/decks" / (name + ".pptx")
            ), campus
            run(cli, "preview", output, draft / "talk.pdf")
            with fitz.open(draft / "talk.pdf") as pdf:
                assert len(pdf) == len(inventory(output))
    print("Both showcase decks, six general starters and two campus decks verified.")


if __name__ == "__main__":
    main()
