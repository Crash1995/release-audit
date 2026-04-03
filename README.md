# release-audit

Full pre-release repository audit for coding agents.

Checks:
- security and hardcoded secrets
- runtime and edge-case failures
- Python tech debt
- repository cleanup candidates
- final `GO / NO-GO` verdict
- saved Markdown report in `docs/release-audits/`

## Installation

### Codex

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/Crash1995/release-audit.git ~/.codex/skills/release-audit
```

### Claude Code

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/Crash1995/release-audit.git ~/.claude/skills/release-audit
```

Or install per project:

```bash
mkdir -p .claude/skills
git clone https://github.com/Crash1995/release-audit.git .claude/skills/release-audit
```

### Cursor

```bash
mkdir -p ~/.cursor/skills
git clone https://github.com/Crash1995/release-audit.git ~/.cursor/skills/release-audit
```

Or install per project:

```bash
mkdir -p .cursor/skills
git clone https://github.com/Crash1995/release-audit.git .cursor/skills/release-audit
```

### Antigravity

```bash
mkdir -p ~/.gemini/antigravity/skills
git clone https://github.com/Crash1995/release-audit.git ~/.gemini/antigravity/skills/release-audit
```

Or install per project:

```bash
mkdir -p .agent/skills
git clone https://github.com/Crash1995/release-audit.git .agent/skills/release-audit
```

## Usage

Start a new session and ask for a full release audit.

Example:

```text
Run a full release audit for this repository.
```

For Codex:

```text
Use $release-audit and run a full release audit for this repository.
```

## What’s Inside

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/`
- `references/`

## Local Run

```bash
python3 scripts/run_release_audit.py /path/to/repo
```
