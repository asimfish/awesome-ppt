# 逐页稿格式

所有路径相对 `deck.json` 所在目录，文件编码为 UTF-8。完整可运行的格式示例在 [文献组会](../assets/starters/journal-club.json)、[研究答辩](../assets/starters/defense.json)、[研制验收](../assets/starters/acceptance.json) 与[项目演示](../assets/starters/demo.json)中。用 `starter` 自动复制相应 CSV 和图片到工作目录。

最小逐页稿如下。

```json
{
  "mode": "conference",
  "language": "zh",
  "presenter": "报告人",
  "slides": [
    {"layout": "cover", "title": "哪些历史观察值得保留？", "subtitle": "长程操作中的记忆检索", "notes": "先用任务例子界定问题。"},
    {"layout": "decision", "section": "讨论", "title": "哪些变化会影响检索？", "takeaway": "用任务依赖界定历史范围。", "items": ["下一轮分别测量错误检索与遗漏。"], "notes": "将这句话作为待验证的研究假设。"}
  ]
}
```

顶层必需 `mode` 和非空 `slides`；可设 `title`、`presenter`、`language`（zh/en）、`style`、`font`、`heading_font`、`datasets`、`facts`。英文稿请用英文重写内容，`language` 只切换系统标签与默认字体。每页必有 `layout` 与 `title`，可写 `section`、`notes` 和简短 `source`，详细定位放入备注。图表所用 CSV 的来源自动出现在页脚和备注。

| 页型 | 适合的内容 | 必需字段和选项 |
|---|---|---|
| cover、section | 报告开头、章节转场 | 可设 subtitle、eyebrow、credit |
| argument | 问题、判断及支持理由 | lead；points 为 1–4 条文字 |
| contrast | 对比两种方案、贡献或条件 | left 与 right 各有 heading、text |
| process | 方法、路线、操作步骤 | steps 为 2–4 组 heading、text |
| figure | 论文原图、系统界面、照片 | file、alt、source；可设 caption。PDF 图件须有 pdf_page（从 1 起）与 crop（左、上、右、下归一化坐标）。位图直接按比例置入 |
| chart | 数值对比、趋势 | dataset、columns；可设 rows、reading、axis_title、min/max、decimals（0–6）。kind 选 column 或 line，最多 8 个类别、3 个系列 |
| table | 结果对照、里程碑、逐项验收 | dataset、columns；可设 rows、widths（含行键列）、highlight（行键），或 highlight_where（按所示列的 column、equals 匹配状态）。每页最多 9 行数据、6 列 |
| equation | 可编辑公式与符号解释 | latex 为不含美元定界符的单行表达式，另需 explanation、source。通过 Pandoc 生成 Office Math，附同一公式的透明位图用于兼容预览 |
| decision | 总结、局限、待决事项 | takeaway；items 为 1–3 条行动或问题 |

### 图表和文本共用一份数据

例如 `scores.csv` 的表头为 `方法,成功率（%）`，行键为 A 和 B，值分别为 45.0 和 52.2。以下字段放在逐页稿顶层。

```json
{
  "datasets": {"scores": {"file": "scores.csv", "key": "方法", "source": "实验记录 · 表 2 · 测试划分"}},
  "facts": {
    "score_b": {"dataset": "scores", "row": "B", "column": "成功率（%）", "unit": "%", "decimals": 1},
    "gain": {"dataset": "scores", "row": "B", "minus_row": "A", "column": "成功率（%）", "unit": " 个百分点", "decimals": 1}
  }
}
```

`chart` 页指定 `"dataset":"scores","rows":["A","B"],"columns":["成功率（%）"]`。标题 `B 的成功率为 {{score_b}}` 与注解 `比 A 高 {{gain}}` 会从相应行与列计算。数值列存十进制数字，单位写入列名；按 0–100 保存的百分数使用普通小数格式。列名和行键必须逐字匹配。状态计数使用 `{"dataset":"tests","count_where":{"column":"判定","equals":"待验证"}}`。验收台账可设置 evidence_rule，指定 status（判定列）、measured（实测列）、record（证据位置列），可用 passing 数组指定代表通过的状态。采用常见中文表头时，验收模式自动识别此规则。判定已通过但实测或证据位置明确缺失时，构建会报出对应行键。记录内容、阈值方向及原始证据的真实性由作者核验。

### 模板编辑计划

```json
{"edits":[
  {"slide":2,"id":7,"paragraph":0,"expect":"阶段成果","text":"本期交付"},
  {"slide":5,"id":12,"cell":[2,1],"paragraph":0,"expect":"待复核","text":"待验证"}
]}
```

页码从 1 开始；单元格的行列与段落从 0 开始。示例 ID 仅演示语法，请先用 `inspect` 读实际模板。每项改一个段落，替换文字沿用该段第一个文本片段的格式。遇到原文不一致、重复目标或带字段与手工换行的段落会报错。表格中的合并单元格请指定实际含文字的格子。音视频、母版和其他未改动文件沿原包带入。
