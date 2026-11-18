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
| video | 实验轨迹对照、设备操作或产品演示 | file 为本地 MP4，poster 为同画幅的代表帧，alt 说明画面，source 记录出处。可用 caption 提示观众应观察的事件。PPTX 内嵌片段，PDF 可从静态帧读图 |
| chart | 数值对比、趋势 | dataset、columns；可设 rows、reading、axis_title、min/max、decimals（0–6）。kind 选 column 或 line，最多 8 个类别、3 个系列 |
| table | 结果对照、里程碑、逐项验收 | dataset、columns；可设 rows、widths（含行键列）、highlight（行键），或 highlight_where（按所示列的 column、equals 匹配状态）。每页最多 9 行数据、6 列 |
| equation | 可编辑公式与符号解释 | latex 为不含美元定界符的单行表达式，另需 explanation、source。通过 Pandoc 生成 Office Math，附同一公式的透明位图用于兼容预览 |
| decision | 总结、局限、待决事项 | takeaway；items 为 1–3 条行动或问题 |
| dotplot | 个体分布与相同观测值的次数 | dataset、columns 依次选组别和数值。每个唯一行键对应一个可编辑的点，重复的数值纵向堆叠。可选 rows、axis_title、caption、min、max。支持 1–4 组，每页最多 300 条 |
| unitgrid | 两次测量在相同总数下的变化 | dataset、rows 两行、columns 依次选命中数和总数、legend。总数必须相同且为 1–100 的整数。格子按计数填充，格子位置只表示数量 |
| spotlight | 结尾的关键区间、资源或决策 | value 和 label 放在色块中，heading 和 text 说明含义、责任人或下一步 |

封面可以用分栏构图。学术图版在 cover 页增加 `plate`，含 file、alt、caption、source。PDF 图版另需 pdf_page 和 crop。指标封面使用 `metrics`，传入 2–3 组 label 和 value，可在 value 中绑定 `{{fact}}`。图版、指标组和单位 stationery 各有独立构图。表格可用 caption 点出最重要的一行。

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

### 复用整份工作稿

`draft 原稿/deck.json 本期工作稿` 复制逐页 JSON、数据集 CSV、图件、封面 plate 和 stationery。稿内的嵌套路径会保留，稿外的素材放入新目录的 `_imported`，相应引用一起更新。工作目录可以移动到另一台装有构建依赖的机器。

### 模板编辑计划

```json
{"edits":[
  {"slide":2,"id":7,"paragraph":0,"expect":"阶段成果","text":"本期交付"},
  {"slide":5,"id":12,"cell":[2,1],"paragraph":0,"expect":"待复核","text":"待验证"}
]}
```

页码从 1 开始；单元格的行列与段落从 0 开始。示例 ID 仅演示语法，请先用 `inspect` 读实际模板。每项改一个段落，替换文字沿用该段第一个文本片段的格式。遇到原文不一致、重复目标或带字段与手工换行的段落会报错。表格中的合并单元格请指定实际含文字的格子。音视频、母版和其他未改动文件沿原包带入。


底图上没有可编辑标题时，可新增透明文本框。选定的名称在目标页内应唯一；在已编辑稿上重复应用同一新增计划会报告该名称已经存在。以下示例将深红色标题置于封面下方。

```json
{"edits":[{"op":"add_text","slide":1,"name":"学术报告标题","text":"书目署名与版本线索",
 "box":[0.10,0.69,0.80,0.13],"size":26,"font":"Songti SC","color":"771725","bold":true,"align":"center"}]}
```

`box` 依次为左、上、宽、高，取值均为原画布的比例。字号以磅计，字体可换成本机已有的字体，颜色是六位 RGB。新增的文本框可在 PowerPoint 中移动或修改；后续用 `inspect` 查看其 ID 即可定点改字。

### 成稿核验与逐页预览

```sh
python3 scripts/deck.py check 成稿.pptx --spec 工作稿/deck.json --pdf 投影稿.pdf --overview 总览.pdf
```

- `--spec` 按当前 CSV 和素材重建参考稿，对照逐页文字、备注、表格单元格、原生图表缓存，以及点图和方格图的数据标记。原构建用过 `--style` 时，在核验中传入相同选项。
- `--pdf` 选择交付时使用的 PDF；省略时用 LibreOffice 临时渲染。核对页数、画幅、可提取的文字和生成图表的数据标签。原生学校模板可直接核对 PPTX 与 PDF；隐藏页会按导出的页序映射。
- JSON 的 `errors` 指向数据或投影不一致的页；`warnings` 指向疑似重叠、越界、字色与邻近背景相近或坐标轴截断的位置。已有模板中的隐藏文本、阴影与渐变会影响判读，请看原大小页面。扫描图里的文字、科研结论和来源本身需要人工核对。
- `--overview` 从实际 PDF 每六页排一张总览，带页级提示的缩略图标为 Review。命令输出 JSON。退出码 0 表示未发现硬性不一致，1 表示核验发现不一致，2 表示输入或运行失败。

### 高校工作稿

`process` 可设整数 `active_step`（从 1 开始）。将相同的 steps 放在两页并保持节点顺序一致，在第二页设 active_step，读者可直接定位本季推进的节点。

`development` 和 `quarterly` 可以使用可选的顶层 `stationery`，其中 `cover` 为 16:9 本地封面底图，`header_mark` 为本地机构标识位图，两者均为相对路径。封面底图应先移除旧标题、人员、日期等内容。底图和标识作为图片置入，题目、数据表和正文保持可编辑。使用原生学校母版、其原始布局及动画时，使用 campus --template 再 fill。
