from __future__ import annotations

import importlib.util
import unittest


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReleaseDecisionTests(unittest.TestCase):
    def test_returns_no_go_for_p0_and_blocked_checks(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/release_decision.py",
            "release_decision",
        )
        findings = [
            {"severity": "P0", "rule": "hardcoded-secret"},
            {"kind": "blocked", "rule": "scan-error", "severity": "P1"},
        ]

        decision = module.build_release_decision(findings)

        self.assertEqual(decision["verdict"], "NO-GO")
        self.assertIn("hardcoded-secret", decision["reasons"])
        self.assertIn("scan-error", decision["reasons"])

    def test_cleanup_findings_do_not_block_release_by_default(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/release_decision.py",
            "release_decision",
        )
        findings = [
            {"severity": "P2", "rule": "legacy-config-file"},
            {"severity": "P2", "rule": "stale-doc-file"},
        ]

        decision = module.build_release_decision(findings)

        self.assertEqual(decision["verdict"], "GO")
        self.assertEqual(decision["reasons"], [])


if __name__ == "__main__":
    unittest.main()
