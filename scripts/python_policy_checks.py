from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from finding_utils import build_finding
from shared import get_short_call_name, load_config_helpers

HTTP_CALLS = {"delete", "get", "patch", "post", "put", "request"}
MONEY_NAMES = {"amount", "balance", "cost", "price", "profit", "size", "total", "value"}


def get_call_name(node: ast.Call) -> str:
    """Возвращает короткое имя вызываемой функции."""
    return get_short_call_name(node)


def has_timeout(node: ast.Call) -> bool:
    """Проверяет, есть ли у HTTP-вызова keyword timeout."""
    return any(keyword.arg == "timeout" for keyword in node.keywords if keyword.arg)


def is_requests_call(node: ast.Call) -> bool:
    """Определяет, является ли вызов requests HTTP-операцией."""
    if not isinstance(node.func, ast.Attribute):
        return False
    if not isinstance(node.func.value, ast.Name):
        return False
    return node.func.value.id == "requests" and node.func.attr in HTTP_CALLS


def is_money_assignment(node: ast.Assign) -> bool:
    """Определяет, выглядит ли assignment как денежное значение."""
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id.lower() in MONEY_NAMES:
            return True
    return False


def build_policy_finding(
    rule: str,
    severity: str,
    category: str,
    path: Path,
    line: int,
    title: str,
    description: str,
    impact: str,
    suggested_fix: str,
    snippet: str,
) -> dict[str, object]:
    """Собирает единый finding для Python policy checks."""
    return build_finding(
        rule=rule,
        severity=severity,
        category=category,
        path=path,
        line=line,
        title=title,
        description=description,
        impact=impact,
        suggested_fix=suggested_fix,
        snippet=snippet,
    )


def scan_except_handler(relative_path: Path, node: ast.ExceptHandler) -> list[dict[str, object]]:
    """Проверяет except-handler на bare except и except-pass."""
    findings: list[dict[str, object]] = []
    if node.type is None:
        findings.append(
            build_policy_finding(
                rule="python-bare-except",
                severity="P1",
                category="Bugs and Logic Errors",
                path=relative_path,
                line=node.lineno,
                title="Bare except in Python code",
                description="The code catches all exceptions without narrowing the error type.",
                impact="Unexpected runtime failures can be hidden, including system-level interrupts.",
                suggested_fix="Catch specific exception types and log or re-raise unknown failures.",
                snippet="bare except",
            )
        )
    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
        findings.append(
            build_policy_finding(
                rule="python-except-pass",
                severity="P1",
                category="Bugs and Logic Errors",
                path=relative_path,
                line=node.lineno,
                title="Exception is swallowed with pass",
                description="The exception handler contains only pass.",
                impact="Operational errors disappear silently and can produce corrupted state or false positives in higher-level logic.",
                suggested_fix="Log the exception, handle the fallback explicitly, or re-raise it.",
                snippet="except pass",
            )
        )
    return findings


def scan_call_node(relative_path: Path, node: ast.Call) -> list[dict[str, object]]:
    """Проверяет Python call-узел на print() и requests без timeout."""
    call_name = get_call_name(node)
    if call_name == "print":
        return [
            build_policy_finding(
                rule="python-print-call",
                severity="P2",
                category="Code Quality",
                path=relative_path,
                line=node.lineno,
                title="print() call in Python code",
                description="The file uses print() directly.",
                impact="Raw print statements reduce observability quality and often leak debug output into production flows.",
                suggested_fix="Replace print() with structured logging unless this is an intentional CLI output path.",
                snippet="print() call",
            )
        ]
    if is_requests_call(node) and not has_timeout(node):
        return [
            build_policy_finding(
                rule="python-http-no-timeout",
                severity="P1",
                category="Performance and Memory",
                path=relative_path,
                line=node.lineno,
                title="HTTP request without timeout",
                description="A requests call is made without an explicit timeout.",
                impact="The process can hang indefinitely on slow or broken networks and exhaust worker capacity.",
                suggested_fix="Pass an explicit timeout to every outbound HTTP request.",
                snippet="requests without timeout",
            )
        ]
    return []


def scan_assignment_node(relative_path: Path, node: ast.Assign) -> list[dict[str, object]]:
    """Проверяет assignment на float в money-like переменных."""
    if is_money_assignment(node) and isinstance(node.value, ast.Call) and get_call_name(node.value) == "float":
        return [
            build_policy_finding(
                rule="python-float-money",
                severity="P1",
                category="Bugs and Logic Errors",
                path=relative_path,
                line=node.lineno,
                title="Money-like value uses float",
                description="A money-like variable is derived through float().",
                impact="Binary floating-point arithmetic can introduce rounding errors into balances, prices, and settlement logic.",
                suggested_fix="Use Decimal for monetary values and convert at system boundaries only.",
                snippet="money-like value uses float",
            )
        ]
    return []


def scan_python_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует Python-файл на policy-нарушения runtime и safety слоя."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        return [
            build_policy_finding(
                rule="python-parse-error",
                severity="P1",
                category="Bugs and Logic Errors",
                path=relative_path,
                line=error.lineno or 1,
                title="Python file does not parse",
                description="The Python parser failed to load the file.",
                impact="Syntax errors block execution and invalidate deeper static checks for this file.",
                suggested_fix="Fix the syntax error and rerun the audit to restore full coverage.",
                snippet=str(error),
            )
        ]
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            findings.extend(scan_except_handler(relative_path, node))
        if isinstance(node, ast.Call):
            findings.extend(scan_call_node(relative_path, node))
        if isinstance(node, ast.Assign):
            findings.extend(scan_assignment_node(relative_path, node))

    return findings


def main() -> None:
    """CLI entrypoint для Python policy checks."""
    root = Path.cwd()
    results: list[dict[str, object]] = []
    for path in root.rglob("*.py"):
        results.extend(scan_python_file(root, path))
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    results = config_module.apply_config(results, config)
    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
