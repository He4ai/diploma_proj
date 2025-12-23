import django_filters
from django.db.models import Q

from backend.models import Product, ProductInfo


class ProductFilter(django_filters.FilterSet):
    # Поиск по имени продукта
    search = django_filters.CharFilter(method="filter_search")

    # по model-slug (точно или частично)
    model = django_filters.CharFilter(field_name="model", lookup_expr="iexact")
    model_contains = django_filters.CharFilter(field_name="model", lookup_expr="icontains")

    category = django_filters.NumberFilter(field_name="category_id")

    class Meta:
        model = Product
        fields = ("category", "model", "model_contains", "search")

    def filter_search(self, qs, name, value):
        value = value.strip()
        if not value:
            return qs
        return qs.filter(Q(name__icontains=value) | Q(model__icontains=value))


class ProductInfoFilter(django_filters.FilterSet):
    # Цена от/до
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    # Категория (берем из product.category)
    category = django_filters.NumberFilter(field_name="product__category_id")

    # Магазин
    shop = django_filters.NumberFilter(field_name="shop_id")

    # Фильтр по "модели"
    model = django_filters.CharFilter(field_name="product__model", lookup_expr="iexact")
    model_contains = django_filters.CharFilter(field_name="product__model", lookup_expr="icontains")

    # поиск по названию/модели
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = ProductInfo
        fields = ("price_min", "price_max", "category", "shop", "model", "model_contains", "search")

    def filter_search(self, qs, name, value):
        value = value.strip()
        if not value:
            return qs
        return qs.filter(
            Q(product__name__icontains=value) |
            Q(product__model__icontains=value) |
            Q(shop__name__icontains=value)
        )
