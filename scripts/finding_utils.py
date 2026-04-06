from __future__ import annotations

from pathlib import Path


def normalize_path(path: str | Path) -> str:
    """Нормализует путь finding-а к строковому представлению."""
    return str(path)


def build_finding(
    *,
    rule: str,
    severity: str,
    category: str,
    path: str | Path,
    title: str,
    description: str,
    impact: str,
    suggested_fix: str,
    line: int | None = None,
    snippet: str | None = None,
    confidence: float = 0.85,
) -> dict[str, object]:
    """Строит стандартный finding в едином формате release-audit."""
    finding: dict[str, object] = {
        "kind": "finding",
        "rule": rule,
        "severity": severity,
        "category": category,
        "path": normalize_path(path),
        "title": title,
        "description": description,
        "impact": impact,
        "suggested_fix": suggested_fix,
        "confidence": confidence,
    }
    if line is not None:
        finding["line"] = line
    if snippet:
        finding["snippet"] = snippet
    return finding


def build_blocked(
    *,
    rule: str,
    severity: str,
    category: str,
    path: str | Path,
    title: str,
    description: str,
    impact: str,
    suggested_fix: str,
    error: str,
    confidence: float = 1.0,
) -> dict[str, object]:
    """Строит blocked finding в едином формате release-audit."""
    return {
        "kind": "blocked",
        "rule": rule,
        "severity": severity,
        "category": category,
        "path": normalize_path(path),
        "title": title,
        "description": description,
        "impact": impact,
        "suggested_fix": suggested_fix,
        "error": error,
        "confidence": confidence,
    }
