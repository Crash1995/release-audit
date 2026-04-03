from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RunReleaseAuditTests(unittest.TestCase):
    def test_aggregates_findings_and_builds_verdict(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/run_release_audit.py",
            "run_release_audit",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_dir = root / "docs" / "release-audits"
            history_dir.mkdir(parents=True)
            previous_report = history_dir / "2026-04-03-1100-release-audit.json"
            previous_report.write_text(
                json.dumps(
                    {
                        "decision": {"verdict": "GO"},
                        "findings": [{"rule": "legacy-config-file", "path": "requirements.lock"}],
                    }
                ),
                encoding="utf-8",
            )
            (root / ".gitignore").write_text(".env\n*.log\n__pycache__/\n", encoding="utf-8")
            (root / "requirements.lock").write_text("legacy\n", encoding="utf-8")
            (root / "service.py").write_text(
                "import requests\n"
                "api_key = 'SECRET12345'\n"
                "\n"
                "def fetch_data(data):\n"
                "    requests.get('https://example.com')\n"
                "    return data\n",
                encoding="utf-8",
            )

            report = module.run_release_audit(root, timestamp="2026-04-03-1200")
            rules = {item["rule"] for item in report["findings"]}
            writer_module = load_module(
                "/Users/albertfedotov/.codex/skills/release-audit/scripts/write_audit_report.py",
                "write_audit_report_reader",
            )
            saved_markdown = Path(report["report_paths"]["markdown_path"]).read_text(encoding="utf-8")
            saved_report = writer_module.extract_saved_report(saved_markdown)

            self.assertEqual(report["decision"]["verdict"], "NO-GO")
            self.assertIn("hardcoded-secret", rules)
            self.assertIn("python-http-no-timeout", rules)
            self.assertIn("legacy-config-file", rules)
            self.assertIn("python-missing-type-hints", rules)
            self.assertTrue(Path(report["report_paths"]["markdown_path"]).exists())
            self.assertNotIn("json_path", report["report_paths"])
            self.assertNotIn("history", saved_report)
            self.assertNotIn("inventory", saved_report)
            self.assertEqual(saved_report["coverage"]["total_files"], 4)
            self.assertEqual(saved_report["finding_summary"]["total"], len(saved_report["findings"]))
            self.assertNotIn("snippet", saved_report["findings"][0])
            self.assertEqual(report["comparison"]["resolved_findings"], [])


if __name__ == "__main__":
    unittest.main()
