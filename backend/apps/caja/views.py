"""
Caja y arqueo por turno (administrador y cajero; cada uno maneja su propio turno).

GET  /api/caja/turno-actual/   turno abierto del usuario con el resumen en vivo
POST /api/caja/abrir/          {baseInicial}
POST /api/caja/cerrar/         {efectivoContado, observaciones} -> registra sobrante o faltante
GET  /api/caja/turnos/         historial (el cajero ve los suyos; el admin, todos; ?usuario=)
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.usuarios.permissions import ADMINISTRADOR, TieneRolPOS, obtener_rol
from config.filtros import filtrar_por_fechas

from . import services
from .models import TurnoCaja
from .serializers import AbrirTurnoSerializer, CerrarTurnoSerializer, TurnoCajaSerializer


class CajaBaseView(APIView):
    permission_classes = [IsAuthenticated, TieneRolPOS]


class TurnoActualView(CajaBaseView):
    def get(self, request):
        turno = services.turno_abierto(request.user)
        if turno is None:
            return Response({"abierto": False, "turno": None})
        services.calcular_resumen(turno)  # en vivo, sin guardar
        return Response({"abierto": True, "turno": TurnoCajaSerializer(turno).data})


class AbrirTurnoView(CajaBaseView):
    def post(self, request):
        entrada = AbrirTurnoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        turno = services.abrir_turno(usuario=request.user, **entrada.validated_data)
        services.calcular_resumen(turno)
        return Response({"abierto": True, "turno": TurnoCajaSerializer(turno).data}, status=status.HTTP_201_CREATED)


class CerrarTurnoView(CajaBaseView):
    def post(self, request):
        entrada = CerrarTurnoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        turno = services.cerrar_turno(usuario=request.user, **entrada.validated_data)
        return Response({"abierto": False, "turno": TurnoCajaSerializer(turno).data})


class TurnosView(CajaBaseView):
    def get(self, request):
        consulta = TurnoCaja.objects.select_related("usuario")
        if obtener_rol(request.user) != ADMINISTRADOR:
            consulta = consulta.filter(usuario=request.user)
        elif request.query_params.get("usuario"):
            consulta = consulta.filter(usuario__username=request.query_params["usuario"])
        consulta = filtrar_por_fechas(consulta, request, campo="abierto_en")
        turnos = list(consulta[:100])
        for turno in turnos:
            if turno.estado == TurnoCaja.Estado.ABIERTO:
                services.calcular_resumen(turno)
        return Response(TurnoCajaSerializer(turnos, many=True).data)
