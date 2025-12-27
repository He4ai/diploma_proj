# Дипломная работа  
**Backend сервиса заказа товаров для розничных сетей (REST API)**

## Общее описание

Проект представляет собой backend-часть сервиса для автоматизации закупок в розничной сети через REST API.  
Все взаимодействие с системой осуществляется **исключительно через API**. Реализация frontend-части не требуется.

Сервис поддерживает два типа пользователей:
- **Покупатель (buyer)** — формирует корзину, оформляет заказы, управляет адресами доставки
- **Поставщик (shop)** — импортирует каталог товаров, управляет магазином и обрабатывает заказы

Проект реализован в соответствии с техническим заданием и покрыт автоматическими тестами.

---

## Реализованный функционал

### Модели данных

Реализованы следующие модели:
- `User` — пользователь (buyer / shop)
- `Shop` — магазин поставщика
- `Category` — категории товаров
- `Product` — товар-эталон
- `ProductInfo` — оффер товара конкретного магазина
- `Parameter`, `ProductParameter` — характеристики товаров
- `Order` — заказ / корзина
- `ShopOrder` — подзаказ конкретного магазина
- `OrderItem` — позиция в заказе
- `Address` — адрес доставки пользователя

---

### Аутентификация и безопасность

- Регистрация пользователя
- Отправка письма с ссылкой активации
- Активация аккаунта
- Login (возвращает DRF Token и создаёт сессию)
- Logout
- Смена пароля
- Смена email с подтверждением по ссылке

Используется гибридная аутентификация:
- `SessionAuthentication` — для DRF Browsable API
- `TokenAuthentication` — для внешних клиентов

---

### Функционал покупателя

- Просмотр каталога товаров
- Поиск и фильтрация
- Корзина:
  - добавление товаров
  - удаление товаров
  - автоматическое разбиение заказа по магазинам
- Управление адресами доставки:
  - создание / редактирование / удаление
  - строгая логика одного адреса по умолчанию
- Оформление заказа:
  - списание остатков
  - смена статусов
  - email-подтверждение покупателю
  - email-накладная администратору
- Просмотр истории заказов
- Детальный просмотр заказа

---

### Функционал поставщика

- Импорт каталога товаров из YAML-файла по URL
- Управление магазином:
  - название
  - URL
  - статус активности
  - категории
- Управление товарами:
  - создание офферов
  - изменение цен, остатков и характеристик
  - удаление офферов
- Просмотр заказов магазина
- Смена статусов подзаказов с контролем допустимых переходов

---

### Email-уведомления

- Покупателю — подтверждение заказа
- Поставщику — накладная по подзаказу
- Администратору — накладная по всему заказу

В dev-окружении используется console email backend.

---

## Асинхронные задачи (Celery)

В проекте используется Celery для выполнения фоновых задач:

- отправка писем (покупателю, магазину, администратору);
- асинхронный импорт каталога магазина из YAML-файла.

### Зависимости
- Redis — брокер сообщений
- Celery — очередь задач

---

## Стек технологий

- Python 3.11
- Django 5.2.9
- Django REST Framework
- PostgreSQL
- psycopg3
- django-filters
- python-dotenv
- Docker / Docker Compose

---

## Структура проекта

Проект расположен в папке `core/`:
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
docker compose up -d redis
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
celery -A config worker -l info -P solo
```

После запуска проект доступен по адресу:
http://127.0.0.1:8000/

## Проведение миграций
```bash
python manage.py makemigrations
python manage.py migrate
```

## Тестирование проекта
Проект покрыт автоматическими тестами, проверяющими ключевой функционал ТЗ.
```bash
python manage.py test backend -v 2
```

## API endpoints

### OPENApi

/api/schema

/api/docs - документация api

### Аутентификация

POST /api/auth/register/

GET /api/auth/activate/<uid>/<token>/

POST /api/auth/login/

POST /api/auth/logout/

POST /api/auth/password/reset/

POST /api/auth/password/reset/confirm/<uid>/<token>/

### Каталог (публичный)

GET /api/catalog/

GET /api/products/

GET /api/shops/<shop_id>/

GET /api/shops/<shop_id>/offers/

### Покупатель

GET /api/buyer/basket/

POST /api/buyer/basket/items/

POST /api/buyer/basket/items/remove/

POST /api/buyer/basket/checkout/

POST /api/buyer/basket/address/

### Профиль клиента

GET /api/client/profile/

PATCH /api/client/profile/

POST /api/client/profile/password/

POST /api/client/profile/email/change/

GET /api/client/profile/addresses/

POST /api/client/profile/addresses/

PATCH /api/client/profile/addresses/<id>/

DELETE /api/client/profile/addresses/<id>/

GET /api/client/orders/

GET /api/client/orders/<id>/

### Поставщик

GET /api/shop/me/

PATCH /api/shop/me/

POST /api/shop/me/import/

GET /api/shop/me/orders/

PATCH /api/shop/me/orders/<order_id>/status/

GET /api/shop/me/products/

POST /api/shop/me/products/

PATCH /api/shop/me/products/<id>/

DELETE /api/shop/me/products/<id>/

## Примечания

- Проект реализует бизнес-логику строго через REST API
- Frontend не требуется
- Архитектура позволяет легко расширять функционал
- Код структурирован и покрыт тестами

