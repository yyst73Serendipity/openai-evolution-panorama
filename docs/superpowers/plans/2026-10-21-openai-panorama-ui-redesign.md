# OpenAI 演进全景 UI 改版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 OpenAI 产品与模型全景页面改造成“数字档案馆 / 技术年鉴”界面，同时保留单文件离线运行、自动更新、组合筛选、深浅主题、打印和无障碍能力。

**Architecture:** 继续由 `work/build-page.py` 生成一个自包含 HTML，但将时间线改为 Python 预渲染的年份分组和事件卡，原生 JavaScript 只负责渐进增强：筛选、排序、筛选标签、章节导航与阅读进度。页面不新增依赖，不更改 `work/timeline-data.json` 的数据契约，也不改变自动更新和 GitHub Pages 发布流程。

**Tech Stack:** Python 3.12 标准库、HTML5、CSS3、原生 JavaScript、`unittest`、Node.js `--check`。

**Spec:** `docs/superpowers/specs/2026-10-21-openai-panorama-ui-redesign-design.md`

## Global Constraints

- 保持纯前端、单文件 HTML，样式、脚本和数据全部内嵌。
- 不新增第三方依赖、CDN、外部字体、外部脚本或运行时网络请求。
- 不修改 `work/timeline-data.json` 中的历史事实、来源和事件结论。
- 不改变 `work/update-openai-panorama.py`、自动写入边界和 GitHub Pages 发布机制。
- 保留 URL hash 筛选、深浅主题、键盘操作、响应式、打印和 `prefers-reduced-motion`。
- 新事件必须仅通过更新数据和重新构建即可进入正确年份与轨道。
- 颜色不得成为唯一状态表达方式；焦点和活动状态必须具有文本或结构语义。
- 项目规定只有用户明确要求时才创建 Git commit，因此本计划以 `git diff` 审查点代替提交步骤。
- 不根据标题关键词推断“关键节点”；当前数据没有稳定重要性字段，首轮只区分人工整理、自动收录和页面变更。

## File Map

- Modify: `work/build-page.py` — 生成档案式页面结构、预渲染年份时间线、内嵌 CSS 和渐进增强脚本。
- Modify: `tests/test-openai-evolution-panorama.py` — 验证新结构、筛选状态、渐进增强、无障碍和离线边界。
- Modify: `README.md` — 同步功能说明、交互方式和视觉架构。
- Regenerate: `outputs/openai-chatgpt-evolution-panorama.html` — 构建后的最终单文件网页。
- Review only: `tests/test-workflow-static.py` — 仅运行回归；本次不修改工作流和提交白名单。
- Preserve: `work/timeline-data.json` — 事实数据不得因 UI 改版发生变化。

---

### Task 1: 建立档案式页面骨架与首屏

**Files:**
- Modify: `tests/test-openai-evolution-panorama.py:29-87`
- Modify: `work/build-page.py:129-170`

**Interfaces:**
- Consumes: `build_html(data: dict) -> str` 和现有模板替换标记。
- Produces: `#archive-hero`、`.hero-era`、`#archive-status`、`#section-directory`、`#reading-progress`、`[data-section-target]`，供后续导航脚本和视觉测试使用。

- [ ] **Step 1: 写入首屏与导航结构的失败测试**

在 `OpenAIPanoramaPageTest` 中新增：

```python
def test_archive_hero_status_and_directory_exist(self) -> None:
    for fragment in (
        'id="archive-hero"',
        'class="hero-era"',
        'id="archive-status"',
        'id="section-directory"',
        'id="reading-progress"',
        'data-section-target="timeline"',
        'data-section-target="sources"',
        'aria-label="章节目录"',
    ):
        with self.subTest(fragment=fragment):
            self.assertIn(fragment, self.html)
    self.assertNotIn('class="metrics"', self.html)
```

- [ ] **Step 2: 运行单项测试确认失败**

Run:

```bash
python3 -m unittest tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_archive_hero_status_and_directory_exist -v
```

