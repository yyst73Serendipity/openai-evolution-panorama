# OpenAI 产品与模型演进全景

一个从 2015 年 OpenAI 成立延伸至当前检查日的中文交互式全景网页，聚合模型、ChatGPT、API / Agents、Codex、多模态、订阅与迁移治理的重要官方更新。

## ✨ 功能介绍

- 以结构化时间线呈现 OpenAI 产品与模型演进，首版收录 121 条重要官方事件。
- 首版覆盖 2015-12-11 至 2026-10-20 的官方历史资料，并单独显示“资料核验截止日”和“最后一条已确认事件”。
- 区分模型体系、ChatGPT 产品、API / Agents、Codex、多模态、订阅计划、技术基础与迁移治理八条轨道。
- 每条事件说明发布时间、更新内容、相对变化、优化重点、可用范围、战略意义和官方来源。
- 支持关键词、年份、类别、产品线、模型家族、时间排序和最近 30 天组合筛选，筛选状态可写入 URL hash。
- 提供模型谱系、ChatGPT 能力层、API / Agents、Codex、多模态、订阅与计费、迁移提示、战略转折和来源索引等专题视图。
- 支持深浅主题、键盘操作、响应式布局、打印样式和减少动态效果偏好。
- 最终生成单文件 HTML：样式、脚本和数据全部内嵌，可离线查看，不依赖 CDN 或运行时网络请求。
- GitHub Actions 每日检查 OpenAI 官方来源；只有完整测试通过才更新数据并发布 GitHub Pages。
- 自动发现的事件明确标记为“自动收录”，避免与人工核验内容混淆。

## 📁 项目目录结构

```text
.
├── .github/workflows/                         # 自动更新、测试与 Pages 发布
├── docs/superpowers/                          # 设计文档与实施计划
├── outputs/
│   └── openai-chatgpt-evolution-panorama.html # 可离线打开的最终单文件网页
├── tests/
│   ├── test-openai-evolution-panorama.py      # 网页结构、交互、安全与离线特性测试
│   └── test-timeline-data.py                  # 历史数据契约测试
├── work/
│   ├── build-page.py                          # 数据校验与单文件 HTML 构建器
│   └── timeline-data.json                     # 时间线单一事实源
├── .gitignore
├── AGENTS.md
└── README.md
```

> 自动更新器、状态文件、变更日志和工作流文件会在后续实施阶段加入并同步到本节。

## 🧰 技术栈

- Python 3.12 标准库
- HTML5、CSS3、原生 JavaScript
- `unittest`
- Node.js `--check`
- GitHub Actions 与 GitHub Pages

项目不引入第三方运行时依赖，不需要 OpenAI API Key。

## 🚀 安装和使用方式

### 生成网页

```bash
python3 work/build-page.py
```

生成文件：

```text
outputs/openai-chatgpt-evolution-panorama.html
```

可直接双击该文件离线查看，也可启动本地静态服务器：

```bash
python3 -m http.server 8765 --directory outputs
```

然后访问：

```text
http://127.0.0.1:8765/openai-chatgpt-evolution-panorama.html
```

### 运行测试

```bash
python3 -m unittest tests/test-timeline-data.py -v
python3 -m unittest tests/test-openai-evolution-panorama.py -v
```

检查内嵌 JavaScript 语法：

```bash
python3 - <<'PY'
from pathlib import Path
import re

html = Path("outputs/openai-chatgpt-evolution-panorama.html").read_text(encoding="utf-8")
script = "\n".join(re.findall(
    r'<script(?![^>]*type="application/json")[^>]*>(.*?)</script>',
    html,
    re.S,
))
Path("/tmp/openai-panorama-script.js").write_text(script, encoding="utf-8")
PY
node --check /tmp/openai-panorama-script.js
```

### 数据范围与证据原则

- 主要来源：OpenAI 官网新闻与研究文章、OpenAI 官方 RSS、产品 Release Notes、Help Center、OpenAI Developers 文档与 Changelog。
- 官方 X 账号只用于官网缺失历史日期时人工补充，不作为定时任务的主发现源。
- `sitemap.xml` 的 `lastmod` 可能只是站点重新生成时间，不能直接视为文章发布日期；发布日优先采用文章正文、RSS `pubDate` 或官方 Release Notes。
- 截止日期表示“资料核验到该日”，不强行要求截止日当天必须存在一条产品发布。
- 无法从官方原始资料确认的传闻、占位更新和推测性指标不收录。
- ChatGPT 计划和 API 价格会因地区、计费方式和发布时间变化；离线页保存结构与计费口径，并引导读者前往官方页面复核，不伪装为实时价格。

## 📄 License 与贡献

本项目用于资料整理与研究查阅。事件摘要为中文归纳，事实与产品可用性以对应 OpenAI 官方来源为准。
