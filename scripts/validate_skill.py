from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def build_finding(rule: str, path: str, message: str) -> dict[str, str]:
    return {"kind": "finding", "rule": rule, "severity": "P1", "path": path, "message": message}


def has_frontmatter_fields(text: str) -> bool:
    return bool(re.search(r"^---\n.*\bname:\s*.+\n.*\bdescription:\s*.+\n---", text, re.DOTALL))


def validate_skill(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    skill_path = root / "SKILL.md"
    if not skill_path.exists():
        return [build_finding("missing-skill-md", "SKILL.md", "Missing SKILL.md")]
    skill_text = skill_path.read_text(encoding="utf-8")
    if not has_frontmatter_fields(skill_text):
        findings.append(build_finding("invalid-skill-frontmatter", "SKILL.md", "SKILL.md must define name and description"))
    if not (root / "agents" / "openai.yaml").exists():
        findings.append(build_finding("missing-openai-yaml", "agents/openai.yaml", "Missing agents/openai.yaml"))
    if not (root / "references").is_dir():
        findings.append(build_finding("missing-references-dir", "references", "Missing references directory"))
    if not (root / "scripts").is_dir():
        findings.append(build_finding("missing-scripts-dir", "scripts", "Missing scripts directory"))
    if not (root / "tests").is_dir():
        findings.append(build_finding("missing-tests-dir", "tests", "Missing tests directory"))
    return findings


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    json.dump(validate_skill(root), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
