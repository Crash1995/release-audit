from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import sys
import tokenize
from pathlib import Path

MAX_FUNCTION_LENGTH = 50
MAX_NESTING = 3
SKIP_DIR_NAMES = {"__pycache__", ".git", ".venv", "build", "dist", "docs", "references", "tests"}
TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK)\b")
WEAK_NAMES = {"data", "temp", "val", "x"}
ALLOWED_MAGIC_VALUES = {0, 1, 2}
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
CONTROL_NODES = (ast.AsyncFor, ast.For, ast.If, ast.Match, ast.Try, ast.While, ast.With, ast.AsyncWith)


def build_finding(rule: str, severity: str, path: Path, line: int, detail: str) -> dict[str, object]:
    return {
        "kind": "finding",
        "rule": rule,
        "severity": severity,
        "path": str(path),
        "line": line,
        "snippet": detail,
    }


def load_config_helpers():
    module_path = Path(__file__).with_name("load_audit_config.py")
    spec = importlib.util.spec_from_file_location("load_audit_config", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def is_source_python(path: Path) -> bool:
    return path.suffix == ".py" and not (set(path.parts) & SKIP_DIR_NAMES)


def get_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def get_qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = get_qualified_name(node.value)
        return f"{parent_name}.{node.attr}" if parent_name else node.attr
    return ""


def is_public_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return not node.name.startswith("_")


def get_body_without_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            return body[1:]
    return body


def is_none_constant(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def is_empty_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = get_body_without_docstring(node)
    if len(body) != 1:
        return False
    statement = body[0]
    if isinstance(statement, ast.Pass):
        return True
    if isinstance(statement, ast.Return) and is_none_constant(statement.value):
        return True
    return False


def iter_nested_blocks(node: ast.AST) -> list[list[ast.stmt]]:
    blocks: list[list[ast.stmt]] = []
    for name in ("body", "orelse", "finalbody"):
        value = getattr(node, name, None)
        if value:
            blocks.append(value)
    if isinstance(node, ast.Try):
        for handler in node.handlers:
            if handler.body:
                blocks.append(handler.body)
    if isinstance(node, ast.Match):
        for case in node.cases:
            if case.body:
                blocks.append(case.body)
    return blocks


def measure_nesting(statements: list[ast.stmt], level: int = 0) -> int:
    max_level = level
    for statement in statements:
        next_level = level + 1 if isinstance(statement, CONTROL_NODES) else level
        max_level = max(max_level, next_level)
        for block in iter_nested_blocks(statement):
            max_level = max(max_level, measure_nesting(block, next_level))
    return max_level


def iter_function_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def walk_without_nested_defs(node: ast.AST):
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from walk_without_nested_defs(child)


def iter_function_body_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef):
    for statement in get_body_without_docstring(node):
        yield from walk_without_nested_defs(statement)


def get_missing_hints(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    missing: list[str] = []
    args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    for arg in args:
        if arg.arg not in {"self", "cls"} and arg.annotation is None:
            missing.append(arg.arg)
    if node.args.vararg and node.args.vararg.annotation is None:
        missing.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg and node.args.kwarg.annotation is None:
        missing.append(f"**{node.args.kwarg.arg}")
    if node.returns is None:
        missing.append("return")
    return missing


def is_mutable_default(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    return isinstance(node, ast.Call) and get_call_name(node) in {"dict", "list", "set"}


def get_weak_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names: set[str] = set()
    for arg in list(node.args.args) + list(node.args.kwonlyargs):
        if arg.arg in WEAK_NAMES:
            names.add(arg.arg)
    for body_node in iter_function_body_nodes(node):
        if isinstance(body_node, ast.Assign):
            for target in body_node.targets:
                if isinstance(target, ast.Name) and target.id in WEAK_NAMES:
                    names.add(target.id)
        if isinstance(body_node, ast.AnnAssign) and isinstance(body_node.target, ast.Name):
            if body_node.target.id in WEAK_NAMES:
                names.add(body_node.target.id)
    return sorted(names)


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_uppercase_assignment(parent: ast.AST | None) -> bool:
    if isinstance(parent, ast.Assign):
        return all(isinstance(target, ast.Name) and target.id.isupper() for target in parent.targets)
    if isinstance(parent, ast.AnnAssign):
        return isinstance(parent.target, ast.Name) and parent.target.id.isupper()
    return False


def get_magic_numbers(node: ast.FunctionDef | ast.AsyncFunctionDef, parents: dict[ast.AST, ast.AST]) -> list[str]:
    values: set[str] = set()
    for body_node in iter_function_body_nodes(node):
        if not isinstance(body_node, ast.Constant) or not is_number(body_node.value):
            continue
        if body_node.value in ALLOWED_MAGIC_VALUES:
            continue
        parent = parents.get(body_node)
        if isinstance(parent, ast.UnaryOp):
            continue
        if is_uppercase_assignment(parent):
            continue
        if isinstance(parent, ast.Call) and get_call_name(parent) in {"Decimal", "dict", "list", "set"}:
            continue
        values.add(str(body_node.value))
    return sorted(values)


def get_async_blocking_calls(node: ast.AsyncFunctionDef) -> list[str]:
    calls: set[str] = set()
    for body_node in iter_function_body_nodes(node):
        if not isinstance(body_node, ast.Call):
            continue
        qualified_name = get_qualified_name(body_node.func)
        if qualified_name == "time.sleep":
            calls.add("time.sleep")
        if qualified_name.startswith("requests."):
            calls.add(qualified_name)
    return sorted(calls)


def has_broad_exception(handler: ast.ExceptHandler) -> bool:
    if isinstance(handler.type, ast.Name):
        return handler.type.id == "Exception"
    if isinstance(handler.type, ast.Tuple):
        return any(isinstance(item, ast.Name) and item.id == "Exception" for item in handler.type.elts)
    return False


def scan_comment_todos(relative_path: Path, source: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    reader = io.StringIO(source).readline
    for token in tokenize.generate_tokens(reader):
        if token.type == tokenize.COMMENT and TODO_PATTERN.search(token.string):
            findings.append(
                build_finding(
                    "python-src-todo",
                    "P2",
                    relative_path,
                    token.start[0],
                    token.string.strip(),
                )
            )
    return findings


def scan_python_file(root: Path, path: Path) -> list[dict[str, object]]:
    relative_path = path.relative_to(root)
    if not is_source_python(relative_path):
        return []
    source = path.read_text(encoding="utf-8", errors="ignore")
    findings = scan_comment_todos(relative_path, source)
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return findings
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    for node in iter_function_nodes(tree):
        function_name = node.name
        line = node.lineno
        function_length = (node.end_lineno or node.lineno) - node.lineno + 1
        if function_length > MAX_FUNCTION_LENGTH:
            findings.append(
                build_finding(
                    "python-long-function",
                    "P2",
                    relative_path,
                    line,
                    f"{function_name} has {function_length} lines",
                )
            )
        nesting_level = measure_nesting(get_body_without_docstring(node))
        if nesting_level > MAX_NESTING:
            findings.append(
                build_finding(
                    "python-deep-nesting",
                    "P2",
                    relative_path,
                    line,
                    f"{function_name} nesting level is {nesting_level}",
                )
            )
        if is_public_function(node):
            missing_hints = get_missing_hints(node)
            if missing_hints:
                findings.append(
                    build_finding(
                        "python-missing-type-hints",
                        "P2",
                        relative_path,
                        line,
                        f"{function_name} missing hints: {', '.join(missing_hints)}",
                    )
                )
            if not ast.get_docstring(node):
                findings.append(
                    build_finding(
                        "python-public-function-no-docstring",
                        "P3",
                        relative_path,
                        line,
                        f"{function_name} has no docstring",
                    )
                )
        if is_empty_function(node):
            findings.append(
                build_finding(
                    "python-empty-function",
                    "P2",
                    relative_path,
                    line,
                    f"{function_name} contains only pass/return None",
                )
            )
        weak_names = get_weak_names(node)
        if weak_names:
            findings.append(
                build_finding(
                    "python-weak-name",
                    "P3",
                    relative_path,
                    line,
                    f"{function_name} uses weak names: {', '.join(weak_names)}",
                )
            )
        magic_numbers = get_magic_numbers(node, parents)
        if magic_numbers:
            findings.append(
                build_finding(
                    "python-magic-number",
                    "P3",
                    relative_path,
                    line,
                    f"{function_name} uses magic numbers: {', '.join(magic_numbers)}",
                )
            )
        defaults = list(node.args.defaults) + [item for item in node.args.kw_defaults if item is not None]
        if any(is_mutable_default(default) for default in defaults):
            findings.append(
                build_finding(
                    "python-mutable-default",
                    "P1",
                    relative_path,
                    line,
                    f"{function_name} uses mutable default arguments",
                )
            )
        if isinstance(node, ast.AsyncFunctionDef):
            blocking_calls = get_async_blocking_calls(node)
            if blocking_calls:
                findings.append(
                    build_finding(
                        "python-async-blocking-call",
                        "P1",
                        relative_path,
                        line,
                        f"{function_name} uses blocking calls: {', '.join(blocking_calls)}",
                    )
                )
    for handler in ast.walk(tree):
        if isinstance(handler, ast.ExceptHandler) and has_broad_exception(handler):
            findings.append(
                build_finding(
                    "python-broad-except",
                    "P2",
                    relative_path,
                    handler.lineno,
                    "except Exception should be narrowed",
                )
            )
    return findings


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
