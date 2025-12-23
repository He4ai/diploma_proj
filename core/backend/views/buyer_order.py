from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum
from backend.models import ProductInfo

from backend.models import Order, ShopOrder, OrderItem, Address
from backend.serializers.buyer_order import (
    BasketSerializer,
    CartAddSerializer,
    CartRemoveSerializer,
    CheckoutSerializer,
    BasketSetAddressSerializer
)


def _require_buyer(request):
    if not request.user.is_authenticated:
        return
    if getattr(request.user, "type", None) != "buyer":
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("Доступно только пользователю-покупателю.")


def _get_or_create_basket(user) -> Order:
    basket = Order.objects.filter(user=user, status=Order.Status.BASKET).first()
    if basket:
        return basket
    return Order.objects.create(user=user, status=Order.Status.BASKET)

def _apply_address_to_order(order: Order, addr: Address) -> None:
    order.shipping_country = addr.country
    order.shipping_city = addr.city
    order.shipping_street = addr.street
    order.shipping_house = addr.house
    order.shipping_apartment = addr.apartment or ""
    order.save(update_fields=[
        "shipping_country", "shipping_city", "shipping_street", "shipping_house", "shipping_apartment"
    ])


def _ensure_basket_has_address(basket: Order) -> None:
    # Если в корзине адрес еще не заполнен - вставляем дефолт
    if basket.shipping_country or basket.shipping_city or basket.shipping_street or basket.shipping_house:
        return

    addr = Address.objects.filter(user=basket.user, is_default=True).first()
    if addr:
        _apply_address_to_order(basket, addr)


def _format_address(order: Order) -> str:
    parts = [order.shipping_country, order.shipping_city, order.shipping_street, order.shipping_house]
    addr = ", ".join([p for p in parts if p])
    if order.shipping_apartment:
        addr += f", кв. {order.shipping_apartment}"
    return addr or "(адрес не указан)"


def _send_shop_invoice(shop_order: ShopOrder):
    shop = shop_order.shop
    to_email = getattr(shop.user, "email", None) if shop.user else None
    if not to_email:
        return

    order = shop_order.order
    address = _format_address(order)

    lines = []
    total = 0
    items = shop_order.items.select_related("product_info__product")
    for item in items:
        line_sum = item.quantity * item.price_at_purchase
        total += line_sum
        lines.append(f"- {item.product_info.product.name} ({item.product_info.product.model}) x{item.quantity} = {line_sum}")

    subject = f"Накладная: заказ #{order.id} — магазин {shop.name}"
    body = (
        f"Заказ: #{order.id}\n"
        f"Магазин: {shop.name}\n"
        f"Адрес доставки: {address}\n\n"
        f"Позиции:\n" + "\n".join(lines) + "\n\n"
        f"Итого: {total}\n"
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[to_email],
        fail_silently=False,
    )


def _send_buyer_confirmation(order: Order):
    to_email = getattr(order.user, "email", None)
    if not to_email:
        return

    address = _format_address(order)
    subject = f"Заказ #{order.id} принят"

    total = 0
    lines = []
    shop_orders = order.shop_orders.select_related("shop").prefetch_related("items__product_info__product")
    for so in shop_orders:
        lines.append(f"\nМагазин: {so.shop.name}")
        for item in so.items.all():
            line_sum = item.quantity * item.price_at_purchase
            total += line_sum
            lines.append(f"- {item.product_info.product.name} x{item.quantity} = {line_sum}")

    lines_text = "\n".join(lines)

    body = (
        f"Ваш заказ #{order.id} принят.\n"
        f"Адрес доставки: {address}\n"
        f"{lines_text}\n"
        f"Итого по заказу: {total}\n"
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[to_email],
        fail_silently=False,
    )

def _send_admin_invoice(order: Order):
    if not settings.ADMINS:
        return

    admin_emails = [email for _, email in settings.ADMINS]

    address = _format_address(order)

    total = 0
    lines = []

    shop_orders = order.shop_orders.select_related("shop").prefetch_related(
        "items__product_info__product"
    )

    for so in shop_orders:
        lines.append(f"\nМагазин: {so.shop.name}")
        for item in so.items.all():
            line_sum = item.quantity * item.price_at_purchase
            total += line_sum
            lines.append(
                f"- {item.product_info.product.name} "
                f"({item.product_info.product.model}) "
                f"x{item.quantity} = {line_sum}"
            )
    lines_text = "\n".join(lines)
    body = (
        f"Новая накладная по заказу #{order.id}\n\n"
        f"Покупатель: {order.user.email}\n"
        f"Адрес доставки: {address}\n"
        f"{lines_text}\n"
        f"Итого: {total}"
    )

    send_mail(
        subject=f"Накладная по заказу #{order.id}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=admin_emails,
        fail_silently=False,
    )


class BasketAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_buyer(request)
        basket = _get_or_create_basket(request.user)
        _ensure_basket_has_address(basket)
        return Response(BasketSerializer(basket).data)


class BasketAddAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_buyer(request)

        s = CartAddSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)

        product_info = s.product_info
        quantity = s.validated_data["quantity"]

        basket = _get_or_create_basket(request.user)

        shop_order, _ = ShopOrder.objects.get_or_create(
            order=basket,
            shop=product_info.shop,
            defaults={"status": ShopOrder.Status.BASKET},
        )

        item, created = OrderItem.objects.get_or_create(
            shop_order=shop_order,
            product_info=product_info,
            defaults={"quantity": quantity, "price_at_purchase": product_info.price},
        )
        if not created:
            item.quantity = F("quantity") + quantity
            item.price_at_purchase = product_info.price
            item.save(update_fields=["quantity", "price_at_purchase"])
            item.refresh_from_db()

        return Response(BasketSerializer(basket).data, status=status.HTTP_200_OK)


class BasketRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_buyer(request)

        s = CartRemoveSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        basket = _get_or_create_basket(request.user)

        item = (
            OrderItem.objects
            .select_related("shop_order", "shop_order__order")
            .filter(id=s.validated_data["order_item_id"], shop_order__order=basket)
            .first()
        )
        if not item:
            return Response({"detail": "Позиция не найдена в корзине."}, status=status.HTTP_404_NOT_FOUND)

        shop_order = item.shop_order
        item.delete()

        if not shop_order.items.exists():
            shop_order.delete()

        return Response(BasketSerializer(basket).data, status=status.HTTP_200_OK)


class CheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_buyer(request)

        basket = _get_or_create_basket(request.user)

        if not basket.shop_orders.exists():
            return Response({"detail": "Корзина пуста."}, status=status.HTTP_400_BAD_REQUEST)

        s = CheckoutSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)

        # Адрес доставки: address_id > уже выбранный в basket > default
        address_id = s.validated_data.get("address_id")

        def _basket_has_address(o: Order) -> bool:
            return bool(o.shipping_country and o.shipping_city and o.shipping_street and o.shipping_house)

        def _apply_address(o: Order, a: Address) -> None:
            o.shipping_country = a.country
            o.shipping_city = a.city
            o.shipping_street = a.street
            o.shipping_house = a.house
            o.shipping_apartment = a.apartment or ""
            o.save(update_fields=[
                "shipping_country", "shipping_city", "shipping_street", "shipping_house", "shipping_apartment"
            ])

        if address_id is not None:
            addr = Address.objects.filter(id=address_id, user=request.user).first()
            if not addr:
                return Response({"detail": "Адрес не найден."}, status=status.HTTP_400_BAD_REQUEST)
            _apply_address(basket, addr)
        else:
            # если пользователь раньше уже выбирал адрес для корзины — оставляем как есть
            if not _basket_has_address(basket):
                addr = Address.objects.filter(user=request.user, is_default=True).first()
                if not addr:
                    return Response(
                        {"detail": "Адрес доставки не выбран и нет адреса по умолчанию."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                _apply_address(basket, addr)

        # Собираем, сколько какого ProductInfo нужно списать
        # (prefetch по items, чтобы не плодить запросы)
        shop_orders = basket.shop_orders.prefetch_related("items")

        # Проверяем, что все магазины всё ещё принимают заказы
        bad_shop = basket.shop_orders.select_related("shop").filter(shop__state=False).first()
        if bad_shop:
            return Response(
                {
                    "detail": f"Магазин '{bad_shop.shop.name}' сейчас не принимает заказы. Удалите его товары из корзины."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        need_map = {}  # product_info_id -> total_qty
        for so in shop_orders:
            for item in so.items.all():
                need_map[item.product_info_id] = need_map.get(item.product_info_id, 0) + item.quantity

        if not need_map:
            return Response({"detail": "Корзина пуста."}, status=status.HTTP_400_BAD_REQUEST)

        # Лочим ProductInfo и проверяем остатки, потом списываем
        product_infos = (
            ProductInfo.objects
            .select_for_update()
            .filter(id__in=list(need_map.keys()))
        )
        pi_by_id = {pi.id: pi for pi in product_infos}

        missing = set(need_map.keys()) - set(pi_by_id.keys())
        if missing:
            return Response({"detail": "Некоторые товары больше недоступны."}, status=status.HTTP_400_BAD_REQUEST)

        # проверка
        for pi_id, need_qty in need_map.items():
            pi = pi_by_id[pi_id]
            if pi.quantity < need_qty:
                return Response(
                    {
                        "detail": "Недостаточно товара на складе.",
                        "product_info_id": pi_id,
                        "available": pi.quantity,
                        "requested": need_qty,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # списание
        for pi_id, need_qty in need_map.items():
            pi = pi_by_id[pi_id]
            pi.quantity -= need_qty
            pi.save(update_fields=["quantity"])

        # Меняем статусы заказа и подзаказов
        basket.status = Order.Status.PLACED
        basket.save(update_fields=["status"])

        ShopOrder.objects.filter(order=basket).update(status=ShopOrder.Status.PROCESSING)

        # Создаём новую пустую корзину (и сразу подставляем default-адрес, если есть)
        new_basket = Order.objects.create(user=request.user, status=Order.Status.BASKET)
        _ensure_basket_has_address(new_basket)

        # Письма
        for so in basket.shop_orders.select_related("shop", "shop__user").prefetch_related("items__product_info__product"):
            _send_shop_invoice(so)
        _send_buyer_confirmation(basket)
        _send_admin_invoice(basket)

        return Response({"success": True, "order_id": basket.id}, status=status.HTTP_200_OK)

class BasketSetAddressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _require_buyer(request)

        basket = _get_or_create_basket(request.user)

        s = BasketSetAddressSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)

        addr = Address.objects.get(id=s.validated_data["address_id"], user=request.user)
        _apply_address_to_order(basket, addr)

        return Response(BasketSerializer(basket).data, status=status.HTTP_200_OK)
