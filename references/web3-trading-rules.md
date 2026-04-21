# Web3 & Trading — Targeted Checklist

Паттерны, которые агенты должны целенаправленно искать в Web3/trading проектах.
Применяй этот чеклист если project rules указывают на Web3/crypto/trading контекст,
или если в коде есть `web3`, `aiohttp`, `order`, `trade`, `balance`, `pnl`.

## Финансовая логика

| Паттерн | Severity | Что искать в коде | Почему риск |
|---------|----------|-------------------|-------------|
| float в расчётах | P1 | `float` для PnL, balance, order size, fee, spread | Потеря точности = потеря денег. Должен быть `Decimal` |
| Нет slippage cap | P1 | Market order без `max_slippage` / `worst_price` | Проскальзывание может обнулить прибыль |
| Деление без проверки | P1 | `/ volume`, `/ liquidity`, `/ count` без guard `if x == 0` | ZeroDivisionError в runtime |
| Неатомарная операция | P1 | Place order → update state без try/rollback | Partial state: ордер исполнен, но state не обновлён |
| Округление в неверную сторону | P2 | `round(amount, 2)` без указания направления | Может привести к overspend или rejection |
| Сравнение float | P2 | `if price == target_price` | float equality ненадёжен, использовать `math.isclose` или `Decimal` |

## Работа с API / ордера

| Паттерн | Severity | Что искать в коде | Почему риск |
|---------|----------|-------------------|-------------|
| Retry на ордерах без idempotency | P0 | `@retry` на `place_order()` без idempotency key | Дублирование ордера = двойная потеря |
| HTTP без таймаутов | P1 | `aiohttp.ClientSession()` без `timeout=` | Зависший запрос блокирует event loop |
| Нет rate limiting | P2 | Цикл с API-вызовами без `asyncio.sleep` / semaphore | 429 от биржи, бан IP |
| Игнорирование 429 | P1 | Ответ API не проверяется на rate limit status | Повторные запросы усугубляют бан |
| Нет проверки ответа API | P1 | `response.json()` без проверки status code / пустого тела | KeyError или None dereference |
| Hardcoded API URL с ключом | P0 | URL содержит `?key=`, `?apikey=`, `?token=` | Утечка ключа в коде/логах |

## Web3 / On-chain

| Паттерн | Severity | Что искать в коде | Почему риск |
|---------|----------|-------------------|-------------|
| Inline private key | P0 | `from_key("0x...")`, `Account.from_key` с литералом | Прямая компрометация кошелька |
| Адрес без checksum | P2 | `"0xabcdef..."` без `Web3.to_checksum_address()` | Может отправить на неверный адрес |
| Hardcoded gas price | P2 | `gas_price = 20_000_000_000` без fallback/estimation | Транзакция зависнет или переплата |
| Nonce без mutex | P1 | `get_transaction_count()` + `send_transaction()` без lock | Race condition = nonce collision |
| Transaction без gas estimate | P2 | `send_transaction()` без предварительного `estimate_gas()` | Out of gas = потеря gas fee |
| Hardcoded chain ID | P2 | `chain_id = 1` без конфига | Сломается при переключении сети |

## Data integrity

| Паттерн | Severity | Что искать в коде | Почему риск |
|---------|----------|-------------------|-------------|
| API данные без валидации | P1 | `.json()["data"]["price"]` без проверки None/empty | KeyError или None dereference в runtime |
| Кэш без TTL | P2 | `dict` / `lru_cache` без expiration для market data | Торговля по устаревшим ценам |
| SQLite write без transaction | P2 | `cursor.execute("INSERT...")` без `with conn:` | Partial write при ошибке |
| Отсутствие дедупликации | P2 | Append в БД/файл без проверки на дубликат | Двойной учёт сделок в аналитике |

## Async-специфика

| Паттерн | Severity | Что искать в коде | Почему риск |
|---------|----------|-------------------|-------------|
| `requests.get()` в async def | P1 | Синхронный HTTP в async-функции | Блокирует event loop |
| `time.sleep()` в async def | P1 | Синхронный sleep в async-функции | Блокирует event loop, use `asyncio.sleep` |
| Session без закрытия | P1 | `aiohttp.ClientSession()` без `async with` / explicit close | Resource leak, connection pool exhaustion |
| `asyncio.gather` без error handling | P2 | `gather(*tasks)` без `return_exceptions=True` при необходимости | Один exception отменяет все tasks |
