"""
Endpoints de ventas. Las vistas coordinan: validan entrada (serializer), llaman al
servicio (services.py, con transacciones) y devuelven la venta completa.

GET    /api/ventas/                    lista (?estado=abierta|cerrada&desde=&hasta=&q=)
GET    /api/ventas/{id}/               detalle (factura)
POST   /api/ventas/                    crea venta abierta (o cerrada con "cerrar": true)
PUT    /api/ventas/{id}/               actualiza una venta abierta
PATCH  /api/ventas/{id}/               actualiza parcialmente una venta abierta
POST   /api/ventas/{id}/cerrar/        cierra una venta abierta
POST   /api/ventas/{id}/corregir/      corrige una venta cerrada        (solo administrador)
POST   /api/ventas/{id}/reembolsos/    registra un reembolso            (solo administrador)

GET    /api/clientes/{id}/cartera/     saldo, ventas fiadas y abonos de un cliente (admin y cajero)
POST   /api/clientes/{id}/abonos/      registra un abono a la deuda (admin y cajero)

No hay DELETE: eliminar o anular ventas está fuera del alcance del MVP 3.
"""
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalogo.models import Cliente
from apps.usuarios.permissions import EsAdministrador, TieneRolPOS
from config.filtros import filtrar_por_fechas

from . import cartera, services
from .models import Venta
from .serializers import (
    AbonoEntradaSerializer,
    AbonoSerializer,
    CorreccionEntradaSerializer,
    ReembolsoEntradaSerializer,
    VentaEntradaSerializer,
    VentaSerializer,
)


def ventas_con_detalle():
    """Consulta optimizada: trae relaciones en pocas consultas SQL (sin N+1)."""
    return Venta.objects.select_related(
        "cliente", "creada_por", "cerrada_por", "corregida_por"
    ).prefetch_related(
        "items__reembolsos",
        "reembolsos__usuario",
        "reembolsos__items__detalle_venta",
    )


class VentaViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = VentaSerializer
    permission_classes = [IsAuthenticated, TieneRolPOS]

    def get_queryset(self):
        consulta = ventas_con_detalle()
        if self.action != "list":
            return consulta
        estado = self.request.query_params.get("estado")
        if estado:
            if estado not in Venta.Estado.values:
                raise ValidationError({"estado": "Usa estado=abierta o estado=cerrada."})
            consulta = consulta.filter(estado=estado)
        texto = self.request.query_params.get("q")
        if texto:
            consulta = consulta.filter(cliente__nombre__icontains=texto)
        return filtrar_por_fechas(consulta, self.request)

    def responder(self, venta, codigo=status.HTTP_200_OK):
        venta = ventas_con_detalle().get(pk=venta.pk)
        # El contexto (request) permite ocultar costos si consulta un cajero.
        return Response(VentaSerializer(venta, context=self.get_serializer_context()).data, status=codigo)

    def leer_entrada(self, serializer_class, **contexto):
        entrada = serializer_class(data=self.request.data, context=contexto)
        entrada.is_valid(raise_exception=True)
        return entrada.validated_data

    def create(self, request, *args, **kwargs):
        datos = self.leer_entrada(VentaEntradaSerializer, items_obligatorios=True)
        venta = services.guardar_venta(usuario=request.user, datos=datos, cerrar=datos["cerrar"])
        return self.responder(venta, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        datos = self.leer_entrada(VentaEntradaSerializer)
        venta = services.guardar_venta(usuario=request.user, datos=datos, venta=self.get_object())
        return self.responder(venta)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        datos = self.leer_entrada(VentaEntradaSerializer)
        venta = services.guardar_venta(
            usuario=request.user, datos=datos, venta=self.get_object(), cerrar=True
        )
        return self.responder(venta)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, EsAdministrador])
    def corregir(self, request, pk=None):
        datos = self.leer_entrada(CorreccionEntradaSerializer)
        venta = services.corregir_venta(usuario=request.user, venta=self.get_object(), datos=datos)
        return self.responder(venta)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, EsAdministrador])
    def reembolsos(self, request, pk=None):
        venta = self.get_object()
        datos = self.leer_entrada(ReembolsoEntradaSerializer)
        services.registrar_reembolso(usuario=request.user, venta=venta, datos=datos)
        return self.responder(venta, status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# Cartera de clientes
# --------------------------------------------------------------------------
def respuesta_cartera(cliente_id, codigo=status.HTTP_200_OK):
    datos = cartera.resumen_cartera(cliente_id)
    datos["abonos"] = AbonoSerializer(datos["abonos"], many=True).data
    return Response(datos, status=codigo)


class CarteraClienteView(APIView):
    permission_classes = [IsAuthenticated, TieneRolPOS]

    def get(self, request, pk):
        get_object_or_404(Cliente, pk=pk)
        return respuesta_cartera(pk)


class AbonoClienteView(APIView):
    permission_classes = [IsAuthenticated, TieneRolPOS]

    def post(self, request, pk):
        get_object_or_404(Cliente, pk=pk)
        entrada = AbonoEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        cartera.registrar_abono(usuario=request.user, cliente_id=pk, datos=entrada.validated_data)
        return respuesta_cartera(pk, status.HTTP_201_CREATED)
