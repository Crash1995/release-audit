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


class ReadAuditHistoryTests(unittest.TestCase):
    def test_reads_latest_previous_audit_report(self) -> None:
        history_module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/read_audit_history.py",
            "read_audit_history",
        )
        writer_module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/write_audit_report.py",
            "write_audit_report",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_dir = root / "docs" / "release-audits"
            history_dir.mkdir(parents=True)
            older = history_dir / "2026-04-02-1000-release-audit.md"
            newer = history_dir / "2026-04-03-0900-release-audit.md"
            older.write_text(
                writer_module.build_markdown(
                    {
                        "root": str(root),
                        "inventory": {"total_files": 1, "files": []},
                        "findings": [],
                        "decision": {"verdict": "GO", "reasons": []},
                        "comparison": {"new_findings": [], "carried_over_findings": [], "resolved_findings": []},
                        "verification": {"checks_run": []},
                    }
                ),
                encoding="utf-8",
            )
            newer_report = {
                "root": str(root),
                "decision": {"verdict": "NO-GO"},
                "findings": [{"rule": "x"}],
                "inventory": {"total_files": 3, "files": [{"path": "a.py"}]},
                "history": {"previous_report": {"findings": [{"rule": "older"}]}},
                "comparison": {"new_findings": [], "carried_over_findings": [], "resolved_findings": []},
                "verification": {"checks_run": []},
            }
            newer.write_text(writer_module.build_markdown(newer_report), encoding="utf-8")

            history = history_module.read_audit_history(root)

            self.assertEqual(len(history["available_reports"]), 2)
            self.assertEqual(history["previous_report"]["decision"]["verdict"], "NO-GO")
            self.assertEqual(history["previous_report"]["coverage"]["total_files"], 3)
            self.assertNotIn("history", history["previous_report"])
            self.assertTrue(history["previous_report_path"].endswith("2026-04-03-0900-release-audit.md"))


if __name__ == "__main__":
    unittest.main()
