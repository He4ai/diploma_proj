from django.contrib import admin
from django.urls import path

from backend.views.auth import RegisterAPIView, AuthAPIView, ActivateAPIView, LogoutAPIView
from backend.views.shop import ImportShopInfoAPIView, ChangeShopStatusAPIView, GetOrdersAPIView, ChangeOrderStatusAPIView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/login/", AuthAPIView.as_view(), name="login"),
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/activate/<str:uidb64>/<str:token>/", ActivateAPIView.as_view(), name="activate"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path("shop/owner/import/", ImportShopInfoAPIView.as_view(), name='import_shop_info'),
    path("shop/owner/change_shop_status/", ChangeShopStatusAPIView.as_view(), name='change_shop_status'),
    path("shop/owner/orders/", GetOrdersAPIView.as_view(), name='get_orders'),
    path("shop/owner/orders/<int:order_id>/", GetOrdersAPIView.as_view(), name='get_order'),
    path("shop/owner/orders/<int:order_id>/change_status/", ChangeOrderStatusAPIView.as_view(), name='change_order_status'),
]
