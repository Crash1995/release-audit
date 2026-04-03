from __future__ import annotations

import json
import re
import sys
import importlib.util
from pathlib import Path

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

PATTERNS: tuple[dict[str, str], ...] = (
    {"rule": "todo", "severity": "P2", "pattern": r"\b(TODO|FIXME|HACK|XXX)\b"},
    {"rule": "placeholder", "severity": "P2", "pattern": r"(?i)\b(lorem ipsum|changeme|password|123456)\b"},
    {"rule": "debug-call", "severity": "P2", "pattern": r"\b(console\.log|debugger|alert|print\()"},
    {"rule": "hardcoded-secret", "severity": "P0", "pattern": r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"]{6,}"},
    {"rule": "private-key-material", "severity": "P0", "pattern": r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"},
    {"rule": "unsafe-exec", "severity": "P0", "pattern": r"\b(eval\(|exec\(|pickle\.loads\(|yaml\.load\()"},
    {"rule": "os-system", "severity": "P1", "pattern": r"\bos\.system\("},
    {"rule": "shell-true", "severity": "P1", "pattern": r"\bsubprocess\.(run|Popen)\(.*shell\s*=\s*True"},
    {"rule": "verify-false", "severity": "P1", "pattern": r"\bverify\s*=\s*False\b"},
    {"rule": "wildcard-cors", "severity": "P1", "pattern": r"(?i)(cors|allow_origins).*(\*|\"\\*\"|'\\*')"},
    {"rule": "http-without-tls", "severity": "P1", "pattern": r"(?i)http://[^\s'\"]+"},
    {"rule": "bare-except", "severity": "P1", "pattern": r"^\s*except\s*:\s*$"},
    {"rule": "except-pass", "severity": "P1", "pattern": r"^\s*pass\s*(#.*)?$"},
)


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIR_NAMES:
        return True
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    return ".min." in path.name


def build_snippet(line: str) -> str:
    return line.strip()[:160]


def should_ignore_match(path: Path, line: str) -> bool:
    if '"pattern": r"' in line:
        return True
    if path.parts and path.parts[0] == "references" and "`" in line:
        return True
    if path.parts and path.parts[0] == "tests":
        return True
    if path.parts and path.parts[0] == "scripts" and "build_finding(" in line:
        return True
    return False


def scan_file(root: Path, path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as error:
        return [
            {
                "kind": "blocked",
                "rule": "scan-error",
                "severity": "P1",
                "path": str(relative_path),
                "error": str(error),
            }
        ]
    for line_no, line in enumerate(text.splitlines(), start=1):
        for entry in PATTERNS:
            if entry["rule"] == "todo" and relative_path.suffix == ".py":
                continue
            if re.search(entry["pattern"], line) and not should_ignore_match(relative_path, line):
                findings.append(
                    {
                        "kind": "finding",
                        "rule": entry["rule"],
                        "severity": entry["severity"],
                        "path": str(relative_path),
                        "line": line_no,
                        "snippet": build_snippet(line),
                    }
                )
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
    for path in root.rglob("*"):
        if path.is_file() and not should_skip(path.relative_to(root)):
            results.extend(scan_file(root, path))
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    results = config_module.apply_config(results, config)
    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