Expected: FAIL，缺少 `archive-hero` 或 `section-directory`。

- [ ] **Step 3: 替换视觉变量与页面骨架**

在模板中将根变量改为纸张式浅色和独立深色表面，并加入稳定的布局类：

```css
:root{color-scheme:light;--bg:#f4f3ef;--surface:#fbfaf7;--surface-strong:#fff;--ink:#111318;--muted:#676a70;--line:#cfd0ca;--soft:#e9e8e2;--accent:#0d8f70;--accent-ink:#075f4c;--radius:10px}
html[data-theme="dark"]{color-scheme:dark;--bg:#111210;--surface:#191b18;--surface-strong:#20231f;--ink:#f1f2ed;--muted:#a7aaa2;--line:#3a3e38;--soft:#252923;--accent:#42c6a2;--accent-ink:#8ce0c8}
```

首屏结构采用：

```html
<section class="archive-hero" id="archive-hero" aria-labelledby="page-title">
  <div class="shell hero-grid">
    <div class="hero-copy">
      <span class="eyebrow">官方资料驱动 · 单文件离线可查</span>
      <h1 id="page-title">OpenAI 产品与模型演进全景</h1>
      <p class="lead">从预训练语言模型到 ChatGPT、推理模型、实时多模态与工作代理。</p>
      <div class="hero-actions"><a href="#timeline" data-section-target="timeline">进入时间线</a><a href="#timeline" data-section-target="timeline" data-show-latest>查看最新更新</a></div>
    </div>
    <div class="hero-era" aria-label="资料覆盖年份">2015 <span>—</span> __CUTOFF_YEAR__</div>
  </div>
  <div class="shell archive-status" id="archive-status">
    <div><strong>__EVENT_COUNT__</strong><span>历史事件</span></div>
    <div><strong>8</strong><span>产品轨道</span></div>
    <div><strong>__SOURCE_COUNT__</strong><span>官方来源</span></div>
    <div><strong>__CUTOFF__</strong><span>资料核验截止</span></div>
    <div><strong>__LAST_CHECKED__</strong><span>最后检查</span></div>
    <div><strong>__LAST_EVENT__</strong><span>最新确认事件</span></div>
  </div>
</section>
```

章节目录使用真实锚点作为无脚本回退，并添加 `data-section-target` 供 JavaScript 阻止 hash 与筛选状态冲突：

```html
<nav id="section-directory" class="section-directory" aria-label="章节目录">
  <a href="#overview" data-section-target="overview">总览</a>
  <a href="#timeline" data-section-target="timeline">时间线</a>
  <a href="#models" data-section-target="models">模型</a>
  <a href="#chatgpt" data-section-target="chatgpt">ChatGPT</a>
  <a href="#api-agents" data-section-target="api-agents">API / Agents</a>
  <a href="#codex" data-section-target="codex">Codex</a>
  <a href="#multimodal" data-section-target="multimodal">多模态</a>
  <a href="#plans" data-section-target="plans">产品与计费</a>
  <a href="#migration" data-section-target="migration">迁移</a>
  <a href="#sources" data-section-target="sources">来源</a>
</nav>
<div id="reading-progress" class="reading-progress" aria-hidden="true"><i></i></div>
```

- [ ] **Step 4: 运行新测试与现有结构测试**

Run:

```bash
python3 -m unittest \
  tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_archive_hero_status_and_directory_exist \
  tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_all_information_architecture_sections_exist \
  -v
```

Expected: PASS。

- [ ] **Step 5: 审查本任务差异**

Run:

```bash
git diff -- work/build-page.py tests/test-openai-evolution-panorama.py
```

Expected: 仅出现首屏、导航骨架、视觉变量和对应测试，没有时间线数据变化。

---

### Task 2: 预渲染年份分组与事件档案卡

**Files:**
- Modify: `work/build-page.py:64-127`
- Modify: `work/build-page.py:157-158`
- Modify: `tests/test-openai-evolution-panorama.py:29-87`

