# release-audit

Skill для полного предрелизного аудита репозитория.

Не diff-review и не grep-скан. Полный проход по репозиторию перед публикацией: инвентаризация файлов, детерминированные проверки, сбор findings, сравнение с прошлым аудитом, финальный `GO / NO-GO` verdict.

## Совместимость

| Платформа | Установка | Вызов |
|-----------|-----------|-------|
| **Claude Code** | `~/.claude/skills/release-audit/` | `/release-audit` или `$release-audit` |
| **Codex CLI** | `~/.codex/skills/release-audit/` | `$release-audit` |
| **Cursor** | `~/.cursor/skills/release-audit/` | по инструкции IDE |
| **Antigravity** | `~/.antigravity/skills/release-audit/` | `$release-audit` |
| **Standalone** | любая директория | `python3 scripts/run_release_audit.py /path/to/repo` |

## Установка

### Вариант 1 — git clone в директорию skills

```bash
# Claude Code
git clone https://github.com/Crash1995/release-audit.git ~/.claude/skills/release-audit

# Codex CLI
git clone https://github.com/Crash1995/release-audit.git ~/.codex/skills/release-audit

# Cursor
git clone https://github.com/Crash1995/release-audit.git ~/.cursor/skills/release-audit
```

### Вариант 2 — standalone

```bash
git clone https://github.com/Crash1995/release-audit.git
cd release-audit
python3 scripts/run_release_audit.py /path/to/repo
```

Зависимостей нет — только Python 3.11+ стандартная библиотека.

## Использование

### Через агента

```text
Проведи полный release-аудит этого репозитория.
```

или

```text
Use $release-audit and run a full release audit for this repository.
```

Агент прочитает `SKILL.md`, запустит pipeline и выдаст структурированный отчёт с verdict.

### Через CLI

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

На выходе — JSON-отчёт в stdout и Markdown в `docs/release-audits/`. Exit code `1` при `NO-GO` — удобно для CI.

## Что проверяется

| Сканер | Что ищет |
|--------|----------|
| `run_fast_scans.py` | task markers, placeholders, debug calls, secrets, `eval/exec`, shell execution, disabled TLS, plain HTTP |
| `security_audit.py` | DOM injection, token storage, sensitive log fields, interpolated subprocess/path |
| `web3_security_audit.py` | hardcoded mnemonics, private keys, `from_key()` с inline ключом, адреса без EIP-55 checksum |
| `performance_audit.py` | expensive calls в циклах, `open()` без context manager, `aiohttp.ClientSession` без lifecycle, listener leaks |
| `dependency_audit.py` | unpinned deps, floating versions, missing manifest |
| `python_policy_checks.py` | bare except, empty handlers, stdout debug, `requests` без timeout, `float` для денег |
| `tech_debt_audit.py` | длинные функции, вложенность, missing type hints, mutable defaults, weak names, magic numbers, blocking calls в async |
| `check_release_artifacts.py` | `.gitignore` hygiene, `.env` risks, tracked logs/caches |
| `stale_files_audit.py` | legacy configs, stale docs/tests, backup files |
| `validate_skill.py` | self-validation skill-репозитория (только если есть `SKILL.md`) |

## Pipeline

```text
history → inventory → scanners → config → compare → decision → report
```

1. Читает прошлый аудит из `docs/release-audits/`
2. Строит инвентарь файлов репозитория
3. Запускает все сканеры
4. Применяет `.release-audit.toml` (suppressions, severity overrides)
5. Сравнивает findings с прошлым аудитом: new / carried over / resolved
6. Строит `GO / NO-GO` verdict
7. Сохраняет Markdown-отчёт с embedded metadata

## Конфигурация

Создай `.release-audit.toml` в корне проекта:

```toml
[suppressions]
# Подавить конкретные правила для конкретных путей
"python-magic-number" = ["scripts/constants.py"]
"python-long-function" = ["legacy/old_module.py"]

[severity_overrides]
# Переопределить severity
"python-missing-type-hints" = "P3"
```

Подробнее: [`references/config-format.md`](references/config-format.md)

## Подавление в коде

Добавь маркер в конец строки:

```python
key = "0xdeadbeef..."  # noqa: release-audit
```

Строка с маркером будет пропущена всеми сканерами.

## NO-GO Policy

Автоматический `NO-GO` при любом из условий:
- finding с `severity = P0`
- blocked проверка по критичному пути
- `hardcoded-secret`, `private-key-material` или `tracked-env-risk`
- отсутствует `.gitignore` или не закрыт риск утечки

## Формат отчёта

```text
docs/release-audits/YYYY-MM-DD-HHMM-release-audit.md
```

Отчёт содержит:
- `GO / NO-GO` verdict
- findings по severity и категориям
- progress: new / carried over / resolved
- coverage summary
- blocked checks
- embedded metadata для автоматического сравнения

## Структура проекта

