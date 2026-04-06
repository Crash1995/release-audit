from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from finding_utils import build_finding
from shared import load_config_helpers

PYTHON_MANIFESTS = ("requirements.txt", "pyproject.toml")
NODE_MANIFESTS = ("package.json",)
UNPINNED_REQUIREMENT = re.compile(r"^[A-Za-z0-9_.-]+(\[[A-Za-z0-9_,.-]+\])?\s*(>=|>|<=|<|~=|!=)")
DIRECT_REFERENCE = re.compile(r"(@\s*(git\+|https?://|file:))|(^-e\s+)")
VERSION_RISK_PATTERN = re.compile(r'(?:"|\')(\*|latest|main|master)(?:"|\')')
MAX_SNIPPET_LENGTH = 160


def scan_requirements(root: Path, path: Path) -> list[dict[str, object]]:
    """Проверяет requirements-файлы на непинованные и прямые зависимости."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if UNPINNED_REQUIREMENT.search(line):
            findings.append(
                build_finding(
                    rule="unpinned-python-dependency",
                    severity="P2",
                    category="Dependencies and Configuration",
                    path=relative_path,
                    line=line_no,
                    title="Python dependency is not pinned exactly",
                    description="The requirements file uses a range or flexible version instead of an exact pin.",
                    impact="Flexible dependency ranges reduce reproducibility and can pull in breaking or vulnerable releases unexpectedly.",
                    suggested_fix="Pin the dependency to an exact reviewed version for release builds.",
                    snippet=line,
                )
            )
        if DIRECT_REFERENCE.search(line):
            findings.append(
                build_finding(
                    rule="direct-dependency-reference",
                    severity="P2",
                    category="Dependencies and Configuration",
                    path=relative_path,
                    line=line_no,
                    title="Direct dependency reference",
                    description="The dependency is installed from a direct URL, VCS source, or editable path.",
                    impact="Direct references reduce reproducibility and make supply-chain review harder.",
                    suggested_fix="Prefer a versioned package release or document why the direct reference is unavoidable.",
                    snippet=line,
                )
            )
    return findings


def scan_text_manifest(root: Path, path: Path) -> list[dict[str, object]]:
    """Проверяет текстовые manifest/lock файлы на floating version references."""
    findings: list[dict[str, object]] = []
    relative_path = path.relative_to(root)
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        if VERSION_RISK_PATTERN.search(raw_line):
            findings.append(
                build_finding(
                    rule="floating-dependency-version",
                    severity="P2",
                    category="Dependencies and Configuration",
                    path=relative_path,
                    line=line_no,
                    title="Floating dependency version",
                    description="The manifest references * / latest / main / master instead of a reviewed version.",
                    impact="Floating versions make release builds non-reproducible and can pull unreviewed code.",
                    suggested_fix="Replace the floating reference with an explicit released version.",
                    snippet=raw_line.strip()[:MAX_SNIPPET_LENGTH],
                )
            )
    return findings


def build_findings(root: Path) -> list[dict[str, object]]:
    """Строит findings по dependency/configuration рискам."""
    findings: list[dict[str, object]] = []
    manifest_paths = [root / name for name in PYTHON_MANIFESTS + NODE_MANIFESTS]
    if not any(path.exists() for path in manifest_paths):
        if (root / "SKILL.md").exists() and (root / "agents" / "openai.yaml").exists():
            return []
        return [
            build_finding(
                rule="missing-dependency-manifest",
                severity="P2",
                category="Dependencies and Configuration",
                path=".",
                title="Dependency manifest not found",
                description="The repository does not expose a standard Python or Node dependency manifest.",
                impact="Dependency review and reproducible setup are harder without an explicit manifest.",
                suggested_fix="Add the appropriate manifest file or document the dependency model clearly in the repository.",
            )
        ]
    for path in root.rglob("requirements*.txt"):
        if path.is_file():
            findings.extend(scan_requirements(root, path))
    for name in ("pyproject.toml", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"):
        manifest_path = root / name
        if manifest_path.exists():
            findings.extend(scan_text_manifest(root, manifest_path))
    return findings


def main() -> None:
    """CLI entrypoint для dependency audit."""
    root = Path.cwd()
    findings = build_findings(root)
    config_module = load_config_helpers()
    config = config_module.load_audit_config(root)
    findings = config_module.apply_config(findings, config)
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
