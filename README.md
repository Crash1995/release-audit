# release-audit

Full pre-release repository audit for coding agents.

Checks:
- security and hardcoded secrets
- runtime and edge-case failures
- Python tech debt
- repository cleanup candidates
- final `GO / NO-GO` verdict
- saved Markdown report in `docs/release-audits/`

## Install

### Claude Code

Follow [`.claude/INSTALL.md`](.claude/INSTALL.md)

### Cursor

Follow [`.cursor/INSTALL.md`](.cursor/INSTALL.md)

### Codex

Tell Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/Crash1995/release-audit/refs/heads/main/.codex/INSTALL.md
```

Or open [`.codex/INSTALL.md`](.codex/INSTALL.md)

### Antigravity

Follow [`.antigravity/INSTALL.md`](.antigravity/INSTALL.md)

## Verify Installation

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

- [`SKILL.md`](SKILL.md)
- [`agents/openai.yaml`](agents/openai.yaml)
- [`scripts/`](scripts)
- [`references/`](references)

## Local Run

```bash
python3 scripts/run_release_audit.py /path/to/repo
```
