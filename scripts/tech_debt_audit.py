from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import sys
import tokenize
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

from finding_utils import build_finding

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


def load_config_helpers() -> ModuleType:
    """Загружает helper для suppressions и severity overrides."""
    module_path = Path(__file__).with_name("load_audit_config.py")
    spec = importlib.util.spec_from_file_location("load_audit_config", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def is_source_python(path: Path) -> bool:
    """Проверяет, относится ли Python-файл к исходному коду, а не к skip-категориям."""
    return path.suffix == ".py" and not (set(path.parts) & SKIP_DIR_NAMES)


def get_call_name(node: ast.Call) -> str:
    """Возвращает короткое имя вызываемой функции."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def get_qualified_name(node: ast.AST) -> str:
    """Возвращает квалифицированное имя атрибута или вызова."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = get_qualified_name(node.value)
        return f"{parent_name}.{node.attr}" if parent_name else node.attr
    return ""


def is_public_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Определяет, является ли функция публичной по имени."""
    return not node.name.startswith("_")


def get_body_without_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    """Возвращает тело функции без leading docstring."""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            return body[1:]
    return body


def is_none_constant(node: ast.AST | None) -> bool:
    """Проверяет, является ли узел литералом None."""
    return isinstance(node, ast.Constant) and node.value is None


def is_empty_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Определяет, содержит ли функция только pass или return None."""
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
    """Собирает вложенные statement blocks для расчёта глубины."""
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
    """Измеряет максимальную глубину вложенности control-flow блоков."""
    max_level = level
    for statement in statements:
        next_level = level + 1 if isinstance(statement, CONTROL_NODES) else level
        max_level = max(max_level, next_level)
        for block in iter_nested_blocks(statement):
            max_level = max(max_level, measure_nesting(block, next_level))
    return max_level


def iter_function_nodes(tree: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Итерирует все function/async function узлы в дереве."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def walk_without_nested_defs(node: ast.AST) -> Iterator[ast.AST]:
    """Идёт по AST, не проваливаясь во вложенные defs/classes/lambdas."""
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from walk_without_nested_defs(child)


def iter_function_body_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[ast.AST]:
    """Итерирует AST-узлы тела функции без вложенных defs."""
    for statement in get_body_without_docstring(node):
        yield from walk_without_nested_defs(statement)


def get_missing_hints(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Возвращает список параметров и return без аннотаций."""
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
    """Определяет, является ли default-значение мутируемым объектом."""
    if node is None:
        return False
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    return isinstance(node, ast.Call) and get_call_name(node) in {"dict", "list", "set"}


def get_weak_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Собирает слабые имена параметров и локальных переменных функции."""
    names: set[str] = set()
    for arg in list(node.args.args) + list(node.args.kwonlyargs):
        if arg.arg in WEAK_NAMES:
            names.add(arg.arg)
    for body_node in iter_function_body_nodes(node):
        names.update(get_assigned_weak_names(body_node))
    return sorted(names)


def get_assigned_weak_names(node: ast.AST) -> set[str]:
    """Возвращает слабые имена, найденные в assign-узле."""
    names: set[str] = set()
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in WEAK_NAMES:
                names.add(target.id)
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        if node.target.id in WEAK_NAMES:
            names.add(node.target.id)
    return names


def is_number(value: object) -> bool:
    """Проверяет, является ли значение числовым литералом, кроме bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_uppercase_assignment(parent: ast.AST | None) -> bool:
    """Проверяет, что литерал присваивается константоподобной UPPERCASE переменной."""
    if isinstance(parent, ast.Assign):
        return all(isinstance(target, ast.Name) and target.id.isupper() for target in parent.targets)
    if isinstance(parent, ast.AnnAssign):
        return isinstance(parent.target, ast.Name) and parent.target.id.isupper()
    return False


def get_magic_numbers(node: ast.FunctionDef | ast.AsyncFunctionDef, parents: dict[ast.AST, ast.AST]) -> list[str]:
    """Собирает числовые литералы, похожие на magic numbers."""
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
    """Возвращает список blocking-вызовов внутри async функции."""
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
    """Проверяет, ловит ли except обработчик слишком широкий Exception."""
    if isinstance(handler.type, ast.Name):
        return handler.type.id == "Exception"
    if isinstance(handler.type, ast.Tuple):
        return any(isinstance(item, ast.Name) and item.id == "Exception" for item in handler.type.elts)
    return False


def scan_comment_todos(relative_path: Path, source: str) -> list[dict[str, object]]:
    """Ищет TODO/FIXME/HACK в комментариях исходного файла."""
    findings: list[dict[str, object]] = []
    reader = io.StringIO(source).readline
    for token in tokenize.generate_tokens(reader):
        if token.type == tokenize.COMMENT and TODO_PATTERN.search(token.string):
            findings.append(
                build_finding(
                    rule="python-src-todo",
                    severity="P2",
                    category="Technical Debt",
                    path=relative_path,
                    line=token.start[0],
                    title="TODO/FIXME/HACK in source",
                    description="The source file still contains an unfinished task marker.",
                    impact="Inline task markers in release code usually mean known debt or unfinished behavior remains in production paths.",
                    suggested_fix="Resolve the task or move it to external tracking and remove the marker from source.",
                    snippet=token.string.strip(),
                )
            )
    return findings


def analyze_function_metrics(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: Path,
    function_name: str,
    line: int,
) -> list[dict[str, object]]:
    """Возвращает findings по длине и вложенности функции."""
    findings: list[dict[str, object]] = []
    function_length = (node.end_lineno or node.lineno) - node.lineno + 1
    if function_length > MAX_FUNCTION_LENGTH:
        findings.append(
            build_finding(
                rule="python-long-function",
                severity="P2",
                category="Technical Debt",
                path=relative_path,
                line=line,
                title="Long Python function",
                description="The function exceeds the configured length limit.",
                impact="Long functions are harder to review, test, and change safely.",
                suggested_fix="Split the function into smaller helpers with single-purpose responsibilities.",
                snippet=f"{function_name} has {function_length} lines",
            )
        )
    nesting_level = measure_nesting(get_body_without_docstring(node))
    if nesting_level > MAX_NESTING:
        findings.append(
            build_finding(
                rule="python-deep-nesting",
                severity="P2",
                category="Technical Debt",
                path=relative_path,
                line=line,
                title="Deeply nested control flow",
                description="The function exceeds the configured nesting depth.",
                impact="Deep nesting increases cognitive load and makes edge cases easier to miss.",
                suggested_fix="Refactor nested branches into guard clauses or extracted helpers.",
                snippet=f"{function_name} nesting level is {nesting_level}",
            )
        )
    return findings


def analyze_function_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: Path,
    parents: dict[ast.AST, ast.AST],
) -> list[dict[str, object]]:
    """Возвращает все tech debt findings для одной функции."""
    findings: list[dict[str, object]] = []
    function_name = node.name
    line = node.lineno
    findings.extend(analyze_function_metrics(node, relative_path, function_name, line))
    findings.extend(analyze_public_function(node, relative_path, function_name, line))
    if is_empty_function(node):
        findings.append(
            build_finding(
                rule="python-empty-function",
                severity="P2",
                category="Technical Debt",
                path=relative_path,
                line=line,
                title="Empty function body",
                description="The function body contains only pass or return None.",
                impact="Empty implementations in release code often mean unfinished logic or silent no-op behavior.",
                suggested_fix="Implement the logic, raise NotImplementedError intentionally, or remove the dead abstraction.",
                snippet=f"{function_name} contains only pass/return None",
            )
        )
    findings.extend(analyze_function_body(node, relative_path, parents, function_name, line))
    return findings


def analyze_public_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: Path,
    function_name: str,
    line: int,
) -> list[dict[str, object]]:
    """Возвращает findings, относящиеся к публичному API функции."""
    if not is_public_function(node):
        return []
    findings: list[dict[str, object]] = []
    missing_hints = get_missing_hints(node)
    if missing_hints:
        findings.append(
            build_finding(
                rule="python-missing-type-hints",
                severity="P2",
                category="Code Quality",
                path=relative_path,
                line=line,
                title="Missing Python type hints",
                description="A public function is missing one or more type hints.",
                impact="Missing types reduce static validation quality and make contract drift harder to catch.",
                suggested_fix="Add explicit parameter and return annotations to the public API.",
                snippet=f"{function_name} missing hints: {', '.join(missing_hints)}",
            )
        )
    if not ast.get_docstring(node):
        findings.append(
            build_finding(
                rule="python-public-function-no-docstring",
                severity="P3",
                category="Code Quality",
                path=relative_path,
                line=line,
                title="Public function has no docstring",
                description="A public function does not document its purpose or contract.",
                impact="Missing docs slow onboarding and make non-obvious behavior easier to misuse.",
                suggested_fix="Add a short docstring that explains inputs, outputs, and important side effects.",
                snippet=f"{function_name} has no docstring",
            )
        )
    return findings


def analyze_function_body(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: Path,
    parents: dict[ast.AST, ast.AST],
    function_name: str,
    line: int,
) -> list[dict[str, object]]:
    """Возвращает findings по содержимому тела функции."""
    findings: list[dict[str, object]] = []
    findings.extend(build_weak_name_findings(node, relative_path, function_name, line))
    findings.extend(build_magic_number_findings(node, relative_path, parents, function_name, line))
    findings.extend(build_mutable_default_findings(node, relative_path, function_name, line))
    findings.extend(build_async_blocking_findings(node, relative_path, function_name, line))
    return findings


def build_weak_name_findings(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: Path,
    function_name: str,
    line: int,
) -> list[dict[str, object]]:
    """Возвращает findings по слабым именам."""
    weak_names = get_weak_names(node)
    if not weak_names:
        return []
    return [
        build_finding(
            rule="python-weak-name",
            severity="P3",
            category="Code Quality",
            path=relative_path,
            line=line,
            title="Weak variable naming",
            description="The function uses generic names such as data, temp, val, or x.",
            impact="Weak names hide intent and make logic and bugs harder to understand in review.",
            suggested_fix="Rename the variables to describe the domain meaning or role in the algorithm.",
            snippet=f"{function_name} uses weak names: {', '.join(weak_names)}",
        )
    ]


def build_magic_number_findings(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: Path,
    parents: dict[ast.AST, ast.AST],
    function_name: str,
    line: int,
) -> list[dict[str, object]]:
    """Возвращает findings по magic numbers."""
    magic_numbers = get_magic_numbers(node, parents)
    if not magic_numbers:
        return []
    return [
        build_finding(
            rule="python-magic-number",
            severity="P3",
            category="Code Quality",
            path=relative_path,
            line=line,
            title="Magic number in function body",
            description="The function contains numeric literals that are not self-explanatory constants.",
            impact="Magic numbers make code intent unclear and create hidden coupling with business rules.",
            suggested_fix="Extract the value into a named constant or document why the literal is safe inline.",
            snippet=f"{function_name} uses magic numbers: {', '.join(magic_numbers)}",
        )
    ]


def build_mutable_default_findings(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: Path,
    function_name: str,
    line: int,
) -> list[dict[str, object]]:
    """Возвращает findings по mutable default arguments."""
    defaults = list(node.args.defaults) + [item for item in node.args.kw_defaults if item is not None]
    if not any(is_mutable_default(default) for default in defaults):
        return []
    return [
        build_finding(
            rule="python-mutable-default",
            severity="P1",
            category="Bugs and Logic Errors",
            path=relative_path,
            line=line,
            title="Mutable default argument",
            description="The function uses a mutable object as a default value.",
            impact="Mutable defaults persist across calls and can leak state between executions.",
            suggested_fix="Default the argument to None and create the mutable object inside the function body.",
            snippet=f"{function_name} uses mutable default arguments",
        )
    ]


def build_async_blocking_findings(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: Path,
    function_name: str,
    line: int,
) -> list[dict[str, object]]:
    """Возвращает findings по blocking calls внутри async-функции."""
    if not isinstance(node, ast.AsyncFunctionDef):
        return []
    blocking_calls = get_async_blocking_calls(node)
    if not blocking_calls:
        return []
    return [
        build_finding(
            rule="python-async-blocking-call",
            severity="P1",
            category="Performance and Memory",
            path=relative_path,
            line=line,
            title="Blocking call inside async function",
            description="The async function calls a blocking API such as time.sleep or requests.*.",
            impact="Blocking calls freeze the event loop and can stall unrelated coroutines.",
            suggested_fix="Replace the call with async-compatible I/O or move the blocking work off the event loop.",
            snippet=f"{function_name} uses blocking calls: {', '.join(blocking_calls)}",
        )
    ]


def scan_python_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует Python-файл на deterministic tech debt правила."""
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
        findings.extend(analyze_function_node(node, relative_path, parents))
    for handler in ast.walk(tree):
        if isinstance(handler, ast.ExceptHandler) and has_broad_exception(handler):
            findings.append(
                build_finding(
                    rule="python-broad-except",
                    severity="P2",
                    category="Bugs and Logic Errors",
                    path=relative_path,
                    line=handler.lineno,
                    title="Broad except Exception handler",
                    description="The code catches Exception instead of a narrower error contract.",
                    impact="Broad exception handling hides unexpected failures and makes root-cause analysis weaker.",
                    suggested_fix="Catch only the exception types the code can actually recover from.",
                    snippet="except Exception should be narrowed",
                )
            )
    return findings


def main() -> None:
    """CLI entrypoint для tech debt audit."""
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
