from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from backend.models import Address, Order, ShopOrder, OrderItem

User = get_user_model()


class ClientProfileSerializer(serializers.ModelSerializer):
    # type нельзя менять — поэтому read_only
    type = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "username", "first_name", "last_name", "type")
        read_only_fields = ("id", "email", "type")


class ClientProfileUpdateSerializer(serializers.ModelSerializer):
    # обновляем только это
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name")

    def validate_username(self, value):
        # username blank=True, значит можем принимать "" / None
        if value is None:
            return value
        return value.strip()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError({"old_password": "Неверный текущий пароль."})
        return attrs


class RequestEmailChangeSerializer(serializers.Serializer):
    new_email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )

    def validate_new_email(self, value):
        value = value.strip().lower()
        return value


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "label",
            "country",
            "city",
            "street",
            "house",
            "apartment",
            "is_default",
        )
        read_only_fields = ("id",)

    def validate_label(self, value):
        return value.strip()


class AddressCreateSerializer(AddressSerializer):
    """
    На создание тоже можно принимать is_default,
    но бизнес-логика решит сама (первый адрес всегда default).
    """
    pass


class AddressUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ("label", "country", "city", "street", "house", "apartment", "is_default")

    def validate(self, attrs):
        # Нельзя оставить пользователя с 0 default, если адреса есть
        request = self.context["request"]
        user = request.user
        addr: Address = self.instance

        # Если пытаются снять default с дефолтного
        if "is_default" in attrs and attrs["is_default"] is False and addr.is_default:
            # Есть ли другие адреса, которые будут default?
            others_default_exists = Address.objects.filter(user=user, is_default=True).exclude(id=addr.id).exists()
            if not others_default_exists:
                raise serializers.ValidationError(
                    {"is_default": "Нельзя снять дефолтность, пока не назначен другой адрес по умолчанию."}
                )

        return attrs

class ClientOrderListSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    shops_count = serializers.IntegerField(read_only=True)
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = ("id", "date", "status", "total", "shops_count", "items_count")


class ClientOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product_info.product.name", read_only=True)
    product_model = serializers.CharField(source="product_info.product.model", read_only=True)
    shop_name = serializers.CharField(source="shop_order.shop.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product_name", "product_model", "shop_name", "quantity", "price_at_purchase")


class ClientShopOrderSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    items = ClientOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShopOrder
        fields = ("id", "shop", "shop_name", "status", "items")


class ClientOrderDetailSerializer(serializers.ModelSerializer):
    shop_orders = ClientShopOrderSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "date",
            "status",
            "shipping_country",
            "shipping_city",
            "shipping_street",
            "shipping_house",
            "shipping_apartment",
            "shop_orders",
        )