# 设计来源

调研核对日期为 2026-11-18。Relationship 为原创实现对上游公开方法或作者样稿的学习。License 记录参考作品的许可或机构使用背景。内置模板、模拟数据与示意界面由本项目编写，评测代码直接调用 Python 和本地办公工具。本包不收录上游主题源码、机构母版、徽标或商业字体文件。

| 参考作品 | 看过的材料 | 在本库采用的设计决定 |
|---|---|---|
| Penn State · Assertion–Evidence | 研究传播团队的工程演讲指南与配套模板入口 | 会议短讲用完整判断作标题，把关键图放在正文，次要解释留给讲者备注。[官方指南](https://writing.engr.psu.edu/assertion_evidence_EA.html) |
| Metropolis · Matthias Vogelgesang 等 | Beamer 示例源码分开演示章节、图表、数学和页脚。主题 License 为 CC BY-SA 4.0 | 学术讲堂采用连贯的章节提示与进度线。字号、位置、色组为本库独立定义。[固定版本示例](https://github.com/matze/mtheme/blob/2fa6084b9d34fec9d2d5470eb9a17d0bf712b6c8/demo/demo.tex) · [主题说明与许可](https://github.com/matze/mtheme/tree/2fa6084b9d34fec9d2d5470eb9a17d0bf712b6c8) |
| Argüelles · Massimo Piazzai | 七页作者样稿的第 2–3 页展示标题、正文与定理的层级，第 6 页以短句聚焦。License 为 MIT | 精读风格用中英文可用的衬线标题、轻分隔和稳定正文区，便于讲解单图或分组结果。[固定版本样稿](https://github.com/piazzai/arguelles/blob/868676d153dfb5f6a92dfe0c243135aa480d9bf8/demo-arguelles.pdf) |
| University of Iowa · Formal PowerPoint | 官方品牌页说明宽屏、可编辑数据与正式评审场景。校方品牌资源按官方适用范围使用 | 正式项目评审采用稳定表头、行级对照、受控配色。用户需要单位母版时走原稿修改路线。[官方模板与可访问性说明](https://brand.uiowa.edu/powerpoint-templates) |
| University of Oslo · PowerPoint | 官方说明页展示封面、章节和配色选择，并说明字号、标题、替代文本与图像比例。校内模板由学校管理设备提供 | 图页保留图像比例、替代文本和短图注；重要内容以标题或文字说明。此处研究对象是校方公开指南。[官方说明](https://www.uio.no/english/about/designmanual/profile-in-use/powerpoint/) |
| scholar-slides、Academic PPT Master、Rich627 slides-skill | 前期调研的论文结果页、答辩样稿、项目进展样稿 | 从前两者学习科学证据定位、章节阅读顺序，从项目样稿学习待决事项与后续责任人。实现和数据资源独立编写。[论文结果页](https://github.com/luwill/research-skills/blob/5e5add4826376ea6ba4371975a4f7c7e1e1f8533/scholar-slides/docs/gallery/glm5-scoreboard-table.png) · [答辩样稿](https://github.com/M1n-n9/academic-ppt-master/blob/6825d33f2931b8894435b9bd25c08cfce3476ff0/assets/previews/attention_demo_07_12.png) · [进展样稿](https://github.com/Rich627/slides-skill/blob/db697da83e97c4498e9ea1d2abbab7869308534c/docs/previews/team-update.png) |
