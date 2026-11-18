# 高校与院校模板

交大研制总结和北京中关村学院季度答辩配有 CiteSlide 原创起稿。目录中的校级与院级资源标注了发布机构。带品牌资产的原版可从校方取得，在本地使用校方允许的用途。

| ID | 学校与资源 | 起稿或原生入口 |
|---|---|---|
| sjtu | 上海交通大学 · 校级通用 PPT；生命学院亦提供 2022 校级合集和院级资源 | [研制总结逐页稿](../assets/campuses/sjtu-review.json) · [学校 VI](https://vi.sjtu.edu.cn/index.php/articles/bulletin/13) · [办公素材下载](https://life.sjtu.edu.cn/En/Data/View/7674) |
| bza | 北京中关村学院 · 季度答辩；正式工具由学院经钉钉分发 | [季度答辩逐页稿](../assets/campuses/bza-quarterly.json) · [学院官网](https://www.bza.edu.cn/) |
| tsinghua | 清华大学文化建设办公室系列 · 校园、通用、人文与科技等主题 | [校内模板发布页](https://www.env.tsinghua.edu.cn/info/1344/7931.htm) |
| pku | 北京大学标识管理办公室 · 模板压缩包 | [标识下载专区](https://vim.pku.edu.cn/xzzq/) |
| fudan | 复旦大学 · 校内资料下载页列出九款演示模板 | [资料下载](https://simi.fudan.edu.cn/xxtd/list.htm) |
| zju-ic | 浙江大学集成电路学院 · 院级汇报模板 | [学院 PPT 模板](https://ic.zju.edu.cn/2025/0912/c81195a3080798/page.htm) |
| ustc | 中国科学技术大学教务处 · 提供校徽与教务处两组标识，16:9 和 4:3 两种尺寸 | [教务处模板选择页](https://www.teach.ustc.edu.cn/document/doc-misc/10319.html) |
| iowa | 爱荷华大学 · 正式评审与品牌模板 | [官方 PowerPoint 模板](https://brand.uiowa.edu/powerpoint-templates) |
| oslo | 奥斯陆大学 · 通过校管设备和 PowerPoint 模板页获取 | [官方使用指南](https://www.uio.no/english/about/designmanual/profile-in-use/powerpoint/) |

### 从专用起稿开始

```sh
python3 scripts/deck.py campus sjtu 研制工作稿
python3 scripts/deck.py build 研制工作稿/deck.json 研制工作稿/研制总结.pptx
python3 scripts/deck.py campus bza 季度工作稿
python3 scripts/deck.py build 季度工作稿/deck.json 季度工作稿/季度答辩.pptx
```

研制总结按目标与指标、研制交付、测试条件和逐项判定组织。季度答辩先给总体路线，再在原位置标出本季节点，然后给可编辑交付表、依赖和下期决定。将模拟案例、备注和来源替换成自己的实际记录。

### 导入持有的正式母版

```sh
python3 scripts/deck.py campus tsinghua
python3 scripts/deck.py campus tsinghua 清华工作稿 --template 校方模板.pptx
# 按 objects.json 填写 edits.json，逐项指定页码、对象 ID、expect 和新文字
python3 scripts/deck.py fill 清华工作稿/template.pptx 清华工作稿/edits.json 清华工作稿/修订稿.pptx
```

导入会产生原版工作副本和对象清单，原有页面尺寸、母版、图形、布局与媒体随源文件保留。列出的院校均支持此路线。ZIP 先解压，老式 PPT 或 POTX 在 PowerPoint 中另存为 PPTX。截图可用作视觉参考；修改既有原生对象需要原文件。
