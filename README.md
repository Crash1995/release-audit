# release-audit

## Русский

`release-audit` — это skill для полного предрелизного аудита репозитория.

Он нужен не для быстрого `grep`-скана и не для проверки одного diff-а, а для полноценной проверки всего проекта перед публикацией или релизом.

Что делает skill:
- строит инвентарь всего репозитория;
- проходит по всем человеко-редактируемым файлам;
- ищет критичные security-проблемы и утечки секретов;
- проверяет runtime-риски, обработку ошибок и edge cases;
- ищет технический долг в Python-коде;
- находит мусор в репозитории: stale docs, legacy-конфиги, backup-файлы, неиспользуемые тесты и другие cleanup-кандидаты;
- сравнивает текущий аудит с предыдущим, если в репозитории уже есть `docs/release-audits/`;
- сохраняет итоговый Markdown-отчёт;
- выдаёт финальный вердикт: `GO` или `NO-GO`.

Что проверяется:
- security и hardcoded secrets;
- runtime и edge-case failures;
- Python tech debt;
- cleanup репозитория;
- готовность к релизу;
- итоговый `GO / NO-GO` verdict.

Что получает пользователь на выходе:
- список критичных и важных проблем;
- tech debt и cleanup-кандидаты;
- сравнение с прошлым аудитом;
- сохранённый отчёт в `docs/release-audits/`;
- финальный вывод о готовности к релизу.

### Установка

#### Codex

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/Crash1995/release-audit.git ~/.codex/skills/release-audit
```

#### Claude Code

Глобальная установка:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/Crash1995/release-audit.git ~/.claude/skills/release-audit
```

Установка в проект:

```bash
mkdir -p .claude/skills
git clone https://github.com/Crash1995/release-audit.git .claude/skills/release-audit
```

#### Cursor

Глобальная установка:

```bash
mkdir -p ~/.cursor/skills
git clone https://github.com/Crash1995/release-audit.git ~/.cursor/skills/release-audit
```

Установка в проект:

```bash
mkdir -p .cursor/skills
git clone https://github.com/Crash1995/release-audit.git .cursor/skills/release-audit
```

#### Antigravity

Глобальная установка:

```bash
mkdir -p ~/.gemini/antigravity/skills
git clone https://github.com/Crash1995/release-audit.git ~/.gemini/antigravity/skills/release-audit
```

Установка в проект:

```bash
mkdir -p .agent/skills
git clone https://github.com/Crash1995/release-audit.git .agent/skills/release-audit
```

### Использование

Начните новую сессию и попросите провести полный release-аудит репозитория.

Пример:

```text
Проведи полный release-аудит этого репозитория.
```

Для Codex:

```text
Используй $release-audit и проведи полный release-аудит этого репозитория.
```

### Локальный запуск

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

### Что внутри

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/`
- `references/`

---

## English

`release-audit` is a skill for full pre-release repository audits.

It is not meant for a quick `grep` scan or a single diff review. It is designed for a full repository-wide audit before shipping or publishing a project.

What the skill does:
- builds a full repository inventory;
- reviews all human-editable files;
- detects critical security issues and hardcoded secrets;
- checks runtime risks, error handling, and edge cases;
- finds Python technical debt;
- detects repository cleanup candidates such as stale docs, legacy configs, backup files, unused tests, and similar clutter;
- compares the current audit with the previous one if `docs/release-audits/` already exists;
- saves a Markdown audit report;
- produces a final `GO` or `NO-GO` verdict.

What it checks:
- security and hardcoded secrets;
- runtime and edge-case failures;
- Python tech debt;
- repository cleanup candidates;
- release readiness;
- final `GO / NO-GO` verdict.

What the user gets:
- critical and important findings;
- tech debt and cleanup candidates;
- comparison with the previous audit;
- a saved report in `docs/release-audits/`;
- a final release-readiness verdict.

### Installation

#### Codex

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/Crash1995/release-audit.git ~/.codex/skills/release-audit
```

#### Claude Code

Global install:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/Crash1995/release-audit.git ~/.claude/skills/release-audit
```

Project install:

```bash
mkdir -p .claude/skills
git clone https://github.com/Crash1995/release-audit.git .claude/skills/release-audit
```

#### Cursor

Global install:

```bash
mkdir -p ~/.cursor/skills
git clone https://github.com/Crash1995/release-audit.git ~/.cursor/skills/release-audit
```

Project install:

```bash
mkdir -p .cursor/skills
git clone https://github.com/Crash1995/release-audit.git .cursor/skills/release-audit
```

#### Antigravity

Global install:

```bash
mkdir -p ~/.gemini/antigravity/skills
git clone https://github.com/Crash1995/release-audit.git ~/.gemini/antigravity/skills/release-audit
```

Project install:

```bash
mkdir -p .agent/skills
git clone https://github.com/Crash1995/release-audit.git .agent/skills/release-audit
```

### Usage

Start a new session and ask for a full release audit.

Example:

```text
Run a full release audit for this repository.
```

For Codex:

```text
Use $release-audit and run a full release audit for this repository.
```

### Local Run

```bash
python3 scripts/run_release_audit.py /path/to/repo
```

### What’s Inside

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/`
- `references/`
