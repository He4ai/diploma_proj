# backend/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.validators import UniqueValidator
from .models import (
    Shop, Category, Product, ProductInfo,
    Parameter, ProductParameter,
    Order, OrderItem, Address
)

User = get_user_model()

class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ("id", "name", "url")


class CategorySerializer(serializers.ModelSerializer):
    # Для вывода полной информации о магазинах при выводе данных (get)
    shops = ShopSerializer(many=True, read_only=True)

    # Для вывода короткой информации (id) при вводе новых данных (put/patch)
    shop_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Shop.objects.all(),
        write_only=True,
        source="shops",
    )

    class Meta:
        model = Category
        fields = ("id", "name", "shops", "shop_ids")


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "category")


class ProductInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductInfo
        fields = ("id", "product", "shop", "name", "quantity", "price", "price_rrc")


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = ("id", "name")


class ProductParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductParameter
        fields = ("id", "product_info", "parameter", "value")


class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all(), message="Такой email уже зарегистрирован.")]
    )
    password = serializers.CharField(write_only=True)
    shop = serializers.PrimaryKeyRelatedField(
        queryset=Shop.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = User
        fields = ("id", "email", "password", "first_name", "last_name", "type", "shop")

    def validate(self, attrs):
        user_type = attrs.get("type", getattr(self.instance, "type", None))
        shop = attrs.get("shop", getattr(self.instance, "shop", None))

        # Проверка: если пользователь покупатель - нельзя привязать магазин; если продавец - нужно привязать магазин.
        if user_type == "buyer" and shop is not None:
            raise serializers.ValidationError({"shop": "Покупателю нельзя назначать магазин."})
        if user_type == "shop" and shop is None:
            raise serializers.ValidationError({"shop": "Для продавца нужно указать магазин."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ("id", "label", "country", "city", "street", "house", "apartment", "is_default")
        read_only_fields = ("id",)

    # Функция для снятия is_default = True с других адресов
    def _unset_other_defaults(self, user, address_id):
        Address.objects.filter(user=user, is_default=True).exclude(id=address_id).update(is_default=False)

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        make_default = validated_data.get("is_default", False)

        # если первый адрес - делаем его дефолтным
        if not Address.objects.filter(user=user).exists() and "is_default" not in validated_data:
            make_default = True
            validated_data["is_default"] = True

        # если новый адрес должен стать дефолтным - сбрасываем старый
        if make_default:
            Address.objects.filter(user=user, is_default=True).update(is_default=False)

        address = Address.objects.create(user=user, **validated_data)
        return address

    @transaction.atomic
    def update(self, instance, validated_data):
        user = self.context["request"].user

        if validated_data.get("is_default") is True:
            Address.objects.filter(user=user, is_default=True).exclude(id=instance.id).update(is_default=False)

        return super().update(instance, validated_data)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "product_info", "quantity", "price_at_purchase")
        read_only_fields = ("price_at_purchase",)

# Сериалайзер для оформления заказа (new-статус)
class OrderCheckoutSerializer(serializers.ModelSerializer):
    address_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Order
        fields = ("id", "address_id")

    def validate(self, attrs):
        user = self.context["request"].user
        order = self.instance

        # Если человек попытается повторно оформить уже оформленный заказ (у которого статус не Basket)
        if order.status != Order.Status.BASKET:
            raise serializers.ValidationError("Этот заказ уже оформлен.")

        address_id = attrs.get("address_id")
        # Проверка адреса, если пользователь указал его явно
        if address_id is not None:
            try:
                attrs["address"] = Address.objects.get(id=address_id, user=user)
            except Address.DoesNotExist:
                raise serializers.ValidationError({"address_id": "Адрес не найден."})
            return attrs

        # Проверка, сущестует ли дефолтный адрес, если пользователь не указал адрес явно
        try:
            attrs["address"] = Address.objects.get(user=user, is_default=True)
        except Address.DoesNotExist:
            raise serializers.ValidationError({"address_id": "Нет дефолтного адреса. Выберите адрес из списка."})

        return attrs

    def update(self, instance, validated_data):
        user = self.context["request"].user
        address = validated_data['address']
        instance.shipping_country = address.country
        instance.shipping_city = address.city
        instance.shipping_street = address.street
        instance.shipping_house = address.house
        instance.shipping_apartment = address.apartment
        instance.status = Order.Status.NEW
        instance.save()
        return instance

# Сериалайзер для корзины (ещё не оформленный заказ)
class BasketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "status", "date")

    def create(self, validated_data):
        user = self.context["request"].user
        basket, _ = Order.objects.get_or_create(user=user, status=Order.Status.BASKET)
        return basket