from __future__ import annotations

from pathlib import Path
import tomllib


def load_audit_config(root: Path) -> dict[str, object]:
    """Загружает локальную конфигурацию release-audit из .release-audit.toml."""
    config_path = root / ".release-audit.toml"
    if not config_path.exists():
        return {"severity_overrides": {}, "suppressions": []}
    config_data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    config_data.setdefault("severity_overrides", {})
    config_data.setdefault("suppressions", [])
    return config_data


def is_suppressed(finding: dict[str, object], suppressions: list[dict[str, object]]) -> bool:
    """Проверяет, подавляется ли finding локальными suppression-правилами."""
    finding_path = str(finding.get("path", ""))
    finding_rule = str(finding.get("rule", ""))
    for suppression in suppressions:
        path = str(suppression.get("path", ""))
        rules = {str(rule) for rule in suppression.get("rules", [])}
        if path == finding_path and finding_rule in rules:
            return True
    return False


def apply_config(
    findings: list[dict[str, object]], config: dict[str, object]
) -> list[dict[str, object]]:
    """Применяет overrides и suppressions к списку findings."""
    overrides = {
        str(rule): str(severity)
        for rule, severity in dict(config.get("severity_overrides", {})).items()
    }
    suppressions = list(config.get("suppressions", []))
    filtered: list[dict[str, object]] = []
    for finding in findings:
        if is_suppressed(finding, suppressions):
            continue
        updated = dict(finding)
        if updated.get("rule") in overrides:
            updated["severity"] = overrides[str(updated["rule"])]
        filtered.append(updated)
    return filtered