**Interfaces:**
- Consumes: 已校验的事件字典、`TRACK_COPY`、`esc(value)`。
- Produces: `build_event_card(event: dict) -> str`、`build_timeline_groups(events: list[dict]) -> str`、`.year-group[data-year]`、`.event-card[data-date][data-category][data-track][data-family]`。
- Later tasks rely on: `#timeline-list` 内已经包含全部事件；JavaScript 只切换 `hidden`、重排节点和更新计数。

- [ ] **Step 1: 写入预渲染时间线的失败测试**

新增：

```python
def test_timeline_is_prerendered_and_grouped_by_year(self) -> None:
    years = sorted({event["date"][:4] for event in self.data["events"]})
    self.assertEqual(self.html.count('class="event-card"'), len(self.data["events"]))
    self.assertEqual(self.html.count('class="year-group"'), len(years))
    for year in years:
        with self.subTest(year=year):
            self.assertIn(f'data-year="{year}"', self.html)
            self.assertIn(f'id="timeline-{year}"', self.html)
    self.assertIn('data-verification="页面变更"', self.html)
    self.assertIn('class="badge auto"', self.html)
```

同时将旧的 `createEventCard(event)` 断言替换为：

```python
self.assertIn("function filterEvents()", self.html)
self.assertIn("function renderTimeline()", self.html)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m unittest tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_timeline_is_prerendered_and_grouped_by_year -v
```

Expected: FAIL，当前 `#timeline-list` 为空，事件由浏览器动态创建。

- [ ] **Step 3: 新增安全的事件卡生成函数**

在 `table()` 后新增：

```python
def build_event_card(event: dict) -> str:
    """把一条已校验事件渲染为可筛选、可展开的静态档案卡。"""
    badges = [event["track"], event["category"]]
    if event["family"]:
        badges.append(event["family"])
    badge_html = "".join(f'<span class="badge">{esc(item)}</span>' for item in badges)
    if event["autoGenerated"]:
        badge_html += '<span class="badge auto">自动收录</span>'
    if event["verification"] != "人工整理":
        badge_html += f'<span class="badge verification">{esc(event["verification"])}</span>'
    color = TRACK_COPY[event["track"]][1]
    detail_items = (
        ("相对变化", event["delta"]),
        ("优化重点", event["optimization"]),
        ("可用范围", event["availability"]),
        ("为什么重要", event["significance"]),
    )
    detail_html = "".join(
        f'<div><b>{esc(label)}</b><span>{esc(value)}</span></div>'
        for label, value in detail_items
    )
    precision = "精确到日" if event["precision"] == "day" else f'日期精度：{event["precision"]}'
    return (
        f'<article class="event-card" style="--track-color:{color}" '
        f'data-date="{esc(event["date"])}" data-year="{esc(event["date"][:4])}" '
        f'data-category="{esc(event["category"])}" data-track="{esc(event["track"])}" '
        f'data-family="{esc(event["family"])}" data-verification="{esc(event["verification"])}">'
        f'<div class="event-date"><time datetime="{esc(event["date"])}">{esc(event["date"])}</time><small>{esc(precision)}</small></div>'
        f'<div class="event-main"><h3>{esc(event["title"])}</h3><div class="badges">{badge_html}</div>'
        f'<p>{esc(event["summary"])}</p><details><summary>查看变化、优化与意义</summary>'
        f'<div class="event-grid">{detail_html}</div>'
        f'<a href="{esc(event["sourceUrl"])}" target="_blank" rel="noopener noreferrer">'
        f'{esc(event["sourceLabel"])}：查看官方来源 ↗</a></details></div></article>'
    )
```

实现时必须继续为外链输出 `target="_blank" rel="noopener noreferrer"`，正文使用 `esc()`，来源 URL 已由 `load_and_validate_data()` 限定为 HTTPS 官方域名。

- [ ] **Step 4: 新增年份分组函数并注入模板**

