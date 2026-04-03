from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StaleFilesAuditTests(unittest.TestCase):
    def test_flags_legacy_files_and_stale_docs(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/stale_files_audit.py",
            "stale_files_audit",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "README.md").write_text("# current\n", encoding="utf-8")
            (root / "requirements.lock").write_text("legacy\n", encoding="utf-8")
            (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
            docs_dir = root / "docs"
            docs_dir.mkdir()
            (docs_dir / "OLD_NOTES.md").write_text("legacy notes\n", encoding="utf-8")
            (docs_dir / "ARCHIVE_PLAN.md").write_text("archive me\n", encoding="utf-8")

            findings = module.build_findings(root)
            rules = {item["rule"] for item in findings}

            self.assertIn("legacy-config-file", rules)
            self.assertIn("stale-doc-file", rules)


if __name__ == "__main__":
    unittest.main()
