from __future__ import annotations

import base64
import json
import re
import zlib
from datetime import datetime
from pathlib import Path

CLEANUP_RULES = {
    "backup-artifact-file",
    "legacy-config-file",
    "stale-doc-file",
    "stale-test-file",
}
SEVERITY_LABELS = {
    "P0": "Critical",
    "P1": "High",
    "P2": "Medium",
    "P3": "Low",
}
SEVERITY_ORDER = ("P0", "P1", "P2", "P3")
CATEGORY_ORDER = (
    "Bugs and Logic Errors",
    "Security",
    "Performance and Memory",
    "Data Leaks",
    "Code Quality",
    "Technical Debt",
    "Dependencies and Configuration",
    "Cleanup",
)
TECH_DEBT_RULES = {
    "python-async-blocking-call",
    "python-broad-except",
    "python-deep-nesting",
    "python-empty-function",
    "python-long-function",
    "python-magic-number",
    "python-missing-type-hints",
    "python-mutable-default",
    "python-public-function-no-docstring",
    "python-src-todo",
    "python-weak-name",
}
LEGACY_METADATA_PREFIX = "<!-- release-audit-data "
METADATA_PREFIX = "<!-- release-audit-data-v2 "
METADATA_SUFFIX = " -->"
METADATA_COMPRESSION_LEVEL = 9


def format_finding(finding: dict[str, object]) -> str:
    """Форматирует один finding в Markdown-блок отчёта."""
    rule = str(finding.get("rule", "unknown"))
    severity = SEVERITY_LABELS.get(str(finding.get("severity", "")), str(finding.get("severity", "")))
    path = str(finding.get("path", "."))
    line = finding.get("line")
    location = f"{path}:{line}" if line else path
    title = str(finding.get("title", rule))
    description = str(finding.get("description", "")).strip()
    impact = str(finding.get("impact", "")).strip()
    suggested_fix = str(finding.get("suggested_fix", "")).strip()
    snippet = str(finding.get("snippet", "")).strip()
    lines = [
        f"- [{severity}] {title} :: {location}",
        f"  Rule: `{rule}`",
    ]
    if description:
        lines.append(f"  Description: {description}")
    if impact:
        lines.append(f"  Why it matters: {impact}")
    if suggested_fix:
        lines.append(f"  Suggested fix: {suggested_fix}")
    if snippet:
        lines.append(f"  Evidence: `{snippet}`")
    return "\n".join(lines)


def build_saved_report(report: dict[str, object]) -> dict[str, object]:
    """Строит компактную persisted-версию отчёта для metadata/history."""
    inventory = dict(report.get("inventory", {}))
    findings = list(report.get("findings", []))
    blocked = [item for item in findings if item.get("kind") == "blocked"]
    verification = dict(report.get("verification", {}))
    compact_findings = [compact_finding(item) for item in findings]
    compact_blocked = [compact_finding(item) for item in blocked]
    return {
        "root": report["root"],
        "decision": dict(report["decision"]),
        "findings": compact_findings,
        "blocked": compact_blocked,
        "comparison": build_compact_comparison(dict(report["comparison"])),
        "finding_summary": build_finding_summary(findings),
        "coverage": {
            "total_files": int(inventory.get("total_files", 0) or 0),
            "finding_count": len(findings),
            "blocked_count": len(blocked),
        },
        "verification": {
            "checks_run": list(verification.get("checks_run", [])),
            "history_source": verification.get("history_source"),
        },
    }


def compact_finding(finding: dict[str, object]) -> dict[str, object]:
    """Оставляет минимальный набор полей finding-а для сохранения."""
    compact = {
        "kind": finding.get("kind", "finding"),
        "rule": finding.get("rule"),
        "severity": finding.get("severity"),
        "category": finding.get("category"),
        "path": finding.get("path"),
    }
    if "title" in finding:
        compact["title"] = finding.get("title")
    if "line" in finding:
        compact["line"] = finding.get("line")
    if compact["kind"] == "blocked" and "error" in finding:
        compact["error"] = finding.get("error")
    return compact


