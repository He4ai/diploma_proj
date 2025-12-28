from decimal import Decimal
from unittest.mock import patch, Mock
from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from django.core.cache import cache


from backend.models import (
    Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
    Order, ShopOrder, OrderItem, Address, User
)

User = get_user_model()


class BaseAPITestCase(APITestCase):
    """
    База: создаём клиента, дефолтные настройки email, удобные хелперы.
    """

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        # Чтобы письма реально попадали в mail.outbox
        self._old_email_backend = settings.EMAIL_BACKEND
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

        # Чтобы накладная админу точно имела адрес
        self._old_admins = getattr(settings, "ADMINS", None)
        settings.ADMINS = [("Admin", "admin@example.com")]

        settings.DEFAULT_FROM_EMAIL = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")

        mail.outbox = []

    def tearDown(self):
        settings.EMAIL_BACKEND = self._old_email_backend
        if self._old_admins is None:
            delattr(settings, "ADMINS")
        else:
            settings.ADMINS = self._old_admins
        super().tearDown()

    def auth_as(self, user: User):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return token.key


class AuthFlowTests(BaseAPITestCase):
    def test_register_activate_login(self):
        # 1) Register -> письмо в outbox
        payload = {
            "first_name": "Ivan",
            "last_name": "Petrov",
            "email": "ivan@example.com",
            "password": "StrongPass123!",
            "username": "ivan",
            "type": "buyer",
        }
        r = self.client.post("/api/auth/register/", payload, format="json")
        self.assertEqual(r.status_code, 201)

        user = User.objects.get(email="ivan@example.com")
        self.assertFalse(user.is_active)

        # письмо активации
        self.assertTrue(len(mail.outbox) >= 1)
        self.assertIn("Подтверждение регистрации", mail.outbox[-1].subject)

        # 2) Activate
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        r = self.client.get(f"/api/auth/activate/{uidb64}/{token}/")
        self.assertEqual(r.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # 3) Login -> token
        r = self.client.post(
            "/api/auth/login/",
            {"email": "ivan@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.data)


class CatalogAndBasketTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()

        # Пользователь-покупатель
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="StrongPass123!",
            first_name="Buyer",
            last_name="Test",
            type="buyer",
        )
        self.buyer.is_active = True
        self.buyer.save(update_fields=["is_active"])

        # Адрес по умолчанию
        self.addr = Address.objects.create(
            user=self.buyer,
            label="Home",
            country="RU",
            city="Moscow",
            street="Tverskaya",
            house="1",
            apartment="10",
            is_default=True,
        )

        # Магазин + оффер
        self.shop_user = User.objects.create_user(
            email="shop@example.com",
            password="StrongPass123!",
            first_name="Shop",
            last_name="Owner",
            type="shop",
        )
        self.shop_user.is_active = True
        self.shop_user.save(update_fields=["is_active"])

        self.shop = Shop.objects.create(name="MyShop", user=self.shop_user, state=True)
        self.cat = Category.objects.create(name="Phones")
        self.cat.shops.add(self.shop)

        self.product = Product.objects.create(name="iPhone", category=self.cat, model="iphone-15")
        self.offer = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            external_id=1,
            quantity=10,
            price=Decimal("100.00"),
            price_rrc=Decimal("120.00"),
        )

        # Характеристики
        p_color = Parameter.objects.create(name="Цвет")
        ProductParameter.objects.create(product_info=self.offer, parameter=p_color, value="черный")

    def test_catalog_filters(self):
        # Публичный каталог: должен вернуть оффер
        r = self.client.get("/api/catalog/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data) >= 1)

        # Фильтр по магазину
        r = self.client.get(f"/api/catalog/?shop={self.shop.id}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(x["shop"]["id"] == self.shop.id for x in r.data))

        # Поиск
        r = self.client.get("/api/catalog/?search=iphone")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data) >= 1)

    def test_basket_add_remove_checkout_and_emails(self):
        self.auth_as(self.buyer)

        # 1) add to basket
        r = self.client.post(
            "/api/buyer/basket/items/",
            {"product_info_id": self.offer.id, "quantity": 2},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        basket_id = r.data["id"]
        self.assertEqual(r.data["status"], "basket")

        # 2) basket view + total_sum должен быть
        r = self.client.get("/api/buyer/basket/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("shop_orders", r.data)

        # 3) checkout (без address_id — должен взять default)
        mail.outbox = []
        r = self.client.post("/api/buyer/basket/checkout/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["success"])
        order_id = r.data["order_id"]
        self.assertEqual(order_id, basket_id)

        # Проверяем: заказ placed
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, Order.Status.PLACED)

        # ShopOrder -> processing
        so = ShopOrder.objects.get(order=order, shop=self.shop)
        self.assertEqual(so.status, ShopOrder.Status.PROCESSING)

        # Остаток списан
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.quantity, 8)

        # Письма: покупателю + админу (и возможно магазину)
        # Минимально по ТЗ: клиент + админ должны быть
        recipients_all = [rcpt for m in mail.outbox for rcpt in m.to]
        self.assertIn("buyer@example.com", recipients_all)
        self.assertIn("admin@example.com", recipients_all)

        # 4) remove (на новой корзине)
        # Добавим снова, потом удалим
        r = self.client.post(
            "/api/buyer/basket/items/",
            {"product_info_id": self.offer.id, "quantity": 1},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

        # найдём order_item_id
        basket = Order.objects.get(user=self.buyer, status=Order.Status.BASKET)
        item = OrderItem.objects.filter(shop_order__order=basket).first()
        self.assertIsNotNone(item)

        r = self.client.post("/api/buyer/basket/items/remove/", {"order_item_id": item.id}, format="json")
        self.assertEqual(r.status_code, 200)


SAMPLE_YAML = """
shop: Тестовый магазин
categories:
  - id: 1
    name: Смартфоны
goods:
  - id: 10
    category: 1
    model: iphone-15
    name: iPhone 15
    price: 89990
    price_rrc: 99990
    quantity: 5
    parameters:
      Цвет: черный
"""
class ShopImportAndOrdersTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.shop_user = User.objects.create_user(
            email="shop@example.com",
            password="12345678",
            type="shop",
            is_active=True,
        )
        self.shop = Shop.objects.create(user=self.shop_user, name="Мой магазин", state=True)

        # логинимся (если у тебя токены — можешь поставить force_authenticate)
        self.client.force_authenticate(self.shop_user)

    @patch("backend.views.shop.import_shop_yaml_task.delay")
    @patch("backend.tasks.requests.get")
    def test_shop_import_yaml_and_get_orders(self, mock_get, mock_delay):
        """
        1) POST /api/shop/me/import/ -> теперь 202 и задача уходит в Celery (delay)
        2) А сам импорт (таск) мы запускаем синхронно прямо в тесте, чтобы проверить запись в БД
        3) GET /api/shop/me/orders/ -> возвращает подзаказы магазина
        """

        # --- мок ответа requests.get для таска ---
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.content = SAMPLE_YAML.encode("utf-8")
        mock_get.return_value = resp

        url = "https://example.com/test.yaml"

        # 1) импорт через API (теперь 202!)
        r = self.client.post("/api/shop/me/import/", {"url": url}, format="json")
        self.assertEqual(r.status_code, 202)
        mock_delay.assert_called_once()  # задача реально поставлена в очередь

        # 2) запускаем таск синхронно, чтобы реально заполнить БД
        from backend.tasks import import_shop_yaml_task
        result = import_shop_yaml_task(self.shop.id, url)
        self.assertTrue(result.get("success"))

        # проверим, что офферы появились
        self.assertTrue(ProductInfo.objects.filter(shop=self.shop).exists())

        # 3) создадим заказ, чтобы эндпоинт /orders/ было что отдавать
        buyer = User.objects.create_user(
            email="buyer@example.com",
            password="12345678",
            type="buyer",
            is_active=True,
        )
        order = Order.objects.create(user=buyer, status=Order.Status.PLACED)

        so = ShopOrder.objects.create(order=order, shop=self.shop, status=ShopOrder.Status.PROCESSING)
        pi = ProductInfo.objects.filter(shop=self.shop).first()
        OrderItem.objects.create(shop_order=so, product_info=pi, quantity=1, price_at_purchase=pi.price)

        r2 = self.client.get("/api/shop/me/orders/")
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(isinstance(r2.json(), list))
        self.assertGreaterEqual(len(r2.json()), 1)


class ThrottleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_throttle_anon(self):
        cache.clear()

        url = "/api/products/"
        last = None

        # anon = 30/min -> ожидаем, что к ~31 запросу получим 429
        for _ in range(35):
            last = self.client.get(url, REMOTE_ADDR="1.2.3.4")  # фиксируем IP
        self.assertIsNotNone(last)
        self.assertEqual(last.status_code, 429)

import sys

if "test" in sys.argv:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True