"""Resolve source tables and named facts before writing any slide."""

import csv
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit


DATA_LAYOUTS = {"table", "chart", "dotplot", "unitgrid", "condition_comparison"}


def required(obj, keys):
    for key in keys:
        if key not in obj or obj[key] is None or obj[key] == "":
            raise ValueError(f"缺少字段 {key}")


def number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"需要明确的十进制数值，收到 {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"数值必须有限：{value!r}")
    return result


def precision(value):
    if type(value) is not int or not 0 <= value <= 6:
        raise ValueError("decimals 需要 0 到 6 的整数")
    return value


class Sources:
    def __init__(self, spec, directory):
        self.mode = spec.get("mode")
        self.references = {}
        bibliography = spec.get("bibliography", {})
        if not isinstance(bibliography, dict):
            raise ValueError("bibliography 需要用文献键关联各条记录")
        for index, (key, entry) in enumerate(bibliography.items(), 1):
            if not isinstance(entry, dict):
                raise ValueError(f"bibliography {key} 需要题名、署名和链接")
            required(entry, ["title", "byline", "url"])
            if any(not isinstance(entry[field], str) or not entry[field].strip() for field in ("title", "byline", "url")):
                raise ValueError(f"bibliography {key} 的题名、署名和链接必须是非空文本")
            url = urlsplit(entry["url"])
            if "short_title" in entry and (not isinstance(entry["short_title"], str) or not entry["short_title"].strip()):
                raise ValueError(f"bibliography {key} 的 short_title 必须是非空文本")
            if url.scheme not in ("https", "http") or not url.hostname:
                raise ValueError(f"bibliography {key} 需要完整的 HTTP(S) 文献链接")
            self.references[key] = dict(entry, number=index)
        self.tables = {}
        self.facts = {}
        for name, item in spec.get("datasets", {}).items():
            required(item, ["file", "key", "source"])
            path = (directory / item["file"]).resolve()
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                headers = reader.fieldnames or []
                if (
                    item["key"] not in headers
                    or len(set(headers)) != len(headers)
                    or "" in headers
                ):
                    raise ValueError(f"{name}: CSV 表头无效")
                rows = {}
                for line, row in enumerate(reader, 2):
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError(f"{name}:{line} 列数不匹配")
                    key = row[item["key"]]
                    if not key.strip() or key in rows:
                        raise ValueError(f"{name}:{line} 行键为空或重复")
                    rows[key] = row
                rule = item.get("evidence_rule")
                if (
                    not rule
                    and spec.get("mode") == "acceptance"
                    and {"判定", "证据位置"} <= set(headers)
                ):
                    measured = next(
                        (h for h in ("实测记录", "实测值", "实测结果") if h in headers),
                        None,
                    )
                    if measured:
                        rule = {
                            "status": "判定",
                            "measured": measured,
                            "record": "证据位置",
                        }
                if rule:
                    self.check_evidence(name, headers, rows, rule)
                self.tables[name] = (item, headers, rows)
        for name, fact in spec.get("facts", {}).items():
            required(fact, ["dataset"])
            item, headers, rows = self.tables[fact["dataset"]]
            if "count_where" in fact:
                condition = fact["count_where"]
                required(condition, ["column", "equals"])
                if condition["column"] not in headers:
                    raise ValueError("计数条件使用了未知列")
                count = sum(
                    row[condition["column"]] == condition["equals"]
                    for row in rows.values()
                )
                self.facts[name] = (str(count) + fact.get("unit", ""), item["source"])
                continue
            required(fact, ["row", "column"])
            if fact["column"] not in headers:
                raise ValueError(
                    f"fact {name}：数据集 {fact['dataset']} 中没有列 {fact['column']}"
                )
            for field in ("row", "minus_row"):
                if field in fact and fact[field] not in rows:
                    raise ValueError(
                        f"fact {name}：数据集 {fact['dataset']} 中没有行键 {fact[field]}"
                    )
            val = number(rows[fact["row"]][fact["column"]])
            if "minus_row" in fact:
                val -= number(rows[fact["minus_row"]][fact["column"]])
            decimals = precision(fact.get("decimals", 1))
            self.facts[name] = (
                f"{val:.{decimals}f}" + fact.get("unit", ""),
                item["source"],
            )

    @staticmethod
    def check_evidence(name, headers, rows, rule):
        required(rule, ["status", "measured", "record"])
        fields = [rule[k] for k in ("status", "measured", "record")]
        if any(field not in headers for field in fields):
            raise ValueError(f"{name}：验收证据规则所指列与 CSV 表头不一致")
        passing = rule.get(
            "passing", ["达到", "已达到", "通过", "合格", "达标", "pass", "passed"]
        )
        missing = {"", "-", "—", "/", "n/a", "none", "unknown", "not recorded"}
        passing_values = {s.casefold() for s in passing}
        for key, row in rows.items():
            if row[rule["status"]].strip().casefold() not in passing_values:
                continue
            for col in fields[1:]:
                value = row[col].strip().casefold()
                if (
                    value in missing
                    or any(
                        t in value
                        for t in (
                            "无记录",
                            "无实测",
                            "无证据",
                            "未提供",
                            "未测试",
                            "未验证",
                        )
                    )
                    or value.startswith(("待补", "待测", "待验证", "缺失", "尚缺"))
                ):
                    raise ValueError(
                        f"{name} / {key}：判定为 {row[fields[0]]}，但 {col} 缺少记录"
                    )

    def choose_layout(self, page):
        if page.get("layout") not in (None, "auto"):
            return page["layout"], "沿用逐页稿指定的页型"
        options = []
        for fields, layout, reason in (
            (("plate", "metrics", "subtitle", "credit"), "cover", "封面信息或开场图版"),
            (("stages",), "handoff", "逐阶段列出责任方、操作与产物"),
            (("steps",), "process", "需要按顺序解释一组操作"),
            (("frames",), "sequence", "按时间顺序解读连续观测"),
            (("papers",), "reading_guide", "列出选读文献及其在正文中的页次"),
            (("lead", "points"), "argument", "判断及其支持理由"),
            (("latex",), "equation", "解释数学表达式"),
            (("takeaway", "items"), "decision", "结论及待讨论或执行事项"),
            (("value", "label"), "spotlight", "突出一个有含义的量或决定"),
        ):
            if any(field in page for field in fields):
                options.append((layout, reason))
        if "left" in page or "right" in page:
            required(page, ["left", "right"])
            panels = (page["left"], page["right"])
            if any("file" in panel for panel in panels):
                options.append(("evidence_pair", "同页比较两份原始图件"))
            else:
                options.append(("contrast", "对照两组文字说明"))
        if any(field in page for field in ("file", "poster", "region")):
            if "poster" in page or str(page.get("file", "")).lower().endswith(".mp4"):
                options.append(("video", "操作回放及其代表帧"))
            elif "region" in page:
                options.append(("detail", "在完整图件上定位并放大选区"))
            else:
                options.append(("figure", "讲解一份原始图件"))
        if "dataset" in page or "conditions" in page:
            required(page, ["dataset", "columns"])
            if "conditions" in page:
                options.append(("condition_comparison", "按同一行键展示条件图与测量记录"))
            else:
                options.append(self.dataset_layout(page))
        if len(options) == 1:
            return options[0]
        if options:
            names = "、".join(layout for layout, _ in options)
            raise ValueError(f"本页材料同时支持 {names}，请按讲解目的指定 layout 或拆页")
        raise ValueError("本页缺少选型依据，请补入图件、数据或论述，或明确指定 layout")

    def dataset_layout(self, page):
        heads, rows = self.select(page)
        table_hints = any(k in page for k in ("highlight", "highlight_where", "widths"))
        chart_hints = any(k in page for k in ("kind", "reading", "axis_title"))
        if table_hints and chart_hints:
            raise ValueError("同页包含表格与图表的显示要求，请指定 layout 或拆页")
        if chart_hints and (len(rows) > 8 or len(heads) > 4):
            raise ValueError("图表的数据超出单页范围，请精选 rows 或 columns")
        if table_hints:
            reason = "逐项核对记录或指定行"
        elif self.mode == "acceptance" and not chart_hints:
            reason = "验收时按行核对指标及其记录"
        elif len(rows) <= 8 and len(heads) <= 4:
            try:
                for row in rows:
                    for value in row[1:]:
                        number(value)
            except ValueError:
                if chart_hints:
                    raise ValueError("图表所选列包含文字或缺测项，请核对指标或使用 table")
                reason = "所选记录包含文字或缺测标记"
            else:
                return "chart", "在共同坐标下比较数值"
        else:
            reason = "按行呈现所选记录"
        if len(rows) > 9 or len(heads) > 6:
            raise ValueError("明细超出单页表格范围，请精选行列；展示个体分布时可指定 dotplot")
        return "table", reason

    def condition_records(self, page):
        heads, rows = self.select(page)
        images = page["conditions"]
        if not isinstance(images, dict) or set(images) != {row[0] for row in rows}:
            raise ValueError("conditions 的键必须逐一对应本页选中的 CSV 行键")
        if not 2 <= len(rows) <= 4 or not 1 <= len(heads) - 1 <= 3:
            raise ValueError("条件对照页可并列 2–4 个条件及 1–3 项指标，请按讲解目的选行列")
        for image in images.values():
            required(image, ["file", "alt", "source"])
        return heads, [(row, images[row[0]]) for row in rows]

    def resolve(self, page):
        citations = []

        def substitute(match):
            name = match.group(1)
            if name not in self.facts:
                raise ValueError(f"未知 fact：{name}")
            value, cite = self.facts[name]
            citations.append(cite)
            return value

        def walk(obj):
            if isinstance(obj, list):
                return [walk(v) for v in obj]
            if isinstance(obj, dict):
                return {k: walk(v) for k, v in obj.items()}
            if isinstance(obj, str):
                text = re.sub(r"\{\{([\w.-]+)\}\}", substitute, obj)
                if "{{" in text or "}}" in text:
                    raise ValueError(f"无法解析占位符：{text}")
                return text
            return obj

        resolved = walk(page)
        layout, reason = self.choose_layout(resolved)
        resolved["layout"], resolved["layout_reason"] = layout, reason
        if layout in DATA_LAYOUTS:
            citations.append(self.tables[resolved["dataset"]][0]["source"])
        if layout == "condition_comparison":
            _, records = self.condition_records(resolved)
            citations.extend(image["source"] for _, image in records)
        if layout == "sequence":
            frames = resolved.get("frames")
            if not isinstance(frames, list) or not 2 <= len(frames) <= 4:
                raise ValueError("frames 需要按时间排列的 2–4 幅观测图")
            for frame in frames:
                required(frame, ["file", "alt", "label"])
                if not frame.get("source") and not resolved.get("source"):
                    raise ValueError("连续观测图需要逐帧 source 或整页共同 source")
                if frame.get("source"):
                    citations.append(frame["source"])
        if resolved.get("plate"):
            required(resolved["plate"], ["source"])
            citations.append(resolved["plate"]["source"])
        if layout == "evidence_pair":
            required(resolved, ["left", "right"])
            for panel in (resolved["left"], resolved["right"]):
                required(panel, ["source"])
                citations.append(panel["source"])
        if resolved.get("source"):
            citations.insert(0, resolved["source"])
        keys = resolved.get("cite", [])
        if not isinstance(keys, list) or any(not isinstance(k, str) or k not in self.references for k in keys):
            raise ValueError("cite 需要 bibliography 中的文献键列表")
        if "paper" in resolved:
            paper = resolved["paper"]
            if not isinstance(paper, str) or paper not in self.references:
                raise ValueError("paper 需要 bibliography 中的一个文献键")
            keys = [paper, *keys]
            ref = self.references[paper]
            resolved.setdefault("section", ref.get("short_title", ref["title"]))
        resolved["references"] = [self.references[k] for k in dict.fromkeys(keys)]
        if layout == "bibliography" and not 1 <= len(resolved["references"]) <= 5:
            raise ValueError("文献页需要用 cite 选择 1–5 项文献")
        resolved["citations"] = list(dict.fromkeys(citations))
        return resolved

    def select(self, page):
        item, headers, rows = self.tables[page["dataset"]]
        keys = page.get("rows", list(rows))
        cols = page["columns"]
        if (
            not keys
            or len(set(keys)) != len(keys)
            or not cols
            or len(set(cols)) != len(cols)
        ):
            raise ValueError("行列选择为空或重复")
        if any(c not in headers or c == item["key"] for c in cols):
            raise ValueError("数据列缺失或与行键重复")
        for key in keys:
            if key not in rows:
                raise ValueError(f"数据集 {page['dataset']} 中没有行键 {key}")
        for key in page.get("highlight", []):
            if key not in keys:
                raise ValueError(f"表格高亮行 {key} 未出现在本页所选数据中")
        return [item["key"], *cols], [[k, *(rows[k][c] for c in cols)] for k in keys]
