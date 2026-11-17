"""
Faltantes y demanda no atendida.

GET    /api/faltantes/                 lista (admin y cajero). Filtros: ?tipo=inexistente|agotado,
                                        ?proveedor={id}|ninguno, ?estado=pendiente|resuelto,
                                        ?desde=, ?hasta=, ?q=texto
POST   /api/faltantes/                 registra un faltante (admin y cajero)
GET    /api/faltantes/{id}/            detalle
POST   /api/faltantes/{id}/resolver/   marca como resuelto (solo admin)
DELETE /api/faltantes/{id}/            elimina un registro equivocado (solo admin)
GET    /api/faltantes/pendientes/      pendientes agrupados por producto y proveedor,
                                        para planear compras (solo admin)
"""
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.usuarios.permissions import EsAdministrador, TieneRolPOS
from config.filtros import filtrar_por_fechas

from .models import Faltante
from .serializers import FaltanteEntradaSerializer, FaltanteSerializer
from .services import agrupar_faltantes
from .utils import normalizar_nombre


def filtrar_faltantes(consulta, request):
    parametros = request.query_params

    tipo = parametros.get("tipo")
    if tipo:
        if tipo not in Faltante.Tipo.values:
            raise ValidationError({"tipo": "Usa tipo=inexistente o tipo=agotado."})
        consulta = consulta.filter(tipo=tipo)

    estado = parametros.get("estado")
    if estado:
        if estado not in Faltante.Estado.values:
            raise ValidationError({"estado": "Usa estado=pendiente o estado=resuelto."})
        consulta = consulta.filter(estado=estado)

    proveedor = parametros.get("proveedor")
    if proveedor == "ninguno":
        consulta = consulta.filter(proveedor__isnull=True)
    elif proveedor:
        if not proveedor.isdigit():
            raise ValidationError({"proveedor": "Usa el id del proveedor o proveedor=ninguno."})
        consulta = consulta.filter(proveedor_id=int(proveedor))

    texto = parametros.get("q")
    if texto:
        consulta = consulta.filter(nombre_normalizado__icontains=normalizar_nombre(texto))

    return filtrar_por_fechas(consulta, request)


class FaltanteViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FaltanteSerializer
    permission_classes = [IsAuthenticated, TieneRolPOS]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), EsAdministrador()]
        return super().get_permissions()

    def get_queryset(self):
        consulta = Faltante.objects.select_related(
            "producto", "proveedor", "registrado_por", "resuelto_por"
        )
        if self.action in ("list", "pendientes"):
            consulta = filtrar_faltantes(consulta, self.request)
        return consulta

    def create(self, request, *args, **kwargs):
        entrada = FaltanteEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        faltante = Faltante.objects.create(
            producto=datos.get("producto"),
            nombre_original=datos["nombre"],
            cantidad=datos["cantidad"],
            tipo=datos["tipo"],
            proveedor=datos.get("proveedor"),
            registrado_por=request.user,
        )
        return Response(FaltanteSerializer(faltante).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, EsAdministrador])
    def resolver(self, request, pk=None):
        faltante = self.get_object()
        if faltante.estado == Faltante.Estado.RESUELTO:
            raise ValidationError({"detail": "Este faltante ya estaba marcado como resuelto."})
        faltante.estado = Faltante.Estado.RESUELTO
        faltante.resuelto_por = request.user
        faltante.resuelto_en = timezone.now()
        faltante.save(update_fields=["estado", "resuelto_por", "resuelto_en", "actualizado_en"])
        return Response(FaltanteSerializer(faltante).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, EsAdministrador])
    def pendientes(self, request):
        consulta = self.get_queryset().filter(estado=Faltante.Estado.PENDIENTE)
        return Response(agrupar_faltantes(consulta, por_proveedor=True))
