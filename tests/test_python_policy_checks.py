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


class PythonPolicyChecksTests(unittest.TestCase):
    def test_flags_python_policy_violations(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/python_policy_checks.py",
            "python_policy_checks",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "service.py"
            target.write_text(
                "import requests\n"
                "from decimal import Decimal\n\n"
                "def fetch_price():\n"
                "    amount = float('1.25')\n"
                "    try:\n"
                "        print('debug')\n"
                "    except:\n"
                "        pass\n"
                "    requests.get('https://example.com')\n"
                "    return Decimal('1') + amount\n",
                encoding="utf-8",
            )

            findings = module.scan_python_file(root, target)
            rules = {item["rule"] for item in findings}

            self.assertIn("python-bare-except", rules)
            self.assertIn("python-except-pass", rules)
            self.assertIn("python-print-call", rules)
            self.assertIn("python-http-no-timeout", rules)
            self.assertIn("python-float-money", rules)


if __name__ == "__main__":
    unittest.main()
