"""Resolve source tables and named facts before writing any slide."""

import csv
import re
from decimal import Decimal, InvalidOperation


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
        if page["layout"] in ("table", "chart", "dotplot", "unitgrid"):
            citations.append(self.tables[page["dataset"]][0]["source"])
        if resolved.get("plate"):
            required(resolved["plate"], ["source"])
            citations.append(resolved["plate"]["source"])
        if resolved.get("source"):
            citations.insert(0, resolved["source"])
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
