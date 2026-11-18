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


def render_showcase(fonts):
    def font(name, size):
        return ImageFont.truetype(str(fonts / (name + ".ttf")), size)

    paper, ink, muted = "#F3F2EC", "#192D2B", "#415653"
    hero = Image.new("RGB", (1600, 690), paper)
    draw = ImageDraw.Draw(hero)
    draw.text((49, 22), "AwesomePPT", font=font("DejaVuSans-Bold", 86), fill=ink)
    draw.multiline_text(
        (1010, 41),
        "Editable academic talks\nand project reviews",
        font=font("DejaVuSans", 35),
        spacing=5,
        fill=ink,
    )
    draw.line((54, 153, 1546, 153), fill="#B7C3B9", width=2)
    for x, stem, label in (
        (54, "iris", "RESEARCH TALK  /  UCI IRIS"),
        (818, "project-review", "PROJECT REVIEW  /  ARCHIVE SEARCH"),
    ):
        shot = slide_image(DECKS / (stem + ".pdf"), 0, 728)
        hero.paste(shot, (x, 185))
        draw.rectangle(
            (x - 1, 184, x + shot.width, 185 + shot.height), outline="#C0C8C0", width=1
        )
        draw.text((x, 620), label, font=font("DejaVuSansMono", 21), fill=muted)
    hero.save(MEDIA / "awesome-ppt.png", optimize=True)


def render(fonts):
    render_showcase(fonts)
    render_grid(fonts, MODES, "modes.png")
    render_grid(
        fonts,
        [
            ("sjtu-review", "SJTU / Opening", 0),
            ("sjtu-review", "Deliverables", 5),
            ("sjtu-review", "Acceptance evidence", 7),
            ("bza-quarterly", "BZA / Opening", 0),
            ("bza-quarterly", "Quarterly roadmap", 2),
            ("bza-quarterly", "Milestone review", 4),
        ],
        "campuses.png",
    )


def render_grid(fonts, entries, output_name):
    cream, ink = "#F5F2E9", "#173A37"
    gallery = Image.new("RGB", (1536, 694), cream)
    draw = ImageDraw.Draw(gallery)
    with tempfile.TemporaryDirectory() as tmp:
        for i, (mode, label, page) in enumerate(entries):
            pdf = Path(tmp) / (mode + ".pdf")
            if not pdf.exists():
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
            draw.text(
                (x, y),
                label,
                font=ImageFont.truetype(str(fonts / "DejaVuSerif.ttf"), 25),
                fill=ink,
            )
            gallery.paste(shot, (x, y + 44))
            draw.rectangle(
                (x - 1, y + 43, x + shot.width, y + 44 + shot.height),
                outline="#BCC7C0",
                width=1,
            )
    gallery.save(MEDIA / output_name, optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fonts",
        type=Path,
        default=Path("/usr/share/fonts/truetype/dejavu"),
        help="Directory containing DejaVuSans, DejaVuSansMono and DejaVuSerif TTFs",
    )
    render(parser.parse_args().fonts)
