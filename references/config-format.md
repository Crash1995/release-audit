# Config Format

Локальная конфигурация skill-а хранится в `.release-audit.toml` в корне репозитория.

Минимальный пример:

```toml
[severity_overrides]
verify-false = "P0"
python-print-call = "P3"

[[suppressions]]
path = "scripts/dev_only.py"
rules = ["os-system", "python-print-call"]
```

Правила:
- `severity_overrides` меняет severity по имени правила;
- `suppressions` отключает конкретные правила для конкретного файла;
- suppression допустим только для осознанных исключений, а не для скрытия реальных блокеров релиза.
