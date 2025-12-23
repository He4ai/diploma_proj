from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.validators import UniqueValidator
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.conf import settings
from utils import make_activation_link

User = get_user_model()

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError("Wrong email or password.")

        if not user.is_active:
            raise serializers.ValidationError("Account is not activated.")

        attrs["user"] = user
        return attrs

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password", "username", "type")

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        password = validated_data.pop("password")
        email = validated_data.get("email").strip().lower()
        validated_data["email"] = email

        user = User.objects.create_user(password=password, **validated_data)
        user.is_active = False
        user.save(update_fields=["is_active"])

        activation_link = make_activation_link(request, user)

        send_mail(
            subject="Подтверждение регистрации",
            message=f"Привет! Нажми ссылку, чтобы активировать аккаунт:\n{activation_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return user

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value