```python
def build_timeline_groups(events: list[dict]) -> str:
    """按年份升序生成时间线，浏览器可在不重建内容的情况下筛选和倒序。"""
    grouped: dict[str, list[dict]] = {}
    for event in events:
        grouped.setdefault(event["date"][:4], []).append(event)
    return "".join(
        f'<section class="year-group" id="timeline-{year}" data-year="{year}">'
        f'<header class="year-heading"><span>{year}</span>'
        f'<strong><span data-year-visible-count>{len(items)}</span> 条事件</strong></header>'
        f'<div class="year-events">{"".join(build_event_card(item) for item in items)}</div>'
        '</section>'
        for year, items in grouped.items()
    )
```

在模板中使用：

```html
<div id="timeline-list" class="timeline-list">__TIMELINE_GROUPS__</div>
<div id="timeline-empty" class="empty-state" hidden>没有符合条件的事件。<button type="button" data-clear-all>清除筛选</button></div>
```

并在 replacements 加入：

```python
"__TIMELINE_GROUPS__": build_timeline_groups(events),
```

- [ ] **Step 5: 运行预渲染、安全和离线测试**

Run:

```bash
python3 -m unittest \
  tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_timeline_is_prerendered_and_grouped_by_year \
  tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_json_and_links_are_safely_embedded \
  tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_output_is_large_standalone_document \
  -v
```

Expected: PASS。

- [ ] **Step 6: 审查本任务差异**

Run:

```bash
git diff --stat && git diff -- work/build-page.py tests/test-openai-evolution-panorama.py
```

Expected: 事件数量与数据文件不变，只有生成方式从浏览器创建改为 Python 预渲染。

---

### Task 3: 实现统一筛选状态、筛选标签与年份显隐

**Files:**
- Modify: `work/build-page.py:157-202`
- Modify: `tests/test-openai-evolution-panorama.py:45-66`

**Interfaces:**
- Consumes: `state() -> {q, year, category, track, family, sort, newOnly}`、预渲染 `.event-card` 和 `.year-group`。
- Produces: `filterEvents() -> HTMLElement[]`、`renderFilterChips(filterState: object) -> void`、`clearFilter(key: string) -> void`、`renderTimeline() -> void`、`#active-filters`、`#timeline-empty`。
- Preserves: `updateHash()` 和 `loadHash()` 的参数名与默认升序行为。

- [ ] **Step 1: 写入筛选标签和统一状态的失败测试**

新增：

```python
def test_filter_chips_year_visibility_and_empty_state_exist(self) -> None:
    for fragment in (
        'id="active-filters"',
        'id="timeline-empty"',
        'data-clear-all',
        "function filterEvents()",
        "function renderFilterChips(filterState)",
        "function clearFilter(key)",
        "function renderTimeline()",
        "group.hidden=visibleCount===0",
    ):
        with self.subTest(fragment=fragment):
            self.assertIn(fragment, self.html)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m unittest tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_filter_chips_year_visibility_and_empty_state_exist -v
```

Expected: FAIL，当前页面没有活动筛选标签和年份组显隐逻辑。

- [ ] **Step 3: 增加筛选标签容器和结果摘要**

筛选工具条结构至少包含：

```html
<div class="filter-summary">
  <div id="active-filters" class="active-filters" aria-label="当前筛选条件"></div>
  <span id="result-status" class="result-status" aria-live="polite"></span>
</div>
```

- [ ] **Step 4: 将动态建卡脚本替换为 DOM 筛选**

使用一个状态源过滤预渲染卡片：

```javascript
function filterEvents(){
 const filterState=state();
 const query=filterState.q.toLocaleLowerCase("zh-CN");
 const cutoff=new Date(data.cutoff+"T00:00:00Z");
 const recent=new Date(cutoff);recent.setUTCDate(recent.getUTCDate()-30);
 return cards.filter(card=>{
   const matches=(!query||card.textContent.toLocaleLowerCase("zh-CN").includes(query))
    &&(!filterState.year||card.dataset.year===filterState.year)
    &&(!filterState.category||card.dataset.category===filterState.category)
    &&(!filterState.track||card.dataset.track===filterState.track)
    &&(!filterState.family||card.dataset.family===filterState.family)
    &&(!filterState.newOnly||new Date(card.dataset.date+"T00:00:00Z")>=recent);
   card.hidden=!matches;
   return matches;
 });
}
```

