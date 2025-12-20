from django.contrib import admin
from django.urls import path

from backend.views.auth import RegisterAPIView, AuthAPIView, ActivateAPIView, LogoutAPIView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/login/", AuthAPIView.as_view()),
    path("auth/register/", RegisterAPIView.as_view()),
    path("auth/activate/<str:uidb64>/<str:token>/", ActivateAPIView.as_view()),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
]
