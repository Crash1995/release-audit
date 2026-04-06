"""Общие утилиты для всех audit-сканеров release-audit."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}

BINARY_EXTENSIONS = {
    ".bin",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".svgz",
    ".webp",
    ".zip",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB — файлы больше этого пропускаются

NOQA_MARKER = "# noqa: release-audit"


def load_config_helpers() -> ModuleType:
    """Загружает helper для suppressions и severity overrides."""
    module_path = Path(__file__).with_name("load_audit_config.py")
    spec = importlib.util.spec_from_file_location("load_audit_config", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def get_short_call_name(node: ast.Call) -> str:
    """Возвращает короткое имя вызываемой функции (без модуля)."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def get_qualified_name(node: ast.AST) -> str:
    """Возвращает квалифицированное имя атрибута или вызова (с модулем)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = get_qualified_name(node.value)
        return f"{parent_name}.{node.attr}" if parent_name else node.attr
    return ""


def compact_finding(finding: dict[str, object]) -> dict[str, object]:
    """Оставляет минимальный набор полей finding-а для сохранения."""
    compact: dict[str, object] = {
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


def is_file_too_large(path: Path) -> bool:
    """Проверяет, превышает ли файл допустимый размер для построчного чтения."""
    try:
        return path.stat().st_size > MAX_FILE_SIZE
    except OSError:
        return False


def safe_read_text(path: Path) -> str | None:
    """Читает файл с проверкой размера. Возвращает None если файл слишком большой."""
    if is_file_too_large(path):
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def has_noqa_marker(line: str) -> bool:
    """Проверяет наличие маркера подавления для release-audit."""
    return NOQA_MARKER in line
