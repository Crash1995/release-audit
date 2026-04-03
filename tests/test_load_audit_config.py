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


class LoadAuditConfigTests(unittest.TestCase):
    def test_filters_suppressed_rules_and_applies_overrides(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/load_audit_config.py",
            "load_audit_config",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".release-audit.toml").write_text(
                "[severity_overrides]\nverify-false = 'P0'\n\n"
                "[[suppressions]]\npath = 'api.py'\nrules = ['os-system']\n",
                encoding="utf-8",
            )

            config = module.load_audit_config(root)
            findings = [
                {"rule": "verify-false", "severity": "P1", "path": "api.py"},
                {"rule": "os-system", "severity": "P1", "path": "api.py"},
            ]

            filtered = module.apply_config(findings, config)

            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]["rule"], "verify-false")
            self.assertEqual(filtered[0]["severity"], "P0")


if __name__ == "__main__":
    unittest.main()
