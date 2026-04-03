from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

HTTP_CALLS = {"delete", "get", "patch", "post", "put", "request"}
MONEY_NAMES = {"amount", "balance", "cost", "price", "profit", "size", "total", "value"}


def build_finding(rule: str, severity: str, path: Path, line: int, detail: str) -> dict[str, object]:
    return {
        "kind": "finding",
        "rule": rule,
        "severity": severity,
        "path": str(path),
        "line": line,
        "snippet": detail,
    }


def get_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def has_timeout(node: ast.Call) -> bool:
    return any(keyword.arg == "timeout" for keyword in node.keywords if keyword.arg)


def is_requests_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if not isinstance(node.func.value, ast.Name):
        return False
    return node.func.value.id == "requests" and node.func.attr in HTTP_CALLS


def is_money_assignment(node: ast.Assign) -> bool:
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id.lower() in MONEY_NAMES:
            return True
    return False


def scan_python_file(root: Path, path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        return [build_finding("python-parse-error", "P1", relative_path, error.lineno or 1, str(error))]
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(build_finding("python-bare-except", "P1", relative_path, node.lineno, "bare except"))
        if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            findings.append(build_finding("python-except-pass", "P1", relative_path, node.lineno, "except pass"))
        if isinstance(node, ast.Call) and get_call_name(node) == "print":
            findings.append(build_finding("python-print-call", "P2", relative_path, node.lineno, "print() call"))
        if isinstance(node, ast.Call) and is_requests_call(node) and not has_timeout(node):
            findings.append(build_finding("python-http-no-timeout", "P1", relative_path, node.lineno, "requests without timeout"))
        if isinstance(node, ast.Assign) and is_money_assignment(node):
            if isinstance(node.value, ast.Call) and get_call_name(node.value) == "float":
                findings.append(build_finding("python-float-money", "P1", relative_path, node.lineno, "money-like value uses float"))


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
