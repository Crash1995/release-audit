from __future__ import annotations

import importlib.util
import unittest


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CompareAuditsTests(unittest.TestCase):
    def test_splits_findings_into_new_carried_and_resolved(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/compare_audits.py",
            "compare_audits",
        )
        previous = [
            {"rule": "missing-license", "path": "LICENSE"},
            {"rule": "python-http-no-timeout", "path": "service.py", "line": 3},
        ]
        current = [
            {"rule": "python-http-no-timeout", "path": "service.py", "line": 3},
            {"rule": "hardcoded-secret", "path": "service.py", "line": 2},
        ]

        comparison = module.compare_audits(previous, current)

        self.assertEqual({item["rule"] for item in comparison["new_findings"]}, {"hardcoded-secret"})
        self.assertEqual({item["rule"] for item in comparison["carried_over_findings"]}, {"python-http-no-timeout"})
        self.assertEqual({item["rule"] for item in comparison["resolved_findings"]}, {"missing-license"})


if __name__ == "__main__":
    unittest.main()
