# False Positive Rules

Правила для отсеивания ложных срабатываний. Агент ОБЯЗАН проверить контекст перед включением finding.

## General

| Паттерн | Контекст "допустим" | Контекст "дефект" |
|---------|---------------------|-------------------|
| `TODO`, `FIXME`, `HACK` | В `tests/`, `docs/`, комментариях к backlog | На runtime-пути в source-коде |
| `example.com`, `test@`, `sample`, `dummy` | В документации, примерах, тестах | В runtime-конфигурации или source |
| `CORS = "*"` | В dev-only конфиге, за `if DEBUG` | В prod-конфигурации или общем runtime-пути |
| Закомментированный код (1-3 строки) | Пояснение "почему не X" | Больше 3 строк подряд — мёртвый код |

## Python-specific

| Паттерн | Контекст "допустим" | Контекст "дефект" |
|---------|---------------------|-------------------|
| `print()` | CLI-вывод в backtest-скриптах (проверь project rules) | В библиотечном коде, в async runtime |
| `pass` | В `__init__.py`, abstract-классах, protocol stubs | На реальном runtime-пути |
| `except Exception` | С `logger.error()` + `raise` / reraise | Голый `except:` без логирования, без reraise |
| `return None` explicit | Caller проверяет `if result is None` | Caller делает `.attribute` без проверки |
| `time.sleep()` | В sync-only коде (не в `async def`) | Внутри `async def` — blocking call |
| `mutable default` | `field(default_factory=list)` в dataclass | `def f(x=[])` — реальный mutable default |
| Отсутствие type hints | В `if __name__ == "__main__"` блоках, internal helpers | На публичных функциях/методах |
| `# type: ignore` | С комментарием причины рядом | Без объяснения, массовое подавление |
| `eval()` / `exec()` | В тестовых fixtures, codegen tools | В runtime с пользовательским вводом |

## Web3/Trading-specific

| Паттерн | Контекст "допустим" | Контекст "дефект" |
|---------|---------------------|-------------------|
| `float` для price | Display, logging, визуализация, отчёты | Расчёт PnL, order size, balance, fee |
| Hardcoded RPC URL | Публичный endpoint без ключа (`llamarpc.com`) | URL содержит API key или приватный endpoint |
| `from_key()` | С `os.environ[...]` / `os.getenv(...)` | С inline строкой-ключом |
| Адрес контракта как константа | Публичный адрес, checksum-формат | Без checksum, в runtime path без валидации |
| Hardcoded dates | В backtest скриптах для тестовых диапазонов | В prod-логике (фильтрация, expiry) |

## Backtest-specific

| Паттерн | Контекст "допустим" | Контекст "дефект" |
|---------|---------------------|-------------------|
| `print()` в backtest | CLI-таблицы, progress bar, финальный отчёт | Если рядом есть logger — значит print лишний |
| Magic numbers в strategy | Рядом есть config/CLI override или именованная константа | Inline без объяснения, влияет на P&L |
| Отсутствие retry | Чтение локальных файлов/БД | Запросы к внешним API |
| `except Exception: pass` | В cleanup/finally для не-критичных операций | В основном потоке данных |
