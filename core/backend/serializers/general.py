from rest_framework import serializers
from django.db.models import Min, Max
from backend.models import ProductParameter


from backend.models import Product, ProductInfo, Shop, Category


class ShopShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ("id", "name", "url")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    offers_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = ("id", "name", "description", "model", "category", "min_price", "max_price", "offers_count")

class ProductParameterCatalogSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="parameter.name", read_only=True)

    class Meta:
        model = ProductParameter
        fields = ("name", "value")

class ProductInfoCatalogSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_model = serializers.CharField(source="product.model", read_only=True)
    category_id = serializers.IntegerField(source="product.category.id", read_only=True)
    category_name = serializers.CharField(source="product.category.name", read_only=True)
    product_description = serializers.CharField(source="product.description", read_only=True)

    shop = ShopShortSerializer(read_only=True)

    parameters = ProductParameterCatalogSerializer(many=True, read_only=True)

    class Meta:
        model = ProductInfo
        fields = (
            "id",
            "product_id",
            "product_name",
            "product_description",
            "product_model",
            "category_id",
            "category_name",
            "shop",
            "external_id",
            "quantity",
            "price",
            "price_rrc",
            "parameters",
        )


class ShopPublicSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)

    offers_count = serializers.IntegerField(read_only=True)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Shop
        fields = ("id", "name", "url", "state", "categories", "offers_count", "min_price", "max_price")
