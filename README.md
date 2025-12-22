# Дипломная работа

На данный момент реализовано: 
- Модели проекта: User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
Order, OrderItem, Address, ShopOrder
- Аутентификация:
  - Регистрация с письмом активации
  - Активация аккаунта по ссылке
  - Login (возвращает DRF token + создаёт сессию)
  - Logout (закрывает сессию и/или удаляет токен)
- Бизнес-логика магазина:
  - Импорт каталога товаров через yaml-файл
  - Управление профилем магазина (изменение данных, в т.ч. статуса активности)
  - Получение информации о заказах
  - Смена статуса заказа
  - Управление продуктами конкретного магазина (удаление/изменение/добавление)


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

#### POST /auth/register/  
Регистрация пользователя. После регистрации отправляется письмо с ссылкой для активации аккаунта.
    Ожидаемые данные: email, password.
    Необязательные данные: nickname, first_name, last_name, type.

#### GET /auth/activate/<uid>/<token>  
Активация аккаунта по ссылке из письма.

#### POST /auth/login/ 

Логин пользователя. Возвращает DRF token, также создаёт сессию для DRF UI.

    Ожидаемые данные: email, password

#### POST /auth/logout/ 
Логаут пользователя. Требует авторизацию.

#### GET /shop/me/
Получение информации о своем магазине

#### PATCH /shop/me/ 
Изменение информации о магазине 
    Необязательные данные: name (название магазина), url (ссылка на сайт магазина), 
    state (статус активности, bool), add_categories (list["str", "str"], добавляемые категории), 
    remove_categories (list["str", "str"], удаляемые категории)

#### POST /shop/me/import/
Импорт данных из yaml-файла
    Ожидаемые данные: url (ссылка на yaml-файл)
    Пример yaml-файла представлен в example.yaml

#### GET /shop/me/orders/
Получение списка заказов магазина

#### GET /shop/me/orders/<int:order_id>/
Получение информации по конкретному заказу

#### PATCH /shop/me/orders/<int:order_id>/status/
Смена статуса заказа
    Ожидаемые данные: status (возможные значения: processing, confirmed, assembled, sent, delivered, canceled)

#### POST /shop/me/products/
Создание нового товара для текущего магазина
    Ожидаемые данные: name (str, только на случай, если в Product нет продукта с таким model), category (int, только на случай, если в Product нет продукта с таким model)
    model (str, slug), external_id (int, ссылка на внешнюю бд), quantity (int, количество товара),
    price (decimal, цена), price_rrc (decimal, РРЦ-цена), parameters(dict{"parameter":"value"})

#### PATCH /shop/me/products/<int:pk>/
Изменение конкретного оффера
    Необязательные данные: quantity (int), price (decimal), price_rrc (decimal), parameters(dict{"parameter":"value"}),
    remove_parameters (dict{"parameter":"value"})

#### DELETE /shop/me/products/<int:pk>/
Удаление конкретного оффера


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
