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


class TechDebtAuditTests(unittest.TestCase):
    def test_flags_core_low_noise_python_tech_debt(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/tech_debt_audit.py",
            "tech_debt_audit",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "service.py"
            long_body = "".join("    total += 3\n" for _ in range(52))
            target.write_text(
                "def process(data, x):\n"
                "    # TODO: replace with real workflow\n"
                "    if data:\n"
                "        for item in data:\n"
                "            while item:\n"
                "                if item > 10:\n"
                "                    if item < 100:\n"
                "                        temp = 42\n"
                "    return data\n\n"
                "def placeholder():\n"
                "    return None\n\n"
                "def long_job() -> None:\n"
                "    \"\"\"Execute a long task.\"\"\"\n"
                "    total = 0\n"
                f"{long_body}",
                encoding="utf-8",
            )

            findings = module.scan_python_file(root, target)
            rules = {item["rule"] for item in findings}

            self.assertIn("python-deep-nesting", rules)
            self.assertIn("python-empty-function", rules)
            self.assertIn("python-long-function", rules)
            self.assertIn("python-magic-number", rules)
            self.assertIn("python-missing-type-hints", rules)
            self.assertIn("python-public-function-no-docstring", rules)
            self.assertIn("python-src-todo", rules)
            self.assertIn("python-weak-name", rules)

    def test_flags_python_pro_style_runtime_smells(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/tech_debt_audit.py",
            "tech_debt_audit",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "worker.py"
            target.write_text(
                "import requests\n"
                "import time\n\n"
                "async def sync_remote() -> None:\n"
                "    time.sleep(5)\n"
                "    requests.get('https://example.com')\n\n"
                "def configure(items: list[str] = []) -> list[str]:\n"
                "    \"\"\"Return config items.\"\"\"\n"
                "    try:\n"
                "        return items\n"
                "    except Exception:\n"
                "        return []\n",
                encoding="utf-8",
            )

            findings = module.scan_python_file(root, target)
            rules = {item["rule"] for item in findings}

            self.assertIn("python-async-blocking-call", rules)
            self.assertIn("python-broad-except", rules)
            self.assertIn("python-mutable-default", rules)


if __name__ == "__main__":
    unittest.main()
