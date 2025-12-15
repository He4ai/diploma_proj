from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.contrib.auth.base_user import BaseUserManager

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
    phone = models.CharField(max_length=11, unique=True)
    company = models.CharField(verbose_name = 'Компания', max_length=100, blank=True)
    type = models.CharField(verbose_name = 'Тип пользователя', max_length=50, blank=True)

    def __str__(self):
        return f'{self.email}: {self.first_name} {self.last_name}'


class Shop(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField()

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=200)
    shops = models.ManyToManyField(Shop, related_name='categories')

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')

    def __str__(self) -> str:
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_rrc = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return self.name


class Parameter(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self) -> str:
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, related_name='product_parameters', on_delete=models.CASCADE)
    value = models.CharField(max_length=50)

class Order(models.Model):
    class Status(models.TextChoices):
        BASKET = 'basket', 'статус корзины'
        NEW = 'new', 'новый'
        CONFIRMED = 'confirmed', 'подтвержден'
        ASSEMBLED = 'assembled', 'собран'
        SENT = 'sent', 'отправлен'
        DELIVERED = 'delivered', 'доставлен'
        CANCELED = 'canceled', 'отменен'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)
    status = models.CharField(choices=Status.choices, default=Status.BASKET, max_length=10)
    shipping_country = models.CharField(verbose_name='Страна', max_length=50)
    shipping_city = models.CharField(verbose_name='Город',max_length=50)
    shipping_street = models.CharField(verbose_name='Улица',max_length=50)
    shipping_house = models.CharField(verbose_name='Дом',max_length=50)
    shipping_apartment = models.CharField(verbose_name='Квартира',max_length=50, blank=True)

    def __str__(self) -> str:
        return f'Order #{self.pk} ({self.status})'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product_info = models.ForeignKey(ProductInfo, related_name='items', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return f'Order #{self.order}.{self.pk}: {self.product_info.name} - {self.quantity}'

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







