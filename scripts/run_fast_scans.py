from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from finding_utils import build_blocked, build_finding
from shared import (
    BINARY_EXTENSIONS,
    SKIP_DIR_NAMES,
    has_noqa_marker,
    load_config_helpers,
    safe_read_text,
)

MAX_SNIPPET_LENGTH = 160

PATTERNS: tuple[dict[str, object], ...] = (
    {
        "rule": "todo",
        "severity": "P2",
        "category": "Technical Debt",
        "title": "TODO or hack marker in code",
        "description": "The file contains TODO/FIXME/HACK/XXX markers.",
        "impact": "Unfinished or temporary logic can leak into release behavior and hide known debt.",
        "suggested_fix": "Resolve the task or convert the note into a tracked issue and remove it from release code.",
        "pattern": r"\b(TODO|FIXME|HACK|XXX)\b",
    },
    {
        "rule": "placeholder",
        "severity": "P2",
        "category": "Code Quality",
        "title": "Placeholder value found",
        "description": "The file contains placeholder or fake values such as lorem ipsum, changeme, password, or 123456.",
        "impact": "Placeholder values in release code can break runtime behavior and hide missing configuration.",
        "suggested_fix": "Replace the placeholder with real configuration, a constant, or explicit test-only scaffolding outside production code.",
        "pattern": r"(?i)\b(lorem ipsum|changeme|password|123456)\b",
    },
    {
        "rule": "debug-call",
        "severity": "P2",
        "category": "Code Quality",
        "title": "Debug-only call left in code",
        "description": "The file contains console.log, debugger, alert, or print-style debug output.",
        "impact": "Debug calls create noisy logs, leak internal state, and reduce signal in production diagnostics.",
        "suggested_fix": "Remove the debug statement or replace it with structured application logging where appropriate.",
        "pattern": r"\b(console\.log|debugger|alert|print\()",
    },
    {
        "rule": "hardcoded-secret",
        "severity": "P0",
        "category": "Security",
        "title": "Possible hardcoded secret",
        "description": "A token-like or password-like value appears to be embedded directly in source.",
        "impact": "Hardcoded credentials can be exfiltrated from the repository and reused against production systems.",
        "suggested_fix": "Move the secret to environment-based configuration and rotate any exposed value.",
        "pattern": r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"]{6,}",
    },
    {
        "rule": "private-key-material",
        "severity": "P0",
        "category": "Security",
        "title": "Private key material in repository",
        "description": "The file contains PEM/OpenSSH private key material.",
        "impact": "Private keys in a repository are a direct compromise path and usually require immediate rotation.",
        "suggested_fix": "Remove the key from the repository history, rotate it, and load keys only from secure external storage.",
        "pattern": r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----",
    },
    {
        "rule": "unsafe-exec",
        "severity": "P0",
        "category": "Security",
        "title": "Unsafe dynamic execution",
        "description": "The file uses eval/exec or unsafe deserialization patterns such as pickle.loads or yaml.load.",
        "impact": "Dynamic execution and unsafe deserialization can lead to remote code execution with attacker-controlled input.",
        "suggested_fix": "Replace the construct with safe parsing, explicit dispatch, or safe loaders such as yaml.safe_load.",
        "pattern": r"\b(eval\(|exec\(|pickle\.loads\(|yaml\.load\()",
    },
    {
        "rule": "os-system",
        "severity": "P1",
        "category": "Security",
        "title": "os.system call found",
        "description": "The file invokes os.system directly.",
        "impact": "Shell execution is hard to sanitize and can become a command-injection vector when inputs are not fully controlled.",
        "suggested_fix": "Use subprocess with an argument list and explicit input validation instead of shell command strings.",
        "pattern": r"\bos\.system\(",
    },
    {
        "rule": "shell-true",
        "severity": "P1",
        "category": "Security",
        "title": "subprocess shell=True usage",
        "description": "The file runs subprocess with shell=True.",
        "impact": "shell=True widens the attack surface for command injection and quoting bugs.",
        "suggested_fix": "Pass commands as argument arrays and avoid shell=True unless the shell is strictly required and fully controlled.",
        "pattern": r"\bsubprocess\.(run|Popen)\(.*shell\s*=\s*True",
    },
    {
        "rule": "verify-false",
        "severity": "P1",
        "category": "Security",
        "title": "TLS verification disabled",
        "description": "The code explicitly disables certificate verification.",
        "impact": "Disabling TLS verification allows man-in-the-middle attacks and defeats transport security.",
        "suggested_fix": "Remove verify=False and configure proper CA trust or certificate pinning if needed.",
        "pattern": r"\bverify\s*=\s*False\b",
    },
    {
        "rule": "wildcard-cors",
        "severity": "P1",
        "category": "Security",
        "title": "Wildcard CORS configuration",
        "description": "The code appears to allow all origins in a CORS policy.",
        "impact": "A wildcard CORS policy can expose authenticated endpoints or sensitive responses to untrusted origins.",
        "suggested_fix": "Restrict allowed origins to an explicit list for the deployed environment.",
        "pattern": r"(?i)(cors|allow_origins).*(\*|\"\\*\"|'\\*')",
    },
    {
        "rule": "http-without-tls",
        "severity": "P1",
        "category": "Data Leaks",
        "title": "Plain HTTP URL found",
        "description": "The file contains an http:// URL.",
        "impact": "Sensitive traffic over plain HTTP can be intercepted or modified in transit.",
        "suggested_fix": "Use HTTPS for remote communication unless the endpoint is local, ephemeral, and explicitly trusted.",
        "pattern": r"(?i)http://[^\s'\"]+",
    },
    {
        "rule": "bare-except",
        "severity": "P1",
        "category": "Bugs and Logic Errors",
        "title": "Bare except block",
        "description": "The file contains a bare except clause.",
        "impact": "Bare except hides unexpected failures, KeyboardInterrupt, and system-exit paths, making debugging unsafe.",
        "suggested_fix": "Catch specific exception types and surface or log unexpected failures explicitly.",
        "pattern": r"^\s*except\s*:\s*$",
    },
    {
        "rule": "except-pass",
        "severity": "P1",
        "category": "Bugs and Logic Errors",
        "title": "Empty pass statement in error flow",
        "description": "The file contains a pass statement that may swallow errors or leave code intentionally empty.",
        "impact": "Silent pass blocks can hide operational failures and make incident triage much harder.",
        "suggested_fix": "Handle the failure explicitly, log it, or document why the branch is intentionally empty.",
        "pattern": r"^\s*pass\s*(#.*)?$",
    },
)


