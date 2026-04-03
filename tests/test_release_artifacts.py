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


class ReleaseArtifactsTests(unittest.TestCase):
    def test_reports_only_gitignore_and_env_risks(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/check_release_artifacts.py",
            "check_release_artifacts",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
            (root / ".env").write_text("SECRET=value\n", encoding="utf-8")

            findings = module.build_findings(root)
            rules = {item["rule"] for item in findings}

            self.assertIn("gitignore-missing-dotenv", rules)
            self.assertIn("gitignore-missing-logs", rules)
            self.assertIn("tracked-env-risk", rules)

    def test_does_not_require_optional_project_artifacts(self) -> None:
        module = load_module(
            "/Users/albertfedotov/.codex/skills/release-audit/scripts/check_release_artifacts.py",
            "check_release_artifacts",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".gitignore").write_text(".env\n*.log\n__pycache__/\n", encoding="utf-8")

            findings = module.build_findings(root)
            rules = {item["rule"] for item in findings}

            self.assertNotIn("missing-license", rules)
            self.assertNotIn("missing-lockfile", rules)
            self.assertNotIn("missing-ci-config", rules)
            self.assertNotIn("missing-dockerignore", rules)


if __name__ == "__main__":
    unittest.main()
