---
name: research-deck
description: AwesomePPT creates editable, evidence-linked academic and project presentations in Chinese or English. Use when a user wants a paper reading, journal club, conference talk, defense, project update, development summary, acceptance review or demo as PPTX, or needs text updates in an existing institutional deck. 适合论文组会、学术分享、个人答辩、季度推进、研制总结与验收、项目路演。Do not use for a paper review without slides, an image-only poster, or a request exclusively for a website.
---

# AwesomePPT · 学术与项目汇报

默认交付可编辑的 16:9 PPTX。根据听众要理解的问题或需要作出的决定选择模式，根据投影环境、内容密度和用户偏好选择风格。用户指定模板、时间、页数、语言或格式时，优先落实这些要求。用用户使用的语言写标题与备注。

学术短讲有标本、仪器或实验原图时，可用带署名的图版开场；需说明个体差异时，在均值前展示原始观测。短项目评审可在封面先交代交付与遗留项，结尾把待决定的资源、责任人和验收证据放在一起。同一批样本的两次计数可以选用方格图。选择具体版式见[模式与风格库](references/library.md)。

## 从材料到成稿

用户给了自己满意的成稿时，先看原稿的放映画面，找出观众凭什么能看懂贡献。记录有讲解价值的架构图、实验回放、交互路径与对照条件，重编后在同尺寸比较对应页。图或演示适合主导整页时，可以按证据专门编排 PowerPoint 对象；起稿库提供常用布局。具体做法见[参考原稿重编](references/reference-led.md)。

1. 读取用户提供的论文、项目材料、数据和现有稿件。记录每个核心判断能追溯到的页码、图表编号、工作表或测试记录。论文先找研究问题、关键图、主结果及反例；项目先找承诺、当前证据、责任人、遗留项和下一次决定。只有标题或提纲时，可以直接做概念稿，明确标出缺少证据的位置。
2. 从[模式与风格库](references/library.md)选一个起点。参考既有 PPT 时，分清「借用叙事或版式」与「沿用这个文件改字」。前者用生成路线，后者用下方的模板编辑路线。确定一个讲完后听众应能回答的问题，然后按时长安排主线、讨论和备份页。
3. 在用户的工作目录运行 `starter`，逐页替换模拟案例的标题、要点、图件、数据、来源与备注。完成后全文搜索原案例的项目名、测试编号与负责人，删除所有无法从用户材料确认的内容。先写每页一句话标题，再配一项图、表、方法步骤或对照证据；备注补充解释顺序、限定条件和转场。五分钟短讲优先保留关键结果；验收评审给逐项记录和待验证项留足篇幅。
4. 数值先抄回带行键的 CSV，核对方法、指标、单位和实验条件。图表与标题引用同一份记录。用 `facts` 将数值、差值或状态计数绑定到标题或备注。原图必须保留来源位置与替代文本。任何「达到」或「已完成」都应有相应实测记录或交付凭据；缺失时写「待验证」并交代谁来补什么记录。
5. 执行构建与预览，用 `check 成稿.pptx --spec 工作稿/deck.json --pdf 成稿.pdf` 对照数据和投影文字。沿用原生模板时省略 `--spec`。先修复报告中的 errors，再打开对应页查看 warnings。需要比较整场节奏时加 `--overview 排版总览.pdf`，回看封面、密集页和收束页。对照输入核对标题、图例、方法—数值配对、单位、分母、图的裁切、小数位与来源。看完整份预览后再调整节奏。改动内容或风格后重新渲染。交付 PPTX 与用户需要的预览；需要复用时一并保留逐页稿、CSV 和图件。向用户说明仍待核对的材料。

## 命令入口

从本 skill 的目录运行以下命令。若从别处调用，把 `scripts/deck.py` 换成该脚本的绝对路径，输入、输出仍指向用户的工作目录。

```sh
python3 scripts/deck.py catalog
python3 scripts/deck.py starter journal-club 工作稿
python3 scripts/deck.py build 工作稿/deck.json 工作稿/论文组会.pptx
python3 scripts/deck.py preview 工作稿/论文组会.pptx 工作稿/论文组会.pdf
```

复用以往的逐页稿时，运行 `python3 scripts/deck.py draft 往期/deck.json 本期工作稿`。图、表、封面图版和校方底图会随稿复制。

可在 `starter` 或 `build` 加 `--style evidence` 等风格名。起稿目录需为新目录。输出默认使用新文件名。`--replace` 用于更新自己生成的目标稿件。支持的页型、字段和示例见[逐页稿格式](references/spec.md)。

首次使用需要可导入 `python-pptx`、`Pillow`、`lxml`、`PyMuPDF` 的 Python 3.9 或更高版本。缺失时在工作目录的虚拟环境中运行 `python -m pip install -r /实际路径/research-deck/requirements.txt`。PDF 预览需要可在 PATH 中找到的 LibreOffice `soffice`，原生公式还需要 `pandoc` 和 LibreOffice 的 Writer、Math 组件。Debian/Ubuntu 精简安装需包含 `libreoffice-writer` 和 `libreoffice-math`。中文稿选本机已有的中文字体。

## 高校与科研院校

如果用户点名学校，先用 `python3 scripts/deck.py campus 学校ID` 核对机构层级、来源和可用起稿。北大学术沙龙、清华科研进展、北航工程开题和复旦方法研讨支持中文简称，例如 `campus 北航 新目录`。上海交通大学研制总结用 `campus sjtu 新目录`，北京中关村学院季度答辩用 `campus bza 新目录`。从专用起稿生成时，照常调用 `build`；这些是 AwesomePPT 的原创工作模板。用户指明“校方原版”或提供指定模板时，优先找工作目录中该校、该院系的原生文件；保留校徽、母版和已有页序时用 `campus 学校ID 新目录 --template 校方文件.pptx` 导入原版。按 `objects.json` 填写 `edits.json` 后对工作副本调用 `fill`。学院工具需要身份认证时，使用用户持有的模板或参考稿。用户提供截图时，用它判断留白、层级和颜色，输出需编辑的布局与可追溯的图表。原生母版保真路线需要 PPTX 文件。[高校与院校使用指南](references/campuses.md)

当前工作区若有 `高校模板库/目录.md`，先按校名和用途查本地索引。用户要求「交大研制总结」或「北京学院季度答辩」时优先使用索引内带校方封面与标识的版本。更新既有页时把对应 PPTX 传给 `campus --template`；重编整稿时用 `draft 模板目录/deck.json 新工作目录` 复制该稿与素材，再按实际材料构建。学校和院系都明确时，匹配相同的发布层级。

## 沿用已有的 PPTX 模板

先运行 `python3 scripts/deck.py inspect 原稿.pptx` 获取真实页序、对象 ID、段落、表格单元格、图表缓存系列与讲者备注。根据清单写编辑计划，再运行 `python3 scripts/deck.py fill 原稿.pptx edits.json 修订稿.pptx`。每次替换提供精确的原文 `expect`。空白封面或只含底图的页面可以在编辑计划中使用 `add_text`，按原画布比例添加标题或说明。先看原页上的校徽、图像与留白，再决定位置和字色。改数据图表、增删章节或重排整份报告时，使用逐页稿重建所需内容。