`renderTimeline()` 必须：

1. 调用 `filterEvents()`。
2. 按升序或倒序重排年份组和组内事件。
3. 更新每个年份的可见数量并执行 `group.hidden=visibleCount===0`。
4. 更新 `#timeline-empty` 和结果数。
5. 调用 `renderFilterChips(filterState)`。
6. 调用 `updateHash()`。

- [ ] **Step 5: 实现可删除筛选标签**

```javascript
function clearFilter(key){
 if(key==="newOnly")controls.newOnly.checked=false;
 else if(key==="q")controls.search.value="";
 else if(controls[key])controls[key].value=key==="sort"?"asc":"";
 renderTimeline();
}
function renderFilterChips(filterState){
 const labels={q:"关键词",year:"年份",category:"类别",track:"产品线",family:"模型家族",newOnly:"最近 30 天"};
 activeFilters.replaceChildren();
 Object.entries(labels).forEach(([key,label])=>{
   if(!filterState[key])return;
   const button=node("button","filter-chip",`${label}：${filterState[key]==="1"?"是":filterState[key]} ×`);
   button.type="button";button.dataset.clearFilter=key;
   button.setAttribute("aria-label",`移除${label}筛选`);
   activeFilters.appendChild(button);
 });
}
```

筛选标签通过事件委托调用 `clearFilter(button.dataset.clearFilter)`；`[data-clear-all]` 与原重置按钮共用同一个 `resetFilters()`，不得复制重置字段列表。

- [ ] **Step 6: 运行筛选相关测试与脚本语法检查**

Run:

```bash
python3 -m unittest \
  tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_filter_controls_and_accessibility_exist \
  tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_filter_chips_year_visibility_and_empty_state_exist \
  -v
python3 work/build-page.py
python3 - <<'PY'
from pathlib import Path
import re
html = Path("outputs/openai-chatgpt-evolution-panorama.html").read_text(encoding="utf-8")
script = "\n".join(re.findall(r'<script(?![^>]*type="application/json")[^>]*>(.*?)</script>', html, re.S))
Path("/tmp/openai-panorama-script.js").write_text(script, encoding="utf-8")
PY
node --check /tmp/openai-panorama-script.js
```

Expected: 两项测试 PASS，Node 输出为空且退出码为 0。

- [ ] **Step 7: 审查筛选状态没有分叉**

Run:

```bash
grep -nE 'function (state|filterEvents|renderFilterChips|clearFilter|resetFilters|renderTimeline|updateHash|loadHash)' work/build-page.py
git diff -- work/build-page.py tests/test-openai-evolution-panorama.py
```

Expected: 所有筛选入口最终调用 `renderTimeline()`；重置逻辑只有 `resetFilters()` 一份。

---

### Task 4: 实现章节导航、阅读进度和页内入口

**Files:**
- Modify: `work/build-page.py:150-202`
- Modify: `tests/test-openai-evolution-panorama.py:45-87`

**Interfaces:**
- Consumes: `[data-section-target]`、主要章节元素、`#reading-progress`。
- Produces: `scrollToSection(sectionId: string) -> void`、`setActiveSection(sectionId: string) -> void`、`updateReadingProgress() -> void`、`setupSectionObserver() -> void`。
- Preserves: 筛选参数继续独占 URL hash；章节点击不写入 hash，避免清除筛选状态。

- [ ] **Step 1: 写入章节导航行为的失败测试**

新增：

