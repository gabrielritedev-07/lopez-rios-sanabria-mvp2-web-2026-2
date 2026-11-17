"""
Compras (solo administrador).

GET  /api/compras/        lista (?desde=&hasta=&proveedor={id})
GET  /api/compras/{id}/   detalle
POST /api/compras/        registra la compra y suma stock
GET  /api/compras/sugerencia-pedido/   lista automática de pedido (stock bajo + faltantes)
"""
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.usuarios.permissions import EsAdministrador
from config.filtros import filtrar_por_fechas

from .models import Compra
from .serializers import CompraEntradaSerializer, CompraSerializer
from .services import registrar_compra
from .sugerencias import sugerencia_pedido as calcular_sugerencia_pedido


def compras_con_detalle():
    return Compra.objects.select_related("proveedor", "registrada_por").prefetch_related("items")


class CompraViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CompraSerializer
    permission_classes = [IsAuthenticated, EsAdministrador]

    def get_queryset(self):
        consulta = compras_con_detalle()
        if self.action != "list":
            return consulta
        proveedor = self.request.query_params.get("proveedor")
        if proveedor:
            if not proveedor.isdigit():
                raise ValidationError({"proveedor": "El filtro de proveedor debe ser un id numérico."})
            consulta = consulta.filter(proveedor_id=int(proveedor))
        return filtrar_por_fechas(consulta, self.request)

    def create(self, request, *args, **kwargs):
        entrada = CompraEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        compra = registrar_compra(usuario=request.user, datos=entrada.validated_data)
        compra = compras_con_detalle().get(pk=compra.pk)
        return Response(CompraSerializer(compra).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="sugerencia-pedido")
    def sugerencia_pedido(self, request):
        return Response(calcular_sugerencia_pedido())
