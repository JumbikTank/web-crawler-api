# Web Crawler - Quality Assurance Setup

Проект веб-краулера с настроенными инструментами обеспечения качества кода.

## Установка

```bash
# Установка зависимостей
uv pip install -e ".[dev]"

# Установка pre-commit hooks
pre-commit install
```

## Запуск проверок

### Тесты
```bash
# Запуск тестов
pytest tests/ -v

# С покрытием
pytest tests/ --cov=crawler

# HTML отчёт
pytest tests/ --cov=crawler --cov-report=html
# Открыть htmlcov/index.html
```

### Allure отчёты
```bash
# Генерация
pytest tests/ --alluredir=allure-results

# Просмотр (требует allure CLI)
allure serve allure-results
```

### Линтинг и типы
```bash
# Все проверки
mypy crawler/ tests/
ruff check crawler/ tests/
black --check crawler/ tests/
isort --check-only crawler/ tests/

# Автофикс
ruff check --fix crawler/ tests/
black crawler/ tests/
isort crawler/ tests/

# Pre-commit (всё вместе)
pre-commit run --all-files
```

## Результаты

- **Покрытие:** 100% (требовалось ≥90%)
- **Тесты:** 10/10 passed
- **Типы:** mypy strict mode, 0 ошибок

## Конфигурация

Все настройки в `pyproject.toml`:
- pytest: минимум 90% покрытия, asyncio mode
- mypy: strict mode, полная типизация
- ruff: 100 символов, Python 3.11+
- black/isort: 100 символов

Pre-commit hooks в `.pre-commit-config.yaml`.

## API

```bash
# Запуск сервера
litestar --app crawler.app:app run --reload
```

Endpoints:
- `POST /urls` - создать запись URL
- `GET /url-data?url=...` - получить данные URL
- `POST /html` - сохранить HTML в S3

OpenAPI: http://127.0.0.1:8000/schema
