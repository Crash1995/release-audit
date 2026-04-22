# release-audit

Skill для полного предрелизного аудита репозитория с параллельными сабагентами.

Не diff-review и не grep-скан. Полный проход по репозиторию: инвентаризация файлов, batch pre-scan сканерами, ручное чтение кода **тремя параллельными сабагентами**, сбор findings, сравнение с прошлым аудитом, финальный `GO / NO-GO` verdict. Опционально — фазы автоматических фиксов, верификации и cleanup артефактов.

## Архитектура

```
                    ┌──────────────┐
                    │ Координатор  │
                    │   Фаза 0     │
                    │  inventory   │
                    │ + history    │
                    │ + run_prescan│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────┴──────┐ ┌──┴────────┐ ┌─┴──────────┐
       │   source    │ │ security  │ │ dependency │
       │  auditor    │ │ auditor   │ │  auditor   │
       └──────┬──────┘ └────┬──────┘ └─────┬──────┘
              │             │              │
              └─────────────┼──────────────┘
                            │
                    ┌───────┴──────┐
                    │ Координатор  │
                    │   Фаза 2     │
                    │  синтез +    │
                    │   verdict    │
                    └───────┬──────┘
                            │
              ┌─────────────┼─────────────┐
              │ (по запросу пользователя) │
       ┌──────┴──────┐ ┌────┴─────┐ ┌─────┴──────┐
       │   Фаза 3    │ │  Фаза 4  │ │   Фаза 5   │
       │   fixers    │→│ verifier │→│  cleanup   │
       │ (3 группы)  │ │          │ │ артефактов │
       └─────────────┘ └──────────┘ └────────────┘
```

**Фаза 0** — координатор строит инвентарь, читает прошлый аудит и project rules, одним вызовом `run_prescan.py` запускает все статические сканеры и группирует результаты по сабагентам.
**Фаза 1** — 3 сабагента запускаются параллельно (`source`, `security`, `dependency`), каждый получает свой срез файлов и pre-scan результаты, возвращает findings JSON-блоком.
**Фаза 2** — координатор собирает findings, делит по confidence (high/medium → основной отчёт, low → «Needs Review»), дедуплицирует, применяет config overrides, сравнивает с прошлым аудитом, выносит verdict, сохраняет Markdown-отчёт.
**Фаза 3** *(опционально)* — если пользователь просит исправления, координатор делит findings на 3 группы (`surgical`, `migration`, `refactor`) и запускает до 3 fixer-агентов параллельно.
**Фаза 4** *(опционально)* — verifier проверяет изменённые файлы по 5 блокам: compile, API compatibility, smoke tests, regression, cross-module integration.
**Фаза 5** — координатор чистит `docs/release-audits/` от устаревших отчётов и временных файлов, оставляя только актуальное.

## Сабагенты

### Фаза 1 — параллельный аудит

| Агент | Зона ответственности | Pre-scan группа |
|-------|---------------------|-----------------|
| **source-auditor** | Баги, edge cases, логика, tech debt, производительность, качество кода | `source` (`run_fast_scans`, `python_policy_checks`, `tech_debt_audit`, `performance_audit`) |
| **security-auditor** | Уязвимости, секреты, data leaks, Web3-специфика, release-гигиена | `security` (`security_audit`, `web3_security_audit`, `check_release_artifacts`) |
| **dependency-auditor** | Зависимости, конфиги, stale-файлы, cleanup-кандидаты | `dependency` (`dependency_audit`, `stale_files_audit`) |

Агенты НЕ запускают Python-скрипты — все сканеры уже отработали в фазе 0, результаты приходят в промпте как `PRE_SCAN_RESULTS`.

### Опциональные агенты

| Агент | Когда вызывается | Шаблон |
|-------|------------------|--------|
| **fixer** | Фаза 3, по запросу пользователя. Параметризуется `{{FIX_GROUP}}` — `surgical`, `migration` или `refactor` | `agents/fixer.md` |
| **verifier** | Фаза 4, после fixer'ов | `agents/verifier.md` |

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

Координатор прочитает `SKILL.md`, построит инвентарь, запустит pre-scan, вызовет 3 сабагента параллельно и выдаст человекочитаемый Markdown-отчёт с verdict.

