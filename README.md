# CityPulse: прототип платформы умного города

CityPulse — учебный прототип платформы, объединяющей телеметрию транспорта, коммунальных служб и сервисов безопасности в единый API для оперативного мониторинга состояния города.

## Функции MVP+

- Снимки состояния города по трем доменам (transport/utilities/safety).
- Расчет KPI и интегрального индекса `city_pulse_index`.
- Фильтрация открытых инцидентов по критичности.
- Рекомендации по реагированию (команда, SLA, шаги).
- Аналитика: общий статус города, тренды KPI, агрегированный отчет за окно времени.
- Симуляция событий в реальном времени (инциденты появляются и закрываются автоматически).
- Ручное закрытие инцидентов из UI и API.
- Веб-интерфейс дашборда (`/ui`) с ограниченной и самоочищающейся лентой событий.

## Запуск локально (venv)

1. Создать и активировать виртуальное окружение:
```bash
python -m venv .venv
.venv\\Scripts\\activate
```
2. Установить зависимости:
```bash
pip install -r requirements.txt
```
3. Запустить API:
```bash
uvicorn citypulse.main:app --reload
```

После старта:
- UI: `http://127.0.0.1:8000/ui`
- Swagger: `http://127.0.0.1:8000/docs`

## Запуск в Docker

```bash
docker compose up --build
```

После старта API и UI доступны по адресу: `http://127.0.0.1:8000`.

Остановить контейнер:
```bash
docker compose down
```

## Переменные окружения

- `CITYPULSE_SEED` (по умолчанию `42`)
- `CITYPULSE_HISTORY_HOURS` (по умолчанию `48`)
- `CITYPULSE_TICK_SECONDS` (по умолчанию `6`)
- `CITYPULSE_MAX_OPEN_INCIDENTS` (по умолчанию `12`)
- `CITYPULSE_INCIDENT_MIN_INTERVAL_SECONDS` (по умолчанию `10`)
- `CITYPULSE_INCIDENT_MAX_INTERVAL_SECONDS` (по умолчанию `30`)

## Endpoint'ы

- `GET /`
- `GET /ui`
- `GET /health`
- `GET /v1/snapshots/latest`
- `GET /v1/snapshots?hours=6`
- `GET /v1/incidents/open?min_severity=high`
- `POST /v1/incidents/{incident_id}/resolve`
- `GET /v1/incidents/recommendations?min_severity=medium`
- `GET /v1/events/recent?limit=20&active_seconds=180`
- `GET /v1/analytics/overview`
- `GET /v1/analytics/trends?hours=12`
- `GET /v1/analytics/report?hours=12`

## Проверка качества

```bash
pytest -q
python scripts/benchmark.py
```

## Материалы лабораторной

- [Архитектура](docs/architecture.md)
- [Отчёт](docs/lab_report.md)

