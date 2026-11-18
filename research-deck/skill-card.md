# research-deck 能力说明

- Reads: 用户提供的素材和原稿、逐页 JSON、CSV、图片、PDF、内置风格和起稿资源。
- Writes: 指定工作目录内的工作稿、PPTX、预览 PDF 和短期渲染文件。
- Executes: 本地 Python；公式编译调用 Pandoc，公式后备图与 PDF 预览调用 LibreOffice。
- Network: 构建、替换、预览均本地执行。外部论文或品牌资料按用户任务另行获取。
- Credentials: 无。
- External effects: 无发布、共享、全局安装或邮件操作。
- Approval gates: 输出默认使用新的路径；显式更新已有衍生产物可用 --replace。输入文件不可作为输出目标。

维护者可运行 evals/test_deck.py 检查科学数值绑定、模板保真与失败行为。
