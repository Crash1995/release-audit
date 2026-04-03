from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

GITIGNORE_RULES: tuple[tuple[str, str], ...] = (
    (".env", "gitignore-missing-dotenv"),
    ("*.log", "gitignore-missing-logs"),
    ("__pycache__", "gitignore-missing-pycache"),
)


def build_finding(rule: str, severity: str, path: str, message: str) -> dict[str, str]:
    return {
        "kind": "finding",
        "rule": rule,
        "severity": severity,
        "path": path,
        "message": message,
    }

def check_gitignore(root: Path) -> list[dict[str, str]]:
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return [build_finding("missing-gitignore", "P1", ".gitignore", "Repository should define .gitignore")]

    text = gitignore_path.read_text(encoding="utf-8", errors="ignore")
    findings: list[dict[str, str]] = []
    for pattern, rule in GITIGNORE_RULES:
        if pattern not in text:
            findings.append(
                build_finding(rule, "P1", ".gitignore", f".gitignore should include `{pattern}`")
            )
    env_path = root / ".env"
    if env_path.exists() and ".env" not in text:
        findings.append(
            build_finding(
                "tracked-env-risk",
                "P0",
                ".env",
                "Repository contains .env but .gitignore does not exclude it",
            )
        )
    return findings


def build_findings(root: Path) -> list[dict[str, str]]:
    return check_gitignore(root)


def load_config_helpers():
    module_path = Path(__file__).with_name("load_audit_config.py")
    spec = importlib.util.spec_from_file_location("load_audit_config", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    root = Path.cwd()
    findings = build_findings(root)
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    findings = config_module.apply_config(findings, config)
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
