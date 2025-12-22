from django.contrib import admin
from django.urls import path

from backend.views.auth import RegisterAPIView, AuthAPIView, ActivateAPIView, LogoutAPIView
from backend.views.shop import ImportShopInfoAPIView, GetOrdersAPIView, \
    ChangeOrderStatusAPIView, ChangeShopInfoAPIView, ProductInfoAPIView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/login/", AuthAPIView.as_view(), name="login"),
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/activate/<str:uidb64>/<str:token>/", ActivateAPIView.as_view(), name="activate"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path("shop/me/", ChangeShopInfoAPIView.as_view(), name="shop-me"),
    path("shop/me/import/", ImportShopInfoAPIView.as_view(), name="shop-import"),
    path("shop/me/orders/", GetOrdersAPIView.as_view(), name="shop-orders"),
    path("shop/me/orders/<int:order_id>/", GetOrdersAPIView.as_view(), name="shop-order-detail"),
    path("shop/me/orders/<int:order_id>/status/", ChangeOrderStatusAPIView.as_view(), name="shop-order-status"),
    path("shop/me/products/", ProductInfoAPIView.as_view(), name="shop-products"),
    path("shop/me/products/<int:pk>/", ProductInfoAPIView.as_view(), name="shop-product-detail"),
]
