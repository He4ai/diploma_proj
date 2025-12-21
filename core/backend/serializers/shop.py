from rest_framework import serializers
from backend.models import ShopOrder, OrderItem, Shop


class ShopStatusSerializer(serializers.Serializer):
    status = serializers.BooleanField()

    def validate(self, attrs):
        shop = self.context.get("shop")
        if not shop:
            raise serializers.ValidationError("Shop not found")

        new_status = attrs["status"]
        if shop.state == new_status:
            self._no_change = True

        return attrs


class ShopOrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product_info.product_id", read_only=True)
    product_name = serializers.CharField(source="product_info.product.name", read_only=True)
    product_model = serializers.CharField(source="product_info.product.model", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_id",
            "product_name",
            "product_model",
            "quantity",
            "price_at_purchase",
        )


class ShopOrderSerializer(serializers.ModelSerializer):
    # поля заказа (Order) — вытягиваем через source="order...."
    order_id = serializers.IntegerField(source="order.id", read_only=True)
    date = serializers.DateTimeField(source="order.date", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)

    shipping_country = serializers.CharField(source="order.shipping_country", read_only=True)
    shipping_city = serializers.CharField(source="order.shipping_city", read_only=True)
    shipping_street = serializers.CharField(source="order.shipping_street", read_only=True)
    shipping_house = serializers.CharField(source="order.shipping_house", read_only=True)
    shipping_apartment = serializers.CharField(source="order.shipping_apartment", read_only=True)

    items = ShopOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShopOrder
        fields = (
            "id",
            "order_id",
            "date",
            "order_status",
            "status",  # статус подзаказа магазина
            "shipping_country",
            "shipping_city",
            "shipping_street",
            "shipping_house",
            "shipping_apartment",
            "items",
        )


class ChangeShopOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ShopOrder.Status.choices)
