---
name: release-audit
description: Use when the user asks for a full pre-release audit of an entire codebase, requiring a complete repository inventory, file-by-file review, security checks, code-quality review, and a release GO/NO-GO verdict
---

# Release Audit

## Назначение

Используй этот skill только для полного `pre-release` аудита репозитория.
Это не `quick scan` и не `diff review`.

Цель:
- построить инвентарь всего репозитория;
- проверить все человеко-редактируемые файлы;
- явно перечислить `skipped` файлы и причины;
- выдать findings с доказательствами;
- закончить вердиктом `GO` или `NO-GO`.

## Обязательный порядок работы

1. Сначала проверь `docs/release-audits/` и прочитай последний сохранённый аудит, если он есть.
2. Построй инвентарь репозитория до чтения файлов.
3. Раздели файлы на `source`, `config`, `tests`, `docs`, `ci`, `infra`, `generated`, `vendor`, `binary`.
4. Проверь все человеко-редактируемые файлы без исключений.
5. Для `generated`, `vendor`, `binary`, `.venv`, `node_modules`, `dist`, `build`, minified-файлов не делай построчное ревью; занеси их в `skipped` с причиной.
6. Перед выводом findings перепроверь контекст, чтобы не репортить ложные срабатывания.
7. После аудита обязательно сохрани Markdown-отчёт в `docs/release-audits/`.

## Инструменты

- Канонический entrypoint: `scripts/run_release_audit.py`. Используй его по умолчанию, когда нужен единый машинно-читаемый отчёт.
- Вспомогательные скрипты:
- `scripts/inventory_repo.py` для полного списка файлов;
- `scripts/read_audit_history.py` для чтения прошлых аудитов;
- `scripts/run_fast_scans.py` для regex/keyword сигналов высокого риска;
- `scripts/python_policy_checks.py` для AST-проверок Python-кода;
- `scripts/tech_debt_audit.py` для детерминированной проверки Python tech debt;
- `scripts/check_release_artifacts.py` для gitignore/.env hygiene и риска утечки env;
- `scripts/stale_files_audit.py` для старой документации, legacy-конфигов и cleanup-кандидатов;
- `scripts/compare_audits.py` для сравнения текущего аудита с прошлым;
- `scripts/write_audit_report.py` для сохранения Markdown-отчёта и встроенных metadata для истории;
- `scripts/validate_skill.py` для локальной self-validation skill-а.
- После автоматических прогонов дочитывай файлы вручную по категориям и подтверждай или отклоняй находки.

## Источники правил

- Шкала приоритетов: `references/severity-rubric.md`
- Правила против ложных срабатываний: `references/false-positive-rules.md`
- Каркас итогового отчёта: `references/report-template.md`
- Project-specific правила: `references/project-rules.md`
- Формат локального конфига: `references/config-format.md`

## Project-specific режим

- Если в репозитории есть `AGENTS.md`, прочитай его в начале аудита и зафиксируй локальные правила.
- Если проект Python/Web3-ориентированный, дополнительно ищи нарушения правил по `Decimal`, `loguru`, `tenacity`, `.env`, таймаутам HTTP и логированию секретов.
- Если в корне есть `.release-audit.toml`, загрузи его и примени `severity_overrides` и `suppressions` до финального verdict.
- Если локальные правила не найдены, оставайся на общих release-критериях и явно скажи об этом в допущениях.

## Области проверки

Проверь и зафиксируй findings по этим блокам:
- заглушки, `TODO`, временный код, захардкоженные ответы, закомментированный мёртвый код;
- безопасность: секреты, небезопасный shell, небезопасная десериализация, `eval`/`exec`, опасные конфиги;
- полнота реализации, если найден источник требований в `README`, `docs/`, `spec`, `issues`, `PRD`;
- обработка ошибок и `edge cases`;
- качество кода: длина функций, вложенность, дублирование, типизация, naming;
- технический долг: пустые функции, TODO/FIXME/HACK в source-коде, слабые имена, mutable defaults, blocking calls в async-коде;
- зависимости, конфигурация окружения и риски утечки через git;
- готовность к продакшену: debug-флаги, логирование, graceful shutdown, таймауты, лимиты.
- cleanup репозитория: устаревшие docs, legacy-конфиги, backup-файлы, неиспользуемые тесты и служебный мусор.

## Coverage

- В отчёте обязательно покажи `total files`, `reviewed files`, `skipped files`, `blocked checks`.
- Если файл человеко-редактируемый, он должен попасть либо в `reviewed`, либо в `blocked` с причиной.
- Если репозиторий большой, проверяй пакетами по категориям, но не завершай аудит до полного покрытия.

## Формат findings

Для каждого finding укажи:
- `severity`;
- `file:line`;
- краткое название проблемы;
- почему это риск;
- доказательство из контекста;
- минимальное исправление.

Если проблема зависит от окружения или не может быть подтверждена локально, перенеси её в `Blocked` вместо уверенного finding.

## Финальный ответ

Финальный ответ всегда строится в таком порядке:
1. `GO` или `NO-GO` verdict.
2. Критичные findings.
3. Что исправили с прошлого аудита.
4. Что осталось и что надо доделать до релиза.
5. Важные findings.
6. Technical Debt.
7. Cleanup-кандидаты: что удалить, архивировать или подтвердить вручную.
8. Coverage summary.
9. `Blocked` проверки и допущения.

Если пользователь не просил исправления, не переходи к патчам автоматически. Сначала закончи аудит.

## NO-GO Policy

Автоматический `NO-GO`, если выполняется хотя бы одно условие:
- есть finding c `severity = P0`;
- есть `blocked` проверка по критичному пути;
- найден `hardcoded-secret`, `private-key-material` или `tracked-env-risk`;
- отсутствует `.gitignore` или в нём не закрыт критичный риск утечки env/logs.

Cleanup-находки сами по себе не блокируют релиз, если это не security/runtime риск. Их надо вынести в отдельный блок и явно показать, что можно удалить до публикации.

## Что нельзя делать

- Нельзя ограничиваться `grep`-совпадениями без чтения контекста.
- Нельзя печатать найденные секреты целиком; маскируй значения.
- Нельзя заявлять о полноте реализации, если в репозитории не найден источник требований.
- Нельзя писать "всё проверено", если есть `blocked` проверки или непрочитанные человеко-редактируемые файлы.

## Публикация Skill

- Не храни в репозитории локальные audit-артефакты из `docs/release-audits/`.
- Не коммить `__pycache__`, временные smoke-отчёты и machine-specific конфиги.
- Для публикации оставляй только сам skill: `SKILL.md`, `agents/`, `scripts/`, `references/`, `README.md`.
