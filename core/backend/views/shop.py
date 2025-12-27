from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from rest_framework.exceptions import NotFound

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from backend.tasks import import_shop_yaml_task
from backend.models import Shop, ProductInfo, OrderItem, ShopOrder
from backend.serializers.shop import (
    ChangeShopInfoSerializer,
    ShopOrderSerializer,
    ChangeShopOrderStatusSerializer, ShopFullSerializer,
    ProductInfoCreateSerializer, ProductInfoUpdateSerializer,
    ProductInfoReadSerializer
)


def check_rights(request):
    if request.user.type != "shop":
        raise PermissionDenied("Это действие доступно только владельцу магазина.")
    return True

def get_shop(request) -> Shop:
    shop = Shop.objects.filter(user=request.user).first()
    if not shop:
        raise NotFound("Shop not found")
    return shop



class ImportShopInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        check_rights(request)
        shop = get_shop(request)

        url = request.data.get("url")
        if not url:
            return Response(
                {"success": False, "error": "Не указан url"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            URLValidator()(url)
        except ValidationError as e:
            return Response(
                {"success": False, "error": e.message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Логика перенесена в таск
        import_shop_yaml_task.delay(shop.id, url)

        return Response(
            {
                "success": True,
                "message": "Импорт поставлен в очередь и будет выполнен асинхронно",
            },
            status=status.HTTP_202_ACCEPTED,
        )

class GetOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id=None, *args, **kwargs):
        check_rights(request)

        shop = get_shop(request)

        items_qs = (
            OrderItem.objects
            .select_related("product_info__product")
            .order_by("id")
        )

        qs = (
            ShopOrder.objects
            .filter(shop=shop)
            .select_related("order")
            .exclude(order__status="basket")
            .exclude(status=ShopOrder.Status.BASKET)
            .prefetch_related(Prefetch("items", queryset=items_qs))
            .order_by("-order__date")
        )

        if order_id:
            qs = qs.filter(order_id=order_id)

        serializer = ShopOrderSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangeOrderStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id=None, *args, **kwargs):
        check_rights(request)

        shop = get_shop(request)

        if not order_id:
            return Response({"detail": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        shop_order = ShopOrder.objects.filter(order_id=order_id, shop=shop).first()
        if not shop_order:
            return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ChangeShopOrderStatusSerializer(data=request.data, context={"shop_order": shop_order})
        serializer.is_valid(raise_exception=True)

        shop_order.status = serializer.validated_data["status"]
        shop_order.save(update_fields=["status"])

        return Response({"success": True, "status": shop_order.status}, status=status.HTTP_200_OK)


class ChangeShopInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        check_rights(request)
        shop = get_shop(request)

        serializer = ChangeShopInfoSerializer(instance=shop, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        shop = serializer.save()
        return Response(
            {"success": True, "shop_data": ShopFullSerializer(shop).data},
            status=status.HTTP_200_OK,
        )

    def get(self, request, *args, **kwargs):
        check_rights(request)
        shop = get_shop(request)

        return Response(
            {"success": True, "shop_data": ShopFullSerializer(shop).data},
            status=status.HTTP_200_OK,
        )


class ProductInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None, *args, **kwargs):
        check_rights(request)
        shop = get_shop(request)

        qs = (
            ProductInfo.objects
            .filter(shop=shop)
            .select_related("product", "product__category")
            .prefetch_related("parameters__parameter")
            .order_by("-id")
        )

        # деталка
        if pk is not None:
            obj = qs.filter(id=pk).first()
            if not obj:
                return Response({"detail": "ProductInfo not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(ProductInfoReadSerializer(obj).data, status=status.HTTP_200_OK)

        # список
        return Response(ProductInfoReadSerializer(qs, many=True).data, status=status.HTTP_200_OK)

    # Создание нового ProductInfo (и, возможно, Product)
    # Ожидаем данные:
    # {
    #   "name": str (только на случай, если в Product нет продукта с таким model)
    #   "category": id (только на случай, если в Product нет продукта с таким model)
    #   "model": slug
    #   "external_id": id
    #   "quantity": int
    #   "price": decimal
    #   "price_rrc": decimal
    #   "parameters": [{"name": "value"},]
    #}
    def post(self, request, *args, **kwargs):
        check_rights(request)
        shop = get_shop(request)

        serializer = ProductInfoCreateSerializer(
            data=request.data,
            context={"shop": shop},
        )
        serializer.is_valid(raise_exception=True)
        product_info = serializer.save()

        return Response(
            {"success": True, "id": product_info.id},
            status=status.HTTP_201_CREATED,
        )


    # Удаление старого ProductInfo
    def delete(self, request, pk, *args, **kwargs):
        check_rights(request)
        shop = get_shop(request)

        product_info = ProductInfo.objects.filter(id=pk, shop=shop).first()
        if not product_info:
            return Response({"detail": "ProductInfo not found"}, status=status.HTTP_404_NOT_FOUND)

        product_info.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Изменение старого ProductInfo
    def patch(self, request, pk, *args, **kwargs):
        check_rights(request)
        shop = get_shop(request)

        product_info = ProductInfo.objects.filter(id=pk, shop=shop).first()
        if not product_info:
            return Response({"detail": "ProductInfo not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductInfoUpdateSerializer(
            instance=product_info,
            data=request.data,
            partial=True,
            context={"shop": shop},
        )
        serializer.is_valid(raise_exception=True)
        product_info = serializer.save()

        return Response(
            {"success": True, "id": product_info.id},
            status=status.HTTP_200_OK,
        )


