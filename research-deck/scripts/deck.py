#!/usr/bin/env python3
"""Local CLI for research-deck."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import BadZipFile

from native import fill, inventory
from render import ASSETS, LAYOUTS, MODES, STYLES, Deck


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def starter(mode, dest, style):
    library = ASSETS / "starters"
    spec = read_json(library / (mode + ".json"))
    if style:
        spec["style"] = style
    files = {d["file"] for d in spec.get("datasets", {}).values()}
    files.update(p["file"] for p in spec["slides"] if "file" in p)
    dest = dest.expanduser().absolute()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise ValueError(f"起稿目录已存在，请使用新目录：{dest}")
    with tempfile.TemporaryDirectory(prefix=".starter-", dir=dest.parent) as tmp:
        draft = Path(tmp) / "draft"
        draft.mkdir()
        for name in sorted(files):
            shutil.copyfile(library / name, draft / name)
        (draft / "deck.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        draft.rename(dest)
    print(dest / "deck.json")


def publish(dest, replace, fn, sources):
    dest = dest.expanduser().absolute()
    if dest.resolve() in {p.resolve() for p in sources}:
        raise ValueError("输出不能覆盖输入文件")
    if dest.exists() and not replace:
        raise ValueError(f"输出已存在：{dest}。改用新路径，或指定 --replace")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".research-deck-", dir=dest.parent) as tmp:
        ready = Path(tmp) / dest.name
        fn(ready)
        if replace:
            os.replace(ready, dest)
        else:
            os.link(ready, dest)
    print(dest)


def preview(src, dest):
    import fitz

    cmd = shutil.which("soffice")
    if not cmd:
        raise ValueError("PDF 预览需要 LibreOffice soffice")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        result = subprocess.run(
            [
                cmd,
                "-env:UserInstallation=" + (work / "profile").as_uri(),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(work),
                str(src.resolve()),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        out = work / (src.stem + ".pdf")
        if result.returncode or not out.is_file():
            raise ValueError(f"LibreOffice 渲染失败：{result.stdout} {result.stderr}")
        with fitz.open(out) as pdf:
            if len(pdf) == 0:
                raise ValueError("渲染未产生任何页面")
        shutil.copyfile(out, dest)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="action", required=True)
    sub.add_parser("catalog", help="列出模式、默认风格和页型")
    start = sub.add_parser("starter", help="从完整模式样稿创建独立工作目录")
    start.add_argument("mode", choices=MODES)
    start.add_argument("directory", type=Path)
    start.add_argument("--style", choices=STYLES)
    inspect = sub.add_parser("inspect", help="读取 PPTX 页序、对象 ID 与文本")
    inspect.add_argument("input", type=Path)
    for name in ("build", "fill", "preview"):
        p = sub.add_parser(name)
        p.add_argument("input", type=Path)
        if name == "fill":
            p.add_argument("plan", type=Path)
        p.add_argument("output", type=Path)
        p.add_argument("--replace", action="store_true", help="允许替换指定的已有输出")
        if name == "build":
            p.add_argument("--style", choices=STYLES)
    args = cli.parse_args()
    if args.action == "starter":
        starter(args.mode, args.directory, args.style)
        return
    if args.action == "catalog":
        print(
            json.dumps(
                {
                    "modes": MODES,
                    "styles": {k: v["name"] for k, v in STYLES.items()},
                    "layouts": LAYOUTS,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.action == "inspect":
        print(json.dumps(inventory(args.input), ensure_ascii=False, indent=2))
        return
    ext = ".pdf" if args.action == "preview" else ".pptx"
    if args.output.suffix.lower() != ext:
        raise ValueError("输出文件扩展名应为 " + ext)
    sources = [args.input]
    if args.action == "build":
        spec = read_json(args.input)
        dirname = args.input.resolve().parent
        sources.extend(dirname / d["file"] for d in spec.get("datasets", {}).values())
        sources.extend(dirname / p["file"] for p in spec["slides"] if p.get("file"))
        fn = lambda target: Deck(spec, dirname, args.style).build().save(target)
    elif args.action == "fill":
        sources.append(args.plan)
        edits = read_json(args.plan)["edits"]
        fn = lambda target: fill(args.input, edits, target)
    else:
        fn = lambda target: preview(args.input, target)
    publish(args.output, args.replace, fn, sources)


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        AttributeError,
        OSError,
        BadZipFile,
        subprocess.SubprocessError,
    ) as exc:
        print(f"research-deck: {exc}", file=sys.stderr)
        sys.exit(2)
