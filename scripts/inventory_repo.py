from __future__ import annotations

import json
import sys
from pathlib import Path

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".cache",
    "build",
    "dist",
    "node_modules",
    ".eggs",
    "*.egg-info",
    "docs",
    "doc",
    ".github",
    ".gitlab",
    ".vscode",
    ".idea",
    ".claude",
    "htmlcov",
    "coverage",
    ".coverage",
    "data",
    "output",
    "outputs",
    "logs",
    "tmp",
    "temp",
    "notebooks",
}

SKIP_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".DS_Store",
    "Thumbs.db",
    ".editorconfig",
    ".prettierrc",
    ".eslintrc",
    "poetry.lock",
    "package-lock.json",
    "yarn.lock",
    "Pipfile.lock",
}

SKIP_FILE_PATTERNS = {
    ".log",
    ".bak",
    ".old",
    ".orig",
    ".swp",
    ".swo",
    ".tmp",
}

BINARY_EXTENSIONS = {
    ".bin",
    ".csv",
    ".db",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".parquet",
    ".pdf",
    ".pickle",
    ".pkl",
    ".png",
    ".pyc",
    ".so",
    ".sqlite",
    ".sqlite3",
    ".svgz",
    ".tar",
    ".webp",
    ".whl",
    ".zip",
}


def is_binary_path(path: Path) -> bool:
    """Проверяет, относится ли путь к бинарным или непострочно-читаемым файлам."""
    return path.suffix.lower() in BINARY_EXTENSIONS


def classify_path(path: Path) -> str:
    """Классифицирует файл по крупной категории для аудита."""
    parts = set(path.parts)
    suffix = path.suffix.lower()
    if is_binary_path(path):
        return "binary"
    if "tests" in parts or path.name.startswith("test_"):
        return "tests"
    if path.name in {"Dockerfile", "docker-compose.yml"} or suffix in {".tf", ".tfvars"}:
        return "infra"
    if any(part in {".github", ".gitlab"} for part in parts):
        return "ci"
    if "docs" in parts or suffix in {".md", ".rst"}:
        return "docs"
    if path.name in {"pyproject.toml", "package.json", "package-lock.json"}:
        return "config"
    if suffix in {".json", ".toml", ".yaml", ".yml", ".ini", ".env"}:
        return "config"
    if suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".sh"}:
        return "source"
    return "other"


def get_skip_reason(path: Path) -> str | None:
    """Возвращает причину skip для deep review, если файл не стоит читать построчно."""
    parts = set(path.parts)
    if parts & SKIP_DIR_NAMES:
        return "tooling-or-build-directory"
    # egg-info директории матчатся по суффиксу
    if any(part.endswith(".egg-info") for part in path.parts):
        return "tooling-or-build-directory"
    if path.name in SKIP_FILE_NAMES:
        return "service-file"
    if path.suffix.lower() in SKIP_FILE_PATTERNS:
        return "temp-or-backup-file"
    if ".min." in path.name:
        return "minified-asset"
    if is_binary_path(path):
        return "binary-file"
    return None


def build_record(root: Path, path: Path) -> dict[str, object]:
    """Строит одну inventory-запись для файла репозитория."""
    relative_path = path.relative_to(root)
    skip_reason = get_skip_reason(relative_path)
    return {
        "path": str(relative_path),
        "category": classify_path(relative_path),
        "should_review_deeply": skip_reason is None,
        "skip_reason": skip_reason,
    }


def build_inventory(root: Path) -> list[dict[str, object]]:
    """Строит полный инвентарь файлов репозитория."""
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            records.append(build_record(root, path))
    return records


def main() -> None:
    """CLI entrypoint для построения inventory репозитория."""
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    files = build_inventory(root)
    inventory = {"root": str(root), "total_files": len(files), "files": files}
    json.dump(inventory, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
