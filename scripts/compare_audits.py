from __future__ import annotations


def build_key(finding: dict[str, object]) -> tuple[object, ...]:
    """Строит ключ сравнения для стабильного diff между аудитами."""
    return (
        finding.get("rule"),
        finding.get("path"),
    )


def compare_audits(
    previous_findings: list[dict[str, object]], current_findings: list[dict[str, object]]
) -> dict[str, list[dict[str, object]]]:
    """Сравнивает текущие findings с предыдущим аудитом."""
    previous_by_key = {build_key(finding): finding for finding in previous_findings}
    current_by_key = {build_key(finding): finding for finding in current_findings}

    new_keys = current_by_key.keys() - previous_by_key.keys()
    carried_keys = current_by_key.keys() & previous_by_key.keys()
    resolved_keys = previous_by_key.keys() - current_by_key.keys()

    return {
        "new_findings": [current_by_key[key] for key in sorted(new_keys)],
        "carried_over_findings": [current_by_key[key] for key in sorted(carried_keys)],
        "resolved_findings": [previous_by_key[key] for key in sorted(resolved_keys)],
    }
