from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

MODULE_SPECS = (
    ("inventory_module", "inventory_repo.py", "inventory_repo"),
    ("fast_module", "run_fast_scans.py", "run_fast_scans"),
    ("security_module", "security_audit.py", "security_audit"),
    ("web3_security_module", "web3_security_audit.py", "web3_security_audit"),
    ("performance_module", "performance_audit.py", "performance_audit"),
    ("dependency_module", "dependency_audit.py", "dependency_audit"),
    ("python_module", "python_policy_checks.py", "python_policy_checks"),
    ("tech_debt_module", "tech_debt_audit.py", "tech_debt_audit"),
    ("artifacts_module", "check_release_artifacts.py", "check_release_artifacts"),
    ("stale_module", "stale_files_audit.py", "stale_files_audit"),
    ("config_module", "load_audit_config.py", "load_audit_config"),
    ("decision_module", "release_decision.py", "release_decision"),
    ("history_module", "read_audit_history.py", "read_audit_history"),
    ("compare_module", "compare_audits.py", "compare_audits"),
    ("validate_module", "validate_skill.py", "validate_skill"),
    ("writer_module", "write_audit_report.py", "write_audit_report"),
)


def load_module(file_name: str, module_name: str) -> ModuleType:
    """Загружает соседний скрипт как модуль по имени файла."""
    module_path = Path(__file__).with_name(file_name)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def collect_fast_findings(root: Path, module: ModuleType) -> list[dict[str, object]]:
    """Собирает findings из текстовых/regex сканеров по всем файлам репозитория."""
    findings: list[dict[str, object]] = []
    for path in root.rglob("*"):
        relative_path = path.relative_to(root)
        if path.is_file() and not module.should_skip(relative_path):
            if "docs" in relative_path.parts and "release-audits" in relative_path.parts:
                continue
            findings.extend(module.scan_file(root, path))
    return findings


def collect_python_findings(root: Path, module: ModuleType) -> list[dict[str, object]]:
    """Собирает findings из Python AST-сканеров по всем .py файлам."""
    findings: list[dict[str, object]] = []
    for path in root.rglob("*.py"):
        findings.extend(module.scan_python_file(root, path))
    return findings


def load_modules() -> dict[str, ModuleType]:
    """Загружает все модули audit pipeline по зафиксированному списку."""
    return {
        key: load_module(file_name, module_name)
        for key, file_name, module_name in MODULE_SPECS
    }


def build_verification_checks(root: Path) -> list[str]:
    """Возвращает список реально запущенных verification checks."""
    checks = [
        "inventory_repo",
        "run_fast_scans",
        "security_audit",
        "web3_security_audit",
        "performance_audit",
        "dependency_audit",
        "python_policy_checks",
        "tech_debt_audit",
        "check_release_artifacts",
        "stale_files_audit",
        "compare_audits",
        "release_decision",
    ]
    if (root / "SKILL.md").exists():
        checks.append("validate_skill")
    return checks


def collect_all_findings(root: Path, modules: dict[str, ModuleType]) -> list[dict[str, object]]:
    """Собирает findings из всех scanner-слоёв до применения config."""
    findings = collect_fast_findings(root, modules["fast_module"])
    findings.extend(modules["security_module"].build_findings(root))
    findings.extend(modules["web3_security_module"].build_findings(root))
    findings.extend(modules["performance_module"].build_findings(root))
    findings.extend(modules["dependency_module"].build_findings(root))
    findings.extend(collect_python_findings(root, modules["python_module"]))
    findings.extend(collect_python_findings(root, modules["tech_debt_module"]))
    findings.extend(modules["artifacts_module"].build_findings(root))
    findings.extend(modules["stale_module"].build_findings(root))
    if (root / "SKILL.md").exists():
        findings.extend(modules["validate_module"].validate_skill(root))
    return findings


def run_release_audit(root: Path, timestamp: str | None = None) -> dict[str, object]:
    """Запускает полный release-аудит и возвращает агрегированный отчёт."""
    modules = load_modules()
    history = modules["history_module"].read_audit_history(root)
    inventory = modules["inventory_module"].build_inventory(root)
    findings = collect_all_findings(root, modules)
    config = modules["config_module"].load_audit_config(root)
    findings = modules["config_module"].apply_config(findings, config)
    previous_findings = (
        list(dict(history).get("previous_report", {}).get("findings", []))
        if history["previous_report"]
        else []
    )
    comparison = modules["compare_module"].compare_audits(previous_findings, findings)
    decision = modules["decision_module"].build_release_decision(findings)
    report = {
        "root": str(root),
        "inventory": {"total_files": len(inventory), "files": inventory},
        "findings": findings,
        "history": history,
        "comparison": comparison,
        "decision": decision,
        "verification": {
            "checks_run": build_verification_checks(root),
            "history_source": history["previous_report_path"],
        },
    }
    report["report_paths"] = modules["writer_module"].write_audit_report(root, report, timestamp)
    return report


def main() -> None:
    """CLI entrypoint для полного release-аудита репозитория."""
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
    if output["decision"].get("verdict") == "NO-GO":
        sys.exit(1)


if __name__ == "__main__":
    main()
