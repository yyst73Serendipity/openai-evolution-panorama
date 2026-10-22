"""
验证 OpenAI 演进全景网页的内容规模、档案式信息架构、交互、安全边界与离线单文件特性。
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "work" / "build-page.py"
OUTPUT = ROOT / "outputs" / "openai-chatgpt-evolution-panorama.html"
DATA = ROOT / "work" / "timeline-data.json"


class OpenAIPanoramaPageTest(unittest.TestCase):
    """保证生成网页包含全景信息架构并可离线交互。"""

    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(["python3", str(BUILD)], cwd=ROOT, check=True)
        cls.html = OUTPUT.read_text(encoding="utf-8")
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_output_is_large_standalone_document(self) -> None:
        self.assertGreater(OUTPUT.stat().st_size, 100_000)
        self.assertIn("<!doctype html>", self.html.lower())
        self.assertNotRegex(self.html, r'<(?:script|link)[^>]+(?:src|href)=["\']https?://')
        self.assertNotIn("fetch(", self.html)
        self.assertNotIn("XMLHttpRequest", self.html)

    def test_all_information_architecture_sections_exist(self) -> None:
        for section_id in (
            "overview", "tracks", "timeline", "models", "chatgpt", "api-agents",
            "codex", "multimodal", "plans", "pricing", "migration", "insights",
            "method", "sources",
        ):
            with self.subTest(section=section_id):
                self.assertIn(f'id="{section_id}"', self.html)

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
        self.assertIn('class="badge verification"', self.html)

    def test_filter_controls_and_accessibility_exist(self) -> None:
        for control_id in (
            "search-input", "year-filter", "category-filter", "track-filter",
            "family-filter", "sort-select", "new-only", "expand-all", "reset-filters",
            "theme-toggle",
        ):
            with self.subTest(control=control_id):
                self.assertIn(f'id="{control_id}"', self.html)
        self.assertIn('class="skip-link"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn("function filterEvents()", self.html)
        self.assertIn("function renderTimeline()", self.html)
        self.assertIn("function updateHash()", self.html)
        self.assertIn("function loadHash()", self.html)

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

    def test_dynamic_metadata_and_representative_milestones_are_embedded(self) -> None:
        self.assertIn(self.data["cutoff"], self.html)
        self.assertIn(self.data["lastChecked"], self.html)
        for phrase in (
            "GPT-1", "GPT-2", "GPT-3", "ChatGPT Research Preview", "GPT-4",
            "GPT-4o", "o1", "GPT-5", "GPT-6 Astra", "GPT-6.1 Sol", "DALL·E",
            "Whisper", "Sora", "Codex", "Responses API", "ChatGPT Agent",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)

    def test_json_and_links_are_safely_embedded(self) -> None:
        self.assertIn('type="application/json" id="timeline-data"', self.html)
        self.assertNotIn("</script><script", self.html.lower())
        for match in re.finditer(r'<a\b[^>]*target="_blank"[^>]*>', self.html):
            self.assertIn('rel="noopener noreferrer"', match.group(0))
        self.assertIn("textContent", self.html)

    def test_responsive_print_theme_and_reduced_motion_styles_exist(self) -> None:
        for fragment in (
            "@media (max-width: 980px)", "@media (max-width: 720px)",
            "@media (max-width: 420px)", "@media print",
            "@media (prefers-reduced-motion: reduce)", ":focus-visible", "color-scheme",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.html)


if __name__ == "__main__":
    unittest.main()
