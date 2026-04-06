"""Web3-специфичные security checks для release-audit."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

from finding_utils import build_finding
from shared import get_qualified_name, has_noqa_marker, load_config_helpers, safe_read_text

# Паттерн мнемонической фразы: 12 или 24 слова из маленьких латинских букв через пробелы
MNEMONIC_PATTERN = re.compile(
    r"""(['"])((?:[a-z]{2,10}\s+){11}[a-z]{2,10}|(?:[a-z]{2,10}\s+){23}[a-z]{2,10})\1"""
)
# Hex-строка похожая на приватный ключ: 64 hex символа (32 байта), опционально с 0x префиксом
PRIVATE_KEY_HEX_PATTERN = re.compile(
    r"""(['"])(?:0x)?([0-9a-fA-F]{64})\1"""
)
# Ethereum-адрес в строковом литерале (для проверки checksum)
ETH_ADDRESS_PATTERN = re.compile(
    r"""(['"])(0x[0-9a-fA-F]{40})\1"""
)
# Известные тестовые / placeholder приватные ключи (первые 16 hex символов)
TEST_KEY_PREFIXES = {
    "0000000000000000",
    "aaaaaaaaaaaaaaaa",
    "1111111111111111",
    "deadbeefdeadbeef",
}
TEXT_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx"}

MAX_SNIPPET_LENGTH = 120


def build_snippet(text: str) -> str:
    """Обрезает строку до компактного фрагмента."""
    return text.strip()[:MAX_SNIPPET_LENGTH]


def is_mixed_case_address(address: str) -> bool:
    """Проверяет, содержит ли адрес mixed case (EIP-55 checksum)."""
    hex_part = address[2:]
    return hex_part != hex_part.lower() and hex_part != hex_part.upper()


def is_test_key(hex_value: str) -> bool:
    """Проверяет, похож ли hex на тестовый placeholder ключ."""
    normalized = hex_value.lower().lstrip("0x")[:16]
    return normalized in TEST_KEY_PREFIXES or len(set(normalized)) <= 2


def scan_mnemonic_in_line(
    relative_path: Path, line: str, line_no: int,
) -> list[dict[str, object]]:
    """Ищет строковые литералы похожие на мнемоническую фразу."""
    findings: list[dict[str, object]] = []
    for match in MNEMONIC_PATTERN.finditer(line):
        words = match.group(2).split()
        if len(words) not in (12, 24):
            continue
        findings.append(
            build_finding(
                rule="web3-hardcoded-mnemonic",
                severity="P0",
                category="Security",
                path=relative_path,
                line=line_no,
                title="Hardcoded mnemonic / seed phrase",
                description="A string literal matches the pattern of a BIP-39 mnemonic phrase (12 or 24 words).",
                impact="Hardcoded mnemonics in source code expose wallet funds to anyone with repo access.",
                suggested_fix="Move the mnemonic to an environment variable and load it via pydantic-settings or os.environ.",
                snippet=f'"{words[0]} {words[1]} ... {words[-1]}" ({len(words)} words)',
            )
        )
    return findings


def scan_private_key_in_line(
    relative_path: Path, line: str, line_no: int,
) -> list[dict[str, object]]:
    """Ищет строковые литералы похожие на приватные ключи (64 hex символа)."""
    findings: list[dict[str, object]] = []
    for match in PRIVATE_KEY_HEX_PATTERN.finditer(line):
        hex_value = match.group(2)
        if is_test_key(hex_value):
            continue
        findings.append(
            build_finding(
                rule="web3-hardcoded-private-key",
                severity="P0",
                category="Security",
                path=relative_path,
                line=line_no,
                title="Hardcoded private key",
                description="A 64-character hex string resembling an Ethereum private key was found in source code.",
                impact="Exposed private keys allow full control of the associated wallet and its funds.",
                suggested_fix="Move the key to an environment variable; never commit key material to version control.",
                snippet=f'"0x{hex_value[:8]}...{hex_value[-4:]}"',
            )
        )
    return findings


def scan_address_checksum_in_line(
    relative_path: Path, line: str, line_no: int,
) -> list[dict[str, object]]:
    """Ищет Ethereum-адреса без EIP-55 checksum."""
    findings: list[dict[str, object]] = []
    for match in ETH_ADDRESS_PATTERN.finditer(line):
        address = match.group(2)
        if is_mixed_case_address(address):
            continue
        # Полностью нулевой или burn-адрес — пропускаем
        hex_part = address[2:]
        if hex_part == "0" * 40 or hex_part.lower() == "dead" * 10:
            continue
        findings.append(
            build_finding(
                rule="web3-address-no-checksum",
                severity="P2",
                category="Security",
                path=relative_path,
                line=line_no,
                title="Ethereum address without EIP-55 checksum",
                description="A hardcoded Ethereum address uses all-lowercase or all-uppercase hex without EIP-55 mixed-case checksum.",
                impact="Non-checksummed addresses bypass typo detection and may silently send funds to a wrong address.",
                suggested_fix="Convert to checksummed form via Web3.to_checksum_address() and store the result.",
                snippet=f'"{address[:10]}...{address[-4:]}"',
            )
        )
    return findings


def scan_from_key_call(
    relative_path: Path, node: ast.Call,
) -> list[dict[str, object]]:
    """Ищет Account.from_key() с inline строковым ключом."""
    call_name = get_qualified_name(node.func)
    if "from_key" not in call_name:
        return []
    if not node.args:
        return []
    first_arg = node.args[0]
    if not isinstance(first_arg, (ast.Constant, ast.JoinedStr)):
        return []
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        val = first_arg.value
        hex_part = val.lstrip("0x")
        if is_test_key(hex_part):
            return []
    return [
        build_finding(
            rule="web3-inline-from-key",
            severity="P0",
            category="Security",
            path=relative_path,
            line=node.lineno,
            title="Inline private key in from_key() call",
            description="Account.from_key() is called with a literal string or f-string instead of an env variable.",
            impact="Hardcoded keys in from_key() calls are easily extracted from source and grant full wallet access.",
            suggested_fix="Load the key from an environment variable: Account.from_key(os.environ['PRIVATE_KEY']).",
            snippet=call_name,
        )
    ]


def scan_text_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует текстовый файл на Web3 security smells построчно."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    text = safe_read_text(path)
    if text is None:
        return []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if has_noqa_marker(line):
            continue
        findings.extend(scan_mnemonic_in_line(relative_path, line, line_no))
        findings.extend(scan_private_key_in_line(relative_path, line, line_no))
        findings.extend(scan_address_checksum_in_line(relative_path, line, line_no))
    return findings


def scan_python_file(root: Path, path: Path) -> list[dict[str, object]]:
    """Сканирует Python-файл на AST-level Web3 security smells."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            findings.extend(scan_from_key_call(relative_path, node))
    return findings


def build_findings(root: Path) -> list[dict[str, object]]:
    """Строит findings по Web3-специфичным security checks."""
    findings: list[dict[str, object]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            findings.extend(scan_text_file(root, path))
        if path.suffix == ".py":
            findings.extend(scan_python_file(root, path))
    return findings


def main() -> None:
    """CLI entrypoint для Web3 security audit."""
    root = Path.cwd()
    findings = build_findings(root)
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    findings = config_module.apply_config(findings, config)
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
