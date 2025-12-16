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
    email = models.EmailField(unique=True)
    company = models.CharField(verbose_name='Компания', max_length=40, blank=True)
    position = models.CharField(verbose_name='Должность', max_length=40, blank=True)
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        max_length=150,
        help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
        validators=[username_validator],
        error_messages={
            'unique': "A user with that username already exists.",
        },
        unique=True,
        blank=True,
    )
    type = models.CharField(verbose_name='Тип пользователя', choices=USER_TYPE_CHOICES, max_length=5, default='buyer')

    def __str__(self):
        full = f'{self.first_name} {self.last_name}'.strip()
        return full or self.email

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Список пользователей"
        ordering = ('email',)


class Shop(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField()

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Список магазинов'
        ordering = ('-name',)


class Category(models.Model):
    name = models.CharField(max_length=200)
    shops = models.ManyToManyField(Shop, related_name='categories')

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Список категорий'
        ordering = ('-name',)


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Список продуктов'
        ordering = ('-name',)


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='products_infos')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products_infos')
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_rrc = models.DecimalField(max_digits=10, decimal_places=2)

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
    name = models.CharField(max_length=200)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Список параметров'
        ordering = ('-name',)


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE, related_name='product_parameters')
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE, related_name='product_parameters')
    value = models.CharField(max_length=50)

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

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    date = models.DateTimeField(default=timezone.now)
    status = models.CharField(choices=Status.choices, default=Status.BASKET, max_length=10)
    shipping_country = models.CharField(verbose_name='Страна', max_length=50)
    shipping_city = models.CharField(verbose_name='Город',max_length=50)
    shipping_street = models.CharField(verbose_name='Улица',max_length=50)
    shipping_house = models.CharField(verbose_name='Дом',max_length=50)
    shipping_apartment = models.CharField(verbose_name='Квартира',max_length=50, blank=True)

    def __str__(self) -> str:
        return f'Order #{self.pk} ({self.status})'

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Список заказов'
        ordering = ('user', '-date',)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_info = models.ForeignKey(ProductInfo,on_delete=models.CASCADE, related_name='items')
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return f'Order #{self.order.id}.{self.pk}: {self.product_info.name} - {self.quantity}'

    class Meta:
        verbose_name = 'Позиция в заказе'
        verbose_name_plural = 'Позиции в заказах'
        ordering = ('order',)

#Хранение адресов в отдельной таблице, чтобы пользователь мог сохранять несколько штук и выбирать основной из них
#Как, например, в приложении озона
class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50)
    country = models.CharField(verbose_name='Страна', max_length=50)
    city = models.CharField(verbose_name='Город', max_length=50)
    street = models.CharField(verbose_name='Улица', max_length=50)
    house = models.CharField(verbose_name='Дом', max_length=50)
    apartment = models.CharField(verbose_name='Квартира', max_length=50, blank=True)
    is_default = models.BooleanField(default=False)

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