from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

from finding_utils import build_finding
from shared import get_qualified_name, has_noqa_marker, load_config_helpers, safe_read_text

TEXT_SUFFIXES = {
    ".html",
    ".js",
    ".jsx",
    ".py",
    ".ts",
    ".tsx",
}
TOKEN_STORAGE_PATTERN = re.compile(
    r"(?i)(localStorage|sessionStorage)\.(setItem|getItem)\(\s*['\"][^'\"]*(token|jwt|auth|secret|session)[^'\"]*['\"]"
)
DOM_INJECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("dangerous-dom-write", r"\bdocument\.write\s*\("),
    ("dangerous-inner-html", r"\b(innerHTML|outerHTML|dangerouslySetInnerHTML)\b"),
)
SENSITIVE_LOG_PATTERN = re.compile(
    r"(?i)(logger\.(debug|info|warning|error)|console\.(log|debug|warn|error)|print\()([^#\n]{0,160})(token|secret|password|mnemonic|private[_ -]?key)"
)
MAX_SNIPPET_LENGTH = 160


def should_scan_text_file(path: Path) -> bool:
    """Проверяет, подходит ли файл для текстового security/data-leak сканирования."""
    return path.suffix.lower() in TEXT_SUFFIXES


def build_snippet(line: str) -> str:
    """Обрезает строку до компактного фрагмента для evidence."""
    return line.strip()[:MAX_SNIPPET_LENGTH]


def build_security_finding(
    rule: str,
    category: str,
    path: Path,
    line: int,
    title: str,
    description: str,
    impact: str,
    suggested_fix: str,
    snippet: str,
) -> dict[str, object]:
    """Собирает единый finding для security audit."""
    severity = "P1"
    if rule in {"dangerous-dom-write", "dangerous-inner-html", "subprocess-interpolated-command", "path-interpolation-risk"}:
        severity = "P1"
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


def should_ignore_match(path: Path, line: str) -> bool:
    """Отсекает self-noise через маркер и минимальные structural rules."""
    if has_noqa_marker(line):
        return True
    if path.parts and path.parts[0] == "references":
        return True
    return False


def scan_dom_patterns(relative_path: Path, line: str, line_no: int) -> list[dict[str, object]]:
    """Ищет DOM injection sinks в одной строке."""
    findings: list[dict[str, object]] = []
    for rule, pattern in DOM_INJECTION_PATTERNS:
        if not re.search(pattern, line):
            continue
        findings.append(
            build_security_finding(
                rule=rule,
                category="Security",
                path=relative_path,
                line=line_no,
                title="Unsafe DOM injection pattern",
                description="The code uses a DOM write primitive that can inject unsanitized HTML or script content.",
                impact="Unsafe DOM writes can become XSS vectors when user-controlled content reaches the sink.",
                suggested_fix="Render content through safe templating/escaping or sanitize the HTML before insertion.",
                snippet=build_snippet(line),
            )
        )
    return findings


def scan_storage_and_logs(relative_path: Path, line: str, line_no: int) -> list[dict[str, object]]:
    """Ищет storage/log data leak patterns в одной строке."""
    findings: list[dict[str, object]] = []
    if TOKEN_STORAGE_PATTERN.search(line):
        findings.append(
            build_security_finding(
                rule="token-storage",
                category="Data Leaks",
                path=relative_path,
                line=line_no,
                title="Token-like value stored in browser storage",
                description="The code stores or reads token-like values from localStorage or sessionStorage.",
                impact="Browser storage is accessible to injected scripts and increases the blast radius of XSS issues.",
                suggested_fix="Prefer secure cookies or short-lived in-memory storage for sensitive tokens.",
                snippet=build_snippet(line),
            )
        )
    if SENSITIVE_LOG_PATTERN.search(line):
        findings.append(
            build_security_finding(
                rule="sensitive-log-field",
                category="Data Leaks",
                path=relative_path,
                line=line_no,
                title="Sensitive field referenced in logs",
                description="A logging or console statement appears to reference secrets, tokens, or private key material.",
                impact="Sensitive fields in logs can leak credentials to consoles, log drains, and monitoring systems.",
                suggested_fix="Remove the sensitive field from logs or mask it before logging.",
                snippet=build_snippet(line),
            )
        )
    return findings


def scan_text_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует текстовый файл на XSS/data-leak эвристики."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    text = safe_read_text(path)
    if text is None:
        return []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if should_ignore_match(relative_path, line):
            continue
        findings.extend(scan_dom_patterns(relative_path, line, line_no))
        findings.extend(scan_storage_and_logs(relative_path, line, line_no))
    return findings


def get_call_name(node: ast.AST) -> str:  # noqa: release-audit
    """Возвращает квалифицированное имя вызова или атрибута."""
    return get_qualified_name(node)


def is_interpolated_command(node: ast.AST) -> bool:
    """Определяет, строится ли команда/путь через интерполяцию или конкатенацию."""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return True
    return isinstance(node, ast.Call) and get_call_name(node.func) in {"format", "str.format"}


def scan_subprocess_call(relative_path: Path, node: ast.Call, call_name: str) -> list[dict[str, object]]:
    """Ищет интерполированные subprocess-команды."""
    if call_name not in {"subprocess.run", "subprocess.Popen"} or not node.args:
        return []
    if not is_interpolated_command(node.args[0]):
        return []
    return [
        build_security_finding(
            rule="subprocess-interpolated-command",
            category="Security",
            path=relative_path,
            line=node.lineno,
            title="Interpolated subprocess command",
            description="A subprocess command is built through string interpolation or concatenation.",
            impact="Interpolated shell commands are much harder to validate and can become injection vectors.",
            suggested_fix="Pass subprocess arguments as an explicit list and validate any user-controlled segments.",
            snippet=call_name,
        )
    ]


def scan_path_call(relative_path: Path, node: ast.Call, call_name: str) -> list[dict[str, object]]:
    """Ищет интерполированные файловые пути."""
    if call_name not in {"open", "Path.open", "Path.read_text", "Path.read_bytes"} or not node.args:
        return []
    if not is_interpolated_command(node.args[0]):
        return []
    return [
        build_security_finding(
            rule="path-interpolation-risk",
            category="Security",
            path=relative_path,
            line=node.lineno,
            title="Interpolated filesystem path",
            description="A filesystem path is built through interpolation or concatenation.",
            impact="Interpolated paths are harder to constrain and can allow traversal into unexpected locations.",
            suggested_fix="Normalize the path, validate allowed roots, and assemble it from safe path components.",
            snippet=call_name,
        )
    ]


def scan_python_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует Python-файл на shell/path injection smells."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = get_call_name(node.func)
        findings.extend(scan_subprocess_call(relative_path, node, call_name))
        findings.extend(scan_path_call(relative_path, node, call_name))
    return findings


def is_skill_repository(root: Path) -> bool:
    """Проверяет, выглядит ли корень как репозиторий skill-а."""
    return (root / "SKILL.md").exists() and (root / "agents" / "openai.yaml").exists()


def build_findings(root: Path) -> list[dict[str, object]]:
    """Строит findings по security и data-leak проверкам."""
    findings: list[dict[str, object]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_scan_text_file(path):
            findings.extend(scan_text_file(root, path))
        if path.suffix == ".py":
            findings.extend(scan_python_file(root, path))
    return findings


def main() -> None:
    """CLI entrypoint для security audit."""
    root = Path.cwd()
    findings = build_findings(root)
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    findings = config_module.apply_config(findings, config)
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
