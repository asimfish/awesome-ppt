#!/usr/bin/env python3
"""Local CLI for research-deck."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from zipfile import BadZipFile

from data import DATA_LAYOUTS, required
from native import fill, inventory
from render import ASSETS, LAYOUTS, MODES, STYLES, Deck


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


CAMPUSES = read_json(ASSETS / "campuses.json")


def campus_key(value):
    query = value.strip().casefold()
    for key, entry in CAMPUSES.items():
        names = (key, entry["name"], entry["en"], *entry.get("aliases", []))
        if any(query == name.casefold() for name in names):
            return key
    raise argparse.ArgumentTypeError("未知学校，请通过 catalog 查看可用学校 ID")


@contextmanager
def new_draft(dest):
    dest = dest.expanduser().absolute()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise ValueError(f"起稿目录已存在，请使用新目录：{dest}")
    with tempfile.TemporaryDirectory(prefix=".starter-", dir=dest.parent) as tmp:
        draft = Path(tmp) / "draft"
        draft.mkdir()
        yield draft
        draft.rename(dest)


def write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def page_asset_fields(page):
    layout = page.get("layout")
    auto = layout in (None, "auto")
    if "file" in page:
        yield page, "file"
    if layout == "video" or (auto and "poster" in page):
        yield page, "poster"
    if layout == "evidence_pair" or (auto and any(
        "file" in page.get(side, {}) for side in ("left", "right")
    )):
        required(page, ["left", "right"])
        for panel in (page["left"], page["right"]):
            required(panel, ["file"])
            yield panel, "file"
    if layout == "condition_comparison" or (auto and "conditions" in page):
        for panel in page["conditions"].values():
            required(panel, ["file"])
            yield panel, "file"
    if "plate" in page:
        yield page["plate"], "file"


def asset_fields(spec):
    for dataset in spec.get("datasets", {}).values():
        yield dataset, "file"
    for page in spec["slides"]:
        yield from page_asset_fields(page)
    stationery = spec.get("stationery", {})
    for key in stationery:
        yield stationery, key


def copy_draft(spec_path, dest, style=None, shared=None):
    spec = read_json(spec_path)
    if style:
        spec["style"] = style
    root = spec_path.resolve().parent
    refs = []
    targets = {}
    used = {"deck.json"}
    for obj, key in asset_fields(spec):
        name = Path(obj[key])
        candidate = (root / name).resolve(strict=False)
        if shared and not candidate.is_file():
            candidate = (shared / name).resolve(strict=False)
        if not candidate.is_file():
            raise ValueError(f"工作稿素材不存在：{obj[key]}")
        refs.append((obj, key, candidate))
        for base in (root, shared):
            if base and candidate.is_relative_to(base):
                relative = candidate.relative_to(base)
                folded = relative.as_posix().casefold()
                if folded not in used and relative.parts[0].casefold() != "deck.json":
                    targets[candidate] = relative
                    used.add(folded)
                break
    top_level = {name.parts[0].casefold() for name in targets.values()}
    import_dir = "_imported"
    while import_dir in top_level:
        import_dir += "_"
    index = 0
    for obj, key, source in refs:
        if source not in targets:
            index += 1
            targets[source] = Path(import_dir, str(index), source.name)
        obj[key] = targets[source].as_posix()
    with new_draft(dest) as draft:
        for source, name in targets.items():
            target = draft / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        write_json(draft / "deck.json", spec)
    print(dest / "deck.json")


def starter(mode, dest, style, library=None):
    shared = ASSETS / "starters"
    copy_draft((library or shared) / (mode + ".json"), dest, style, shared)


def storyboard(spec, directory, style=None):
    deck = Deck(spec, directory, style)
    report = {
        "mode": spec["mode"], "audience_question": deck.mode["question"],
        "style": style or spec.get("style", deck.mode["style"]), "slides": [],
    }
    for index, p in enumerate(deck.pages, 1):
        files = [obj[key] for obj, key in page_asset_fields(p)]
        if p["layout"] == "condition_comparison":
            _, records = deck.sources.condition_records(p)
            files = [image["file"] for _, image in records]
        page = {
            "page": index, "title": p["title"], "layout": p["layout"],
            "reason": p["layout_reason"], "sources": p["citations"], "files": files,
        }
        missing = [name for name in files if not (directory / name).is_file()]
        if missing:
            page["missing_files"] = missing
        if p["layout"] in DATA_LAYOUTS:
            heads, rows = deck.sources.select(p)
            page["dataset"] = p["dataset"]
            if len(rows) <= 12:
                page["rows"] = [row[0] for row in rows]
            else:
                page["row_count"] = len(rows)
                page["first_rows"] = [row[0] for row in rows[:4]]
            page["columns"] = heads[1:]
        report["slides"].append(page)
    return report


def campus(key, dest, template):
    entry = CAMPUSES[key]
    if dest is None:
        if template is not None:
            raise ValueError("--template 需要指定新工作目录")
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return
    if template is None:
        if "starter" not in entry:
            raise ValueError(
                f"请从校方获取 PPTX 后通过 --template 提供：{entry['url']}"
            )
        starter(entry["starter"], dest, None, ASSETS / "campuses")
        return
    if template.suffix.lower() != ".pptx":
        raise ValueError(
            "原生模板请提供 .pptx；.ppt 或 .potx 可在 PowerPoint 中另存为 .pptx"
        )
    with new_draft(dest) as draft:
        shutil.copyfile(template, draft / "template.pptx")
        write_json(draft / "objects.json", inventory(draft / "template.pptx"))
        write_json(draft / "edits.json", {"edits": []})
    print(dest / "template.pptx")


def publish(dest, replace, fn, sources, announce=True):
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
    if announce:
        print(dest)


def preview(src, dest):
    from pdf_api import fitz

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
    story = sub.add_parser("storyboard", help="在构建前查看逐页选型、依据、数据行与素材")
    story.add_argument("input", type=Path)
    story.add_argument("--style", choices=STYLES)
    start = sub.add_parser("starter", help="从完整模式样稿创建独立工作目录")
    start.add_argument("mode", choices=MODES)
    start.add_argument("directory", type=Path)
    start.add_argument("--style", choices=STYLES)
    draft = sub.add_parser("draft", help="从已有逐页稿和引用的素材创建独立工作目录")
    draft.add_argument("input", type=Path)
    draft.add_argument("directory", type=Path)
    school = sub.add_parser("campus", help="查询高校来源、创建专用起稿或导入原生 PPTX")
    school.add_argument("institution", type=campus_key, metavar="学校简称、全称或ID")
    school.add_argument("directory", nargs="?", type=Path)
    school.add_argument(
        "--template", type=Path, help="从持有的学校 PPTX 创建保留母版的工作副本"
    )
    inspect = sub.add_parser("inspect", help="读取 PPTX 页序、对象 ID 与文本")
    inspect.add_argument("input", type=Path)
    compare = sub.add_parser("compare", help="将承担同一讲解任务的原版和新版 PDF 页并排")
    compare.add_argument("original", type=Path)
    compare.add_argument("revision", type=Path)
    compare.add_argument("output", type=Path)
    compare.add_argument("--pairs", nargs="+", required=True, metavar="原页:新页")
    compare.add_argument("--replace", action="store_true")
    check = sub.add_parser("check", help="核对成稿、源数据和投影文字，报告需目检的页码")
    check.add_argument("input", type=Path)
    check.add_argument("--spec", type=Path, help="用于生成该 PPTX 的逐页稿")
    check.add_argument("--pdf", type=Path, help="核对已有 PDF，省略时临时渲染当前 PPTX")
    check.add_argument("--style", choices=STYLES, help="复现 build 的风格覆盖")
    check.add_argument("--overview", type=Path, help="将实际投影页排成六页一览的 PDF")
    check.add_argument("--replace", action="store_true", help="允许更新已有的概览 PDF")
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
    if args.action == "storyboard":
        report = storyboard(read_json(args.input), args.input.resolve().parent, args.style)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.action == "campus":
        campus(args.institution, args.directory, args.template)
        return
    if args.action == "starter":
        starter(args.mode, args.directory, args.style)
        return
    if args.action == "draft":
        copy_draft(args.input, args.directory)
        return
    if args.action == "catalog":
        print(
            json.dumps(
                {
                    "modes": MODES,
                    "styles": {k: v["name"] for k, v in STYLES.items()},
                    "layouts": LAYOUTS,
                    "campuses": CAMPUSES,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.action == "inspect":
        print(json.dumps(inventory(args.input), ensure_ascii=False, indent=2))
        return
    if args.action in ("check", "compare"):
        from pdf_api import fitz

        # A video poster can have an unsupported PDF screen annotation.
        # Send diagnostics to stderr so callers can consume the report or path.
        if hasattr(fitz, "set_messages"):
            fitz.set_messages(stream=sys.stderr)
    if args.action == "compare":
        from checks import compare_layouts

        if args.output.suffix.lower() != ".pdf":
            cli.error("compare 需要 .pdf 输出路径")
        publish(
            args.output,
            args.replace,
            lambda path: compare_layouts(args.original, args.revision, args.pairs, path),
            [args.original, args.revision],
        )
        return
    if args.action == "check":
        from checks import check, overview

        if args.style and not args.spec:
            cli.error("--style 需要与 --spec 一起使用")
        if args.overview and args.overview.suffix.lower() != ".pdf":
            cli.error("--overview 需要 .pdf 输出路径")
        spec = read_json(args.spec) if args.spec else None
        directory = args.spec.resolve().parent if args.spec else None
        with tempfile.TemporaryDirectory() as scratch:
            pdf = args.pdf or Path(scratch) / "preview.pdf"
            if args.pdf is None:
                preview(args.input, pdf)
            result = check(args.input, pdf, spec, directory, args.style)
            if args.overview:
                inputs = [args.input, pdf]
                if spec is not None:
                    inputs.append(args.spec)
                    inputs.extend(
                        directory / obj[key] for obj, key in asset_fields(spec)
                    )
                publish(
                    args.overview,
                    args.replace,
                    lambda target: overview(
                        pdf,
                        target,
                        result["pdf_slides"],
                        result["errors"] + result["warnings"],
                    ),
                    inputs,
                    announce=False,
                )
                result["overview"] = str(args.overview.absolute())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["ok"]:
            sys.exit(1)
        return
    ext = ".pdf" if args.action == "preview" else ".pptx"
    if args.output.suffix.lower() != ext:
        raise ValueError("输出文件扩展名应为 " + ext)
    sources = [args.input]
    if args.action == "build":
        spec = read_json(args.input)
        dirname = args.input.resolve().parent
        sources.extend(dirname / obj[key] for obj, key in asset_fields(spec))
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
