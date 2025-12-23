from django.db.models import Min, Max, Count
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from backend.models import Product, ProductInfo, Shop
from backend.serializers.general import ProductSerializer, ProductInfoCatalogSerializer, ShopPublicSerializer
from backend.filters.general import ProductFilter, ProductInfoFilter

# Все продукты-эталоны
class ProductListAPIView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductFilter

    # Сортировки для списка продуктов (по имени, по минимальной цене и т.п.)
    ordering_fields = ["name", "model", "min_price", "max_price", "offers_count"]
    ordering = ["name"]

    def get_queryset(self):
        return (
            Product.objects
            .select_related("category")
            .annotate(
                min_price=Min("offers__price"),
                max_price=Max("offers__price"),
                offers_count=Count("offers", distinct=True),
            )
        )


class CatalogOfferListAPIView(ListAPIView):
    """
    2) Витрина офферов (ProductInfo) — то, что реально продается.
    Фильтры: цена, категория, магазин, model-слиг, поиск.
    Сортировки: price / quantity / и т.д.
    """
    permission_classes = [AllowAny]
    serializer_class = ProductInfoCatalogSerializer

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductInfoFilter

    # ordering=price или -price
    ordering_fields = ["price", "quantity", "price_rrc", "external_id"]
    ordering = ["price"]

    def get_queryset(self):
        return (
            ProductInfo.objects
            .select_related("shop", "product", "product__category")
            .prefetch_related("parameters__parameter")
            .filter(quantity__gt=0)
            .filter(shop__state=True)
        )

# Публичный профиль магазина
class ShopPublicDetailAPIView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ShopPublicSerializer
    lookup_url_kwarg = "shop_id"

    def get_queryset(self):
        return (
            Shop.objects
            .prefetch_related("categories")
            .annotate(
                offers_count=Count("offers", distinct=True),
                min_price=Min("offers__price"),
                max_price=Max("offers__price"),
            )
        )

# Публичные товары/офферы конкретного магазина
class ShopPublicOffersAPIView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductInfoCatalogSerializer
    lookup_url_kwarg = "shop_id"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductInfoFilter
    ordering_fields = ["price", "quantity", "price_rrc", "external_id"]
    ordering = ["price"]

    def get_queryset(self):
        shop_id = self.kwargs["shop_id"]
        return (
            ProductInfo.objects
            .select_related("shop", "product", "product__category")
            .prefetch_related("parameters__parameter")
            .filter(shop_id=shop_id)
            .filter(quantity__gt=0)
            .filter(shop__state=True)
        )