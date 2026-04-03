# Report Template

## GO / NO-GO

Одна строка с финальным вердиктом и краткой причиной.

## Machine Report

- Путь репозитория
- `total_files`
- количество findings
- список triggered rules
- путь к сохранённому `.md` отчёту

## Verdict Basis

- Какие правила перевели аудит в `NO-GO`
- Какие blocked-проверки остались
- Какие допущения были сделаны

## Progress Since Previous Audit

- Что было исправлено с прошлого аудита
- Что осталось без изменений
- Какие новые проблемы появились

## Remaining Work

- Что обязательно исправить до релиза
- Что можно перенести в post-release backlog

## Technical Debt

- Какие Python debt-findings остались
- Что нужно вынести в константы, типизировать или упростить
- Какие async/mutable default/broad except проблемы требуют рефакторинга

## Cleanup Candidates

- Что удалить из репозитория
- Что архивировать
- Что выглядит неиспользуемым, но требует ручного подтверждения

## Coverage

- Всего файлов:
- Проверено файлов:
- Skipped:
- Blocked:

## Critical Findings

Для каждого finding:
- severity
- file:line
- проблема
- почему это риск
- минимальное исправление
