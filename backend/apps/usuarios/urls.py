from django.urls import path

from .views import LoginView, RefrescarTokenView, UsuarioActualView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefrescarTokenView.as_view(), name="auth-refresh"),
    path("me/", UsuarioActualView.as_view(), name="auth-me"),
]
