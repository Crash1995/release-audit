from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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


def build_finding(rule: str, severity: str, path: str, message: str) -> dict[str, str]:
    return {
        "kind": "finding",
        "rule": rule,
        "severity": severity,
        "path": path,
        "message": message,
    }


def is_stale_doc(path: Path) -> bool:
    if "docs" not in path.parts:
        return False
    stem = path.stem.lower()
    return any(marker in stem for marker in STALE_DOC_MARKERS)


def is_stale_test(path: Path) -> bool:
    if "tests" not in path.parts:
        return False
    stem = path.stem.lower()
    return any(marker in stem for marker in STALE_TEST_MARKERS)


def build_findings(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        name = relative_path.name
        if name in LEGACY_CONFIG_FILES:
            findings.append(
                build_finding(
                    "legacy-config-file",
                    "P2",
                    str(relative_path),
                    "Legacy config file should be reviewed for cleanup before release",
                )
            )
        if is_stale_doc(relative_path):
            findings.append(
                build_finding(
                    "stale-doc-file",
                    "P2",
                    str(relative_path),
                    "Documentation file looks stale and should be archived or removed",
                )
            )
        if is_stale_test(relative_path):
            findings.append(
                build_finding(
                    "stale-test-file",
                    "P2",
                    str(relative_path),
                    "Test file looks legacy or unused and should be reviewed for cleanup",
                )
            )
        if any(relative_path.name.endswith(suffix) for suffix in BACKUP_SUFFIXES):
            findings.append(
                build_finding(
                    "backup-artifact-file",
                    "P2",
                    str(relative_path),
                    "Backup or temporary file should be removed from the repository",
                )
            )
    return findings


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