Если после отчёта сказать «исправь всё» — координатор перейдёт к Фазе 3 (fixers) и Фазе 4 (verifier).

## Конфигурация

Создай `.release-audit.toml` в корне проекта:

```toml
[suppressions]
"python-magic-number" = ["scripts/constants.py"]
"python-long-function" = ["legacy/old_module.py"]

[severity_overrides]
"python-missing-type-hints" = "P3"
```

Формат полностью описан в `references/config-format.md`.

## Подавление в коде

```python
key = "0xdeadbeef..."  # noqa: release-audit
```

## NO-GO Policy

Автоматический `NO-GO` при любом из условий:
- finding с `severity = P0`;
- blocked проверка по критичному пути;
- `hardcoded-secret`, `private-key-material` или `tracked-env-risk`;
- отсутствует `.gitignore` или не закрыт риск утечки env/logs.

Cleanup-находки сами по себе релиз не блокируют — выносятся в отдельный блок отчёта.

## Структура

```
release-audit/
├── SKILL.md                          # инструкция для координатора
├── README.md                         # этот файл
├── agents/
│   ├── source-auditor.md             # промпт source сабагента
│   ├── security-auditor.md           # промпт security сабагента
│   ├── dependency-auditor.md         # промпт dependency сабагента
│   ├── fixer.md                      # шаблон для Фазы 3 (3 группы)
│   └── verifier.md                   # промпт verifier'а (Фаза 4)
├── scripts/
│   ├── shared.py                     # общие утилиты
│   ├── finding_utils.py              # нормализация findings
│   ├── inventory_repo.py             # инвентарь файлов
│   ├── run_prescan.py                # оркестратор pre-scan сканеров
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
│   ├── validate_skill.py             # self-validation
│   └── run_release_audit.py          # legacy последовательный workflow (не использовать)
└── references/
    ├── severity-rubric.md
    ├── false-positive-rules.md
    ├── web3-trading-rules.md
    ├── report-template.md
    ├── project-rules.md
    └── config-format.md
```

---

# English

`release-audit` is a skill for full pre-release repository audits using parallel subagents.

Not a diff review or quick grep scan. A full repository pass: file inventory, batch pre-scan of all static scanners, manual code review by **three parallel subagents**, finding aggregation, comparison with the previous audit, and a final `GO / NO-GO` verdict. Optional phases add automated fixes, verification, and artifact cleanup.

## Architecture

- **Phase 0 (coordinator)** — builds the inventory, reads history and project rules, runs `run_prescan.py` once and groups results per subagent.
- **Phase 1** — three subagents run in parallel: `source-auditor`, `security-auditor`, `dependency-auditor`. Each receives its file slice and pre-scan results, returns findings as JSON.
- **Phase 2 (coordinator)** — collects findings, splits by confidence (high/medium → main report, low → "Needs Review"), deduplicates, applies config overrides, diffs against the previous audit, renders the verdict, saves the Markdown report.
- **Phase 3 (optional)** — on user request, findings are split into `surgical` / `migration` / `refactor` groups, up to three fixer agents run in parallel.
- **Phase 4 (optional)** — verifier checks modified files across five blocks: compile, API compatibility, smoke tests, regression, cross-module integration.
- **Phase 5** — coordinator cleans up `docs/release-audits/`, keeping only the current report (and at most one prior report if open findings still reference it).

## Subagents

| Agent | Focus | Pre-scan group |
|-------|-------|----------------|
| `source-auditor` | Bugs, logic, edge cases, tech debt, performance, code quality | `source` |
| `security-auditor` | Vulnerabilities, secrets, data leaks, Web3 specifics, release hygiene | `security` |
| `dependency-auditor` | Dependencies, configs, stale files, cleanup candidates | `dependency` |

Optional: `fixer` (Phase 3, parameterised by group) and `verifier` (Phase 4).

## Installation

```bash
git clone https://github.com/Crash1995/release-audit.git ~/.claude/skills/release-audit
```

No dependencies — Python 3.11+ standard library only.

## Usage

```text
Run a full release audit for this repository.
```

The coordinator reads `SKILL.md`, builds the inventory, runs pre-scan, dispatches three subagents in parallel, and produces a human-readable Markdown report with a verdict. Ask it to "fix everything" afterwards to trigger Phases 3–4.
