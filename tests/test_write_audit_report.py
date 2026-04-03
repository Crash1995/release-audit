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


class WriteAuditReportTests(unittest.TestCase):
    def test_writes_markdown_report_with_embedded_machine_data(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/write_audit_report.py",
            "write_audit_report",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = {
                "root": str(root),
                "inventory": {"total_files": 2, "files": [{"path": "app.py"}, {"path": "docs/OLD.md"}]},
                "findings": [
                    {"rule": "hardcoded-secret", "severity": "P0", "path": "app.py", "line": 1},
                    {"rule": "python-long-function", "severity": "P2", "path": "app.py", "line": 5},
                    {"rule": "python-public-function-no-docstring", "severity": "P3", "path": "app.py", "line": 9},
                    {"rule": "python-public-function-no-docstring", "severity": "P3", "path": "app.py", "line": 11},
                    {"rule": "stale-doc-file", "severity": "P2", "path": "docs/OLD.md"},
                ],
                "decision": {"verdict": "NO-GO", "reasons": ["hardcoded-secret"]},
                "comparison": {"new_findings": [], "carried_over_findings": [], "resolved_findings": []},
                "verification": {"checks_run": ["run_fast_scans", "tech_debt_audit"]},
                "history": {"previous_report": {"findings": [{"rule": "legacy-config-file"}]}},
            }

            paths = module.write_audit_report(root, report, timestamp="2026-04-03-1200")

            markdown = Path(paths["markdown_path"]).read_text(encoding="utf-8")
            saved_report = module.extract_saved_report(markdown)
            self.assertTrue(Path(paths["markdown_path"]).exists())
            self.assertNotIn("json_path", paths)
            self.assertIn("NO-GO", markdown)
            self.assertIn("Technical Debt", markdown)
            self.assertIn("python-long-function", markdown)
            self.assertIn("python-public-function-no-docstring :: app.py (2 findings; lines: 9, 11)", markdown)
            self.assertIn("Cleanup Candidates", markdown)
            self.assertIn("stale-doc-file", markdown)
            self.assertIn("release-audit-data-v2", markdown)
            self.assertNotIn('"finding_summary"', markdown)
            self.assertNotIn('"history"', markdown)
            self.assertNotIn("history", saved_report)
            self.assertNotIn("inventory", saved_report)
            self.assertEqual(saved_report["coverage"]["total_files"], 2)
            self.assertEqual(saved_report["finding_summary"]["total"], 5)
            self.assertEqual(saved_report["verification"]["checks_run"], ["run_fast_scans", "tech_debt_audit"])
            self.assertNotIn("snippet", saved_report["findings"][0])


if __name__ == "__main__":
    unittest.main()
