from __future__ import annotations

import json
import sys
from pathlib import Path

from finding_utils import build_finding
from shared import load_config_helpers

LEGACY_CONFIG_FILES = {
    "pytest.ini",
    "requirements.lock",
}

BACKUP_SUFFIXES = (
    ".bak",
    ".old",
    ".orig",
    ".tmp",
)

STALE_DOC_MARKERS = (
    "archive",
    "deprecated",
    "legacy",
    "old",
    "unused",
)

STALE_TEST_MARKERS = STALE_DOC_MARKERS


def build_cleanup_finding(
    rule: str,
    path: Path,
    title: str,
    description: str,
    impact: str,
    suggested_fix: str,
) -> dict[str, object]:
    """Собирает единый cleanup finding."""
    return build_finding(
        rule=rule,
        severity="P2",
        category="Cleanup",
        path=path,
        title=title,
        description=description,
        impact=impact,
        suggested_fix=suggested_fix,
    )

def is_stale_doc(path: Path) -> bool:
    """Определяет, похож ли документ на устаревший или архивный файл."""
    if "docs" not in path.parts:
        return False
    stem = path.stem.lower()
    return any(marker in stem for marker in STALE_DOC_MARKERS)


def is_stale_test(path: Path) -> bool:
    """Определяет, похож ли тест на legacy или archive-файл."""
    if "tests" not in path.parts:
        return False
    stem = path.stem.lower()
    return any(marker in stem for marker in STALE_TEST_MARKERS)


def inspect_file(relative_path: Path) -> list[dict[str, object]]:
    """Возвращает cleanup-findings для одного файла."""
    findings: list[dict[str, object]] = []
    name = relative_path.name
    if name in LEGACY_CONFIG_FILES:
        findings.append(
            build_cleanup_finding(
                rule="legacy-config-file",
                path=relative_path,
                title="Legacy config file in repository",
                description="The repository contains a legacy config file that may no longer be required.",
                impact="Unused config files create confusion and can mislead maintainers about the active toolchain.",
                suggested_fix="Confirm whether the config is still used; remove or archive it if it is obsolete.",
            )
        )
    if is_stale_doc(relative_path):
        findings.append(
            build_cleanup_finding(
                rule="stale-doc-file",
                path=relative_path,
                title="Documentation file looks stale",
                description="The file name suggests the document is deprecated, archived, legacy, or otherwise stale.",
                impact="Stale documentation misleads users and increases maintenance noise.",
                suggested_fix="Review the document, then delete it, archive it, or replace it with current documentation.",
            )
        )
    if is_stale_test(relative_path):
        findings.append(
            build_cleanup_finding(
                rule="stale-test-file",
                path=relative_path,
                title="Test file looks stale or legacy",
                description="The test file name suggests it is deprecated, archived, or no longer active.",
                impact="Legacy tests create false confidence and slow down maintenance and triage.",
                suggested_fix="Verify whether the test still protects active behavior; remove or archive it if not.",
            )
        )
    if any(relative_path.name.endswith(suffix) for suffix in BACKUP_SUFFIXES):
        findings.append(
            build_cleanup_finding(
                rule="backup-artifact-file",
                path=relative_path,
                title="Backup or temporary artifact in repository",
                description="The repository contains a backup or temporary file variant.",
                impact="Backup artifacts increase repository noise and can expose outdated code or data accidentally.",
                suggested_fix="Delete the backup file from version control and keep only the current source of truth.",
            )
        )
    return findings


def build_findings(root: Path) -> list[dict[str, object]]:
    """Строит findings по cleanup-кандидатам в репозитории."""
    findings: list[dict[str, object]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        findings.extend(inspect_file(path.relative_to(root)))
    return findings


def main() -> None:
    """CLI entrypoint для stale files audit."""
    root = Path.cwd()
    findings = build_findings(root)
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    findings = config_module.apply_config(findings, config)
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
