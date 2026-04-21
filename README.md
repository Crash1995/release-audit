# release-audit

Skill для полного предрелизного аудита репозитория с параллельными сабагентами.

Не diff-review и не grep-скан. Полный проход по репозиторию: инвентаризация файлов, автоматические сканеры, ручное чтение кода **пятью параллельными агентами**, сбор findings, сравнение с прошлым аудитом, финальный `GO / NO-GO` verdict.

## Архитектура

```
                    ┌─────────────┐
                    │ Координатор │
                    │  (фаза 0)   │
                    │  inventory   │
                    │  + history   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
    │  security   │ │ code-quality│ │ performance │
    │  auditor    │ │   auditor   │ │   auditor   │
    └─────────────┘ └─────────────┘ └─────────────┘
           │               │               │
    ┌──────┴──────┐ ┌──────┴──────┐        │
    │ dependency  │ │   source    │        │
    │   auditor   │ │  reviewer   │        │
    └─────────────┘ └─────────────┘        │
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────┴──────┐
                    │ Координатор │
                    │  (фаза 2)   │
                    │  синтез +   │
                    │   verdict   │
                    └─────────────┘
```

**Фаза 0** — координатор строит инвентарь, читает прошлый аудит и project rules.
**Фаза 1** — 5 сабагентов запускаются параллельно, каждый со своими скриптами и зоной ответственности.
**Фаза 2** — координатор собирает findings, дедуплицирует, применяет config, выносит verdict, сохраняет отчёт.

## Сабагенты

| Агент | Зона ответственности | Скрипты |
|-------|---------------------|---------|
| **security-auditor** | Уязвимости, секреты, data leaks, .env гигиена | `security_audit.py`, `web3_security_audit.py`, `check_release_artifacts.py` |
| **code-quality-auditor** | Tech debt, task markers, мёртвый код, качество | `run_fast_scans.py`, `python_policy_checks.py`, `tech_debt_audit.py` |
| **performance-auditor** | Blocking calls, ресурсы, memory, таймауты | `performance_audit.py` |
| **dependency-auditor** | Зависимости, конфиги, cleanup-кандидаты | `dependency_audit.py`, `stale_files_audit.py` |
| **source-reviewer** | Построчный ревью: баги, edge cases, логика | (ручное чтение всех source файлов) |

## Совместимость

| Платформа | Установка | Вызов |
|-----------|-----------|-------|
| **Claude Code** | `~/.claude/skills/release-audit/` | `/release-audit` |
| **Codex CLI** | `~/.codex/skills/release-audit/` | `$release-audit` |
| **Cursor** | `~/.cursor/skills/release-audit/` | по инструкции IDE |

## Установка

```bash
git clone https://github.com/Crash1995/release-audit.git ~/.claude/skills/release-audit
```

Зависимостей нет — только Python 3.11+ стандартная библиотека.

## Использование

```text
Проведи полный release-аудит этого репозитория.
```

Агент прочитает `SKILL.md`, запустит 5 сабагентов параллельно и выдаст человекочитаемый отчёт с verdict.

## Конфигурация

Создай `.release-audit.toml` в корне проекта:

```toml
[suppressions]
"python-magic-number" = ["scripts/constants.py"]
"python-long-function" = ["legacy/old_module.py"]

[severity_overrides]
"python-missing-type-hints" = "P3"
```

## Подавление в коде

```python
key = "0xdeadbeef..."  # noqa: release-audit
```

## NO-GO Policy

Автоматический `NO-GO` при любом из условий:
- finding с `severity = P0`
- blocked проверка по критичному пути
- `hardcoded-secret`, `private-key-material` или `tracked-env-risk`
- отсутствует `.gitignore` или не закрыт риск утечки

## Структура

```
release-audit/
├── SKILL.md                          # инструкция для координатора
├── README.md                         # этот файл
├── agents/
│   ├── security-auditor.md           # промпт security сабагента
│   ├── code-quality-auditor.md       # промпт code quality сабагента
│   ├── performance-auditor.md        # промпт performance сабагента
│   ├── dependency-auditor.md         # промпт dependency сабагента
│   └── source-reviewer.md            # промпт source reviewer сабагента
├── scripts/
│   ├── shared.py                     # общие утилиты
│   ├── inventory_repo.py             # инвентарь файлов
│   ├── run_fast_scans.py             # regex/keyword сканер
│   ├── security_audit.py             # security checks
│   ├── web3_security_audit.py        # Web3 checks
│   ├── performance_audit.py          # performance checks
│   ├── dependency_audit.py           # dependency risks
│   ├── python_policy_checks.py       # Python AST checks
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
    ├── severity-rubric.md
    ├── false-positive-rules.md
    ├── report-template.md
    ├── project-rules.md
    └── config-format.md
```

---

# English

`release-audit` is a skill for full pre-release repository audits using 5 parallel subagents.

Not a diff review or quick grep scan. A full repository pass: file inventory, automated scanners, manual code review by **five parallel agents**, finding aggregation, comparison with the previous audit, and a final `GO / NO-GO` verdict.

## Architecture

Phase 0 (coordinator) builds inventory, reads history and project rules.
Phase 1 dispatches 5 subagents in parallel — each with its own scripts and review focus.
Phase 2 (coordinator) collects findings, deduplicates, applies config overrides, renders the verdict, saves the report.

## Installation

```bash
git clone https://github.com/Crash1995/release-audit.git ~/.claude/skills/release-audit
```

No dependencies — Python 3.11+ standard library only.

## Usage

```text
Run a full release audit for this repository.
```

The agent reads `SKILL.md`, launches 5 subagents in parallel, and produces a human-readable report with a verdict.
