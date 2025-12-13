# Дипломная работа

Базовый шаблон (skeleton) Django-проекта для дипломного задания.  
На этом этапе реализована только инфраструктура: настройки, подключение PostgreSQL и запуск проекта.  
Бизнес-логика, модели и API будут добавляться после получения доступа к ТЗ.

## Стек
- Python 3.11
- Django 5.2.9
- PostgreSQL
- psycopg 3
- python-dotenv
- Docker / Docker Compose

## Структура
Проект находится в папке `core/`:
- `core/manage.py` — точка входа Django
- `core/config/` — настройки проекта (settings/urls/asgi/wsgi)
- `core/orders/` — приложение (пока без логики)
- `core/docker-compose.yml` — PostgreSQL
- `core/.env` — переменные окружения (НЕ коммитится)

## Переменные окружения
Файл `core/.env` следует создать и заполнить по следующему примеру:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=deep_v_lom
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5431
DJANGO_SECRET_KEY=your_secret_key
```

## Запуск PostgreSQL (Docker)
Из папки /core:
```bash
docker compose up -d
```

Проверка статуса:
```bash
docker compose ps
```

Остановка:
```bash
docker compose down
```

Остановка с удалением данных:
```bash
docker compose down -v
```

## Установка зависимостей и запуск Django

Из папки /core:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

После запуска проект доступен по адресу:
http://127.0.0.1:8000/

## Примечания
- Данный коммит - только базовая структура проекта
- Реализация моделей/эндпоинтов/тестов будет добавляться после получения ТЗ