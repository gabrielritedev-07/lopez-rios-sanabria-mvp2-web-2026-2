"""
Autenticación con JWT.

- POST /api/auth/login/    {username, password}  -> {access, refresh, usuario}
- POST /api/auth/refresh/  {refresh}             -> {access}
- GET  /api/auth/me/       (Bearer token)        -> {id, username, nombre, rol}

El cierre de sesión ocurre en el frontend: borra los tokens de sessionStorage.
El access token vence solo (JWT_ACCESS_MINUTES) y el refresh también (JWT_REFRESH_HOURS).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .permissions import TieneRolPOS
from .serializers import LoginSerializer, UsuarioSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class RefrescarTokenView(TokenRefreshView):
    pass


class UsuarioActualView(APIView):
    permission_classes = [IsAuthenticated, TieneRolPOS]

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)