```python
def test_section_navigation_preserves_filter_hash(self) -> None:
    for fragment in (
        "function scrollToSection(sectionId)",
        "function setActiveSection(sectionId)",
        "function updateReadingProgress()",
        "function setupSectionObserver()",
        "function showLatestEvents()",
        'id="back-to-top"',
        "event.preventDefault()",
        'link.setAttribute("aria-current","location")',
        'window.addEventListener("scroll",updateReadingProgress',
    ):
        with self.subTest(fragment=fragment):
            self.assertIn(fragment, self.html)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m unittest tests.test-openai-evolution-panorama.OpenAIPanoramaPageTest.test_section_navigation_preserves_filter_hash -v
```

Expected: FAIL，缺少章节观察和阅读进度函数。

- [ ] **Step 3: 实现不占用筛选 hash 的页内导航**

```javascript
function scrollToSection(sectionId){
 const target=document.getElementById(sectionId);
 if(target)target.scrollIntoView({behavior:reduceMotion.matches?"auto":"smooth",block:"start"});
}
document.querySelectorAll("[data-section-target]").forEach(link=>{
 link.addEventListener("click",event=>{
   event.preventDefault();
   scrollToSection(link.dataset.sectionTarget);
 });
});
```

`reduceMotion` 使用：

```javascript
const reduceMotion=window.matchMedia("(prefers-reduced-motion: reduce)");
```

- [ ] **Step 4: 实现章节活动状态和阅读进度**

```javascript
function setActiveSection(sectionId){
 sectionLinks.forEach(link=>{
   if(link.dataset.sectionTarget===sectionId)link.setAttribute("aria-current","location");
   else link.removeAttribute("aria-current");
 });
}
function updateReadingProgress(){
 const root=document.documentElement;
 const maximum=root.scrollHeight-root.clientHeight;
 const ratio=maximum>0?Math.min(1,Math.max(0,root.scrollTop/maximum)):0;
 progressBar.style.transform=`scaleX(${ratio})`;
}
function setupSectionObserver(){
 if(!("IntersectionObserver" in window))return;
 const observer=new IntersectionObserver(entries=>{
   const visible=entries.filter(entry=>entry.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];
   if(visible)setActiveSection(visible.target.id);
 },{rootMargin:"-20% 0px -65%",threshold:[0,.15,.4]});
 observedSections.forEach(section=>observer.observe(section));
}
```

滚动监听使用 `{passive:true}`；顶部目录即使没有 IntersectionObserver 仍可点击。

- [ ] **Step 5: 实现“最新更新”和返回顶部入口**

在页面框架加入：

```html
<button id="back-to-top" class="back-to-top" type="button" data-section-target="archive-hero" aria-label="返回页面顶部">↑</button>
```

“查看最新更新”不写入章节 hash，而是复用现有排序与渲染状态：

```javascript
function showLatestEvents(){
 controls.sort.value="desc";
 renderTimeline();
 const latestGroup=yearGroups.find(group=>!group.hidden);
 if(latestGroup)latestGroup.scrollIntoView({behavior:reduceMotion.matches?"auto":"smooth",block:"start"});
}
document.querySelector("[data-show-latest]").addEventListener("click",event=>{
 event.preventDefault();
 showLatestEvents();
});
```

返回顶部按钮调用 `scrollToSection("archive-hero")`；当 `document.documentElement.scrollTop` 小于一个视口高度时通过 `hidden` 隐藏，超过阈值后显示。

- [ ] **Step 6: 运行导航、无障碍和减少动效测试**

Run:

```bash
python3 -m unittest discover -s tests -p 'test-openai-evolution-panorama.py' -v
```

Expected: 页面测试全部 PASS。

- [ ] **Step 7: 审查 URL hash 边界**

Run:

```bash
grep -nE 'location.hash|replaceState|data-section-target|scrollIntoView|aria-current' work/build-page.py
```

Expected: 只有 `loadHash()` 和 `updateHash()` 读写筛选 hash；章节导航只调用 `scrollIntoView()`。

---

### Task 5: 重构专题视觉、响应式、深色与打印样式

**Files:**
- Modify: `work/build-page.py:139-169`
- Modify: `tests/test-openai-evolution-panorama.py:75-84`

