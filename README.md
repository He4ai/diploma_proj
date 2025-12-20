# Дипломная работа

На этом этапе реализовано: 
- Модели проекта: User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
Order, OrderItem, Address
- Аутентификация:
  - Регистрация с письмом активации
  - Активация аккаунта по ссылке
  - Login (возвращает DRF token + создаёт сессию)
  - Logout (закрывает сессию и/или удаляет токен)


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
- `core/backend/` — приложение
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

## Проведение миграций
```bash
python manage.py makemigrations
python manage.py migrate
```

## API endpoints

POST /auth/register/  
Регистрация пользователя (email, password). После регистрации отправляется письмо
с ссылкой для активации аккаунта.

GET /auth/activate/<uid>/<token>  
Активация аккаунта по ссылке из письма.

POST /auth/login/  
Логин пользователя. Возвращает DRF token, также создаёт сессию для DRF UI.

POST /auth/logout/  
Логаут пользователя. Требует авторизацию.


## Тестирование

- Открыть /auth/register/ -> отправить JSON (обязательно: email, password)
- В консоли появится письмо с ссылкой -> перейти, чтобы активировать аккаунт
- Залогиниться /auth/login/ -> получить токен и открыть сессию

## Примечания

- Реализован гибридный режим аутентификации:
  - для браузерного тестирования через DRF Browsable API используется сессия;
  - для внешних клиентов используется TokenAuthentication
- Такой подход выбран для удобства разработки и тестирования
- Для отправки писем в dev-окружении используется console backend
  (письма выводятся в консоль)
- Для тестирования TokenAuthentication рекомендуется использовать Postman или curl
