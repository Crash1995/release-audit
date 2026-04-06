from __future__ import annotations

import ast
import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

from finding_utils import build_finding

EXPENSIVE_CALLS = {
    "json.load",
    "json.loads",
    "open",
    "Path.read_bytes",
    "Path.read_text",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.patch",
    "requests.delete",
}
JS_EVENT_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}


def load_config_helpers() -> ModuleType:
    """Загружает helper для suppressions и severity overrides."""
    module_path = Path(__file__).with_name("load_audit_config.py")
    spec = importlib.util.spec_from_file_location("load_audit_config", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def get_qualified_name(node: ast.AST) -> str:
    """Возвращает квалифицированное имя функции или атрибута."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = get_qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def walk_without_nested_defs(node: ast.AST) -> Iterator[ast.AST]:
    """Идёт по AST, не проваливаясь во вложенные defs/classes/lambdas."""
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from walk_without_nested_defs(child)


def build_performance_finding(
    rule: str,
    severity: str,
    path: Path,
    line: int | None,
    title: str,
    description: str,
    impact: str,
    suggested_fix: str,
    snippet: str,
) -> dict[str, object]:
    """Собирает единый finding для performance audit."""
    return build_finding(
        rule=rule,
        severity=severity,
        category="Performance and Memory",
        path=path,
        line=line,
        title=title,
        description=description,
        impact=impact,
        suggested_fix=suggested_fix,
        snippet=snippet,
    )


def scan_loop_node(relative_path: Path, node: ast.For | ast.AsyncFor | ast.While) -> list[dict[str, object]]:
    """Ищет дорогие вызовы внутри одного loop-узла."""
    findings: list[dict[str, object]] = []
    for child in walk_without_nested_defs(node):
        if not isinstance(child, ast.Call):
            continue
        call_name = get_qualified_name(child.func)
        if call_name not in EXPENSIVE_CALLS:
            continue
        findings.append(
            build_performance_finding(
                rule="expensive-call-in-loop",
                severity="P2",
                path=relative_path,
                line=child.lineno,
                title="Expensive call inside loop",
                description="The loop contains file, network, or parsing work that may run on every iteration.",
                impact="Repeated expensive work in loops can create avoidable latency and memory churn on large inputs.",
                suggested_fix="Hoist invariant work out of the loop or batch operations where possible.",
                snippet=call_name,
            )
        )
    return findings


def scan_resource_call(relative_path: Path, node: ast.Call) -> list[dict[str, object]]:
    """Проверяет вызов на ресурсные smells вне контекст-менеджера."""
    if isinstance(node.func, ast.Name) and node.func.id == "open":
        if not isinstance(getattr(node, "parent", None), ast.With):
            return [
                build_performance_finding(
                    rule="open-without-context-manager",
                    severity="P2",
                    path=relative_path,
                    line=node.lineno,
                    title="File opened without context manager",
                    description="The code opens a file without using a with-statement.",
                    impact="Open file descriptors may stay alive longer than needed and can leak on error paths.",
                    suggested_fix="Wrap file access in a with-statement so the descriptor is closed deterministically.",
                    snippet="open(...)",
                )
            ]
    if get_qualified_name(node.func) == "aiohttp.ClientSession":
        parent = getattr(node, "parent", None)
        if not isinstance(parent, (ast.AsyncWith, ast.With)):
            return [
                build_performance_finding(
                    rule="aiohttp-session-without-context",
                    severity="P1",
                    path=relative_path,
                    line=node.lineno,
                    title="aiohttp ClientSession without context manager",
                    description="The code creates ClientSession outside a with/async with block.",
                    impact="HTTP sessions may stay open longer than intended and leak sockets or connectors.",
                    suggested_fix="Create ClientSession inside async with or ensure explicit close() on all execution paths.",
                    snippet="aiohttp.ClientSession(...)",
                )
            ]
    return []


def scan_python_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует Python-файл на resource leaks и дорогие конструкции."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return findings
    attach_parents(tree)

    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            findings.extend(scan_loop_node(relative_path, node))
        if isinstance(node, ast.Call):
            findings.extend(scan_resource_call(relative_path, node))
    return findings


def attach_parents(tree: ast.AST) -> None:
    """Подвешивает ссылки на parent-узлы для локального AST-анализа."""
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent


def scan_js_like_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует JS/TS файл на явные listener cleanup smells."""
    relative_path = path.relative_to(root)
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "addEventListener(" in text and "removeEventListener(" not in text:
        return [
            build_finding(
                rule="event-listener-cleanup-missing",
                severity="P2",
                category="Performance and Memory",
                path=relative_path,
                title="Event listener without visible cleanup",
                description="The file adds an event listener but no matching removeEventListener was found.",
                impact="Forgotten listeners can retain closures and DOM references longer than expected.",
                suggested_fix="Ensure the listener is removed during teardown or component cleanup.",
                snippet="addEventListener(...)",
            )
        ]
    return []


def build_findings(root: Path) -> list[dict[str, object]]:
    """Строит findings по performance и memory smells."""
    findings: list[dict[str, object]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".py":
            findings.extend(scan_python_file(root, path))
        if path.suffix.lower() in JS_EVENT_EXTENSIONS:
            findings.extend(scan_js_like_file(root, path))
    return findings


def main() -> None:
    """CLI entrypoint для performance audit."""
    root = Path.cwd()
    findings = build_findings(root)
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    findings = config_module.apply_config(findings, config)
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
