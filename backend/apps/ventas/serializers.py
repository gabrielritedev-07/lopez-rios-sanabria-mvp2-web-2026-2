"""
Serializers de ventas.

- Entrada (*EntradaSerializer): validan tipos, obligatorios y existencia de registros.
  Solo aceptan ids y cantidades; nunca precios ni totales.
- Salida (VentaSerializer): forma estable del JSON que consume el frontend.
"""
from rest_framework import serializers

from apps.catalogo.models import Cliente, Descuento, Producto

from apps.usuarios.permissions import OcultarCostosMixin

from .models import Abono, DetalleReembolso, DetalleVenta, Reembolso, Venta


def nombre_usuario(usuario):
    return usuario.username if usuario else None


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------
class LineaVentaEntradaSerializer(serializers.Serializer):
    """
    Una línea es un producto del catálogo ({productoId, cantidad}) o un ítem libre /
    servicio rápido ({descripcion, precio, cantidad}) que no mueve inventario.
    """

    productoId = serializers.PrimaryKeyRelatedField(
        source="producto",
        queryset=Producto.objects.all(),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "El producto con id {pk_value} no existe."},
    )
    descripcion = serializers.CharField(max_length=150, required=False, allow_blank=True)
    precio = serializers.IntegerField(
        min_value=1, required=False, error_messages={"min_value": "El valor del ítem debe ser mayor que 0."}
    )
    cantidad = serializers.IntegerField(
        min_value=1, error_messages={"min_value": "La cantidad debe ser al menos 1."}
    )

    def validate(self, attrs):
        if attrs.get("producto") is not None:
            return {"producto": attrs["producto"], "cantidad": attrs["cantidad"]}
        descripcion = (attrs.get("descripcion") or "").strip()
        if not descripcion or attrs.get("precio") is None:
            raise serializers.ValidationError(
                "Cada línea necesita un producto del catálogo, o una descripción y un valor (ítem libre)."
            )
        return {"producto": None, "descripcion": descripcion, "precio": attrs["precio"], "cantidad": attrs["cantidad"]}


class VentaEntradaSerializer(serializers.Serializer):
    clienteId = serializers.PrimaryKeyRelatedField(
        source="cliente",
        queryset=Cliente.objects.all(),
        allow_null=True,
        required=False,
        error_messages={"does_not_exist": "El cliente seleccionado no existe."},
    )
    metodoPago = serializers.ChoiceField(
        source="metodo_pago",
        choices=Venta.MetodoPago.choices,
        required=False,
        error_messages={"invalid_choice": "El método de pago debe ser Efectivo, Nequi o Debe."},
    )
    descuentoId = serializers.PrimaryKeyRelatedField(
        source="descuento",
        queryset=Descuento.objects.all(),
        allow_null=True,
        required=False,
        error_messages={"does_not_exist": "El descuento seleccionado no existe."},
    )
    valorRecibido = serializers.IntegerField(
        source="valor_recibido",
        min_value=0,
        required=False,
        allow_null=True,
        error_messages={"min_value": "El valor recibido no puede ser negativo."},
    )
    items = LineaVentaEntradaSerializer(many=True, required=False)
    # Solo para POST /api/ventas/: true = crear y cerrar en un solo paso.
    cerrar = serializers.BooleanField(required=False, default=False)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("La venta debe tener al menos un producto.")
        # Si el mismo producto llega dos veces, se suman las cantidades.
        # Los ítems libres se conservan tal cual.
        unidas, libres = {}, []
        for item in items:
            if item["producto"] is None:
                libres.append(item)
                continue
            pid = item["producto"].pk
            if pid in unidas:
                unidas[pid]["cantidad"] += item["cantidad"]
            else:
                unidas[pid] = {"producto": item["producto"], "cantidad": item["cantidad"]}
        return list(unidas.values()) + libres

    def validate(self, attrs):
        if self.context.get("items_obligatorios") and "items" not in attrs:
            raise serializers.ValidationError({"items": "La venta debe tener al menos un producto."})
        return attrs


class CorreccionEntradaSerializer(VentaEntradaSerializer):
    cerrar = None  # no aplica a correcciones


class LineaReembolsoEntradaSerializer(serializers.Serializer):
    # detalleId identifica la línea de la venta (sirve también para ítems libres).
    detalleId = serializers.IntegerField(source="detalle_id", min_value=1, required=False)
    productoId = serializers.IntegerField(source="producto_id", min_value=1, required=False)
    cantidad = serializers.IntegerField(
        min_value=1, error_messages={"min_value": "La cantidad a reembolsar debe ser al menos 1."}
    )
    retornaInventario = serializers.BooleanField(source="retorna_inventario", default=True)

    def validate(self, attrs):
        if not attrs.get("detalle_id") and not attrs.get("producto_id"):
            raise serializers.ValidationError("Indica la línea (detalleId) o el producto (productoId) a reembolsar.")
        return attrs


class ReembolsoEntradaSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    # todo=true reembolsa todas las unidades pendientes de la venta (reembolso total).
    todo = serializers.BooleanField(required=False, default=False)
    retornaInventario = serializers.BooleanField(
        source="retorna_inventario", required=False, default=True
    )
    items = LineaReembolsoEntradaSerializer(many=True, required=False)

    def validate_items(self, items):
        claves = [("d", i["detalle_id"]) if i.get("detalle_id") else ("p", i["producto_id"]) for i in items]
        if len(claves) != len(set(claves)):
            raise serializers.ValidationError("Cada producto debe aparecer una sola vez en el reembolso.")
        return items

    def validate(self, attrs):
        if not attrs.get("todo") and not attrs.get("items"):
            raise serializers.ValidationError({
                "items": "Selecciona al menos un producto a reembolsar o envía todo: true."
            })
        return attrs


