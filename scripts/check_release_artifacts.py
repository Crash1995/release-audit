from __future__ import annotations

import json
import sys
from pathlib import Path

from finding_utils import build_finding
from shared import load_config_helpers

GITIGNORE_RULES: tuple[tuple[str, str], ...] = (
    (".env", "gitignore-missing-dotenv"),
    ("*.log", "gitignore-missing-logs"),
    ("__pycache__", "gitignore-missing-pycache"),
)

def check_gitignore(root: Path) -> list[dict[str, object]]:
    """Проверяет базовую hygiene .gitignore и риск коммита env/log/cache артефактов."""
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return [
            build_finding(
                rule="missing-gitignore",
                severity="P1",
                category="Dependencies and Configuration",
                path=".gitignore",
                title="Repository has no .gitignore",
                description="The repository does not define ignore rules for local secrets, logs, and cache files.",
                impact="Sensitive or machine-specific artifacts can be committed accidentally.",
                suggested_fix="Add a .gitignore that excludes .env, logs, caches, and other local runtime artifacts.",
            )
        ]

    text = gitignore_path.read_text(encoding="utf-8", errors="ignore")
    findings: list[dict[str, object]] = []
    for pattern, rule in GITIGNORE_RULES:
        if pattern not in text:
            findings.append(
                build_finding(
                    rule=rule,
                    severity="P1",
                    category="Dependencies and Configuration",
                    path=".gitignore",
                    title="Important ignore rule is missing",
                    description=f".gitignore does not include `{pattern}`.",
                    impact="Local runtime artifacts can leak into version control and pollute release state.",
                    suggested_fix=f"Add `{pattern}` to .gitignore and verify it is not already tracked.",
                    snippet=f".gitignore should include `{pattern}`",
                )
            )
    env_path = root / ".env"
    if env_path.exists() and ".env" not in text:
        findings.append(
            build_finding(
                rule="tracked-env-risk",
                severity="P0",
                category="Data Leaks",
                path=".env",
                title=".env file can be committed",
                description="The repository contains a .env file but .gitignore does not exclude it.",
                impact="Secrets and local credentials can be committed and leaked through Git history.",
                suggested_fix="Ignore .env files, remove any tracked copies, and rotate exposed secrets if needed.",
            )
        )
    return findings


def build_findings(root: Path) -> list[dict[str, object]]:
    """Строит findings по release-artifact hygiene."""
    return check_gitignore(root)


def main() -> None:
    """CLI entrypoint для проверки release-artifact hygiene."""
    root = Path.cwd()
    findings = build_findings(root)
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    findings = config_module.apply_config(findings, config)
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
