"""
静态验证 OpenAI 全景每日更新工作流的触发时间、权限、测试、提交边界与 Pages 发布步骤。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "update-openai-panorama.yml"


class WorkflowStaticTest(unittest.TestCase):
    """检查工作流文本，不引入 YAML 第三方解析依赖。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_daily_schedule_and_manual_trigger(self) -> None:
        self.assertIn('cron: "15 0 * * *"', self.workflow)
        self.assertRegex(self.workflow, r"(?m)^\s*workflow_dispatch:\s*$")

    def test_permissions_and_concurrency_are_limited(self) -> None:
        self.assertRegex(self.workflow, r"(?m)^\s*contents:\s*write\s*$")
        self.assertRegex(self.workflow, r"(?m)^\s*pages:\s*write\s*$")
        self.assertRegex(self.workflow, r"(?m)^\s*id-token:\s*write\s*$")
        self.assertNotIn("pull-requests: write", self.workflow)
        self.assertRegex(self.workflow, r"(?m)^\s*group:\s*openai-panorama-pages\s*$")
        self.assertRegex(self.workflow, r"(?m)^\s*cancel-in-progress:\s*false\s*$")

    def test_update_build_and_full_verification_are_run(self) -> None:
        self.assertIn('python-version: "3.12"', self.workflow)
        self.assertIn("python3 work/update-openai-panorama.py", self.workflow)
        self.assertIn("python3 work/build-page.py", self.workflow)
        self.assertIn("node --check", self.workflow)
        for test_path in (
            "tests/test-timeline-data.py",
            "tests/test-openai-evolution-panorama.py",
            "tests/test-auto-update.py",
            "tests/test-workflow-static.py",
        ):
            self.assertIn(test_path, self.workflow)

    def test_commit_scope_is_explicit(self) -> None:
        self.assertNotRegex(self.workflow, r"git add\s+(?:-|--\s+)?[.]\s*(?:$|\n)")
        expected_paths = (
            "work/timeline-data.json",
            "work/source-state.json",
            "outputs/openai-chatgpt-evolution-panorama.html",
            "CHANGELOG.md",
        )
        for path in expected_paths:
            self.assertIn(path, self.workflow)

    def test_pages_artifact_contains_homepage_and_downloadable_copy(self) -> None:
        self.assertIn("site/index.html", self.workflow)
        self.assertIn("site/openai-chatgpt-evolution-panorama.html", self.workflow)
        self.assertIn("site/.nojekyll", self.workflow)
        self.assertIn("actions/configure-pages@", self.workflow)
        self.assertIn("actions/upload-pages-artifact@", self.workflow)
        self.assertIn("actions/deploy-pages@", self.workflow)


if __name__ == "__main__":
    unittest.main()
