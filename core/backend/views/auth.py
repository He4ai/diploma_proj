from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth import logout as django_logout
from rest_framework.authentication import TokenAuthentication

from backend.serializers.auth import UserLoginSerializer, RegisterSerializer


User = get_user_model()

class AuthAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return Response(
                {"Status": True, "message": "You are already logged in!"},
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
        return Response({"Status": True, "token": token.key})

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
            {"Status": True, "message": "Account created. Check your email to activate."},
            status=status.HTTP_201_CREATED
        )

class ActivateAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token, *args, **kwargs):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"Status": False, "message": "Invalid activation link."},
                            status=status.HTTP_400_BAD_REQUEST)

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            return Response({"Status": True, "message": "Account activated."},
                            status=status.HTTP_200_OK)

        return Response({"Status": False, "message": "Activation link expired/invalid."},
                        status=status.HTTP_400_BAD_REQUEST)

class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.auth:
            request.auth.delete()

        django_logout(request)
        return Response({"Status": True, "message": "Logged out"})