**Interfaces:**
- Consumes: 现有专题内容和表格生成器 `table(headers, rows)`。
- Produces: `.archive-grid`、`.lineage-list`、`.capability-matrix`、`.evolution-steps`、`.media-matrix`、`.comparison-table`、`.source-index` 等语义化视觉类；不改变专题事实内容。

- [ ] **Step 1: 写入专题差异化和响应式失败测试**

新增：

```python
def test_topic_sections_use_distinct_archive_layouts(self) -> None:
    for class_name in (
        "lineage-list",
        "capability-matrix",
        "evolution-steps",
        "media-matrix",
        "comparison-table",
        "source-index",
    ):
        with self.subTest(class_name=class_name):
            self.assertIn(f'class="{class_name}', self.html)
    self.assertIn("@media (max-width: 980px)", self.html)
    self.assertIn("@media (max-width: 720px)", self.html)
    self.assertIn("@media print", self.html)
    self.assertIn("@media (prefers-reduced-motion: reduce)", self.html)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m unittest discover -s tests -p 'test-openai-evolution-panorama.py' -v
```

Expected: 新专题类断言失败。

- [ ] **Step 3: 为专题分配不同但统一的布局类**

按内容职责调整模板：

```html
<div class="lineage-list topic-grid">原有三个模型谱系 article 保持文案不变</div>
<div class="capability-matrix">__CHATGPT_TABLE__</div>
<div class="evolution-steps topic-grid">原有 API / Agents 三个年代 article 保持文案不变</div>
<div class="evolution-steps">__CODEX_TABLE__</div>
<div class="media-matrix">__MULTIMODAL_TABLE__</div>
<div class="comparison-table">__PLAN_TABLE__</div>
<ol class="source-index">__SOURCE_LIST__</ol>
```

保留原有章节 `id`、标题和文案，避免 UI 改版引入事实变化。

- [ ] **Step 4: 完成桌面、平板、移动端样式**

CSS 需要明确覆盖：

```css
@media (max-width:980px){.hero-grid,.overview-grid,.section-head{grid-template-columns:1fr}.section-directory{overflow-x:auto}.filter-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:720px){.shell{width:min(100% - 24px,1180px)}.hero-era{font-size:clamp(3rem,22vw,6rem)}.filter-grid{grid-template-columns:1fr}.year-heading{position:static}.event-card{grid-template-columns:1fr}.table-wrap{overflow-x:auto}}
@media (max-width:420px){.archive-status{grid-template-columns:1fr 1fr}.section-directory a{padding-inline:10px}.event-card{padding:16px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
```

深色主题必须分别定义 surface、边框、弱文本、输入控件和轨道标签对比度，不能只反转颜色。

- [ ] **Step 5: 完成打印样式**

```css
@media print{
 .topbar,.section-directory,.reading-progress,.controls,.quick-pills,.back-to-top{display:none!important}
 body{background:#fff;color:#000;font-size:10pt}
 .shell{width:100%}
 section{break-inside:auto;padding:18pt 0}
 .event-card,.year-group,.topic-card{break-inside:avoid;box-shadow:none}
 details{display:block}details>*{display:block}details summary{display:none}
 a{color:#000;text-decoration:none}a[href^="http"]::after{content:" (" attr(href) ")";font-size:8pt}
 }
```

- [ ] **Step 6: 运行页面测试和脚本检查**

Run:

```bash
python3 -m unittest discover -s tests -p 'test-openai-evolution-panorama.py' -v
python3 work/build-page.py
python3 - <<'PY'
from pathlib import Path
import re
html = Path("outputs/openai-chatgpt-evolution-panorama.html").read_text(encoding="utf-8")
script = "\n".join(re.findall(r'<script(?![^>]*type="application/json")[^>]*>(.*?)</script>', html, re.S))
Path("/tmp/openai-panorama-script.js").write_text(script, encoding="utf-8")
PY
node --check /tmp/openai-panorama-script.js
```

Expected: 全部 PASS，Node 退出码为 0。