def should_skip(path: Path) -> bool:
    """Определяет, нужно ли пропустить файл на fast scan этапе."""
    parts = set(path.parts)
    if parts & SKIP_DIR_NAMES:
        return True
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    return ".min." in path.name


def build_snippet(line: str) -> str:
    """Обрезает строку до компактного evidence snippet."""
    return line.strip()[:MAX_SNIPPET_LENGTH]


def should_ignore_match(path: Path, line: str) -> bool:
    """Отсекает self-noise через маркер и минимальные structural rules."""
    if has_noqa_marker(line):
        return True
    if path.parts and path.parts[0] == "references" and "`" in line:
        return True
    if path.parts and path.parts[0] == "tests":
        return True
    return False


def scan_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует один файл regex/keyword правилами высокого риска."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    text = safe_read_text(path)
    if text is None:
        return [
            build_blocked(
                rule="scan-error",
                severity="P1",
                category="Blocked",
                path=relative_path,
                title="File too large or unreadable",
                description="The file exceeds size limit or could not be read.",
                impact="Coverage is incomplete until the file can be inspected.",
                suggested_fix="Check file size and permissions, then rerun the audit.",
                error="file too large or unreadable",
            )
        ]
    for line_no, line in enumerate(text.splitlines(), start=1):
        for entry in PATTERNS:
            if entry["rule"] == "todo" and relative_path.suffix == ".py":
                continue
            if re.search(entry["pattern"], line) and not should_ignore_match(relative_path, line):
                findings.append(
                    build_finding(
                        rule=str(entry["rule"]),
                        severity=str(entry["severity"]),
                        category=str(entry["category"]),
                        path=relative_path,
                        line=line_no,
                        title=str(entry["title"]),
                        description=str(entry["description"]),
                        impact=str(entry["impact"]),
                        suggested_fix=str(entry["suggested_fix"]),
                        snippet=build_snippet(line),
                    )
                )
    return findings


def main() -> None:
    """CLI entrypoint для fast scan."""
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
