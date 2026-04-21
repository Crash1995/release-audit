# Report Template

Этот шаблон определяет структуру финального отчёта, который координатор выводит пользователю и сохраняет в `docs/release-audits/`.

---

## Формат вывода в консоль

Отчёт выводится как Markdown. Каждая секция визуально отделена. Используй эмодзи-маркеры для быстрого сканирования глазами.

---

### 1. Verdict (первая строка)

```
# Release Audit — <REPO_NAME>

**Verdict: GO** | Дата: 2026-04-09 | Файлов: 87 проверено / 12 skipped / 0 blocked
```

или

```
# Release Audit — <REPO_NAME>

**Verdict: NO-GO** — 2 critical findings | Дата: 2026-04-09
```

Verdict всегда первый. Одна строка. Причина NO-GO — тут же.

---

### 2. Summary (3-5 строк)

Кратко: что за проект, сколько findings по severity, главный риск или его отсутствие.

```
## Summary

Python trading bot, 87 source files. 0 critical, 3 high, 8 medium, 12 low findings.
Все P1 — code quality (float вместо Decimal, broad except). Блокеров безопасности нет.
```

---

### 3. Findings по severity

Группировка: сначала severity, внутри — по категории. Каждый finding — компактная карточка.

```
## P1 — High

### Bugs and Logic Errors

**[P1-1] float для денежных значений**
`core/engine/delta_neutral.py:847`
> `realized_pnl: Dict[str, Optional[float]]` — PnL хранится как float, теряет точность
- Fix: заменить на `Decimal`

**[P1-2] Rollback молча падает**
`core/engine/execution.py:608`
> После неудачного rollback лог пишется, но исключение не пробрасывается — вызывающий код думает, что всё ок
- Fix: добавить `raise` после `logger.error`

### Security

No issues found.

### Performance and Memory

No issues found.

---

## P2 — Medium

### Code Quality

**[P2-1] Функция > 50 строк**
`core/engine/delta_neutral.py:open_delta_neutral` (72 строки)
- Fix: вынести валидацию и sizing в отдельные методы

### Technical Debt

**[P2-2] Broad except без reraise**
`core/backpack/client.py:312`
> `except Exception: pass` — ошибка API молча проглатывается
- Fix: логировать и пробросить или сузить тип исключения
```

Правила:
- Нумерация findings сквозная: `[P1-1]`, `[P1-2]`, `[P2-1]` и т.д.
- Если в категории нет находок — одна строка `No issues found.`
- Evidence — короткая цитата кода (1-3 строки), не стена текста
- Fix — одно предложение, без развёрнутого кода
- В основной отчёт попадают только findings с `confidence: high` и `confidence: medium`

---

### 3.5. Needs Review (low confidence)

Findings с `confidence: low` выносятся в отдельную секцию. Они не засоряют основной отчёт, но не теряются.

```
## Needs Review

Находки с низкой уверенностью — требуют ручной проверки.

- [?-1] Возможно отсутствует rate limiting — `src/collectors/clob.py:45`
  > Цикл с API-вызовами, но semaphore мог быть определён в вызывающем коде
- [?-2] Кэш без TTL — `src/storage/csv_storage.py:12`
  > Используется dict для кэширования, но может обновляться при каждом запуске
```

Нумерация: `[?-1]`, `[?-2]` — отдельная от основных findings.

---

### 4. Progress (если есть прошлый аудит)

```
## С прошлого аудита

**Исправлено (5):**
- [P1-3] float PnL в settlement — fixed in `core/backpack/client.py`
- [P1-5] bare Exception в Extended — fixed
- ...

**Осталось (2):**
- [P2-1] Функция > 50 строк — без изменений
- [P2-4] Magic number в retry — без изменений

**Новое (1):**
- [P2-7] Unpinned dependency `aiohttp`
```

---

### 5. Remaining Work

```
## До релиза

**Обязательно:**
- [ ] Исправить P1-1, P1-2 (logic errors)

**Желательно (можно после релиза):**
- [ ] P2-1 рефакторинг длинных функций
- [ ] P3 cleanup: удалить `scripts/old_debug.py`
```

Чеклист-формат — пользователь может копировать в issue tracker.

---

### 6. Cleanup

