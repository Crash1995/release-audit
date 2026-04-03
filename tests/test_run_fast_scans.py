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


class RunFastScansTests(unittest.TestCase):
    def test_flags_release_blocking_security_patterns(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/run_fast_scans.py",
            "run_fast_scans",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "client.py"
            target.write_text(
                "requests.get(url, verify=False)\n"
                "os.system(command)\n"
                "CORS_ALLOW_ORIGINS = ['*']\n",
                encoding="utf-8",
            )

            findings = module.scan_file(root, target)
            rules = {item["rule"] for item in findings}

            self.assertIn("verify-false", rules)
            self.assertIn("os-system", rules)
            self.assertIn("wildcard-cors", rules)

    def test_ignores_rule_description_noise_in_scanner_sources(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/run_fast_scans.py",
            "run_fast_scans",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "scripts" / "scanner.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                'findings.append(build_finding("python-print-call", "P2", relative_path, 10, "print() call"))\n',
                encoding="utf-8",
            )

            findings = module.scan_file(root, target)
            rules = {item["rule"] for item in findings}

            self.assertNotIn("debug-call", rules)


if __name__ == "__main__":
    unittest.main()
