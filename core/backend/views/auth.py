from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.contrib.auth import logout as django_logout
from django.conf import settings
from django.core.mail import send_mail


from backend.serializers.auth import UserLoginSerializer, RegisterSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer

User = get_user_model()

class AuthAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return Response(
                {"success": True, "message": "You are already logged in!"},
                status=status.HTTP_200_OK
            )

        serializer = UserLoginSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        login(request, user)  # сессия для DRF UI
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"success": True, "token": token.key})

class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(
            data=request.data,
            context={"request": request}  # <-- вот оно
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"success": True, "message": "Account created. Check your email to activate."},
            status=status.HTTP_201_CREATED
        )

class ActivateAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token, *args, **kwargs):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"success": False, "message": "Invalid activation link."},
                            status=status.HTTP_400_BAD_REQUEST)

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            return Response({"success": True, "message": "Account activated."},
                            status=status.HTTP_200_OK)

        return Response({"success": False, "message": "Activation link expired/invalid."},
                        status=status.HTTP_400_BAD_REQUEST)

class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.auth:
            request.auth.delete()

        django_logout(request)
        return Response({"success": True, "message": "Logged out"})


class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = PasswordResetRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        email = s.validated_data["email"]

        user = User.objects.filter(email=email).first()

        # ВАЖНО: всегда отвечаем одинаково (anti-user-enumeration)
        # Но письмо отправляем только если пользователь существует и активен (по желанию).
        if user and user.is_active:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            link = request.build_absolute_uri(
                f"/api/auth/password/reset/confirm/{uidb64}/{token}/"
            )

            send_mail(
                subject="Сброс пароля",
                message=(
                    "Привет!\n"
                    "Ты запросил сброс пароля. Чтобы установить новый пароль, перейди по ссылке:\n"
                    f"{link}\n\n"
                    "Если это был не ты — просто проигнорируй письмо."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

        return Response(
            {"success": True, "message": "Если такой email зарегистрирован, мы отправили ссылку для сброса пароля."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"success": False, "message": "Некорректная ссылка."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"success": False, "message": "Ссылка истекла или неверна."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(s.validated_data["new_password"])
        user.save(update_fields=["password"])

        return Response({"success": True, "message": "Пароль обновлён."}, status=status.HTTP_200_OK)

