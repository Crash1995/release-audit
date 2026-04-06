from __future__ import annotations

import json
import sys

AUTO_NO_GO_RULES = {
    "hardcoded-secret",
    "missing-gitignore",
    "private-key-material",
    "tracked-env-risk",
}
BLOCKING_CATEGORIES = {
    "Bugs and Logic Errors",
    "Data Leaks",
    "Performance and Memory",
    "Security",
}


def build_release_decision(findings: list[dict[str, object]]) -> dict[str, object]:
    """Строит финальный GO/NO-GO verdict по набору findings."""
    reasons: list[str] = []
    for finding in findings:
        rule = str(finding.get("rule", "unknown"))
        severity = str(finding.get("severity", ""))
        kind = str(finding.get("kind", "finding"))
        category = str(finding.get("category", ""))
        if (
            kind == "blocked"
            or severity == "P0"
            or rule in AUTO_NO_GO_RULES
            or (severity == "P1" and category in BLOCKING_CATEGORIES)
        ):
            reasons.append(rule)
    verdict = "NO-GO" if reasons else "GO"
    return {"verdict": verdict, "reasons": reasons}


def main() -> None:
    """CLI entrypoint для расчёта release verdict из stdin."""
    findings = json.load(sys.stdin)
    json.dump(build_release_decision(findings), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
