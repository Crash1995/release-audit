# release-audit

Полный pre-release аудит репозитория для агентных IDE и CLI.

`release-audit` проверяет весь репозиторий перед релизом и фокусируется не на формальных артефактах, а на реальных рисках:
- security и hardcoded secrets;
- runtime и edge-case проблемы;
- Python tech debt;
- cleanup репозитория: stale docs, legacy configs, backup-файлы, неиспользуемые тесты;
- итоговый `GO / NO-GO` verdict;
- сохранение краткого Markdown-отчёта в `docs/release-audits/`.

## Что внутри

- `SKILL.md`: основная инструкция skill-а.
- `scripts/`: детерминированные проверки и агрегатор.
- `references/`: шкала severity, шаблон отчёта и правила против ложных срабатываний.
- `tests/`: unit tests.

## Требования

- Python `3.11+`
- доступ на запись в аудируемый репозиторий, если нужно сохранить `docs/release-audits/*.md`

Дополнительные зависимости не нужны: skill работает на стандартной библиотеке Python.

## Установка

### Codex

Personal skill:

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/Crash1995/release-audit.git ~/.codex/skills/release-audit
```

Проверка:

```bash
ls ~/.codex/skills/release-audit
```

Использование:

```text
Используй $release-audit и проведи полный release-аудит этого репозитория.
```

### Claude Code

У Claude Code подтверждены project commands и subagents, а не Codex-style skill folders. Поэтому надёжная установка здесь через `.claude/commands` или `.claude/agents`, а сам этот репозиторий используется как prompt-pack + scripts.

Вариант 1, project command:

```bash
git clone https://github.com/Crash1995/release-audit.git tools/release-audit
mkdir -p .claude/commands
cp tools/release-audit/SKILL.md .claude/commands/release-audit.md
```

После этого можно вызывать:

```text
/release-audit
```

Вариант 2, subagent:

```bash
git clone https://github.com/Crash1995/release-audit.git tools/release-audit
mkdir -p .claude/agents
cp tools/release-audit/SKILL.md .claude/agents/release-audit.md
```

Если нужен не project-level, а user-level setup, используйте те же файлы в `~/.claude/commands/` или `~/.claude/agents/`.

### Cursor

У Cursor нет native skill-каталога как в Codex. Поддерживаемые варианты здесь: `.cursor/rules` или `AGENTS.md`.

Вариант 1, project rule:

```bash
mkdir -p .cursor/rules
cp SKILL.md .cursor/rules/release-audit.mdc
```

После этого:
- добавьте в начало файла короткое frontmatter Cursor rule;
- оставьте основное содержимое как workflow-инструкцию.

Минимальный frontmatter:

```md
---
description: Full pre-release repository audit with security, tech-debt, cleanup and GO/NO-GO verdict
alwaysApply: false
---
```

Вариант 2, project `AGENTS.md`:
- положите содержимое `SKILL.md` в `AGENTS.md` проекта или сослитесь на него как на внешний workflow-документ.

### Antigravity

Для Antigravity я не нашёл подтверждённого native skills-формата, поэтому здесь правильный режим установки как reusable audit playbook:

1. Клонируйте репозиторий в любое место.
2. Откройте `SKILL.md` как основной system/workflow prompt.
3. Дайте агенту доступ к `references/` и `scripts/`.
4. Запускайте `scripts/run_release_audit.py` напрямую, если Antigravity умеет вызывать локальные Python-скрипты.

Прямой запуск:

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

## Локальная проверка

Запуск тестов:

```bash
python3 -m unittest discover -s tests
```

Smoke run:

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

## Публикация

Если вы хотите вести этот skill как отдельный GitHub-репозиторий:

```bash
git init
git remote add origin https://github.com/Crash1995/release-audit.git
git add .
git commit -m "feat(skill): publish release audit skill"
git push -u origin main
```

Перед push проверьте, что в репозитории нет локальных audit-артефактов в `docs/release-audits/` и нет `__pycache__`.
