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


def format_finding(finding: dict[str, object]) -> str:
    rule = str(finding.get("rule", "unknown"))
    path = str(finding.get("path", "."))
    severity = str(finding.get("severity", ""))
    return f"- [{severity}] {rule} :: {path}"


def format_grouped_finding(group: dict[str, object]) -> str:
    severity = str(group["severity"])
    rule = str(group["rule"])
    path = str(group["path"])
    count = int(group["count"])
    label = "finding" if count == 1 else "findings"
    line_summary = str(group["line_summary"])
    if line_summary:
        return f"- [{severity}] {rule} :: {path} ({count} {label}; lines: {line_summary})"
    return f"- [{severity}] {rule} :: {path} ({count} {label})"


def build_saved_report(report: dict[str, object]) -> dict[str, object]:
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
    compact = {
        "kind": finding.get("kind", "finding"),
        "rule": finding.get("rule"),
        "severity": finding.get("severity"),
        "path": finding.get("path"),
    }
    if "line" in finding:
        compact["line"] = finding.get("line")
    if compact["kind"] == "blocked" and "error" in finding:
        compact["error"] = finding.get("error")
    return compact


def build_compact_comparison(comparison: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    return {
        "new_findings": [compact_finding(item) for item in comparison.get("new_findings", [])],
        "carried_over_findings": [compact_finding(item) for item in comparison.get("carried_over_findings", [])],
        "resolved_findings": [compact_finding(item) for item in comparison.get("resolved_findings", [])],
    }


def build_finding_summary(findings: list[dict[str, object]]) -> dict[str, object]:
    by_rule: dict[str, int] = {}
    for finding in findings:
        rule = str(finding.get("rule", "unknown"))
        by_rule[rule] = by_rule.get(rule, 0) + 1
    return {"total": len(findings), "by_rule": by_rule}


def summarize_lines(lines: list[int], max_ranges: int = 8) -> str:
    if not lines:
        return ""
    unique_lines = sorted(set(lines))
    ranges: list[str] = []
    start = unique_lines[0]
    end = unique_lines[0]
    for line in unique_lines[1:]:
        if line == end + 1:
            end = line
            continue
        ranges.append(str(start) if start == end else f"{start}-{end}")
        start = end = line
    ranges.append(str(start) if start == end else f"{start}-{end}")
    if len(ranges) <= max_ranges:
        return ", ".join(ranges)
    visible = ", ".join(ranges[:max_ranges])
    return f"{visible}, +{len(ranges) - max_ranges} more"


def group_findings(findings: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}
    for finding in findings:
        key = (
            str(finding.get("severity", "")),
            str(finding.get("rule", "unknown")),
            str(finding.get("path", ".")),
        )
        group = grouped.setdefault(
            key,
            {
                "severity": key[0],
                "rule": key[1],
                "path": key[2],
                "count": 0,
                "lines": [],
            },
        )
        group["count"] = int(group["count"]) + 1
        if "line" in finding and finding.get("line") is not None:
            group["lines"].append(int(finding["line"]))
    items = list(grouped.values())
    for item in items:
        item["line_summary"] = summarize_lines(list(item["lines"]))
    return sorted(items, key=lambda item: (item["severity"], item["rule"], item["path"]))


def build_markdown(report: dict[str, object]) -> str:
    decision = dict(report["decision"])
    inventory = dict(report["inventory"])
    findings = list(report["findings"])
    comparison = dict(report["comparison"])
    saved_report = build_saved_report(report)
    cleanup_findings = [item for item in findings if item.get("rule") in CLEANUP_RULES]
    tech_debt_findings = [item for item in findings if item.get("rule") in TECH_DEBT_RULES]
    grouped_cleanup = group_findings(cleanup_findings)
    grouped_tech_debt = group_findings(tech_debt_findings)
    blocking_findings = [
        item
        for item in findings
        if item.get("rule") in decision.get("reasons", []) or item.get("severity") == "P0"
    ]
    lines = [
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
    if blocking_findings:
        lines.extend(format_finding(item) for item in blocking_findings)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Technical Debt",
            "",
            f"- Raw findings: {len(tech_debt_findings)}",
            f"- Grouped entries: {len(grouped_tech_debt)}",
            "",
        ]
    )
    if grouped_tech_debt:
        lines.extend(format_grouped_finding(item) for item in grouped_tech_debt)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Cleanup Candidates",
            "",
            f"- Raw findings: {len(cleanup_findings)}",
            f"- Grouped entries: {len(grouped_cleanup)}",
            "",
        ]
    )
    if grouped_cleanup:
        lines.extend(format_grouped_finding(item) for item in grouped_cleanup)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            build_metadata_block(saved_report),
        ]
    )
    return "\n".join(lines) + "\n"


def build_metadata_block(saved_report: dict[str, object]) -> str:
    payload = json.dumps(saved_report, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(payload, level=9)
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    return f"{METADATA_PREFIX}{encoded}{METADATA_SUFFIX}"


def extract_saved_report(markdown: str) -> dict[str, object]:
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
    report_time = timestamp or datetime.now().strftime("%Y-%m-%d-%H%M")
    history_dir = root / "docs" / "release-audits"
    history_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = history_dir / f"{report_time}-release-audit.md"
    markdown_path.write_text(build_markdown(report), encoding="utf-8")
    return {"markdown_path": str(markdown_path)}
