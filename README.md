# release-audit

## Русский

`release-audit` — это skill для полного предрелизного аудита репозитория.

Это не diff-review и не быстрый grep-скан. Skill рассчитан на полный проход по репозиторию перед публикацией или релизом: с инвентаризацией файлов, запуском детерминированных проверок, сбором findings, сравнением с прошлым аудитом и финальным `GO / NO-GO`.

### Как это устроено

В репозитории есть три слоя:

- [`SKILL.md`](/Users/albertfedotov/.codex/skills/release-audit/SKILL.md)
  Основная инструкция для агента. Здесь описан workflow: что читать сначала, как покрывать файлы, как оформлять findings, когда ставить `GO / NO-GO`, что сохранять в отчёт.

- [`agents/openai.yaml`](/Users/albertfedotov/.codex/skills/release-audit/agents/openai.yaml)
  Метаданные skill-а: display name, short description и default prompt для вызова.

- [`scripts/`](/Users/albertfedotov/.codex/skills/release-audit/scripts)
  Исполняемый движок аудита. Эти скрипты реально строят findings, verdict и Markdown-отчёт.

### Как работает pipeline

Канонический entrypoint:

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

Что делает entrypoint:

1. Читает прошлую историю из `docs/release-audits/`, если она есть.
2. Строит инвентарь файлов репозитория.
3. Запускает все аудит-сканеры.
4. Применяет локальный `.release-audit.toml`, если он есть.
5. Сравнивает текущие findings с прошлым аудитом.
6. Строит `GO / NO-GO`.
7. Сохраняет Markdown-отчёт в `docs/release-audits/`.

### Что именно проверяется

- security-проблемы и hardcoded secrets;
- утечки данных и `.env`/gitignore риски;
- runtime и edge-case проблемы;
- memory/performance smells;
- Python policy violations;
- Python tech debt;
- cleanup-кандидаты в репозитории;
- comparison с предыдущим аудитом;
- финальный `GO / NO-GO`.

### Структура `scripts/`

- [`scripts/run_release_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/run_release_audit.py)
  Главный агрегатор. Запускает все остальные проверки, собирает единый отчёт и сохраняет Markdown.

- [`scripts/inventory_repo.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/inventory_repo.py)
  Строит инвентарь файлов и их категорий: `source`, `config`, `tests`, `docs`, `ci`, `infra`, `binary`, `other`.

- [`scripts/run_fast_scans.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/run_fast_scans.py)
  Быстрые regex/keyword проверки высокого риска: task markers, placeholder values, debug calls, secrets, `eval/exec`, shell execution, disabled TLS verification, plain HTTP URLs и похожие сигналы.

- [`scripts/security_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/security_audit.py)
  Дополнительные security/data-leak проверки: DOM injection patterns, token storage, sensitive log fields, interpolated subprocess/path usage.

- [`scripts/performance_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/performance_audit.py)
  Performance и resource checks: expensive calls inside loops, `open()` без context manager, `aiohttp.ClientSession` без явного lifecycle, listener cleanup smells.

- [`scripts/dependency_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/dependency_audit.py)
  Проверка dependency/configuration рисков: непинованные зависимости, direct references, floating versions, отсутствие manifest-а.

- [`scripts/python_policy_checks.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/python_policy_checks.py)
  Python policy checks: bare except, empty exception handlers, stdout debug calls, `requests` без timeout, `float` в money-like code.

- [`scripts/tech_debt_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/tech_debt_audit.py)
  Deterministic tech debt audit для Python: длинные функции, вложенность, missing type hints, mutable defaults, weak names, magic numbers, task markers в source и blocking calls in async.

- [`scripts/check_release_artifacts.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/check_release_artifacts.py)
  Проверка release hygiene: `.gitignore`, `.env`, `*.log`, `__pycache__` и риск утечки локальных артефактов.

- [`scripts/stale_files_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/stale_files_audit.py)
  Cleanup-аудит: legacy configs, stale docs, stale tests, backup files.

- [`scripts/read_audit_history.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/read_audit_history.py)
  Читает прошлые Markdown-отчёты из `docs/release-audits/`.

- [`scripts/compare_audits.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/compare_audits.py)
  Сравнивает прошлый и текущий набор findings: `new`, `carried_over`, `resolved`.

- [`scripts/release_decision.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/release_decision.py)
  Строит итоговый `GO / NO-GO` verdict по severity, blocked checks и критичным rules.

- [`scripts/write_audit_report.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/write_audit_report.py)
  Собирает Markdown-отчёт, встраивает compact metadata и сохраняет его в `docs/release-audits/`.

- [`scripts/validate_skill.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/validate_skill.py)
  Локальная self-validation самого skill-репозитория.

- [`scripts/finding_utils.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/finding_utils.py)
  Общий builder для findings и blocked-findings в едином формате.

### Формат результата

На выходе skill даёт:

- `GO` или `NO-GO`;
- findings по категориям и severity;
- comparison с прошлым аудитом;
- coverage summary;
- saved Markdown report в `docs/release-audits/`.

Отчёт сохраняется как:

```text
docs/release-audits/YYYY-MM-DD-HHMM-release-audit.md
```

### Что лежит в `references/`

- [`references/severity-rubric.md`](/Users/albertfedotov/.codex/skills/release-audit/references/severity-rubric.md)
  Шкала severity и правила приоритизации.

- [`references/false-positive-rules.md`](/Users/albertfedotov/.codex/skills/release-audit/references/false-positive-rules.md)
  Правила против ложных срабатываний.

