from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch

import requests
from yaml import safe_load
from yaml.error import YAMLError

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from backend.models import Shop, Category, ProductInfo, Product, Parameter, ProductParameter, OrderItem, ShopOrder
from backend.serializers.shop import (
    ShopStatusSerializer,
    ShopOrderSerializer,
    ChangeShopOrderStatusSerializer,
)


def check_rights(request):
    if request.user.type != "shop":
        raise PermissionDenied("Только владелец магазина может импортировать каталог.")


class ImportShopInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        check_rights(request)

        url = request.data.get("url")
        if not url:
            return Response({"success": False, "errors": "Не указаны аргументы"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            URLValidator()(url)
        except ValidationError as e:
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)

        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            return Response({"error": f"Не удалось скачать файл: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = safe_load(resp.content)
        except YAMLError:
            return Response({"error": "Файл не является корректным YAML."}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(data, dict):
            return Response({"error": "Некорректная структура YAML."}, status=status.HTTP_400_BAD_REQUEST)

        required = ("shop", "categories", "goods")
        for k in required:
            if k not in data:
                return Response({"error": f"В YAML нет ключа '{k}'."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # магазин привязываем к текущему пользователю-владельцу
            shop, _ = Shop.objects.get_or_create(
                user=request.user,
                defaults={"name": data["shop"], "url": url},
            )
            # если магазин уже есть обновление имени/урла
            updated = False
            if shop.name != data["shop"]:
                shop.name = data["shop"]
                updated = True
            if shop.url != url:
                shop.url = url
                updated = True
            if updated:
                shop.save(update_fields=["name", "url"])

            # категории
            for c in data["categories"]:
                cid = c.get("id")
                cname = c.get("name")
                if cid is None or not cname:
                    continue

                category_obj, created = Category.objects.get_or_create(
                    id=cid,
                    defaults={"name": cname},
                )
                if not created and category_obj.name != cname:
                    category_obj.name = cname
                    category_obj.save(update_fields=["name"])

                category_obj.shops.add(shop)

            # полностью очищаем офферы магазина и их параметры
            ProductInfo.objects.filter(shop=shop).delete()

            # товары
            for item in data["goods"]:
                model = item.get("model")
                name = item.get("name")
                category_id = item.get("category")

                if not model or not name or not category_id:
                    continue

                product, _ = Product.objects.get_or_create(
                    model=model,
                    defaults={"name": name, "category_id": category_id},
                )

                # если товар был создан раньше, но название/категория поменялись - обновление
                p_updated = False
                if product.name != name:
                    product.name = name
                    p_updated = True
                if product.category_id != category_id:
                    product.category_id = category_id
                    p_updated = True
                if p_updated:
                    product.save(update_fields=["name", "category"])

                product_info = ProductInfo.objects.create(
                    product=product,
                    shop=shop,
                    external_id=item.get("id", 0),
                    quantity=item.get("quantity", 0),
                    price=item.get("price", 0),
                    price_rrc=item.get("price_rrc", 0),
                )

                params = item.get("parameters") or {}
                if isinstance(params, dict):
                    for pname, pvalue in params.items():
                        param_obj, _ = Parameter.objects.get_or_create(name=str(pname))
                        ProductParameter.objects.create(
                            product_info=product_info,
                            parameter=param_obj,
                            value=str(pvalue),
                        )

        return Response({"success": True}, status=status.HTTP_201_CREATED)


class ChangeShopStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        check_rights(request)

        shop = Shop.objects.filter(user=request.user).first()
        if not shop:
            return Response({"detail": "Shop not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ShopStatusSerializer(data=request.data, context={"request": request, "shop": shop})
        serializer.is_valid(raise_exception=True)

        if getattr(serializer, "_no_change", False):
            return Response(
                {"success": True, "detail": "Статус уже был таким"},
                status=status.HTTP_200_OK
            )

        shop.state = serializer.validated_data["status"]
        shop.save(update_fields=["state"])
        return Response({"success": True}, status=status.HTTP_200_OK)


class GetOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id=None, *args, **kwargs):
        check_rights(request)

        shop = Shop.objects.filter(user=request.user).first()
        if not shop:
            return Response({"detail": "Shop not found"}, status=status.HTTP_404_NOT_FOUND)

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

    def post(self, request, order_id=None, *args, **kwargs):
        check_rights(request)

        shop = Shop.objects.filter(user=request.user).first()
        if not shop:
            return Response({"detail": "Shop not found"}, status=status.HTTP_404_NOT_FOUND)

        if not order_id:
            return Response({"detail": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        shop_order = ShopOrder.objects.filter(order_id=order_id, shop=shop).first()
        if not shop_order:
            return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ChangeShopOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shop_order.status = serializer.validated_data["status"]
        shop_order.save(update_fields=["status"])

        return Response({"success": True, "status": shop_order.status}, status=status.HTTP_200_OK)
