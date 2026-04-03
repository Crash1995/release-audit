from __future__ import annotations

import json
import sys

AUTO_NO_GO_RULES = {
    "hardcoded-secret",
    "missing-gitignore",
    "private-key-material",
    "tracked-env-risk",
}


def build_release_decision(findings: list[dict[str, object]]) -> dict[str, object]:
    reasons: list[str] = []
    for finding in findings:
        rule = str(finding.get("rule", "unknown"))
        severity = str(finding.get("severity", ""))
        kind = str(finding.get("kind", "finding"))
        if kind == "blocked" or severity == "P0" or rule in AUTO_NO_GO_RULES:
            reasons.append(rule)
    verdict = "NO-GO" if reasons else "GO"
    return {"verdict": verdict, "reasons": reasons}


def main() -> None:
    findings = json.load(sys.stdin)
    json.dump(build_release_decision(findings), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
