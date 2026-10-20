"""
验证 OpenAI 全景自动更新器的官方来源解析、分类、去重、边界保护和原子写入。
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "work" / "update-openai-panorama.py"


def load_updater():
    """从 kebab-case 脚本路径加载更新模块。"""
    spec = importlib.util.spec_from_file_location("openai_panorama_updater", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 OpenAI 自动更新模块")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AutoUpdateTest(unittest.TestCase):
    """使用内嵌官方页面样本测试更新器，不访问真实网络。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.updater = load_updater()

    def test_canonical_url_accepts_only_official_https_and_removes_noise(self) -> None:
        self.assertEqual(
            self.updater.canonical_url("https://www.openai.com/index/gpt-7/?utm_source=x#top"),
            "https://openai.com/index/gpt-7",
        )
        self.assertEqual(
            self.updater.canonical_url("https://developers.openai.com/api/docs/changelog/?a=1"),
            "https://developers.openai.com/api/docs/changelog",
        )
        with self.assertRaisesRegex(ValueError, "官方 HTTPS"):
            self.updater.canonical_url("http://openai.com/index/gpt-7")
        with self.assertRaisesRegex(ValueError, "官方 HTTPS"):
            self.updater.canonical_url("https://example.com/openai-news")

    def test_parse_sitemap_supports_namespace_without_treating_lastmod_as_publish_date(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://openai.com/index/gpt-7/</loc><lastmod>2026-10-20</lastmod></url>
          <url><loc>https://openai.com/research/</loc></url>
        </urlset>"""
        items = self.updater.parse_sitemap(xml)
        self.assertEqual(items[0], {"url": "https://openai.com/index/gpt-7", "lastmod": "2026-10-20"})
        self.assertEqual(items[1]["lastmod"], "")

    def test_parse_rss_uses_pubdate_and_official_link(self) -> None:
        rss = """<?xml version="1.0"?><rss version="2.0"><channel>
          <item><title>Introducing GPT-7</title><link>https://openai.com/index/gpt-7/</link>
          <description>New model for complex work.</description>
          <pubDate>Tue, 20 Oct 2026 00:15:00 GMT</pubDate></item>
        </channel></rss>"""
        items = self.updater.parse_feed(rss)
        self.assertEqual(items[0]["date"], "2026-10-20")
        self.assertEqual(items[0]["url"], "https://openai.com/index/gpt-7")
        self.assertEqual(items[0]["title"], "Introducing GPT-7")

    def test_parse_page_metadata_ignores_meta_without_name_or_property(self) -> None:
        page = """<!doctype html><html><head>
          <meta charset="utf-8"><meta content="width=device-width">
          <title>OpenAI Changelog</title>
        </head><body><main>Version notes</main></body></html>"""
        metadata = self.updater.parse_page_metadata(
            page, "https://developers.openai.com/api/docs/changelog"
        )
        self.assertEqual(metadata["title"], "OpenAI Changelog")
        self.assertIn("Version notes", metadata["stableText"])

    def test_parse_page_metadata_prefers_json_ld_date_published(self) -> None:
        page = """<!doctype html><html><head>
          <title>Introducing GPT-7 | OpenAI</title>
          <meta property="og:title" content="Introducing GPT-7">
          <meta name="description" content="A model update for complex professional work.">
          <meta property="article:published_time" content="2026-10-19T23:00:00Z">
          <script type="application/ld+json">{
            "@context":"https://schema.org","@type":"NewsArticle",
            "datePublished":"2026-10-20T01:00:00Z"
          }</script>
        </head><body><main>Official product details.</main></body></html>"""
        metadata = self.updater.parse_page_metadata(page, "https://openai.com/index/gpt-7")
        self.assertEqual(metadata["title"], "Introducing GPT-7")
        self.assertEqual(metadata["description"], "A model update for complex professional work.")
        self.assertEqual(metadata["date"], "2026-10-20")
        self.assertIn("Official product details", metadata["stableText"])

    def test_classify_event_maps_all_panorama_tracks(self) -> None:
        cases = {
            "Introducing GPT-7 model": ("模型", "模型体系", "GPT"),
            "ChatGPT memory and canvas update": ("ChatGPT", "ChatGPT 产品", ""),
            "Responses API and Agents SDK changelog": ("API", "API / Agents", ""),
            "Codex CLI code review": ("Codex", "Codex", "Codex"),
            "Sora video and image generation": ("多模态", "多模态", "Sora"),
            "ChatGPT Plus subscription pricing": ("订阅", "订阅计划", ""),
            "Model deprecation migration notice": ("安全", "迁移与治理", ""),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.updater.classify_event(text), expected)

    def test_make_event_fills_contract_and_uses_conservative_language(self) -> None:
        metadata = {
            "url": "https://openai.com/index/gpt-7",
            "title": "Introducing GPT-7",
            "description": "OpenAI introduces GPT-7 for complex professional work.",
            "date": "2026-10-20",
        }
        event = self.updater.make_event(metadata, "OpenAI News")
        required = {
            "date", "precision", "category", "track", "family", "title", "summary",
            "delta", "optimization", "availability", "significance", "sourceLabel",
            "sourceUrl", "autoGenerated", "verification",
        }
        self.assertEqual(set(event), required)
        self.assertEqual(event["category"], "模型")
        self.assertEqual(event["track"], "模型体系")
        self.assertTrue(event["autoGenerated"])
        self.assertEqual(event["verification"], "自动收录")
        self.assertIn("官方", event["delta"])
        self.assertIn("以官方原文为准", event["availability"])
        self.assertNotIn("领先", event["optimization"])

    def test_merge_events_deduplicates_rejects_future_and_sorts(self) -> None:
        existing = [{
            "date": "2026-10-18", "category": "模型", "title": "旧事件",
            "sourceUrl": "https://openai.com/index/old",
        }]
        candidates = [
            {"date": "2026-10-20", "category": "模型", "title": "新事件", "sourceUrl": "https://openai.com/index/new?utm=x"},
            {"date": "2026-10-20", "category": "模型", "title": "重复", "sourceUrl": "https://www.openai.com/index/old/"},
            {"date": "2026-10-21", "category": "模型", "title": "未来", "sourceUrl": "https://openai.com/index/future"},
        ]
        merged, added = self.updater.merge_events(existing, candidates, "2026-10-20")
        self.assertEqual(added, 1)
        self.assertEqual([item["title"] for item in merged], ["旧事件", "新事件"])
        self.assertEqual(merged[-1]["sourceUrl"], "https://openai.com/index/new")

    def test_merge_events_aborts_when_single_run_exceeds_limit(self) -> None:
        candidates = [
            {
                "date": "2026-10-20", "category": "模型", "title": f"事件 {index}",
                "sourceUrl": f"https://openai.com/index/event-{index}",
            }
            for index in range(21)
        ]
        with self.assertRaisesRegex(ValueError, "单次自动新增超过 20 条"):
            self.updater.merge_events([], candidates, "2026-10-20", max_additions=20)

    def test_monitored_page_first_run_only_builds_baseline_then_detects_change(self) -> None:
        page = {"url": "https://developers.openai.com/api/docs/changelog", "name": "Developers Changelog"}
        first_state, first_candidate = self.updater.evaluate_monitored_page(page, "版本 A", {}, "2026-10-20")
        self.assertIsNone(first_candidate)
        self.assertIn(page["url"], first_state)
        second_state, second_candidate = self.updater.evaluate_monitored_page(
            page, "版本 B", first_state, "2026-10-21"
        )
        self.assertEqual(second_state.keys(), first_state.keys())
        self.assertEqual(second_candidate["date"], "2026-10-21")
        self.assertIn("发生更新", second_candidate["title"])

    def test_write_update_is_atomic_and_leaves_no_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "timeline.json"
            state_path = root / "state.json"
            data_path.write_text(json.dumps({"cutoff": "2026-10-19", "events": []}), encoding="utf-8")
            state_path.write_text(json.dumps({"knownUrls": [], "pageHashes": {}}), encoding="utf-8")
            self.updater.write_update(
                data_path,
                state_path,
                {"cutoff": "2026-10-20", "lastChecked": "2026-10-20T08:15:00+08:00", "events": []},
                {"lastChecked": "2026-10-20T08:15:00+08:00", "knownUrls": [], "pageHashes": {}},
            )
            self.assertEqual(json.loads(data_path.read_text(encoding="utf-8"))["cutoff"], "2026-10-20")
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["lastChecked"], "2026-10-20T08:15:00+08:00")
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_future_discovery_is_not_marked_known_before_publish_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "source-config.json"
            data_path = root / "timeline-data.json"
            state_path = root / "source-state.json"
            changelog_path = root / "CHANGELOG.md"
            config_path.write_text(json.dumps({
                "timezone": "Asia/Shanghai",
                "userAgent": "test",
                "allowedHosts": ["openai.com"],
                "discoverySources": [{
                    "name": "测试 RSS", "label": "OpenAI", "type": "rss",
                    "url": "https://openai.com/news/rss.xml", "required": True,
                    "requiredKeywords": ["gpt"],
                }],
                "monitoredPages": [],
            }), encoding="utf-8")
            data_path.write_text(json.dumps({
                "cutoff": "2026-10-20", "lastChecked": "", "events": [],
            }), encoding="utf-8")
            state_path.write_text(json.dumps({
                "lastChecked": "", "knownUrls": [], "pageHashes": {},
            }), encoding="utf-8")
            changelog_path.write_text("# 更新日志\n", encoding="utf-8")
            original_paths = (
                self.updater.CONFIG_PATH, self.updater.DATA_PATH, self.updater.STATE_PATH,
                self.updater.CHANGELOG_PATH, self.updater.discover_source,
            )
            self.updater.CONFIG_PATH = config_path
            self.updater.DATA_PATH = data_path
            self.updater.STATE_PATH = state_path
            self.updater.CHANGELOG_PATH = changelog_path
            self.updater.discover_source = lambda source, user_agent: [{
                "url": "https://openai.com/index/gpt-7",
                "title": "Introducing GPT-7",
                "description": "New GPT model",
                "date": "2026-10-21",
            }]
            try:
                self.updater.run_update("2026-10-20")
            finally:
                (
                    self.updater.CONFIG_PATH, self.updater.DATA_PATH, self.updater.STATE_PATH,
                    self.updater.CHANGELOG_PATH, self.updater.discover_source,
                ) = original_paths
            saved_state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn("https://openai.com/index/gpt-7", saved_state["knownUrls"])

    def test_optional_monitor_failure_does_not_abort_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "source-config.json"
            data_path = root / "timeline-data.json"
            state_path = root / "source-state.json"
            changelog_path = root / "CHANGELOG.md"
            config_path.write_text(json.dumps({
                "timezone": "Asia/Shanghai",
                "userAgent": "test",
                "allowedHosts": ["openai.com"],
                "discoverySources": [],
                "monitoredPages": [{
                    "name": "OpenAI Release Notes",
                    "label": "OpenAI Release Notes",
                    "url": "https://openai.com/products/release-notes",
                    "required": False,
                    "category": "技术基础",
                    "track": "技术基础",
                    "family": "",
                }],
            }), encoding="utf-8")
            data_path.write_text(json.dumps({
                "cutoff": "2026-10-19", "lastChecked": "", "events": [],
            }), encoding="utf-8")
            state_path.write_text(json.dumps({
                "lastChecked": "", "knownUrls": [], "pageHashes": {},
            }), encoding="utf-8")
            changelog_path.write_text("# 更新日志\n", encoding="utf-8")
            original_values = (
                self.updater.CONFIG_PATH, self.updater.DATA_PATH, self.updater.STATE_PATH,
                self.updater.CHANGELOG_PATH, self.updater.fetch_text,
            )
            self.updater.CONFIG_PATH = config_path
            self.updater.DATA_PATH = data_path
            self.updater.STATE_PATH = state_path
            self.updater.CHANGELOG_PATH = changelog_path
            self.updater.fetch_text = lambda url, user_agent: (_ for _ in ()).throw(
                RuntimeError("HTTP 403: Cloudflare challenge")
            )
            try:
                self.updater.run_update("2026-10-20")
            finally:
                (
                    self.updater.CONFIG_PATH, self.updater.DATA_PATH, self.updater.STATE_PATH,
                    self.updater.CHANGELOG_PATH, self.updater.fetch_text,
                ) = original_values
            saved_data = json.loads(data_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_data["cutoff"], "2026-10-20")

    def test_required_monitor_failure_leaves_data_and_state_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "source-config.json"
            data_path = root / "timeline-data.json"
            state_path = root / "source-state.json"
            changelog_path = root / "CHANGELOG.md"
            config_path.write_text(json.dumps({
                "timezone": "Asia/Shanghai",
                "userAgent": "test",
                "allowedHosts": ["developers.openai.com"],
                "discoverySources": [],
                "monitoredPages": [{
                    "name": "OpenAI Developers Changelog",
                    "label": "OpenAI Developers",
                    "url": "https://developers.openai.com/api/docs/changelog",
                    "required": True,
                    "category": "API",
                    "track": "API / Agents",
                    "family": "",
                }],
            }), encoding="utf-8")
            original_data = json.dumps({
                "cutoff": "2026-10-19", "lastChecked": "", "events": [],
            })
            original_state = json.dumps({
                "lastChecked": "", "knownUrls": [], "pageHashes": {},
            })
            data_path.write_text(original_data, encoding="utf-8")
            state_path.write_text(original_state, encoding="utf-8")
            changelog_path.write_text("# 更新日志\n", encoding="utf-8")
            original_values = (
                self.updater.CONFIG_PATH, self.updater.DATA_PATH, self.updater.STATE_PATH,
                self.updater.CHANGELOG_PATH, self.updater.fetch_text,
            )
            self.updater.CONFIG_PATH = config_path
            self.updater.DATA_PATH = data_path
            self.updater.STATE_PATH = state_path
            self.updater.CHANGELOG_PATH = changelog_path
            self.updater.fetch_text = lambda url, user_agent: (_ for _ in ()).throw(
                RuntimeError("HTTP 503")
            )
            try:
                with self.assertRaisesRegex(RuntimeError, "必需监控页失败"):
                    self.updater.run_update("2026-10-20")
            finally:
                (
                    self.updater.CONFIG_PATH, self.updater.DATA_PATH, self.updater.STATE_PATH,
                    self.updater.CHANGELOG_PATH, self.updater.fetch_text,
                ) = original_values
            self.assertEqual(data_path.read_text(encoding="utf-8"), original_data)
            self.assertEqual(state_path.read_text(encoding="utf-8"), original_state)

    def test_source_config_contains_required_official_sources(self) -> None:
        config = json.loads((ROOT / "work" / "source-config.json").read_text(encoding="utf-8"))
        discovery_urls = {item["url"] for item in config["discoverySources"]}
        monitored_urls = {item["url"] for item in config["monitoredPages"]}
        self.assertIn("https://openai.com/news/rss.xml", discovery_urls)
        self.assertTrue(any("sitemap" in url for url in discovery_urls))
        self.assertTrue(any("changelog" in url for url in monitored_urls))
        self.assertTrue(any("release-notes" in url for url in monitored_urls))
        self.assertTrue(any("pricing" in url for url in monitored_urls))
        self.assertTrue(any("deprecations" in url for url in monitored_urls))
        self.assertGreaterEqual(len(config["allowedHosts"]), 6)
        release_notes = next(
            item for item in config["monitoredPages"]
            if item["url"] == "https://openai.com/products/release-notes"
        )
        self.assertFalse(release_notes["required"])


if __name__ == "__main__":
    unittest.main()
