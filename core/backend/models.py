from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import UniqueConstraint, Q
from django.utils import timezone
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator

USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),
)

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):

        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    REQUIRED_FIELDS = []
    objects = UserManager()
    USERNAME_FIELD = 'email'

    email = models.EmailField(unique=True, verbose_name='Email')
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        max_length=150,
        help_text='Необязательно. До 150 символов. Буквы, цифры и @/./+/-/_',
        validators=[username_validator],
        error_messages={
            'unique': "A user with that username already exists.",
        },
        blank=True,
        verbose_name='Имя пользователя'
    )
    type = models.CharField(choices=USER_TYPE_CHOICES, max_length=5, default='buyer', verbose_name='Тип пользователя')
    shop = models.ForeignKey(
        "Shop",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
        verbose_name="Магазин"
    )
    def __str__(self):
        full = f'{self.first_name} {self.last_name}'.strip()
        return full or self.email

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Пользователи"
        ordering = ('email',)


class Shop(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название магазина')
    url = models.URLField(verbose_name='Ссылка на магазин')

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'
        ordering = ('-name',)


class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название категории')
    shops = models.ManyToManyField(Shop, related_name='categories', verbose_name='Магазины')

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ('-name',)


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название продукта')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products',
                                 verbose_name='Категория')

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        ordering = ('-name',)


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_infos',
                                verbose_name='Продукт')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='product_infos',
                             verbose_name='Магазин')
    name = models.CharField(max_length=200, verbose_name='Название в магазине')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    price_rrc = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='РРЦ')

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = 'Информация о продуктах'
        ordering = ('shop', '-name',)
        constraints = [
            UniqueConstraint(fields=['product', 'shop'], name='uniq_product_shop')
        ]


class Parameter(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название параметра')

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Параметры'
        ordering = ('-name',)


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE, related_name='product_parameters',
                                     verbose_name='Информация о продукте')
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE, related_name='product_parameters',
                                  verbose_name='Параметр')
    value = models.CharField(max_length=50, verbose_name='Значение')

    def __str__(self) -> str:
        return f'{self.product_info.name} - {self.parameter.name} - {self.value}'

    class Meta:
        verbose_name = 'Параметр продукта'
        verbose_name_plural = 'Параметры продуктов'
        ordering = ('product_info__name',)

class Order(models.Model):
    class Status(models.TextChoices):
        BASKET = 'basket', 'статус корзины'
        NEW = 'new', 'новый'
        CONFIRMED = 'confirmed', 'подтвержден'
        ASSEMBLED = 'assembled', 'собран'
        SENT = 'sent', 'отправлен'
        DELIVERED = 'delivered', 'доставлен'
        CANCELED = 'canceled', 'отменен'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders',
                             verbose_name='Заказчик')
    date = models.DateTimeField(default=timezone.now, verbose_name='Дата заказа')
    status = models.CharField(choices=Status.choices, default=Status.BASKET, max_length=10,
                              verbose_name='Статус заказа')
    shipping_country = models.CharField(max_length=50, blank=True, default="", verbose_name='Страна')
    shipping_city = models.CharField(max_length=50, blank=True, default="", verbose_name='Город')
    shipping_street = models.CharField(max_length=50, blank=True, default="", verbose_name='Улица')
    shipping_house = models.CharField(max_length=50, blank=True, default="", verbose_name='Дом')
    shipping_apartment = models.CharField(max_length=50,blank=True, default="", verbose_name='Квартира')

    def __str__(self) -> str:
        return f'Order #{self.pk} ({self.get_status_display()})'

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ('user', '-date',)
        constraints = [
            UniqueConstraint(
                fields=["user"],
                condition=Q(status="basket"),
                name="uniq_basket_per_user"
            )
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items',
                              verbose_name='Заказ')
    product_info = models.ForeignKey(ProductInfo,on_delete=models.CASCADE, related_name='items',
                                     verbose_name='Информация о продукте')
    quantity = models.PositiveIntegerField(verbose_name='Количество продукта')
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')

    def __str__(self) -> str:
        return f'Order #{self.order.id}.{self.pk}: {self.product_info.name} - {self.quantity}'

    class Meta:
        verbose_name = 'Позиция в заказе'
        verbose_name_plural = 'Позиции в заказах'
        ordering = ('order',)


#Хранение адресов в отдельной таблице, чтобы пользователь мог сохранять несколько штук и выбирать основной из них
#Как, например, в приложении озона
class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses',
                             verbose_name='Пользователь')
    label = models.CharField(max_length=50, verbose_name='Название адреса')
    country = models.CharField(max_length=50, verbose_name='Страна', )
    city = models.CharField(max_length=50, verbose_name='Город', )
    street = models.CharField(max_length=50, verbose_name='Улица')
    house = models.CharField(max_length=50, verbose_name='Дом')
    apartment = models.CharField(max_length=50, blank=True, verbose_name='Квартира')
    is_default = models.BooleanField(default=False, verbose_name='Основной адрес')

    class Meta:
        verbose_name = 'Адрес пользователя'
        verbose_name_plural = 'Адреса пользователей'
        ordering = ('user',)
        constraints = [
            UniqueConstraint(fields=['user'],
                                    condition=Q(is_default=True),
                                    name='uniq_default_address_per_user'
                                    )
        ]