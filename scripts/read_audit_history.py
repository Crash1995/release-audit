from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def get_history_dir(root: Path) -> Path:
    return root / "docs" / "release-audits"


def list_report_files(root: Path) -> list[Path]:
    history_dir = get_history_dir(root)
    if not history_dir.exists():
        return []
    files = list(history_dir.glob("*-release-audit.md")) + list(history_dir.glob("*-release-audit.json"))
    return sorted(files)


def load_writer_module():
    module_path = Path(__file__).with_name("write_audit_report.py")
    spec = importlib.util.spec_from_file_location("write_audit_report", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def normalize_report(report: dict[str, object]) -> dict[str, object]:
    findings = [compact_finding(item) for item in report.get("findings", [])]
    blocked = [compact_finding(item) for item in report.get("blocked", [])]
    if not blocked:
        blocked = [item for item in findings if item.get("kind") == "blocked"]
    coverage = report.get("coverage")
    if not isinstance(coverage, dict):
        inventory = dict(report.get("inventory", {}))
        coverage = {
            "total_files": int(inventory.get("total_files", 0) or 0),
            "finding_count": len(findings),
            "blocked_count": len(blocked),
        }
    verification = report.get("verification")
    if not isinstance(verification, dict):
        verification = {"checks_run": [], "history_source": None}
    comparison = report.get("comparison")
    if not isinstance(comparison, dict):
        comparison = {"new_findings": [], "carried_over_findings": [], "resolved_findings": []}
    return {
        "root": report.get("root"),
        "decision": dict(report.get("decision", {})),
        "findings": findings,
        "blocked": blocked,
        "comparison": comparison,
        "coverage": coverage,
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


def read_audit_history(root: Path) -> dict[str, object]:
    report_files = list_report_files(root)
    previous_report = None
    previous_report_path = None
    writer_module = load_writer_module()
    for report_file in reversed(report_files):
        raw_text = report_file.read_text(encoding="utf-8")
        try:
            if report_file.suffix == ".md":
                previous_report = normalize_report(writer_module.extract_saved_report(raw_text))
            else:
                previous_report = normalize_report(json.loads(raw_text))
        except (ValueError, json.JSONDecodeError):
            continue
        previous_report_path = str(report_file)
        break
    return {
        "history_dir": str(get_history_dir(root)),
        "available_reports": [str(path) for path in report_files],
        "previous_report_path": previous_report_path,
        "previous_report": previous_report,
    }