---

### Task 6: 更新文档、生成产物并执行完整回归

**Files:**
- Modify: `README.md:1-80`
- Regenerate: `outputs/openai-chatgpt-evolution-panorama.html`
- Verify unchanged: `work/timeline-data.json`

**Interfaces:**
- Consumes: 完成后的构建器和测试。
- Produces: 与实际界面一致的 README、可发布的最终 HTML 和完整验证证据。

- [ ] **Step 1: 更新 README 功能说明**

在“功能介绍”中加入并准确描述：

```markdown
- 采用数字档案馆 / 技术年鉴式界面，以年份分组、轨道标识和差异化专题视图提升长时间线的查阅效率。
- 桌面端提供章节目录和阅读进度，移动端使用紧凑的横向章节导航。
- 时间线由构建器预渲染；JavaScript 关闭时仍可阅读全部事件，启用后提供筛选、排序、筛选标签和 URL hash 分享。
```

更新原有筛选说明，加入可删除筛选标签与零结果恢复入口；不要宣称存在数据契约未提供的“里程碑等级”。

- [ ] **Step 2: 重新生成最终 HTML**

Run:

```bash
python3 work/build-page.py
```

Expected: 输出包含 123 条事件；事件数量以当前数据实际值为准，构建过程中不得运行自动更新器。

- [ ] **Step 3: 运行完整测试套件**

Run:

```bash
python3 -m unittest \
  tests/test-timeline-data.py \
  tests/test-openai-evolution-panorama.py \
  tests/test-auto-update.py \
  tests/test-workflow-static.py \
  -v
```

Expected: 全部 PASS。

- [ ] **Step 4: 检查内嵌 JavaScript**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re
html = Path("outputs/openai-chatgpt-evolution-panorama.html").read_text(encoding="utf-8")
script = "\n".join(re.findall(r'<script(?![^>]*type="application/json")[^>]*>(.*?)</script>', html, re.S))
Path("/tmp/openai-panorama-script.js").write_text(script, encoding="utf-8")
PY
node --check /tmp/openai-panorama-script.js
```

Expected: Node 输出为空且退出码为 0。

- [ ] **Step 5: 验证事实数据没有变化**

Run:

```bash
git diff --exit-code -- work/timeline-data.json work/source-config.json work/source-state.json work/update-openai-panorama.py .github/workflows/update-openai-panorama.yml
```

Expected: 退出码为 0。

- [ ] **Step 6: 启动本地页面进行视觉验收**

Run:

```bash
python3 -m http.server 8765 --directory outputs
```

在浏览器检查：

- 1440px：非对称首屏、常驻章节目录、年份双列节奏、筛选工具条。
- 768px：首屏改为单列或紧凑布局，章节导航可横向滚动，筛选器不溢出。
- 390px：无页面级横向滚动，事件卡、表格和来源链接可读。
- 浅色与深色主题：正文、弱文本、边框、标签和焦点状态均清晰。
- 搜索、年份、类别、产品线、模型家族、最近 30 天、正倒序和快捷筛选。
- 单独移除筛选标签、清除全部筛选、零结果恢复和 URL hash 刷新恢复。
- 章节目录、阅读进度、首屏入口、事件展开、展开全部和键盘焦点。
- 打印预览隐藏交互控件，事件详情和来源仍可阅读。

- [ ] **Step 7: 最终差异审查**

Run:

```bash
git status --short
git diff --stat
git diff --check
git diff -- work/build-page.py tests/test-openai-evolution-panorama.py README.md
git diff --numstat -- work/timeline-data.json
```

Expected: 修改范围仅包括设计文档、实施计划、构建器、页面测试、README 和生成 HTML；`timeline-data.json` 无差异；`git diff --check` 无错误。

- [ ] **Step 8: 停止在提交与发布之前**

不运行 `git commit`、`git push` 或 GitHub Actions。向用户报告测试结果、视觉验收结果和差异摘要，等待用户明确授权提交与发布。