```
release-audit/
├── SKILL.md                          # инструкция для агента
├── README.md                         # этот файл
├── .gitignore
├── agents/
│   └── openai.yaml                   # метаданные skill-а
├── scripts/
│   ├── run_release_audit.py          # главный entrypoint
│   ├── shared.py                     # общие утилиты всех сканеров
│   ├── finding_utils.py              # builder для findings
│   ├── inventory_repo.py             # инвентарь файлов
│   ├── run_fast_scans.py             # regex/keyword сканер
│   ├── security_audit.py             # security + data leaks
│   ├── web3_security_audit.py        # Web3-специфичные checks
│   ├── performance_audit.py          # performance + resources
│   ├── dependency_audit.py           # dependency risks
│   ├── python_policy_checks.py       # Python policy checks
│   ├── tech_debt_audit.py            # tech debt checks
│   ├── check_release_artifacts.py    # release hygiene
│   ├── stale_files_audit.py          # cleanup candidates
│   ├── load_audit_config.py          # .release-audit.toml loader
│   ├── read_audit_history.py         # чтение прошлых аудитов
│   ├── compare_audits.py             # diff findings
│   ├── release_decision.py           # GO / NO-GO logic
│   ├── write_audit_report.py         # Markdown report builder
│   └── validate_skill.py             # self-validation
└── references/
    ├── severity-rubric.md            # шкала severity
    ├── false-positive-rules.md       # правила против FP
    ├── report-template.md            # каркас отчёта
    ├── project-rules.md              # project-specific policy
    └── config-format.md              # формат .release-audit.toml
```

---

# English

`release-audit` is a skill for full pre-release repository audits.

Not a diff review or a quick grep scan. A full repository pass before publishing: file inventory, deterministic checks, finding aggregation, comparison with the previous audit, and a final `GO / NO-GO` verdict.

## Compatibility

| Platform | Install path | Invocation |
|----------|-------------|------------|
| **Claude Code** | `~/.claude/skills/release-audit/` | `/release-audit` or `$release-audit` |
| **Codex CLI** | `~/.codex/skills/release-audit/` | `$release-audit` |
| **Cursor** | `~/.cursor/skills/release-audit/` | per IDE instructions |
| **Antigravity** | `~/.antigravity/skills/release-audit/` | `$release-audit` |
| **Standalone** | any directory | `python3 scripts/run_release_audit.py /path/to/repo` |

## Installation

### Option 1 — clone into skills directory

```bash
# Claude Code
git clone https://github.com/Crash1995/release-audit.git ~/.claude/skills/release-audit

# Codex CLI
git clone https://github.com/Crash1995/release-audit.git ~/.codex/skills/release-audit

# Cursor
git clone https://github.com/Crash1995/release-audit.git ~/.cursor/skills/release-audit
```

### Option 2 — standalone

```bash
git clone https://github.com/Crash1995/release-audit.git
cd release-audit
python3 scripts/run_release_audit.py /path/to/repo
```

No dependencies — Python 3.11+ standard library only.

## Usage

### Via agent

```text
Run a full release audit for this repository.
```

The agent reads `SKILL.md`, runs the pipeline, and produces a structured report with a verdict.

### Via CLI

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

Outputs JSON to stdout, saves Markdown to `docs/release-audits/`. Exit code `1` on `NO-GO` for CI integration.

## What it checks

| Scanner | Focus |
|---------|-------|
| `run_fast_scans.py` | task markers, placeholders, debug calls, secrets, `eval/exec`, shell execution, disabled TLS, plain HTTP |
| `security_audit.py` | DOM injection, token storage, sensitive log fields, interpolated subprocess/path |
| `web3_security_audit.py` | hardcoded mnemonics, private keys, inline `from_key()`, addresses without EIP-55 checksum |
| `performance_audit.py` | expensive calls in loops, `open()` without context manager, `aiohttp.ClientSession` lifecycle, listener leaks |
| `dependency_audit.py` | unpinned deps, floating versions, missing manifest |
| `python_policy_checks.py` | bare except, empty handlers, stdout debug, `requests` without timeout, `float` for money |
| `tech_debt_audit.py` | long functions, nesting, missing type hints, mutable defaults, weak names, magic numbers, blocking calls in async |
| `check_release_artifacts.py` | `.gitignore` hygiene, `.env` risks, tracked logs/caches |
| `stale_files_audit.py` | legacy configs, stale docs/tests, backup files |
| `validate_skill.py` | skill self-validation (only when `SKILL.md` exists) |

## Configuration

Create `.release-audit.toml` in the project root:

```toml
[suppressions]
"python-magic-number" = ["scripts/constants.py"]

[severity_overrides]
"python-missing-type-hints" = "P3"
```

Details: [`references/config-format.md`](references/config-format.md)

## Inline suppression

```python
key = "0xdeadbeef..."  # noqa: release-audit
```

Lines with this marker are skipped by all scanners.

## NO-GO Policy

Automatic `NO-GO` on any of:
- any `P0` finding
- blocked check on a critical path
- `hardcoded-secret`, `private-key-material`, or `tracked-env-risk`
- missing `.gitignore` or uncovered env leak risk