```
## Cleanup-кандидаты

Не блокируют релиз, но стоит убрать:
- `docs/old-spec.md` — устаревшая спецификация (последнее изменение 8 мес назад)
- `scripts/debug_extended.py` — debug-скрипт, не используется в prod
- `data/fees_backup.yaml` — backup, дубликат `data/fees.yaml`
```

---

### 7. Coverage

```
## Coverage

| Метрика | Значение |
|---------|----------|
| Всего файлов | 99 |
| Проверено | 87 |
| Skipped | 12 (venv, __pycache__, .git) |
| Blocked | 0 |
| Сабагенты | 3/3 завершены |
```

---

### 7.5. Post-audit fixes (если применялась Фаза 3)

Если координатор запускал fix-агентов, добавь секцию сразу после Coverage:

```
## Post-audit fixes

**Исправлено fix-агентами:**

| ID | Файл | Что сделано | Агент |
|----|------|-------------|-------|
| P1-1 | cli.py:112 | Bare except → except Exception as e + logging | fixer-surgical |
| P2-1 | src/utils/logger.py | Миграция на loguru | fixer-migration |
| P1-5 | src/analysis/hedge.py | float → Decimal в HedgeCalculator | fixer-refactor |

**Пропущено (требует ручной работы):**
- P2-13: cli.py — декомпозиция analyze_underdog() — слишком связан с CLI framework
- P2-10: src/collectors/clob.py — sync→async миграция ломает вызывающий код

**Compile check:** pass (все изменённые файлы скомпилировались)
```

Правила:
- Каждый finding из Фазы 3 должен быть либо в "Исправлено", либо в "Пропущено"
- Указывай какой агент сделал правку
- Если compile_check failed — покажи какие файлы и ошибки

---

### 7.6. Verification (если применялась Фаза 4)

Результаты verifier-агента после fix-агентов:

```
## Verification

**Verdict: PASS** | 25 checks | 22 passed | 0 failed | 2 env_skipped

### Compile & Import
| Файл | Статус |
|------|--------|
| src/analysis/hedge.py | pass |
| scripts/backtest/simulator.py | pass |
| src/utils/helpers.py | env_skip (no yaml) |

### API Compatibility
- `HedgeCalculator` → `HedgeStrategyAnalyzer`: переименован, старое имя нигде не импортируется ✓
- `simulate_trade()`: сигнатура не изменена ✓
- `get_returns()`: возвращает `List[Decimal]` вместо `List[float]` — вызывающий код совместим ✓

### Smoke Tests
| Тест | Модуль | Результат |
|------|--------|-----------|
| hedge_simulate_basic | src.analysis.hedge | pass — ROI=0.0%, tp_hit=True |
| simulator_trade_basic | scripts.backtest.simulator | pass — ROI_net=38.86% |
| constants_import | src.constants | pass — 7 SA keywords |
| filter_winner | src.utils.filters | pass — 4/4 cases |

### Regression Check
| Тест | Baseline | Actual | Δ | Статус |
|------|----------|--------|---|--------|
| hedge_roi | 0.0 | 0.0 | 0.0 | pass |
| simulator_pnl | 9.71 | 9.71 | 0.0 | pass |

### Integration
| Пара | Статус |
|------|--------|
| constants → cli.py | pass |
| filters → lol_backfill.py | pass |
| simulator → analyzer.py | pass |
```

Правила:
- verdict верификации всегда явно: PASS / PASS_WITH_WARNINGS / FAIL
- Если FAIL — перечисли конкретные ошибки и какие findings затронуты
- env_skip не считается ошибкой — это ограничение окружения
- Regression check показывает delta от baseline — ненулевая delta > 0.01 = регрессия

---

### 8. Blocked & Assumptions

```
## Blocked

- Проверка runtime-зависимостей от внешних API — нет доступа к prod окружению
- `pip audit` не запускался — нет сети / не установлен

## Допущения

- `.env` не tracked (проверено через `.gitignore`)
- Логирование секретов проверено regex + ручным чтением, но 100% гарантии нет
```

---

## Формат сохранённого .md файла

Файл в `docs/release-audits/YYYY-MM-DD-HHMMSS-release-audit.md` содержит тот же отчёт + metadata header:

```markdown
---
date: 2026-04-09T10:07:16Z
verdict: GO
total_files: 99
reviewed: 87
skipped: 12
blocked: 0
p0: 0
p1: 3
p2: 8
p3: 12
---

# Release Audit — repo-name
...
```
