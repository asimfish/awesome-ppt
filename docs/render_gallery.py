"""Render the README artwork from the project's editable PowerPoint examples."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs/media"
DECKS = ROOT / "docs/decks"
MODES = [
    ("journal-club", "Journal club", 4),
    ("conference", "Conference talk", 3),
    ("defense", "Research defense", 2),
    ("progress", "Project update", 2),
    ("acceptance", "Acceptance review", 4),
    ("demo", "Project demo", 3),
]


def slide_image(pdf_path, index, width):
    with fitz.open(pdf_path) as pdf:
        page = pdf[index]
        scale = width / page.rect.width
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def render(fonts):
    def font(name, size):
        return ImageFont.truetype(str(fonts / (name + ".ttf")), size)

    cream, ink, green = "#F5F2E9", "#173A37", "#0E5950"
    hero = Image.new("RGB", (1600, 640), cream)
    draw = ImageDraw.Draw(hero)
    draw.rectangle((0, 0, 600, 639), fill=ink)
    draw.line((65, 104, 529, 104), fill="#729087", width=2)
    draw.text(
        (62, 59),
        "RESEARCH PRESENTATIONS",
        font=font("DejaVuSansMono", 24),
        fill="#ACCDC1",
    )
    draw.text((58, 178), "CiteSlide", font=font("DejaVuSerif", 103), fill="#FCF9EE")
    draw.multiline_text(
        (66, 337),
        "From source data to an\neditable PowerPoint talk.",
        font=font("DejaVuSans", 33),
        spacing=12,
        fill="#D6E6DC",
    )
    draw.line((65, 530, 529, 530), fill="#729087", width=2)
    draw.text(
        (65, 556),
        "AGENT SKILL  /  RESEARCH-DECK",
        font=font("DejaVuSansMono", 20),
        fill="#ACCDC1",
    )
    shot = slide_image(DECKS / "iris.pdf", 2, 840)
    draw.text(
        (677, 40), "FIG. 01   /   UCI IRIS", font=font("DejaVuSansMono", 23), fill=green
    )
    hero.paste(shot, (677, 91))
    draw.rectangle(
        (676, 90, 677 + shot.width, 91 + shot.height), outline="#BAC8BA", width=2
    )
    draw.text(
        (677, 586),
        "Rendered from the editable example deck",
        font=font("DejaVuSans", 22),
        fill="#37564F",
    )
    hero.save(MEDIA / "citeslide.png", optimize=True)

    gallery = Image.new("RGB", (1536, 694), cream)
    draw = ImageDraw.Draw(gallery)
    with tempfile.TemporaryDirectory() as tmp:
        for i, (mode, label, page) in enumerate(MODES):
            pdf = Path(tmp) / (mode + ".pdf")
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "research-deck/scripts/deck.py"),
                    "preview",
                    str(DECKS / (mode + ".pptx")),
                    str(pdf),
                ],
                check=True,
            )
            shot = slide_image(pdf, page, 472)
            x, y = 33 + i % 3 * 500, 20 + i // 3 * 336
            draw.text((x, y), label, font=font("DejaVuSerif", 25), fill=ink)
            gallery.paste(shot, (x, y + 44))
            draw.rectangle(
                (x - 1, y + 43, x + shot.width, y + 44 + shot.height),
                outline="#BCC7C0",
                width=1,
            )
    gallery.save(MEDIA / "modes.png", optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fonts",
        type=Path,
        default=Path("/usr/share/fonts/truetype/dejavu"),
        help="Directory containing DejaVuSans, DejaVuSansMono and DejaVuSerif TTFs",
    )
    render(parser.parse_args().fonts)
