from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from finding_utils import build_finding


def has_frontmatter_fields(text: str) -> bool:
    """Проверяет наличие обязательных полей frontmatter в SKILL.md."""
    return bool(re.search(r"^---\n.*\bname:\s*.+\n.*\bdescription:\s*.+\n---", text, re.DOTALL))


def build_missing_skill_finding() -> dict[str, object]:
    """Возвращает finding для отсутствующего SKILL.md."""
    return build_finding(
        rule="missing-skill-md",
        severity="P1",
        category="Dependencies and Configuration",
        path="SKILL.md",
        title="Missing SKILL.md",
        description="The skill repository does not contain SKILL.md.",
        impact="The package cannot be invoked as a skill without its primary instruction file.",
        suggested_fix="Add SKILL.md with valid frontmatter and workflow instructions.",
    )


def check_optional_paths(root: Path) -> list[dict[str, object]]:
    """Проверяет обязательные каталоги и manifests, кроме самого SKILL.md."""
    findings: list[dict[str, object]] = []
    checks = (
        (
            root / "agents" / "openai.yaml",
            "missing-openai-yaml",
            "agents/openai.yaml",
            "Missing agents/openai.yaml",
            "The skill repository does not contain the OpenAI agent manifest.",
            "Default invocation metadata and agent display information are missing.",
            "Add agents/openai.yaml with interface and policy configuration.",
        ),
        (
            root / "references",
            "missing-references-dir",
            "references",
            "Missing references directory",
            "The skill package does not contain its bundled reference documents.",
            "Audit rules and report templates are harder to keep stable without bundled references.",
            "Add the references directory or remove dead references from SKILL.md.",
        ),
        (
            root / "scripts",
            "missing-scripts-dir",
            "scripts",
            "Missing scripts directory",
            "The skill package does not include its helper scripts.",
            "The documented entrypoints cannot run without the scripts directory.",
            "Add the scripts directory or remove script-based instructions from the skill.",
        ),
    )
    for checked_path, rule, path, title, description, impact, suggested_fix in checks:
        if checked_path.exists():
            continue
        findings.append(
            build_finding(
                rule=rule,
                severity="P1",
                category="Dependencies and Configuration",
                path=path,
                title=title,
                description=description,
                impact=impact,
                suggested_fix=suggested_fix,
            )
        )
    return findings


def validate_skill(root: Path) -> list[dict[str, object]]:
    """Валидирует минимальную publishable-структуру skill-репозитория."""
    findings: list[dict[str, object]] = []
    skill_path = root / "SKILL.md"
    if not skill_path.exists():
        return [build_missing_skill_finding()]
    skill_text = skill_path.read_text(encoding="utf-8")
    if not has_frontmatter_fields(skill_text):
        findings.append(
            build_finding(
                rule="invalid-skill-frontmatter",
                severity="P1",
                category="Dependencies and Configuration",
                path="SKILL.md",
                title="Invalid SKILL.md frontmatter",
                description="SKILL.md must define name and description in frontmatter.",
                impact="Tooling may fail to register or describe the skill correctly.",
                suggested_fix="Add valid frontmatter with at least name and description.",
            )
        )
    findings.extend(check_optional_paths(root))
    return findings


def main() -> None:
    """CLI entrypoint для локальной self-validation skill-а."""
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    json.dump(validate_skill(root), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
