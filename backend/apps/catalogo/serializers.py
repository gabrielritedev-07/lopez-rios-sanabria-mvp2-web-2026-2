"""
Validación y representación JSON del catálogo.

Los nombres de campo del JSON siguen la Guía P2.2 que ya usa el frontend
(camelCase: categoriaId, seguimientoInventario). En la base de datos se usan
nombres snake_case; la traducción se hace aquí con `source=`.
"""
import re

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from apps.usuarios.permissions import OcultarCostosMixin

from .models import Categoria, Cliente, Descuento, MovimientoInventario, Producto, Proveedor

PATRON_TELEFONO = re.compile(r"^[0-9+\-\s()]*$")


def texto_obligatorio(valor, mensaje="Este campo es obligatorio."):
    valor = (valor or "").strip()
    if not valor:
        raise serializers.ValidationError(mensaje)
    return valor


def validar_nombre_unico(modelo, nombre, instancia, mensaje):
    """Nombre único sin distinguir mayúsculas (ej. 'Cuadernos' = 'cuadernos')."""
    consulta = modelo.objects.filter(nombre__iexact=nombre)
    if instancia is not None:
        consulta = consulta.exclude(pk=instancia.pk)
    if consulta.exists():
        raise serializers.ValidationError(mensaje)


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ["id", "nombre"]

    def validate_nombre(self, valor):
        valor = texto_obligatorio(valor, "El nombre de la categoría es obligatorio.")
        validar_nombre_unico(Categoria, valor, self.instance, "Ya existe una categoría con ese nombre.")
        return valor


class ContactoSerializer(serializers.ModelSerializer):
    """Validaciones comunes de clientes y proveedores."""

    class Meta:
        fields = ["id", "nombre", "telefono", "correo"]

    def validate_nombre(self, valor):
        return texto_obligatorio(valor, "El nombre es obligatorio.")

    def validate_telefono(self, valor):
        valor = (valor or "").strip()
        if not PATRON_TELEFONO.match(valor):
            raise serializers.ValidationError(
                "El teléfono solo puede tener números, espacios, +, - y paréntesis."
            )
        return valor

    def validate_correo(self, valor):
        return (valor or "").strip().lower()


class ClienteSerializer(ContactoSerializer):
    # Deuda pendiente por ventas "Debe" (ver apps/ventas/cartera.py). Solo lectura.
    saldo = serializers.SerializerMethodField()

    class Meta(ContactoSerializer.Meta):
        model = Cliente
        fields = ContactoSerializer.Meta.fields + ["saldo"]

    def get_saldo(self, cliente):
        saldo = getattr(cliente, "saldo_pendiente", None)
        if saldo is None:
            from apps.ventas.cartera import cliente_con_saldo  # import diferido: evita ciclo

            saldo = cliente_con_saldo(cliente.pk).saldo_pendiente if cliente.pk else 0
        return saldo


class ProveedorSerializer(ContactoSerializer):
    class Meta(ContactoSerializer.Meta):
        model = Proveedor


