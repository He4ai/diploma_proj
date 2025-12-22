from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import UniqueConstraint, Q
from django.utils import timezone
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator


USER_TYPE_CHOICES = (
    ("shop", "Магазин"),
    ("buyer", "Покупатель"),
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    REQUIRED_FIELDS = []
    objects = UserManager()
    USERNAME_FIELD = "email"

    email = models.EmailField(unique=True, verbose_name="Email")

    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        max_length=150,
        help_text="Необязательно. До 150 символов. Буквы, цифры и @/./+/-/_",
        validators=[username_validator],
        blank=True,
        verbose_name="Имя пользователя",
    )

    type = models.CharField(
        choices=USER_TYPE_CHOICES,
        max_length=5,
        default="buyer",
        verbose_name="Тип пользователя",
    )

    def __str__(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ("email",)


class Shop(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название магазина")
    url = models.URLField(verbose_name="Ссылка на магазин", blank=True, null=True)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="owned_shop",   # <- ВАЖНО: не "shop"
        verbose_name="Владелец магазина",
    )

    state = models.BooleanField(default=True, verbose_name="Статус получения заказов")

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"
        ordering = ("name",)


class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название категории")
    shops = models.ManyToManyField(Shop, related_name="categories", verbose_name="Магазины")

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ("name",)


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название продукта")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products", verbose_name="Категория")
    model = models.CharField(max_length=80, unique=True, verbose_name="Модель")

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"
        ordering = ("name",)


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="offers", verbose_name="Продукт")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="offers", verbose_name="Магазин")

    external_id = models.PositiveIntegerField(verbose_name="Внешний ИД")
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    price_rrc = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="РРЦ")

    def __str__(self) -> str:
        return f"{self.product.name}: q-{self.quantity}, p-{self.price}"

    class Meta:
        verbose_name = "Информация о продукте"
        verbose_name_plural = "Информация о продуктах"
        ordering = ("shop", "external_id")
        constraints = [
            UniqueConstraint(fields=["shop", "external_id"], name="uniq_shop_external_id"),
        ]


class Parameter(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название параметра")

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Параметр"
        verbose_name_plural = "Параметры"
        ordering = ("name",)


class ProductParameter(models.Model):
    product_info = models.ForeignKey(
        ProductInfo,
        on_delete=models.CASCADE,
        related_name="parameters",
        verbose_name="Информация о продукте",
    )
    parameter = models.ForeignKey(
        Parameter,
        on_delete=models.CASCADE,
        related_name="product_parameters",
        verbose_name="Параметр",
    )
    value = models.CharField(max_length=50, verbose_name="Значение")

    def __str__(self) -> str:
        return f"{self.product_info.product.name} - {self.parameter.name} - {self.value}"

    class Meta:
        verbose_name = "Параметр продукта"
        verbose_name_plural = "Параметры продуктов"
        ordering = ("product_info__product__name",)


class Order(models.Model):
    class Status(models.TextChoices):
        BASKET = "basket", "статус корзины"
        PLACED = "placed", "оформлен"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders", verbose_name="Заказчик")
    date = models.DateTimeField(default=timezone.now, verbose_name="Дата заказа")
    status = models.CharField(choices=Status.choices, default=Status.BASKET, max_length=10, verbose_name="Статус заказа")

    shipping_country = models.CharField(max_length=50, blank=True, default="", verbose_name="Страна")
    shipping_city = models.CharField(max_length=50, blank=True, default="", verbose_name="Город")
    shipping_street = models.CharField(max_length=50, blank=True, default="", verbose_name="Улица")
    shipping_house = models.CharField(max_length=50, blank=True, default="", verbose_name="Дом")
    shipping_apartment = models.CharField(max_length=50, blank=True, default="", verbose_name="Квартира")

    def __str__(self) -> str:
        return f"Order #{self.pk} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ("-date",)
        constraints = [
            UniqueConstraint(
                fields=["user"],
                condition=Q(status="basket"),
                name="uniq_basket_per_user",
            )
        ]


class ShopOrder(models.Model):
    class Status(models.TextChoices):
        BASKET = "basket", "статус корзины"
        PROCESSING = "processing", "обрабатывается"
        CONFIRMED = "confirmed", "подтвержден"
        ASSEMBLED = "assembled", "собран"
        SENT = "sent", "отправлен"
        DELIVERED = "delivered", "доставлен"
        CANCELED = "canceled", "отменен"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shop_orders")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="shop_orders")
    status = models.CharField(choices=Status.choices, default=Status.PROCESSING, max_length=20, verbose_name="Статус заказа")

    class Meta:
        verbose_name = "Подзаказ магазина"
        verbose_name_plural = "Подзаказы магазина"
        ordering = ("order_id",)
        constraints = [
            UniqueConstraint(fields=["order", "shop"], name="uniq_order_shop"),
        ]

    def __str__(self) -> str:
        return f"ShopOrder #{self.pk} order={self.order_id} shop={self.shop_id} ({self.status})"


class OrderItem(models.Model):
    shop_order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name="items")
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE, related_name="order_items")

    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Позиция в заказе"
        verbose_name_plural = "Позиции в заказах"
        ordering = ("shop_order_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["shop_order", "product_info"],
                name="uniq_item_per_shoporder_productinfo",
            )
        ]

    def __str__(self) -> str:
        return f"Order #{self.shop_order.order_id}.{self.pk}: {self.product_info.product.name} - {self.quantity}"


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses", verbose_name="Пользователь")
    label = models.CharField(max_length=50, verbose_name="Название адреса")
    country = models.CharField(max_length=50, verbose_name="Страна")
    city = models.CharField(max_length=50, verbose_name="Город")
    street = models.CharField(max_length=50, verbose_name="Улица")
    house = models.CharField(max_length=50, verbose_name="Дом")
    apartment = models.CharField(max_length=50, blank=True, verbose_name="Квартира")
    is_default = models.BooleanField(default=False, verbose_name="Основной адрес")

    class Meta:
        verbose_name = "Адрес пользователя"
        verbose_name_plural = "Адреса пользователей"
        ordering = ("user_id", "id")
        constraints = [
            UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True),
                name="uniq_default_address_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.label}"
