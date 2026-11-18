---
name: research-deck
description: AwesomePPT creates editable, evidence-linked academic and project presentations in Chinese or English. Use when a user wants a paper reading, journal club, conference talk, defense, project update, development summary, acceptance review or demo as PPTX, or needs text updates in an existing institutional deck. 适合论文组会、学术分享、个人答辩、季度推进、研制总结与验收、项目路演。Do not use for a paper review without slides, an image-only poster, or a request exclusively for a website.
---

# AwesomePPT · 学术与项目汇报

默认交付可编辑的 16:9 PPTX。根据听众要理解的问题或需要作出的决定选择模式，根据投影环境、内容密度和用户偏好选择风格。用户指定模板、时间、页数、语言或格式时，优先落实这些要求。用用户使用的语言写标题与备注。

学术短讲有标本、仪器或实验原图时，可用带署名的图版开场；需说明个体差异时，在均值前展示原始观测。短项目评审可在封面先交代交付与遗留项，结尾把待决定的资源、责任人和验收证据放在一起。同一批样本的两次计数可以选用方格图。选择具体版式见[模式与风格库](references/library.md)。

## 从材料到成稿

多篇文献的组会或近期进展分享，默认逐篇讲。先确定选读论文和次序，每篇首次出现时给出工作名称、作者和时间，交代研究问题、作者的做法、关键实验和结果的适用范围。同一篇连续讲完，再转入下一篇。篇间比较放到讨论页。用户指定主题式综述时按指定主线组织。逐篇稿可以用 `paper` 关联正文，用 `reading_guide` 从实际页序生成目录。[逐页稿格式](references/spec.md)

用论文里的任务名、操作和指标写标题与图注。保留图号、版本和实验条件，把单次观察与多次试验的统计分开。原始论文、模型发布说明和汇报人的判断分别署明来源。[学术用词与备注](references/editorial.md)

有实物照片、论文分图和实测数据的报告可选 `plates`（研究图版）。先判断观众要读清整张图的连接关系，还是要分别读图 a 和图 b。前者给整图通栏，后者可用 `figure_panels` 把分图与解释逐行对齐。结果依赖特殊设备或采集条件时，给统计图配一幅能辨认该条件的原图。按放映尺寸查看图内文字、刻度、条形起点和末端数值。[版式选择](references/library.md)

先判断用户交给你的是一批待组织的材料、一份喜欢的参考稿，还是一套需要原样沿用的单位模板。新报告从用户的论文、图件、数据和任务记录建立工作稿。参考稿用来辨认图与图、条件与结果、操作与产物之间的关系；要求沿用校方原版时，走下方的原生模板路线。[参考原稿重编](references/reference-led.md)

1. **选整场模式。** 从听众、时长和现场问题决定主线。会议短讲先找决定性实验和适用边界，项目推进会先找状态变化和待决定事项，验收先找条款、实测和记录。用户有喜欢的原稿时，对照其中的关键页决定哪些关系要放在主讲部分。[模式与风格库](references/library.md)
2. **从证据写逐页稿。** 每页写一个讲得清的判断，选出支撑它的图、数据行或操作记录，把出处写到材料旁。数字、差值与状态计数用 `facts` 绑定到记录。只有提纲时先写概念稿，在相应页说明待补的证据。需要示范结构时可以运行 `starter`；新项目也可以直接写自己的 `deck.json`。
3. **走一遍讲解顺序。** 材料已编排成页时，可以省略 `layout`，用 `storyboard` 查看每页选择、理由、图片和数据行。在同一条件下比较测量值用 `condition_comparison`，追溯界面字段用 `detail`，说明多人怎样交付结果用 `handoff`。已有作者布局、学校要求或统计表达意图时直接指定页型。遇到同时有图件和数据的页，先明确两者是否按实验条件一一对应。保留有意义的连续对照，把需要逐行查阅的细节放进备注或答疑页。[逐页稿格式](references/spec.md)
4. **做文字和投影视图校订。** 标题交代对象、条件与发现；界面或仪器沿用真实字段名。正文用来解释观众从图上难以判断的地方。参考原稿重编时，在同尺寸下检查关键图幅、坐标、条件名及数据标签。看整场缩略图，再打开密集页检查断行和裁切。[学术用词与备注](references/editorial.md) · [投影字号与图幅](references/reference-led.md#投影字号与图幅)
5. **验证交付。** 运行 `build`、`preview` 和 `check 成稿.pptx --spec 工作稿/deck.json --pdf 成稿.pdf`，核对可编辑数据、图件、备注和投影文字。需要看整场节奏时加 `--overview 排版总览.pdf`；有原生参考稿时用 `compare` 对照相同讲解任务。沿用原生模板时省略 `--spec`。修复报告中的 errors，打开有 warnings 的页目检，再交付所需文件。

## 命令入口

从本 skill 的目录运行以下命令。若从别处调用，把 `scripts/deck.py` 换成该脚本的绝对路径，输入、输出仍指向用户的工作目录。

```sh
python3 scripts/deck.py catalog
python3 scripts/deck.py starter journal-club 工作稿
python3 scripts/deck.py storyboard 工作稿/deck.json
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
