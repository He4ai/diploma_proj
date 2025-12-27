from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

def make_activation_link(request, user) -> str:
    """
    Генерирует абсолютную ссылку на активацию аккаунта.

    Должна совпадать с urls.py:
    path("api/auth/activate/<str:uidb64>/<str:token>/", ActivateAPIView.as_view(), name="auth-activate")
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    return request.build_absolute_uri(f"/api/auth/activate/{uidb64}/{token}/")