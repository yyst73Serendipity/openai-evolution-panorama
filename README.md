# OpenAI 产品与模型演进全景

一个从 2015 年 OpenAI 成立延伸至当前检查日的中文交互式全景网页，聚合模型、ChatGPT、API / Agents、Codex、多模态、订阅与迁移治理的重要官方更新。

## ✨ 功能介绍

- 以结构化时间线呈现 OpenAI 产品与模型演进。
- 首版覆盖 2015-12-11 至 2026-10-20 的官方历史资料。
- 区分模型体系、ChatGPT 产品、API / Agents、Codex、多模态、订阅计划、技术基础与迁移治理八条轨道。
- 每条事件说明发布时间、更新内容、相对变化、优化重点、可用范围、战略意义和官方来源。
- 最终生成单文件 HTML：样式、脚本和数据全部内嵌，可离线查看。
- GitHub Actions 每日检查 OpenAI 官方来源；只有完整测试通过才更新数据并发布 GitHub Pages。
- 自动发现的事件明确标记为“自动收录”，避免与人工核验内容混淆。

## 📁 项目目录结构

```text
.
├── .github/workflows/                 # 自动更新、测试与 Pages 发布
├── docs/superpowers/                  # 设计文档与实施计划
├── outputs/                           # 生成的单文件全景网页
├── tests/
│   └── test-timeline-data.py          # 历史数据契约测试
├── work/
│   └── timeline-data.json             # 时间线单一事实源
├── .gitignore
├── AGENTS.md
├── CHANGELOG.md
└── README.md
```

> 目录树会随构建器、更新器和工作流落地继续同步更新。

## 🧰 技术栈

- Python 3.12 标准库
- HTML5、CSS3、原生 JavaScript
- `unittest`
- GitHub Actions 与 GitHub Pages

项目不引入第三方运行时依赖，不需要 OpenAI API Key。

## 🚀 安装和使用方式

### 验证历史数据

```bash
python3 -m unittest tests/test-timeline-data.py -v
```

### 数据范围与证据原则

- 主要来源：OpenAI 官网新闻与研究文章、OpenAI 官方 RSS、产品 Release Notes、Help Center、OpenAI Developers 文档与 Changelog。
- 官方 X 账号只用于官网缺失历史日期时人工补充，不作为定时任务的主发现源。
- `sitemap.xml` 的 `lastmod` 可能只是站点重新生成时间，不能直接视为文章发布日期；发布日优先采用文章正文、RSS `pubDate` 或官方 Release Notes。
- 截止日期表示“资料核验到该日”，不强行要求截止日当天必须存在一条产品发布。
- 无法从官方原始资料确认的传闻、占位更新和推测性指标不收录。

## 📄 License 与贡献

本项目用于资料整理与研究查阅。事件摘要为中文归纳，事实与产品可用性以对应 OpenAI 官方来源为准。
