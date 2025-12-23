from rest_framework import serializers
from django.db.models import Sum
from decimal import Decimal

from backend.models import Order, ShopOrder, OrderItem, ProductInfo, Address


class CartAddSerializer(serializers.Serializer):
    product_info_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_info_id(self, value):
        pi = ProductInfo.objects.select_related("shop", "product").filter(id=value).first()
        if not pi:
            raise serializers.ValidationError("Оффер (ProductInfo) не найден.")
        self.product_info = pi
        return value

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        pi = self.product_info
        add_qty = attrs["quantity"]
        if not pi.shop.state:
            raise serializers.ValidationError({"shop": "Магазин не принимает заказы."})

        if pi.quantity <= 0:
            raise serializers.ValidationError({"quantity": "Товара нет в наличии."})

        # текущая корзина (если нет — считаем что 0)
        basket = Order.objects.filter(user=user, status=Order.Status.BASKET).first()

        already = 0
        if basket:
            already = (
                OrderItem.objects.filter(
                    shop_order__order=basket,
                    product_info=pi
                ).aggregate(s=Sum("quantity"))["s"] or 0
            )

        available_to_add = pi.quantity - already
        if add_qty > available_to_add:
            raise serializers.ValidationError({
                "quantity": f"Недостаточно товара на складе. Доступно для добавления: {available_to_add}."
            })

        return attrs


class CartRemoveSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField()


class CheckoutSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(required=False)

    def validate_address_id(self, value):
        user = self.context["request"].user
        if not Address.objects.filter(id=value, user=user).exists():
            raise serializers.ValidationError("Адрес не найден.")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product_info.product.name", read_only=True)
    product_model = serializers.CharField(source="product_info.product.model", read_only=True)
    shop_id = serializers.IntegerField(source="product_info.shop.id", read_only=True)
    shop_name = serializers.CharField(source="product_info.shop.name", read_only=True)

    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_name",
            "product_model",
            "shop_id",
            "shop_name",
            "quantity",
            "price_at_purchase",
            "line_total",
        )

    def get_line_total(self, obj):
        return obj.price_at_purchase * obj.quantity


class ShopOrderCartSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShopOrder
        fields = ("id", "shop", "shop_name", "status", "items")


class BasketSerializer(serializers.ModelSerializer):
    shop_orders = ShopOrderCartSerializer(many=True, read_only=True)

    total_sum = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "date",
            "shipping_country",
            "shipping_city",
            "shipping_street",
            "shipping_house",
            "shipping_apartment",
            "shop_orders",
            "total_sum",
        )

    def get_total_sum(self, obj):
        total = Decimal("0.00")
        # obj.shop_orders и items обычно уже подтянуты, но даже если нет — ок.
        for so in obj.shop_orders.all():
            for item in so.items.all():
                total += item.price_at_purchase * item.quantity
        return total


class BasketSetAddressSerializer(serializers.Serializer):
    address_id = serializers.IntegerField()

    def validate_address_id(self, value):
        user = self.context["request"].user
        if not Address.objects.filter(id=value, user=user).exists():
            raise serializers.ValidationError("Адрес не найден.")
        return value