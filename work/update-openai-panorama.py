# -*- coding: utf-8 -*-
"""
从 OpenAI 官方 RSS、sitemap 和受监控页面发现更新，安全合并时间线并写入审计状态。
"""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "work" / "timeline-data.json"
CONFIG_PATH = ROOT / "work" / "source-config.json"
STATE_PATH = ROOT / "work" / "source-state.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT = 30
ALLOWED_HOSTS = {
    "openai.com", "www.openai.com", "help.openai.com", "developers.openai.com",
    "platform.openai.com", "learn.chatgpt.com", "chatgpt.com",
}
RELEASE_SIGNALS = {
    "introducing", "launch", "launched", "release", "released", "available",
    "update", "updated", "new", "preview", "general availability", "deprecated",
    "deprecation", "pricing", "changelog", "model", "api", "chatgpt", "codex",
}


class MetadataParser(HTMLParser):
    """提取页面标题、元数据、JSON-LD 和稳定可见文本。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.visible_parts: list[str] = []
        self.json_ld_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self._in_title = False
        self._in_json_ld = False
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.casefold(): (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if tag == "script" and attributes.get("type", "").casefold() == "application/ld+json":
            self._in_json_ld = True
            self._ignored_depth = max(0, self._ignored_depth - 1)
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").casefold()
            content = attributes.get("content", "").strip()
            if key and content:
                self.meta[key] = content

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            return
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if not value:
            return
        if self._in_json_ld:
            self.json_ld_parts.append(data)
        elif self._in_title:
            self.title_parts.append(value)
        elif not self._ignored_depth:
            self.visible_parts.append(value)


def canonical_url(url: str) -> str:
    """验证官方 HTTPS URL，并移除 query、fragment、www 与尾部斜杠差异。"""
    parsed = urlparse(url.strip())
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or hostname not in ALLOWED_HOSTS:
        raise ValueError(f"只允许 OpenAI 官方 HTTPS URL：{url}")
    if hostname == "www.openai.com":
        hostname = "openai.com"
    port = f":{parsed.port}" if parsed.port else ""
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunparse(("https", hostname + port, path, "", "", ""))


def parse_sitemap(xml_text: str) -> list[dict[str, str]]:
    """解析 sitemap urlset 或 sitemapindex，保留 lastmod 仅供发现变化。"""
    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []
    for node in list(root):
        loc = ""
        lastmod = ""
        for child in list(node):
            name = child.tag.rsplit("}", 1)[-1]
            if name == "loc" and child.text:
                loc = child.text.strip()
            elif name == "lastmod" and child.text:
                lastmod = child.text.strip()[:10]
        if not loc:
            continue
        items.append({"url": canonical_url(loc), "lastmod": lastmod})
    return items


def parse_feed(xml_text: str) -> list[dict[str, str]]:
    """解析 RSS/Atom 条目，发布日期只采用 pubDate、published 或 updated。"""
    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
            continue
        values: dict[str, str] = {}
        link = ""
        for child in list(node):
            name = child.tag.rsplit("}", 1)[-1]
            text = " ".join("".join(child.itertext()).split())
            if name == "link":
                link = (child.attrib.get("href") or text).strip()
            elif name in {"title", "description", "summary", "pubDate", "published", "updated"}:
                values[name] = text
        if not link:
            continue
        raw_date = values.get("pubDate") or values.get("published") or values.get("updated") or ""
        date_value = normalize_date(raw_date)
        items.append({
            "url": canonical_url(link),
            "title": html.unescape(values.get("title", "")).strip(),
            "description": clean_text(values.get("description") or values.get("summary") or ""),
            "date": date_value,
        })
    return items


def normalize_date(value: str) -> str:
    """把 ISO 或 RFC 2822 日期规范为 YYYY-MM-DD；无法判断时返回空字符串。"""
    candidate = value.strip()
    match = re.search(r"\d{4}-\d{2}-\d{2}", candidate)
    if match:
        return match.group(0)
    if candidate:
        try:
            parsed = email.utils.parsedate_to_datetime(candidate)
            return parsed.date().isoformat()
        except (TypeError, ValueError, OverflowError):
            pass
    return ""


def extract_json_dates(value: object) -> list[str]:
    """递归提取 JSON-LD 中明确的首次发布日期。"""
    dates: list[str] = []
    if isinstance(value, dict):
        published = value.get("datePublished")
        if isinstance(published, str) and normalize_date(published):
            dates.append(normalize_date(published))
        for child in value.values():
            dates.extend(extract_json_dates(child))
    elif isinstance(value, list):
        for child in value:
            dates.extend(extract_json_dates(child))
    return dates


def parse_page_metadata(page: str, url: str) -> dict[str, str]:
    """从 HTML 中提取官方标题、摘要、发布日期和稳定正文。"""
    canonical = canonical_url(url)
    parser = MetadataParser()
    parser.feed(page)
    title = parser.meta.get("og:title") or " ".join(parser.title_parts)
    title = re.sub(r"\s*[|–—-]\s*OpenAI\s*$", "", title, flags=re.IGNORECASE).strip()
    description = parser.meta.get("description") or parser.meta.get("og:description") or ""
    dates: list[str] = []
    if parser.json_ld_parts:
        raw_json = "".join(parser.json_ld_parts).strip()
        try:
            dates.extend(extract_json_dates(json.loads(raw_json)))
        except json.JSONDecodeError:
            for block in parser.json_ld_parts:
                try:
                    dates.extend(extract_json_dates(json.loads(block)))
                except json.JSONDecodeError:
                    continue
    meta_date = parser.meta.get("article:published_time") or parser.meta.get("date") or ""
    date_value = dates[0] if dates else normalize_date(meta_date)
    stable_text = " ".join(parser.visible_parts)
    stable_text = re.sub(r"\s+", " ", html.unescape(stable_text)).strip()
    return {
        "url": canonical,
        "title": html.unescape(title).strip(),
        "description": clean_text(description),
        "date": date_value,
        "stableText": stable_text,
    }


def clean_text(value: str) -> str:
    """移除 HTML 标签并压缩空白，避免把外部标记写入数据。"""
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", text).strip()


def classify_event(text: str) -> tuple[str, str, str]:
    """根据官方标题与摘要映射类别、产品轨道和模型家族。"""
    value = unicodedata.normalize("NFKC", text).casefold()
    if any(word in value for word in ("deprecat", "sunset", "retire", "migration", "system card", "safety")):
        return "安全", "迁移与治理", ""
    if any(word in value for word in ("subscription", "pricing", "price", "plus", "pro plan", "business plan", "enterprise", "chatgpt go")):
        return "订阅", "订阅计划", ""
    if "codex" in value:
        family = "GPT-5 Codex" if "gpt-5" in value and "codex" in value else "Codex"
        return "Codex", "Codex", family
    if any(word in value for word in ("sora", "video generation", "image generation", "dall·e", "dall-e", "whisper", "voice", "audio", "realtime", "gpt live", "gpt-live")):
        if "sora" in value or "video" in value:
            family = "Sora"
        elif "dall" in value:
            family = "DALL·E"
        elif "whisper" in value:
            family = "Whisper"
        elif "image" in value:
            family = "GPT Image"
        elif "live" in value:
            family = "GPT Live"
        else:
            family = "Realtime"
        return "多模态", "多模态", family
    if any(word in value for word in ("responses api", "agents api", "agents sdk", "api", "developer", "function calling", "structured outputs", "mcp")):
        return "API", "API / Agents", ""
    if "chatgpt" in value or any(word in value for word in ("memory", "canvas", "deep research", "operator", "study mode")):
        return "ChatGPT", "ChatGPT 产品", ""
    if any(word in value for word in ("model", "gpt", "o1", "o3", "o4", "open weight", "gpt-oss")):
        if any(word in value for word in ("o1", "o3", "o4")):
            family = "o 系列"
        elif "gpt-6" in value:
            family = "GPT-6"
        elif "gpt-4o" in value:
            family = "GPT-4o"
        elif "gpt-4" in value:
            family = "GPT-4"
        elif "gpt-3.5" in value:
            family = "GPT-3.5"
        elif "gpt-oss" in value or "open weight" in value:
            family = "Open models"
        else:
            family = "GPT"
        return "模型", "模型体系", family
    return "技术基础", "技术基础", ""


def make_event(
    metadata: dict[str, str],
    source_label: str,
    classification: tuple[str, str, str] | None = None,
    verification: str = "自动收录",
) -> dict:
    """把官方页面元数据转换为完整且措辞保守的时间线事件。"""
    if not metadata.get("date") or not metadata.get("title"):
        raise ValueError("自动事件缺少发布日期或标题")
    category, track, family = classification or classify_event(
        f"{metadata['title']} {metadata.get('description', '')}"
    )
    summary = clean_text(metadata.get("description", ""))
    if not summary:
        summary = f"OpenAI 官方页面发布或更新了“{metadata['title']}”。"
    summary = summary[:360].rstrip()
    optimization_focus = {
        "模型": "优化重点以官方公布的模型能力、效率和适用任务说明为准。",
        "ChatGPT": "优化重点以官方公布的产品体验、工具和工作流说明为准。",
        "API": "优化重点以官方公布的接口、工具和开发者工作流说明为准。",
        "Codex": "优化重点以官方公布的软件工程、代码执行和审查能力说明为准。",
        "多模态": "优化重点以官方公布的图像、语音、视频或实时交互能力说明为准。",
        "订阅": "优化重点以官方公布的计划结构、额度或计费口径说明为准。",
        "安全": "优化重点以官方公布的迁移时间表、安全边界和替代方案为准。",
        "技术基础": "优化重点以官方页面说明为准。",
    }[category]
    return {
        "date": metadata["date"],
        "precision": "day",
        "category": category,
        "track": track,
        "family": family,
        "title": clean_text(metadata["title"])[:180],
        "summary": summary,
        "delta": "相较于此前公开状态，官方新增或更新了该模型、产品或平台信息；具体差异以官方原文为准。",
        "optimization": optimization_focus,
        "availability": "适用计划、地区、平台、配额和发布时间可能分阶段变化，以官方原文为准。",
        "significance": "该条目来自官方更新，用于提示产品与模型演进中的新节点，不推断官方未公布的指标。",
        "sourceLabel": source_label,
        "sourceUrl": canonical_url(metadata["url"]),
        "autoGenerated": True,
        "verification": verification,
    }


def merge_events(
    existing: list[dict],
    candidates: list[dict],
    cutoff: str,
    max_additions: int = 20,
) -> tuple[list[dict], int]:
    """去重并合并不晚于检查日的自动事件，异常大量新增时终止。"""
    known_urls = {
        canonical_url(item["sourceUrl"])
        for item in existing
        if item.get("verification") != "页面变更"
    }
    page_change_keys = {
        (canonical_url(item["sourceUrl"]), item["date"])
        for item in existing
        if item.get("verification") == "页面变更"
    }
    accepted: list[dict] = []
    for candidate in candidates:
        event_date = normalize_date(candidate.get("date", ""))
        if not event_date or event_date > cutoff:
            continue
        url = canonical_url(candidate["sourceUrl"])
        candidate = dict(candidate)
        candidate["date"] = event_date
        candidate["sourceUrl"] = url
        if candidate.get("verification") == "页面变更":
            key = (url, event_date)
            if key in page_change_keys:
                continue
            page_change_keys.add(key)
        else:
            if url in known_urls:
                continue
            known_urls.add(url)
        accepted.append(candidate)
        if len(accepted) > max_additions:
            raise ValueError(f"单次自动新增超过 {max_additions} 条，已终止更新")
    merged = list(existing) + accepted
    merged.sort(key=lambda item: (item["date"], item.get("category", ""), item.get("title", "")))
    return merged, len(accepted)


def content_hash(text: str) -> str:
    """对归一化可见文本计算摘要，降低空白与 Unicode 形式造成的噪声。"""
    normalized = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", text)).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def evaluate_monitored_page(
    page_config: dict,
    stable_text: str,
    page_hashes: dict[str, str],
    current_date: str,
) -> tuple[dict[str, str], dict[str, str] | None]:
    """首次仅建立页面基线，之后正文摘要变化时返回页面变更候选。"""
    url = canonical_url(page_config["url"])
    updated_hashes = dict(page_hashes)
    digest = content_hash(stable_text)
    previous = updated_hashes.get(url)
    updated_hashes[url] = digest
    if not previous or previous == digest:
        return updated_hashes, None
    return updated_hashes, {
        "url": url,
        "date": current_date,
        "title": f"{page_config['name']}发生更新",
        "description": (
            f"自动监控检测到“{page_config['name']}”官方页面的稳定可见内容发生变化。"
            "具体条款、价格、型号、可用范围或时间表以官方原文为准。"
        ),
    }


def atomic_write_json(path: Path, value: dict) -> None:
    """在目标目录写临时文件并以 os.replace 原子替换 JSON。"""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_update(data_path: Path, state_path: Path, data: dict, state: dict) -> None:
    """在全部抓取和校验完成后原子写入时间线与状态。"""
    atomic_write_json(data_path, data)
    atomic_write_json(state_path, state)


def fetch_text(url: str, user_agent: str, retries: int = 3) -> str:
    """使用有限重试读取官方页面，并限制协议、主机、超时和响应体大小。"""
    target = canonical_url(url)
    request = urllib.request.Request(
        target,
        headers={"User-Agent": user_agent, "Accept": "text/html,application/xml,application/rss+xml;q=0.9,*/*;q=0.8"},
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError(f"响应超过 5MB 限制：{target}")
                charset = response.headers.get_content_charset() or "utf-8"
                return body.decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1 + attempt)
    raise RuntimeError(f"读取官方页面失败：{target}：{last_error}")


def discover_source(source: dict, user_agent: str) -> list[dict[str, str]]:
    """读取 RSS 或 sitemap；sitemap 的 lastmod 只用于减少无关页面抓取。"""
    body = fetch_text(source["url"], user_agent)
    if source["type"] == "rss":
        return parse_feed(body)
    items = parse_sitemap(body)
    expanded: list[dict[str, str]] = []
    for item in items[:10000]:
        path = urlparse(item["url"]).path
        if path.endswith(".xml"):
            nested = parse_sitemap(fetch_text(item["url"], user_agent))
            expanded.extend(nested)
        else:
            expanded.append(item)
    prefixes = tuple(source.get("pathPrefixes", []))
    if prefixes:
        expanded = [item for item in expanded if urlparse(item["url"]).path.startswith(prefixes)]
    return expanded


def is_relevant_release(metadata: dict[str, str], required_keywords: list[str]) -> bool:
    """只保留同时包含产品关键词与发布信号的官方页面。"""
    text = f"{metadata.get('title', '')} {metadata.get('description', '')}".casefold()
    has_keyword = any(keyword.casefold() in text for keyword in required_keywords)
    has_signal = any(signal in text for signal in RELEASE_SIGNALS)
    return has_keyword and has_signal


def append_changelog(events: list[dict], checked_at: str) -> None:
    """把本轮自动新增事件写入更新日志顶部。"""
    if not events:
        return
    existing = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else "# 更新日志\n"
    body = existing[len("# 更新日志\n"):].lstrip("\n") if existing.startswith("# 更新日志\n") else existing
    lines = [f"## {checked_at[:10]} 自动更新", ""]
    lines.extend(
        f"- **{event['date']} · {event['category']}**：[{event['title']}]({event['sourceUrl']})"
        for event in events
    )
    temporary = CHANGELOG_PATH.with_name(f".{CHANGELOG_PATH.name}.{os.getpid()}.tmp")
    temporary.write_text("# 更新日志\n\n" + "\n".join(lines) + "\n\n" + body, encoding="utf-8")
    os.replace(temporary, CHANGELOG_PATH)


def run_update(today: str | None = None) -> int:
    """执行官方发现、页面监控、边界校验、状态写入和更新日志记录。"""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    configured_hosts = set(config.get("allowedHosts", []))
    if not configured_hosts <= ALLOWED_HOSTS:
        raise ValueError("来源配置包含未允许的官方主机")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {
        "lastChecked": "", "knownUrls": [], "pageHashes": {},
    }
    timezone = ZoneInfo(config.get("timezone", "Asia/Shanghai"))
    now = datetime.now(timezone)
    current_date = today or now.date().isoformat()
    if not normalize_date(current_date) or current_date != normalize_date(current_date):
        raise ValueError("检查日期必须为 YYYY-MM-DD")
    checked_at = now.isoformat(timespec="seconds")
    previous_cutoff = data.get("cutoff", "0001-01-01")
    known_urls = set(state.get("knownUrls", [])) | {
        canonical_url(item["sourceUrl"]) for item in data.get("events", [])
    }
    candidates: list[dict] = []

    for source in config["discoverySources"]:
        try:
            discovered = discover_source(source, config["userAgent"])
        except (RuntimeError, ValueError, ET.ParseError) as error:
            if source.get("required", True):
                raise RuntimeError(f"必需发现源失败：{source['name']}：{error}") from error
            print(f"警告：可选发现源失败：{source['name']}：{error}")
            continue
        for item in discovered:
            url = canonical_url(item["url"])
            if url in known_urls:
                continue
            metadata = dict(item)
            if source["type"] == "sitemap":
                lastmod = item.get("lastmod", "")
                if lastmod and lastmod <= previous_cutoff:
                    continue
                try:
                    metadata = parse_page_metadata(fetch_text(url, config["userAgent"]), url)
                except (RuntimeError, ValueError) as error:
                    print(f"警告：无法读取候选页面 {url}：{error}")
                    continue
            metadata["url"] = url
            publish_date = metadata.get("date", "")
            if not publish_date or publish_date > current_date:
                continue
            known_urls.add(url)
            if publish_date <= previous_cutoff:
                continue
            if is_relevant_release(metadata, source["requiredKeywords"]):
                candidates.append(make_event(metadata, source["label"]))

    page_hashes = dict(state.get("pageHashes", {}))
    for page_config in config["monitoredPages"]:
        url = canonical_url(page_config["url"])
        try:
            page = fetch_text(url, config["userAgent"])
            metadata = parse_page_metadata(page, url)
            page_hashes, change = evaluate_monitored_page(
                page_config, metadata["stableText"], page_hashes, current_date
            )
        except (RuntimeError, ValueError) as error:
            if page_config.get("required", True):
                raise RuntimeError(f"必需监控页失败：{page_config['name']}：{error}") from error
            print(f"警告：可选监控页失败：{page_config['name']}：{error}")
            continue
        known_urls.add(url)
        if change:
            classification = (
                page_config["category"], page_config["track"], page_config.get("family", "")
            )
            candidates.append(make_event(
                change,
                page_config["label"],
                classification=classification,
                verification="页面变更",
            ))

    merged, added = merge_events(data["events"], candidates, current_date, max_additions=20)
    previous_keys = {
        (canonical_url(item["sourceUrl"]), item["date"], item.get("verification", ""))
        for item in data["events"]
    }
    added_events = [
        item for item in merged
        if (canonical_url(item["sourceUrl"]), item["date"], item.get("verification", "")) not in previous_keys
    ]
    data["events"] = merged
    data["cutoff"] = current_date
    data["lastChecked"] = checked_at
    next_state = {
        "lastChecked": checked_at,
        "knownUrls": sorted(known_urls | {canonical_url(item["sourceUrl"]) for item in merged}),
        "pageHashes": page_hashes,
    }
    write_update(DATA_PATH, STATE_PATH, data, next_state)
    append_changelog(added_events, checked_at)
    print(f"检查完成：候选 {len(candidates)} 条，新增 {added} 条，时间线共 {len(merged)} 条。")
    return added


def main() -> None:
    """解析可选补跑日期并执行自动更新。"""
    parser = argparse.ArgumentParser(description="自动检查并更新 OpenAI 产品与模型演进全景")
    parser.add_argument("--today", help="测试或补跑日期，格式 YYYY-MM-DD（Asia/Shanghai）")
    args = parser.parse_args()
    run_update(args.today)


if __name__ == "__main__":
    main()
