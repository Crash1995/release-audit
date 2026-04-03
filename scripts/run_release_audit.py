from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_module(file_name: str, module_name: str):
    module_path = Path(__file__).with_name(file_name)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def collect_fast_findings(root: Path, module) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in root.rglob("*"):
        relative_path = path.relative_to(root)
        if path.is_file() and not module.should_skip(relative_path):
            if "docs" in relative_path.parts and "release-audits" in relative_path.parts:
                continue
            findings.extend(module.scan_file(root, path))
    return findings


def collect_python_findings(root: Path, module) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in root.rglob("*.py"):
        findings.extend(module.scan_python_file(root, path))
    return findings


def run_release_audit(root: Path, timestamp: str | None = None) -> dict[str, object]:
    inventory_module = load_module("inventory_repo.py", "inventory_repo")
    fast_module = load_module("run_fast_scans.py", "run_fast_scans")
    python_module = load_module("python_policy_checks.py", "python_policy_checks")
    tech_debt_module = load_module("tech_debt_audit.py", "tech_debt_audit")
    artifacts_module = load_module("check_release_artifacts.py", "check_release_artifacts")
    stale_module = load_module("stale_files_audit.py", "stale_files_audit")
    config_module = load_module("load_audit_config.py", "load_audit_config")
    decision_module = load_module("release_decision.py", "release_decision")
    history_module = load_module("read_audit_history.py", "read_audit_history")
    compare_module = load_module("compare_audits.py", "compare_audits")
    validate_module = load_module("validate_skill.py", "validate_skill")
    writer_module = load_module("write_audit_report.py", "write_audit_report")

    history = history_module.read_audit_history(root)
    inventory = inventory_module.build_inventory(root)
    findings = collect_fast_findings(root, fast_module)
    findings.extend(collect_python_findings(root, python_module))
    findings.extend(collect_python_findings(root, tech_debt_module))
    findings.extend(artifacts_module.build_findings(root))
    findings.extend(stale_module.build_findings(root))
    if (root / "SKILL.md").exists():
        findings.extend(validate_module.validate_skill(root))
    config = config_module.load_audit_config(root)
    findings = config_module.apply_config(findings, config)
    previous_findings = (
        list(dict(history).get("previous_report", {}).get("findings", []))
        if history["previous_report"]
        else []
    )
    comparison = compare_module.compare_audits(previous_findings, findings)
    decision = decision_module.build_release_decision(findings)
    report = {
        "root": str(root),
        "inventory": {"total_files": len(inventory), "files": inventory},
        "findings": findings,
        "history": history,
        "comparison": comparison,
        "decision": decision,
        "verification": {
            "checks_run": [
                "inventory_repo",
                "run_fast_scans",
                "python_policy_checks",
                "tech_debt_audit",
                "check_release_artifacts",
                "stale_files_audit",
                "compare_audits",
                "release_decision",
                *(
                    ["validate_skill"]
                    if (root / "SKILL.md").exists()
                    else []
                ),
            ],
            "history_source": history["previous_report_path"],
        },
    }
    report["report_paths"] = writer_module.write_audit_report(root, report, timestamp)
    return report


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    timestamp = sys.argv[2] if len(sys.argv) > 2 else None
    report = run_release_audit(root, timestamp=timestamp)
    writer_module = load_module("write_audit_report.py", "write_audit_report_cli")
    saved_report = writer_module.build_saved_report(report)
    output = {
        "root": saved_report["root"],
        "decision": saved_report["decision"],
        "coverage": saved_report["coverage"],
        "finding_summary": saved_report["finding_summary"],
        "blocked": saved_report["blocked"],
        "verification": saved_report["verification"],
        "report_paths": report["report_paths"],
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
