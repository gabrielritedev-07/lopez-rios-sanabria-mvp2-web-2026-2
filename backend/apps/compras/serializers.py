from django.utils import timezone
from rest_framework import serializers

from apps.catalogo.models import Producto, Proveedor

from .models import Compra, DetalleCompra


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------
class LineaCompraEntradaSerializer(serializers.Serializer):
    productoId = serializers.PrimaryKeyRelatedField(
        source="producto",
        queryset=Producto.objects.all(),
        error_messages={"does_not_exist": "El producto con id {pk_value} no existe."},
    )
    cantidad = serializers.IntegerField(
        min_value=1, error_messages={"min_value": "La cantidad debe ser al menos 1."}
    )
    costo = serializers.IntegerField(
        min_value=0, error_messages={"min_value": "El costo no puede ser negativo."}
    )


class CompraEntradaSerializer(serializers.Serializer):
    proveedorId = serializers.PrimaryKeyRelatedField(
        source="proveedor",
        queryset=Proveedor.objects.all(),
        error_messages={
            "required": "Selecciona un proveedor.",
            "null": "Selecciona un proveedor.",
            "does_not_exist": "El proveedor seleccionado no existe.",
        },
    )
    # Fecha de la compra (AAAA-MM-DD). Si no se envía, se usa la fecha actual.
    fecha = serializers.DateField(required=False)
    items = LineaCompraEntradaSerializer(many=True)

    def validate_fecha(self, fecha):
        if fecha > timezone.localdate():
            raise serializers.ValidationError("La fecha de la compra no puede ser futura.")
        return fecha

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("La compra debe tener al menos un producto.")
        ids = [item["producto"].pk for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Cada producto debe aparecer una sola vez en la compra.")
        return items


# --------------------------------------------------------------------------
# Salida
# --------------------------------------------------------------------------
class DetalleCompraSerializer(serializers.ModelSerializer):
    productoId = serializers.IntegerField(source="producto_id")
    nombre = serializers.CharField(source="nombre_producto")
    costoUnitario = serializers.IntegerField(source="costo_unitario")

    class Meta:
        model = DetalleCompra
        fields = ["id", "productoId", "nombre", "costoUnitario", "cantidad", "subtotal"]


class CompraSerializer(serializers.ModelSerializer):
    numero = serializers.CharField(read_only=True)
    proveedorId = serializers.IntegerField(source="proveedor_id")
    proveedorNombre = serializers.CharField(source="proveedor.nombre")
    registradaPor = serializers.CharField(source="registrada_por.username")
    items = DetalleCompraSerializer(many=True)

    class Meta:
        model = Compra
        fields = [
            "id",
            "numero",
            "fecha",
            "proveedorId",
            "proveedorNombre",
            "total",
            "registradaPor",
            "items",
        ]