class ProductoSerializer(OcultarCostosMixin, serializers.ModelSerializer):
    # El cajero no ve el costo (ni, por tanto, el margen) de los productos.
    campos_costo = ("costo",)

    codigo = serializers.CharField(
        max_length=50, required=False, allow_blank=True, allow_null=True
    )
    categoriaId = serializers.PrimaryKeyRelatedField(
        source="categoria",
        queryset=Categoria.objects.all(),
        error_messages={
            "required": "Selecciona una categoría.",
            "null": "Selecciona una categoría.",
            "does_not_exist": "La categoría seleccionada no existe.",
            "incorrect_type": "La categoría no es válida.",
        },
    )
    categoriaNombre = serializers.CharField(source="categoria.nombre", read_only=True)
    seguimientoInventario = serializers.BooleanField(
        source="seguimiento_inventario", required=False
    )
    stockMinimo = serializers.IntegerField(
        source="stock_minimo",
        min_value=0,
        required=False,
        error_messages={"min_value": "El stock mínimo no puede ser negativo."},
    )
    fechaVencimiento = serializers.DateField(source="fecha_vencimiento", required=False, allow_null=True)
    # Alertas calculadas (solo lectura).
    estadoStock = serializers.CharField(source="estado_stock", read_only=True, allow_null=True)
    alertaVencimiento = serializers.SerializerMethodField()
    diasParaVencer = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            "id",
            "codigo",
            "nombre",
            "categoriaId",
            "categoriaNombre",
            "precio",
            "costo",
            "seguimientoInventario",
            "stock",
            "stockMinimo",
            "estadoStock",
            "fechaVencimiento",
            "alertaVencimiento",
            "diasParaVencer",
        ]
        # PositiveIntegerField ya rechaza negativos (min_value=0); aquí van mensajes claros.
        extra_kwargs = {
            "precio": {"error_messages": {"min_value": "El precio no puede ser negativo."}},
            "costo": {"error_messages": {"min_value": "El costo no puede ser negativo."}},
            "stock": {"error_messages": {"min_value": "El stock no puede ser negativo."}},
        }

    def get_diasParaVencer(self, producto):
        if not producto.fecha_vencimiento:
            return None
        return (producto.fecha_vencimiento - timezone.localdate()).days

    def get_alertaVencimiento(self, producto):
        """None sin fecha; 'vencido', 'proximo' (dentro del umbral de días) u 'ok'."""
        dias = self.get_diasParaVencer(producto)
        if dias is None:
            return None
        if dias < 0:
            return "vencido"
        if dias <= settings.POS_DIAS_ALERTA_VENCIMIENTO:
            return "proximo"
        return "ok"

    def validate_nombre(self, valor):
        return texto_obligatorio(valor, "El nombre del producto es obligatorio.")

    def validate_codigo(self, valor):
        valor = (valor or "").strip()
        if not valor:
            return None  # Sin código: se guarda NULL (puede haber varios sin código).
        consulta = Producto.objects.filter(codigo__iexact=valor)
        if self.instance is not None:
            consulta = consulta.exclude(pk=self.instance.pk)
        if consulta.exists():
            raise serializers.ValidationError("Ya existe un producto con ese código.")
        return valor


class ProductoEdicionRapidaSerializer(ProductoSerializer):
    """
    Edición en caliente desde el flujo de venta (administrador y cajero).
    Solo permite corregir datos de venta del producto; NO toca stock, costo
    ni el seguimiento de inventario (eso es función del administrador).
    """

    seguimientoInventario = None  # elimina el campo heredado

    class Meta(ProductoSerializer.Meta):
        fields = ["id", "codigo", "nombre", "categoriaId", "categoriaNombre", "precio"]


class DescuentoSerializer(serializers.ModelSerializer):
    tipoNombre = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Descuento
        fields = ["id", "nombre", "tipo", "tipoNombre", "valor"]
        extra_kwargs = {
            "tipo": {
                "error_messages": {
                    "invalid_choice": "El tipo debe ser PORCENTAJE o VALOR_FIJO.",
                }
            },
        }

    def validate_nombre(self, valor):
        valor = texto_obligatorio(valor, "El nombre del descuento es obligatorio.")
        validar_nombre_unico(Descuento, valor, self.instance, "Ya existe un descuento con ese nombre.")
        return valor

    def validate(self, attrs):
        # En PATCH parcial se combinan los datos nuevos con los ya guardados.
        tipo = attrs.get("tipo", getattr(self.instance, "tipo", None))
        valor = attrs.get("valor", getattr(self.instance, "valor", None))
        if valor is not None and valor <= 0:
            raise serializers.ValidationError({"valor": "El valor del descuento debe ser mayor que 0."})
        if tipo == Descuento.Tipo.PORCENTAJE and valor is not None and valor > 100:
            raise serializers.ValidationError(
                {"valor": "Un descuento porcentual debe estar entre 1 y 100."}
            )
        return attrs


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    tipoNombre = serializers.CharField(source="get_tipo_display")
    stockAnterior = serializers.IntegerField(source="stock_anterior")
    stockResultante = serializers.IntegerField(source="stock_resultante")
    usuario = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoInventario
        fields = [
            "id", "fecha", "tipo", "tipoNombre", "cantidad", "stockAnterior",
            "stockResultante", "usuario", "referencia", "nota",
        ]

    def get_usuario(self, movimiento):
        return movimiento.usuario.username if movimiento.usuario_id else None


class AjusteStockSerializer(serializers.Serializer):
    """Ajuste manual: el administrador indica el stock real contado y el motivo."""

    stock = serializers.IntegerField(
        min_value=0, error_messages={"min_value": "El stock no puede ser negativo."}
    )
    motivo = serializers.CharField(max_length=255)

    def validate_motivo(self, valor):
        return texto_obligatorio(valor, "Indica el motivo del ajuste.")
