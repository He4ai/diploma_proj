from django.contrib import admin
from django.urls import path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from backend.views.auth import RegisterAPIView, AuthAPIView, ActivateAPIView, LogoutAPIView, \
    PasswordResetRequestAPIView, PasswordResetConfirmAPIView
from backend.views.buyer_order import BasketAPIView, BasketAddAPIView, BasketRemoveAPIView, CheckoutAPIView, \
    BasketSetAddressAPIView
from backend.views.client_profile import ClientProfileAPIView, ClientChangePasswordAPIView, \
    ClientRequestEmailChangeAPIView, ClientConfirmEmailChangeAPIView, ClientAddressListCreateAPIView, \
    ClientAddressDetailAPIView, ClientAddressSetDefaultAPIView, ClientOrdersAPIView, ClientOrderDetailAPIView
from backend.views.general import ProductListAPIView, CatalogOfferListAPIView, ShopPublicDetailAPIView, \
    ShopPublicOffersAPIView
from backend.views.shop import ImportShopInfoAPIView, GetOrdersAPIView, \
    ChangeOrderStatusAPIView, ChangeShopInfoAPIView, ProductInfoAPIView

urlpatterns = [
    path("admin/", admin.site.urls),

    # OpenAPI schema + Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # AUTH
    path("api/auth/login/", AuthAPIView.as_view(), name="auth-login"),
    path("api/auth/logout/", LogoutAPIView.as_view(), name="auth-logout"),
    path("api/auth/register/", RegisterAPIView.as_view(), name="auth-register"),
    path("api/auth/activate/<str:uidb64>/<str:token>/", ActivateAPIView.as_view(), name="auth-activate"),
    path("api/auth/password/reset/", PasswordResetRequestAPIView.as_view()),
    path("api/auth/password/reset/confirm/<str:uidb64>/<str:token>/", PasswordResetConfirmAPIView.as_view()),

    # SHOP (owner)
    path("api/shop/me/", ChangeShopInfoAPIView.as_view(), name="shop-me"),
    path("api/shop/me/import/", ImportShopInfoAPIView.as_view(), name="shop-import"),
    path("api/shop/me/products/", ProductInfoAPIView.as_view(), name="shop-products"),
    path("api/shop/me/products/<int:pk>/", ProductInfoAPIView.as_view(), name="shop-product-detail"),
    path("api/shop/me/orders/", GetOrdersAPIView.as_view(), name="shop-orders"),
    path("api/shop/me/orders/<int:order_id>/", GetOrdersAPIView.as_view(), name="shop-order-detail"),
    path("api/shop/me/orders/<int:order_id>/status/", ChangeOrderStatusAPIView.as_view(), name="shop-order-status"),

    # CATALOG (public)
    path("api/products/", ProductListAPIView.as_view(), name="products-list"),
    path("api/catalog/", CatalogOfferListAPIView.as_view(), name="catalog-offers"),
    path("api/shops/<int:shop_id>/", ShopPublicDetailAPIView.as_view(), name="shop-public-detail"),
    path("api/shops/<int:shop_id>/offers/", ShopPublicOffersAPIView.as_view(), name="shop-public-offers"),

    # BUYER — BASKET
    path("api/buyer/basket/", BasketAPIView.as_view(), name="buyer-basket"),
    path("api/buyer/basket/items/", BasketAddAPIView.as_view(), name="buyer-basket-add"),
    path("api/buyer/basket/items/remove/", BasketRemoveAPIView.as_view(), name="buyer-basket-remove"),
    path("api/buyer/basket/address/", BasketSetAddressAPIView.as_view(), name="buyer-basket-address"),
    path("api/buyer/basket/checkout/", CheckoutAPIView.as_view(), name="buyer-checkout"),

    # CLIENT PROFILE
    path("api/client/profile/", ClientProfileAPIView.as_view(), name="client-profile"),
    path("api/client/profile/password/", ClientChangePasswordAPIView.as_view(), name="client-change-password"),
    path("api/client/profile/email/change/", ClientRequestEmailChangeAPIView.as_view(), name="client-email-change"),
    path("api/client/profile/email/confirm/<str:signed>/", ClientConfirmEmailChangeAPIView.as_view(), name="client-email-confirm"),
    path("api/client/profile/addresses/", ClientAddressListCreateAPIView.as_view(), name="client-addresses"),
    path("api/client/profile/addresses/<int:address_id>/", ClientAddressDetailAPIView.as_view(), name="client-address-detail"),
    path("api/client/profile/addresses/<int:address_id>/set-default/", ClientAddressSetDefaultAPIView.as_view(), name="client-address-set-default"),
    path("api/client/orders/", ClientOrdersAPIView.as_view(), name="client-orders"),
    path("api/client/orders/<int:order_id>/", ClientOrderDetailAPIView.as_view(), name="client-order-detail"),
]
