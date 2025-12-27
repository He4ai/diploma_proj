from django.db.models import Min, Max, Count
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from backend.models import Product, ProductInfo, Shop
from backend.serializers.general import ProductSerializer, ProductInfoCatalogSerializer, ShopPublicSerializer
from backend.filters.general import ProductFilter, ProductInfoFilter
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


# Все продукты-эталоны
@extend_schema(
    summary="Список продуктов (эталоны)",
    description=(
        "Возвращает список продуктов-эталонов (Product).\n\n"
        "Дополнительно считает агрегаты по офферам (ProductInfo):\n"
        "- min_price: минимальная цена среди офферов\n"
        "- max_price: максимальная цена среди офферов\n"
        "- offers_count: количество офферов\n\n"
        "Поддерживает фильтрацию (DjangoFilterBackend) и сортировку (OrderingFilter)."
    ),
    responses={
        200: ProductSerializer(many=True),
    },
)
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

@extend_schema(
    summary="Каталог офферов (витрина товаров)",
    description=(
        "Витрина офферов (ProductInfo) — то, что реально продаётся.\n\n"
        "Возвращаются только доступные офферы:\n"
        "- quantity > 0\n"
        "- shop.state = True (магазин принимает заказы)\n\n"
        "Поддерживает фильтры и сортировку."
    ),
    responses={
        200: ProductInfoCatalogSerializer(many=True),
    },
)
class CatalogOfferListAPIView(ListAPIView):
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
@extend_schema(
    summary="Публичный профиль магазина",
    description=(
        "Возвращает публичную информацию о магазине.\n\n"
        "Дополнительно считает агрегаты по офферам:\n"
        "- offers_count\n"
        "- min_price\n"
        "- max_price"
    ),
    parameters=[
        OpenApiParameter(
            name="shop_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            required=True,
            description="ID магазина",
        )
    ],
    responses={
        200: ShopPublicSerializer,
        404: OpenApiResponse(description="Магазин не найден"),
    },
)
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
@extend_schema(
    summary="Публичные офферы магазина",
    description=(
        "Список офферов (ProductInfo) конкретного магазина.\n\n"
        "Возвращаются только доступные офферы:\n"
        "- quantity > 0\n"
        "- shop.state = True\n\n"
        "Поддерживает фильтры и сортировку."
    ),
    parameters=[
        OpenApiParameter(
            name="shop_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            required=True,
            description="ID магазина",
        )
    ],
    responses={
        200: ProductInfoCatalogSerializer(many=True),
        404: OpenApiResponse(description="Магазин не найден"),
    },
)
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