- [`references/report-template.md`](/Users/albertfedotov/.codex/skills/release-audit/references/report-template.md)
  Каркас итогового отчёта.

- [`references/project-rules.md`](/Users/albertfedotov/.codex/skills/release-audit/references/project-rules.md)
  Project-specific policy ideas.

- [`references/config-format.md`](/Users/albertfedotov/.codex/skills/release-audit/references/config-format.md)
  Формат `.release-audit.toml`.

### Как использовать как skill

Если ваша среда поддерживает skills, агент должен читать [`SKILL.md`](/Users/albertfedotov/.codex/skills/release-audit/SKILL.md) и следовать описанному там workflow.

Пример запроса:

```text
Используй $release-audit и проведи полный release-аудит этого репозитория.
```

Если среда не умеет вызывать skill напрямую, можно запускать движок локально:

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

---

## English

`release-audit` is a skill for full pre-release repository audits.

This is not a diff review or a quick grep pass. It is designed for a full repository-wide audit before publishing or shipping: file inventory, deterministic checks, finding aggregation, comparison with the previous audit, and a final `GO / NO-GO` verdict.

### How it is structured

The repository has three layers:

- [`SKILL.md`](/Users/albertfedotov/.codex/skills/release-audit/SKILL.md)
  The main agent instruction file. It defines the workflow: what to inspect first, how to cover files, how to format findings, when to issue `GO / NO-GO`, and what to save.

- [`agents/openai.yaml`](/Users/albertfedotov/.codex/skills/release-audit/agents/openai.yaml)
  Skill metadata: display name, short description, and default prompt.

- [`scripts/`](/Users/albertfedotov/.codex/skills/release-audit/scripts)
  The executable audit engine. These scripts actually build findings, the verdict, and the Markdown report.

### Pipeline

Canonical entrypoint:

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

What the entrypoint does:

1. Reads previous audit history from `docs/release-audits/`, if present.
2. Builds a repository file inventory.
3. Runs all audit scanners.
4. Applies local `.release-audit.toml`, if present.
5. Compares current findings against the previous audit.
6. Builds the final `GO / NO-GO`.
7. Saves a Markdown report to `docs/release-audits/`.

### What it checks

- security issues and hardcoded secrets;
- data leaks and `.env` / gitignore hygiene;
- runtime and edge-case risks;
- memory/performance smells;
- Python policy violations;
- Python technical debt;
- repository cleanup candidates;
- comparison with the previous audit;
- final `GO / NO-GO`.

### `scripts/` layout

- [`scripts/run_release_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/run_release_audit.py)
  Main orchestrator. Runs all other checks, assembles the report, and saves Markdown.

- [`scripts/inventory_repo.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/inventory_repo.py)
  Builds the repository file inventory and categories.

- [`scripts/run_fast_scans.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/run_fast_scans.py)
  Fast regex/keyword checks for high-risk signals.

- [`scripts/security_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/security_audit.py)
  Additional security and data-leak checks.

- [`scripts/performance_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/performance_audit.py)
  Performance and resource-handling checks.

- [`scripts/dependency_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/dependency_audit.py)
  Dependency and configuration risk checks.

- [`scripts/python_policy_checks.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/python_policy_checks.py)
  Python runtime/safety policy checks.

- [`scripts/tech_debt_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/tech_debt_audit.py)
  Deterministic Python tech-debt checks.

- [`scripts/check_release_artifacts.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/check_release_artifacts.py)
  `.gitignore` and local artifact hygiene.

- [`scripts/stale_files_audit.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/stale_files_audit.py)
  Cleanup audit for stale docs, stale tests, legacy configs, and backup files.

- [`scripts/read_audit_history.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/read_audit_history.py)
  Reads previous saved audit reports.

- [`scripts/compare_audits.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/compare_audits.py)
  Compares current findings with the previous audit.

- [`scripts/release_decision.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/release_decision.py)
  Builds the final `GO / NO-GO` verdict.

- [`scripts/write_audit_report.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/write_audit_report.py)
  Builds and saves the Markdown report with embedded compact metadata.

- [`scripts/validate_skill.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/validate_skill.py)
  Local self-validation for the skill repository itself.

- [`scripts/finding_utils.py`](/Users/albertfedotov/.codex/skills/release-audit/scripts/finding_utils.py)
  Shared helpers for normalized findings and blocked findings.

### Output

The skill produces:

- `GO` or `NO-GO`;
- findings grouped by category and severity;
- comparison with the previous audit;
- coverage summary;
- a saved Markdown report in `docs/release-audits/`.

Saved report path:

```text
docs/release-audits/YYYY-MM-DD-HHMM-release-audit.md
```

### `references/`

- [`references/severity-rubric.md`](/Users/albertfedotov/.codex/skills/release-audit/references/severity-rubric.md)
- [`references/false-positive-rules.md`](/Users/albertfedotov/.codex/skills/release-audit/references/false-positive-rules.md)
- [`references/report-template.md`](/Users/albertfedotov/.codex/skills/release-audit/references/report-template.md)
- [`references/project-rules.md`](/Users/albertfedotov/.codex/skills/release-audit/references/project-rules.md)
- [`references/config-format.md`](/Users/albertfedotov/.codex/skills/release-audit/references/config-format.md)

### Using it as a skill

If your environment supports skills, the agent should read [`SKILL.md`](/Users/albertfedotov/.codex/skills/release-audit/SKILL.md) and follow that workflow.

Example prompt:

```text
Use $release-audit and run a full release audit for this repository.
```

If your environment does not support direct skill invocation, run the engine locally:

```bash
python3 scripts/run_release_audit.py /path/to/repo
```
