"""Pre-scan оркестратор: запускает все автоматические сканеры и собирает результаты.

Координатор запускает этот скрипт в фазе 0, а результаты передаёт
сабагентам через плейсхолдер {{PRE_SCAN_RESULTS}}.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Маппинг: имя сканера → скрипт
# Группировка по сабагентам-потребителям
SCANNERS: dict[str, dict[str, list[str]]] = {
    "security": {
        "description": "Сканеры для security-auditor",
        "scripts": [
            "security_audit.py",
            "web3_security_audit.py",
            "check_release_artifacts.py",
        ],
    },
    "source": {
        "description": "Сканеры для source-auditor",
        "scripts": [
            "run_fast_scans.py",
            "python_policy_checks.py",
            "tech_debt_audit.py",
            "performance_audit.py",
        ],
    },
    "dependency": {
        "description": "Сканеры для dependency-auditor",
        "scripts": [
            "dependency_audit.py",
            "stale_files_audit.py",
        ],
    },
}


def run_scanner(script_path: Path, repo_root: str) -> dict[str, object]:
    """Запускает один сканер и возвращает его результат."""
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), repo_root],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return {
            "error": f"exit_code={result.returncode}",
            "stderr": result.stderr[:500] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout (120s)"}
    except json.JSONDecodeError:
        return {"error": "invalid JSON output", "raw": result.stdout[:500]}
    except Exception as exc:
        return {"error": str(exc)}


def run_all_prescans(repo_root: str) -> dict[str, object]:
    """Запускает все сканеры и группирует результаты по сабагентам."""
    scripts_dir = Path(__file__).parent
    results: dict[str, object] = {}

    for group_name, group_info in SCANNERS.items():
        group_results: dict[str, object] = {}
        for script_name in group_info["scripts"]:
            script_path = scripts_dir / script_name
            if script_path.exists():
                group_results[script_name] = run_scanner(script_path, repo_root)
            else:
                group_results[script_name] = {"error": f"script not found: {script_path}"}
        results[group_name] = group_results

    return results


def main() -> None:
    """CLI entrypoint: запускает все pre-scan сканеры."""
    repo_root = sys.argv[1] if len(sys.argv) > 1 else str(Path.cwd())
    results = run_all_prescans(repo_root)
    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