# --------------------------------------------------------------------------
# Salida
# --------------------------------------------------------------------------
class DetalleVentaSerializer(OcultarCostosMixin, serializers.ModelSerializer):
    campos_costo = ("costoUnitario",)

    productoId = serializers.IntegerField(source="producto_id", allow_null=True)
    esLibre = serializers.BooleanField(source="es_libre")
    nombre = serializers.CharField(source="nombre_producto")
    precioUnitario = serializers.IntegerField(source="precio_unitario")
    costoUnitario = serializers.IntegerField(source="costo_unitario")
    cantidadReembolsada = serializers.SerializerMethodField()

    class Meta:
        model = DetalleVenta
        fields = [
            "id",
            "productoId",
            "esLibre",
            "nombre",
            "precioUnitario",
            "costoUnitario",
            "cantidad",
            "subtotal",
            "cantidadReembolsada",
        ]

    def get_cantidadReembolsada(self, detalle):
        return sum(r.cantidad for r in detalle.reembolsos.all())


class DetalleReembolsoSerializer(serializers.ModelSerializer):
    detalleId = serializers.IntegerField(source="detalle_venta_id")
    productoId = serializers.IntegerField(source="detalle_venta.producto_id", allow_null=True)
    nombre = serializers.CharField(source="detalle_venta.nombre_producto")
    retornaInventario = serializers.BooleanField(source="retorna_inventario")

    class Meta:
        model = DetalleReembolso
        fields = ["id", "detalleId", "productoId", "nombre", "cantidad", "valor", "retornaInventario"]


class ReembolsoSerializer(serializers.ModelSerializer):
    usuario = serializers.SerializerMethodField()
    items = DetalleReembolsoSerializer(many=True)

    class Meta:
        model = Reembolso
        fields = ["id", "fecha", "usuario", "total", "motivo", "items"]

    def get_usuario(self, reembolso):
        return nombre_usuario(reembolso.usuario)


class VentaSerializer(serializers.ModelSerializer):
    numero = serializers.CharField(read_only=True)
    clienteId = serializers.IntegerField(source="cliente_id", allow_null=True)
    clienteNombre = serializers.SerializerMethodField()
    metodoPago = serializers.CharField(source="metodo_pago")
    descuentoId = serializers.IntegerField(source="descuento_id", allow_null=True)
    descuento = serializers.SerializerMethodField()
    descuentoMonto = serializers.IntegerField(source="descuento_monto")
    ivaPorcentaje = serializers.IntegerField(source="iva_porcentaje")
    ivaIncluido = serializers.IntegerField(source="iva")
    valorRecibido = serializers.IntegerField(source="valor_recibido")
    creadaPor = serializers.SerializerMethodField()
    cerradaPor = serializers.SerializerMethodField()
    cerradaEn = serializers.DateTimeField(source="cerrada_en")
    corregidaPor = serializers.SerializerMethodField()
    corregidaEn = serializers.DateTimeField(source="corregida_en")
    estadoReembolso = serializers.CharField(source="estado_reembolso")
    totalReembolsado = serializers.SerializerMethodField()
    items = DetalleVentaSerializer(many=True)
    reembolsos = ReembolsoSerializer(many=True)

    class Meta:
        model = Venta
        fields = [
            "id",
            "numero",
            "estado",
            "fecha",
            "clienteId",
            "clienteNombre",
            "metodoPago",
            "subtotal",
            "descuentoId",
            "descuento",
            "descuentoMonto",
            "total",
            "ivaPorcentaje",
            "ivaIncluido",
            "valorRecibido",
            "cambio",
            "creadaPor",
            "cerradaPor",
            "cerradaEn",
            "corregida",
            "corregidaPor",
            "corregidaEn",
            "estadoReembolso",
            "totalReembolsado",
            "items",
            "reembolsos",
        ]

    def get_clienteNombre(self, venta):
        return venta.cliente.nombre if venta.cliente_id else None

    def get_descuento(self, venta):
        """Fotografía del descuento aplicado (sigue visible aunque se borre del catálogo)."""
        if not venta.descuento_tipo:
            return None
        return {
            "nombre": venta.descuento_nombre,
            "tipo": venta.descuento_tipo,
            "valor": venta.descuento_valor,
            "monto": venta.descuento_monto,
        }

    def get_creadaPor(self, venta):
        return nombre_usuario(venta.creada_por)

    def get_cerradaPor(self, venta):
        return nombre_usuario(venta.cerrada_por)

    def get_corregidaPor(self, venta):
        return nombre_usuario(venta.corregida_por)

    def get_totalReembolsado(self, venta):
        return sum(r.total for r in venta.reembolsos.all())


# --------------------------------------------------------------------------
# Cartera de clientes: abonos
# --------------------------------------------------------------------------
class AbonoEntradaSerializer(serializers.Serializer):
    valor = serializers.IntegerField(
        min_value=1, error_messages={"min_value": "El abono debe ser mayor que 0."}
    )
    metodoPago = serializers.ChoiceField(
        source="metodo_pago",
        choices=Abono.MetodoPago.choices,
        default=Abono.MetodoPago.EFECTIVO,
        error_messages={"invalid_choice": "El método de pago del abono debe ser Efectivo o Nequi."},
    )
    nota = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class AbonoSerializer(serializers.ModelSerializer):
    clienteId = serializers.IntegerField(source="cliente_id")
    metodoPago = serializers.CharField(source="metodo_pago")
    usuario = serializers.SerializerMethodField()

    class Meta:
        model = Abono
        fields = ["id", "clienteId", "fecha", "valor", "metodoPago", "usuario", "nota"]

    def get_usuario(self, abono):
        return nombre_usuario(abono.usuario)
