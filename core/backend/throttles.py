from rest_framework.throttling import ScopedRateThrottle

class AuthThrottle(ScopedRateThrottle):
    scope = "auth"

class PasswordResetThrottle(ScopedRateThrottle):
    scope = "password_reset"

class ImportThrottle(ScopedRateThrottle):
    scope = "import"

class CheckoutThrottle(ScopedRateThrottle):
    scope = "checkout"
