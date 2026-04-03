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


class ValidateSkillTests(unittest.TestCase):
    def test_reports_missing_skill_files(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/validate_skill.py",
            "validate_skill",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SKILL.md").write_text("---\nname: demo\ndescription: test\n---\n", encoding="utf-8")

            findings = module.validate_skill(root)
            rules = {item["rule"] for item in findings}

            self.assertIn("missing-openai-yaml", rules)
            self.assertIn("missing-references-dir", rules)
            self.assertIn("missing-scripts-dir", rules)


if __name__ == "__main__":
    unittest.main()
