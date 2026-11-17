"""
CRUD del catálogo con ModelViewSet (GET lista, GET detalle, POST, PUT, PATCH, DELETE).

Permisos (matriz del MVP 3):
- Categorías, productos, proveedores y descuentos: todos los roles consultan;
  solo el administrador crea, edita y elimina.
  (El cajero lee proveedores y descuentos porque los necesita para registrar
  faltantes y para aplicar un descuento existente a una venta.)
- Clientes: administrador y cajero tienen CRUD completo (incluye su saldo pendiente).
- Productos: el cajero puede usar /edicion-rapida/ desde el flujo de venta, consultar
  el kardex y las alertas de stock y vencimiento. El costo solo lo ve el administrador.

Rutas adicionales de productos:
GET  /api/productos/alertas/              stock bajo, agotados, por vencer y vencidos
GET  /api/productos/{id}/kardex/          historial de movimientos de inventario
POST /api/productos/{id}/ajustar-stock/   ajuste manual con motivo (solo administrador)

Si se intenta eliminar un registro con datos asociados, Django lanza ProtectedError
y config/exceptions.py lo convierte en una respuesta 409 con un mensaje claro.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.usuarios.permissions import EsAdministrador, LecturaTodosEscrituraAdministrador, TieneRolPOS

from .inventario import mover_stock, registrar_movimiento
from .models import Categoria, Cliente, Descuento, MovimientoInventario, Producto, Proveedor
from .serializers import (
    AjusteStockSerializer,
    CategoriaSerializer,
    ClienteSerializer,
    DescuentoSerializer,
    MovimientoInventarioSerializer,
    ProductoEdicionRapidaSerializer,
    ProductoSerializer,
    ProveedorSerializer,
)


class CatalogoViewSet(viewsets.ModelViewSet):
    """Base: búsqueda con ?q=texto y permisos de lectura para todos / escritura admin."""

    permission_classes = [IsAuthenticated, LecturaTodosEscrituraAdministrador]
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre"]


class CategoriaViewSet(CatalogoViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer


class ProveedorViewSet(CatalogoViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    search_fields = ["nombre", "telefono", "correo"]


class ClienteViewSet(CatalogoViewSet):
    serializer_class = ClienteSerializer
    search_fields = ["nombre", "telefono", "correo"]
    permission_classes = [IsAuthenticated, TieneRolPOS]

    def get_queryset(self):
        from apps.ventas.cartera import anotar_saldo  # import diferido: evita ciclo entre apps

        return anotar_saldo(Cliente.objects.all())


class DescuentoViewSet(CatalogoViewSet):
    queryset = Descuento.objects.all()
    serializer_class = DescuentoSerializer


class ProductoViewSet(CatalogoViewSet):
    serializer_class = ProductoSerializer
    search_fields = ["nombre", "codigo"]

    def get_queryset(self):
        consulta = Producto.objects.select_related("categoria")
        categoria = self.request.query_params.get("categoria")
        if categoria:
            if not categoria.isdigit():
                raise ValidationError({"categoria": "El filtro de categoría debe ser un id numérico."})
            consulta = consulta.filter(categoria_id=int(categoria))
        return consulta

    # --- Kardex automático al crear o editar el stock desde el formulario ---
    @transaction.atomic
    def perform_create(self, serializer):
        producto = serializer.save()
        if producto.seguimiento_inventario and producto.stock > 0:
            registrar_movimiento(
                producto, producto.stock, 0,
                tipo=MovimientoInventario.Tipo.INICIAL, usuario=self.request.user,
                nota="Stock inicial al crear el producto",
            )

    @transaction.atomic
    def perform_update(self, serializer):
        anterior = Producto.objects.select_for_update().get(pk=serializer.instance.pk)
        producto = serializer.save()
        diferencia = producto.stock - anterior.stock
        if producto.seguimiento_inventario and diferencia:
            registrar_movimiento(
                producto, diferencia, anterior.stock,
                tipo=MovimientoInventario.Tipo.AJUSTE, usuario=self.request.user,
                nota="Edición del producto",
            )

    @action(
        detail=True,
        methods=["patch"],
        url_path="edicion-rapida",
        permission_classes=[IsAuthenticated, TieneRolPOS],
    )
    def edicion_rapida(self, request, pk=None):
        """PATCH /api/productos/{id}/edicion-rapida/ — edición desde la venta en curso."""
        producto = self.get_object()
        serializer = ProductoEdicionRapidaSerializer(producto, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Devuelve el producto completo para que el POS refresque precio/nombre en el carrito.
        return Response(ProductoSerializer(producto, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated, TieneRolPOS])
    def kardex(self, request, pk=None):
        """Trazabilidad: entradas por compras, salidas por ventas, ajustes y reembolsos."""
        producto = self.get_object()
        movimientos = producto.movimientos.select_related("usuario")
        return Response({
            "producto": ProductoSerializer(producto, context=self.get_serializer_context()).data,
            "movimientos": MovimientoInventarioSerializer(movimientos, many=True).data,
        })

    @action(
        detail=True,
        methods=["post"],
        url_path="ajustar-stock",
        permission_classes=[IsAuthenticated, EsAdministrador],
    )
    def ajustar_stock(self, request, pk=None):
        """Ajuste manual (conteo físico, daño, pérdida…). Queda en el kardex con el motivo."""
        entrada = AjusteStockSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        with transaction.atomic():
            producto = Producto.objects.select_for_update().get(pk=self.get_object().pk)
            if not producto.seguimiento_inventario:
                raise ValidationError({"detail": f"“{producto.nombre}” no lleva control de inventario."})
            diferencia = entrada.validated_data["stock"] - producto.stock
            if diferencia == 0:
                raise ValidationError({"stock": "El stock indicado es igual al actual; no hay nada que ajustar."})
            mover_stock(
                producto, diferencia,
                tipo=MovimientoInventario.Tipo.AJUSTE, usuario=request.user,
                nota=entrada.validated_data["motivo"],
            )
        producto = Producto.objects.select_related("categoria").get(pk=producto.pk)
        return Response(ProductoSerializer(producto, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, TieneRolPOS])
    def alertas(self, request):
        """Productos con stock bajo o agotado y productos vencidos o próximos a vencer."""
        hoy = timezone.localdate()
        limite = hoy + timedelta(days=settings.POS_DIAS_ALERTA_VENCIMIENTO)
        base = Producto.objects.select_related("categoria")
        con_inventario = base.filter(seguimiento_inventario=True)
        contexto = self.get_serializer_context()

        def serializar(consulta):
            return ProductoSerializer(consulta, many=True, context=contexto).data

        return Response({
            "diasAlertaVencimiento": settings.POS_DIAS_ALERTA_VENCIMIENTO,
            "agotados": serializar(con_inventario.filter(stock=0)),
            "stockBajo": serializar(con_inventario.filter(stock__gt=0, stock__lte=F("stock_minimo"))),
            "vencidos": serializar(base.filter(fecha_vencimiento__lt=hoy).order_by("fecha_vencimiento")),
            "porVencer": serializar(
                base.filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=limite).order_by("fecha_vencimiento")
            ),
        })