def build_compact_comparison(comparison: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """Уплотняет comparison-секции для сохранения в metadata."""
    return {
        "new_findings": [compact_finding(item) for item in comparison.get("new_findings", [])],
        "carried_over_findings": [compact_finding(item) for item in comparison.get("carried_over_findings", [])],
        "resolved_findings": [compact_finding(item) for item in comparison.get("resolved_findings", [])],
    }


def build_finding_summary(findings: list[dict[str, object]]) -> dict[str, object]:
    """Строит агрегированную статистику findings по rule/severity/category."""
    by_rule: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for finding in findings:
        rule = str(finding.get("rule", "unknown"))
        severity = str(finding.get("severity", "unknown"))
        category = str(finding.get("category", "Uncategorized"))
        by_rule[rule] = by_rule.get(rule, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
    return {
        "total": len(findings),
        "by_rule": by_rule,
        "by_severity": by_severity,
        "by_category": by_category,
    }


def build_section_findings(
    findings: list[dict[str, object]],
    category: str,
    severity: str,
) -> list[dict[str, object]]:
    """Фильтрует findings по категории и severity для секции отчёта."""
    return [
        finding
        for finding in findings
        if finding.get("category") == category and finding.get("severity") == severity
    ]


def build_blocking_findings(
    findings: list[dict[str, object]],
    reasons: list[str],
) -> list[dict[str, object]]:
    """Возвращает findings, которые попадают в blocking section."""
    return [
        item
        for item in findings
        if item.get("rule") in reasons or item.get("severity") == "P0" or item.get("kind") == "blocked"
    ]


def build_machine_report_lines(
    report: dict[str, object],
    inventory: dict[str, object],
    findings: list[dict[str, object]],
    comparison: dict[str, object],
    decision: dict[str, object],
    summary: dict[str, object],
) -> list[str]:
    """Строит верхнюю summary-часть Markdown-отчёта."""
    return [
        "# Release Audit",
        "",
        "## GO / NO-GO",
        "",
        f"{decision.get('verdict', 'UNKNOWN')}: {', '.join(decision.get('reasons', [])) or 'no blocking reasons'}",
        "",
        "## Machine Report",
        "",
        f"- Root: {report['root']}",
        f"- Total files: {inventory['total_files']}",
        f"- Findings: {len(findings)}",
        f"- Critical: {summary['by_severity'].get('P0', 0)}",
        f"- High: {summary['by_severity'].get('P1', 0)}",
        f"- Medium: {summary['by_severity'].get('P2', 0)}",
        f"- Low: {summary['by_severity'].get('P3', 0)}",
        "",
        "## Progress",
        "",
        f"- New: {len(comparison['new_findings'])}",
        f"- Carried over: {len(comparison['carried_over_findings'])}",
        f"- Resolved: {len(comparison['resolved_findings'])}",
        "",
        "## Blocking Findings",
        "",
    ]


def build_category_sections(findings: list[dict[str, object]]) -> list[str]:
    """Строит category/severity секции findings."""
    lines: list[str] = []
    for category in CATEGORY_ORDER:
        category_findings = [item for item in findings if item.get("category") == category]
        lines.extend(["", f"## {category}", ""])
        if not category_findings:
            lines.append("No issues found.")
            continue
        for severity in SEVERITY_ORDER:
            severity_findings = build_section_findings(findings, category, severity)
            if not severity_findings:
                continue
            lines.extend([f"### {SEVERITY_LABELS[severity]}", ""])
            lines.extend(format_finding(item) for item in severity_findings)
            lines.append("")
    return lines


def build_coverage_lines(
    inventory: dict[str, object],
    findings: list[dict[str, object]],
    saved_report: dict[str, object],
) -> list[str]:
    """Строит coverage summary и blocked checks."""
    cleanup_findings = [item for item in findings if item.get("rule") in CLEANUP_RULES]
    tech_debt_findings = [item for item in findings if item.get("rule") in TECH_DEBT_RULES]
    lines = [
        "## Coverage Summary",
        "",
        f"- Total files: {inventory['total_files']}",
        f"- Total findings: {len(findings)}",
        f"- Technical debt findings: {len(tech_debt_findings)}",
        f"- Cleanup findings: {len(cleanup_findings)}",
        f"- Blocked checks: {saved_report['coverage']['blocked_count']}",
        "",
        "## Blocked Checks",
        "",
    ]
    blocked_findings = [item for item in findings if item.get("kind") == "blocked"]
    if blocked_findings:
        lines.extend(format_finding(item) for item in blocked_findings)
    else:
        lines.append("No issues found.")
    return lines


def build_markdown(report: dict[str, object]) -> str:
    """Собирает полный Markdown-отчёт release-аудита."""
    decision = dict(report["decision"])
    inventory = dict(report["inventory"])
    findings = list(report["findings"])
    comparison = dict(report["comparison"])
    saved_report = build_saved_report(report)
    blocking_findings = build_blocking_findings(findings, list(decision.get("reasons", [])))
    summary = saved_report["finding_summary"]
    lines = build_machine_report_lines(report, inventory, findings, comparison, decision, summary)
    if blocking_findings:
        lines.extend(format_finding(item) for item in blocking_findings)
    else:
        lines.append("- none")
    lines.extend(build_category_sections(findings))
    lines.extend(["", *build_coverage_lines(inventory, findings, saved_report), "", build_metadata_block(saved_report)])
    return "\n".join(lines) + "\n"


def build_metadata_block(saved_report: dict[str, object]) -> str:
    """Строит скрытый metadata-блок для хранения compact report в Markdown."""
    payload = json.dumps(saved_report, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(payload, level=METADATA_COMPRESSION_LEVEL)
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    return f"{METADATA_PREFIX}{encoded}{METADATA_SUFFIX}"


def extract_saved_report(markdown: str) -> dict[str, object]:
    """Извлекает компактный сохранённый отчёт из Markdown metadata."""
    pattern = re.escape(METADATA_PREFIX) + r"(.*?)" + re.escape(METADATA_SUFFIX)
    match = re.search(pattern, markdown, flags=re.DOTALL)
    if match:
        compressed = base64.urlsafe_b64decode(match.group(1).encode("ascii"))
        payload = zlib.decompress(compressed).decode("utf-8")
        return json.loads(payload)
    legacy_pattern = re.escape(LEGACY_METADATA_PREFIX) + r"(.*?)" + re.escape(METADATA_SUFFIX)
    match = re.search(legacy_pattern, markdown, flags=re.DOTALL)
    if not match:
        raise ValueError("release audit metadata block not found")
    return json.loads(match.group(1))


def write_audit_report(root: Path, report: dict[str, object], timestamp: str | None = None) -> dict[str, str]:
    """Сохраняет Markdown-отчёт в docs/release-audits и возвращает путь."""
    report_time = timestamp or datetime.now().strftime("%Y-%m-%d-%H%M")
    history_dir = root / "docs" / "release-audits"
    history_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = history_dir / f"{report_time}-release-audit.md"
    markdown_path.write_text(build_markdown(report), encoding="utf-8")
    return {"markdown_path": str(markdown_path)}
