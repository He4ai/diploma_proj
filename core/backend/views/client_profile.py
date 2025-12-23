from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.db.models import Sum, F, Count

from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from backend.models import Address, Order

from backend.serializers.client_profile import (
    ClientProfileSerializer,
    ClientProfileUpdateSerializer,
    ChangePasswordSerializer,
    RequestEmailChangeSerializer,
    AddressSerializer,
    AddressCreateSerializer,
    AddressUpdateSerializer, ClientOrderDetailSerializer, ClientOrderListSerializer,
)

User = get_user_model()
signer = TimestampSigner()


def _build_absolute(request, path: str) -> str:
    return request.build_absolute_uri(path)


def _ensure_single_default_address(user):
    # Если у пользователя есть адреса - ровно 1 дефолтный
    qs = Address.objects.filter(user=user)
    if not qs.exists():
        return

    if qs.filter(is_default=True).count() == 1:
        return

    # если 0 или >1 — фиксируем: делаем дефолтным самый новый (макс id)
    newest = qs.order_by("-id").first()
    Address.objects.filter(user=user).update(is_default=False)
    Address.objects.filter(id=newest.id).update(is_default=True)


class ClientProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ClientProfileSerializer(request.user).data)

    def patch(self, request):
        s = ClientProfileUpdateSerializer(instance=request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(ClientProfileSerializer(request.user).data, status=status.HTTP_200_OK)


class ClientChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ChangePasswordSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)

        request.user.set_password(s.validated_data["new_password"])
        request.user.save(update_fields=["password"])

        return Response({"success": True}, status=status.HTTP_200_OK)


class ClientRequestEmailChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = RequestEmailChangeSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        new_email = s.validated_data["new_email"]

        # payload: uid + new_email
        uidb64 = urlsafe_base64_encode(force_bytes(request.user.pk))
        signed = signer.sign(f"{uidb64}:{new_email}")  # timestamp inside signer

        confirm_link = _build_absolute(request, f"/api/client/profile/email/confirm/{signed}/")

        send_mail(
            subject="Подтверждение смены email",
            message=(
                "Привет!\n"
                "Ты запросил смену email. Подтверди по ссылке:\n"
                f"{confirm_link}\n\n"
                "Если это был не ты — просто игнорируй письмо."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[new_email],
            fail_silently=False,
        )

        return Response({"success": True}, status=status.HTTP_200_OK)


class ClientConfirmEmailChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, signed, *args, **kwargs):

        try:
            raw = signer.unsign(signed, max_age=60 * 60 * 24)  # 24 часа
        except SignatureExpired:
            return Response({"success": False, "message": "Ссылка истекла."}, status=status.HTTP_400_BAD_REQUEST)
        except BadSignature:
            return Response({"success": False, "message": "Некорректная ссылка."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uidb64, new_email = raw.split(":", 1)
            uid = force_str(urlsafe_base64_decode(uidb64))
        except Exception:
            return Response({"success": False, "message": "Некорректные данные ссылки."}, status=status.HTTP_400_BAD_REQUEST)

        # подтверждать может только тот же пользователь
        if str(request.user.pk) != str(uid):
            return Response({"success": False, "message": "Это не ваша ссылка подтверждения."}, status=status.HTTP_403_FORBIDDEN)

        new_email = new_email.strip().lower()

        # проверка уникальности
        if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            return Response({"success": False, "message": "Этот email уже занят."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.email = new_email
        request.user.save(update_fields=["email"])
        return Response({"success": True, "message": "Email обновлён."}, status=status.HTTP_200_OK)


class ClientAddressListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Address.objects.filter(user=request.user).order_by("-is_default", "-id")
        return Response(AddressSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        s = AddressCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        has_any = Address.objects.filter(user=request.user).exists()
        want_default = bool(s.validated_data.get("is_default", False))

        addr = Address.objects.create(user=request.user, **s.validated_data)

        # правило: первый адрес всегда default
        if not has_any:
            Address.objects.filter(user=request.user).update(is_default=False)
            Address.objects.filter(id=addr.id).update(is_default=True)

        # если адрес не первый, но попросили default — делаем его единственным default
        elif want_default:
            Address.objects.filter(user=request.user).update(is_default=False)
            Address.objects.filter(id=addr.id).update(is_default=True)

        # если не попросили default — оставляем как есть (старый default остаётся)

        _ensure_single_default_address(request.user)

        addr.refresh_from_db()
        return Response(AddressSerializer(addr).data, status=status.HTTP_201_CREATED)


class ClientAddressDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, address_id) -> Address:
        return Address.objects.filter(id=address_id, user=request.user).first()

    def get(self, request, address_id):
        addr = self.get_object(request, address_id)
        if not addr:
            return Response({"detail": "Адрес не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AddressSerializer(addr).data)

    @transaction.atomic
    def patch(self, request, address_id):
        addr = self.get_object(request, address_id)
        if not addr:
            return Response({"detail": "Адрес не найден."}, status=status.HTTP_404_NOT_FOUND)

        s = AddressUpdateSerializer(instance=addr, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        updated = s.save()

        # если сделали default=True -> сбрасываем остальные
        if request.data.get("is_default") is True or request.data.get("is_default") == "true":
            Address.objects.filter(user=request.user).exclude(id=updated.id).update(is_default=False)
            Address.objects.filter(id=updated.id).update(is_default=True)

        _ensure_single_default_address(request.user)
        updated.refresh_from_db()
        return Response(AddressSerializer(updated).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def delete(self, request, address_id):
        addr = self.get_object(request, address_id)
        if not addr:
            return Response({"detail": "Адрес не найден."}, status=status.HTTP_404_NOT_FOUND)

        was_default = addr.is_default
        addr.delete()

        if was_default:
            _ensure_single_default_address(request.user)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientAddressSetDefaultAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, address_id):
        addr = Address.objects.filter(id=address_id, user=request.user).first()
        if not addr:
            return Response({"detail": "Адрес не найден."}, status=status.HTTP_404_NOT_FOUND)

        Address.objects.filter(user=request.user).update(is_default=False)
        Address.objects.filter(id=addr.id).update(is_default=True)

        addr.refresh_from_db()
        return Response(AddressSerializer(addr).data, status=status.HTTP_200_OK)

class ClientOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        qs = (
            Order.objects
            .filter(user=request.user)
            .exclude(status=Order.Status.BASKET)
            .annotate(
                total=Sum(F("shop_orders__items__quantity") * F("shop_orders__items__price_at_purchase")),
                shops_count=Count("shop_orders", distinct=True),
                items_count=Count("shop_orders__items", distinct=True),
            )
            .order_by("-date")
        )
        return Response(ClientOrderListSerializer(qs, many=True).data, status=status.HTTP_200_OK)


class ClientOrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id: int):

        order = (
            Order.objects
            .filter(id=order_id, user=request.user)
            .exclude(status=Order.Status.BASKET)
            .prefetch_related(
                "shop_orders__shop",
                "shop_orders__items__product_info__product",
            )
            .first()
        )
        if not order:
            return Response({"detail": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND)

        return Response(ClientOrderDetailSerializer(order).data, status=status.HTTP_200_OK)