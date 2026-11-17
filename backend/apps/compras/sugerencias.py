"""
Lista automática de pedido a proveedores.

Junta dos fuentes:
1. Productos con inventario cuyo stock está en el mínimo o por debajo (punto de reorden).
2. Faltantes pendientes anotados por los cajeros (agotados del catálogo e inexistentes).

Cantidad sugerida para un producto del catálogo:
    reponer hasta el doble del stock mínimo  ->  max(2 * stock_minimo - stock, 0)
    + unidades que pidieron clientes y no había (faltantes pendientes de ese producto)

Para un producto inexistente (descrito en texto) se sugiere la cantidad total pedida.
El proveedor sugerido es el de la última compra del producto; si nunca se ha comprado,
el que anotó el cajero en el faltante.
"""
from django.db.models import F, Q, Sum

from apps.catalogo.models import Producto
from apps.faltantes.models import Faltante
from apps.faltantes.services import agrupar_faltantes

from .models import DetalleCompra

SIN_PROVEEDOR = None


def ultimo_proveedor(producto_ids):
    """{producto_id: (proveedor_id, nombre)} según la compra más reciente de cada producto."""
    resultado = {}
    detalles = (
        DetalleCompra.objects.filter(producto_id__in=producto_ids)
        .select_related("compra__proveedor")
        .order_by("producto_id", "-compra__fecha", "-id")
    )
    for detalle in detalles:
        if detalle.producto_id not in resultado:
            proveedor = detalle.compra.proveedor
            resultado[detalle.producto_id] = (proveedor.id, proveedor.nombre)
    return resultado


def sugerencia_pedido():
    pendientes = Faltante.objects.filter(estado=Faltante.Estado.PENDIENTE)

    # Demanda no atendida por producto del catálogo.
    demanda = {
        fila["producto_id"]: fila
        for fila in pendientes.filter(producto__isnull=False)
        .values("producto_id")
        .annotate(cantidad=Sum("cantidad"))
    }
    ids_faltantes = {}
    proveedor_faltante = {}
    for f in pendientes.filter(producto__isnull=False).select_related("proveedor").order_by("fecha"):
        ids_faltantes.setdefault(f.producto_id, []).append(f.id)
        if f.proveedor_id:
            proveedor_faltante[f.producto_id] = (f.proveedor_id, f.proveedor.nombre)

    productos = Producto.objects.filter(
        Q(seguimiento_inventario=True, stock__lte=F("stock_minimo")) | Q(pk__in=list(demanda))
    ).select_related("categoria")
    proveedores = ultimo_proveedor([p.pk for p in productos])

    grupos = {}

    def grupo(proveedor):
        clave = proveedor[0] if proveedor else SIN_PROVEEDOR
        if clave not in grupos:
            grupos[clave] = {
                "proveedorId": clave,
                "proveedorNombre": proveedor[1] if proveedor else "Sin proveedor asignado",
                "items": [],
                "costoEstimado": 0,
            }
        return grupos[clave]

    for p in productos:
        pedido_clientes = demanda.get(p.pk, {}).get("cantidad", 0)
        reposicion = max(2 * p.stock_minimo - p.stock, 0) if p.seguimiento_inventario else 0
        sugerido = reposicion + pedido_clientes
        if sugerido <= 0:
            continue
        motivos = []
        if p.seguimiento_inventario and p.stock == 0:
            motivos.append("Agotado")
        elif p.seguimiento_inventario and p.stock <= p.stock_minimo:
            motivos.append("Stock bajo")
        if pedido_clientes:
            motivos.append("Pedido por clientes")
        destino = grupo(proveedores.get(p.pk) or proveedor_faltante.get(p.pk))
        destino["items"].append({
            "tipo": "producto",
            "productoId": p.pk,
            "nombre": p.nombre,
            "categoria": p.categoria.nombre,
            "stockActual": p.stock if p.seguimiento_inventario else None,
            "stockMinimo": p.stock_minimo if p.seguimiento_inventario else None,
            "pedidoClientes": pedido_clientes,
            "sugerido": sugerido,
            "motivos": motivos,
            "ultimoCosto": p.costo,
            "costoEstimado": p.costo * sugerido,
            "faltanteIds": ids_faltantes.get(p.pk, []),
        })
        destino["costoEstimado"] += p.costo * sugerido

    # Productos que no existen en el catálogo, agrupados por nombre normalizado y proveedor.
    for g in agrupar_faltantes(pendientes.filter(producto__isnull=True), por_proveedor=True):
        proveedor = (g["proveedorId"], g["proveedorNombre"]) if g["proveedorId"] else None
        grupo(proveedor)["items"].append({
            "tipo": "nuevo",
            "productoId": None,
            "nombre": g["nombre"],
            "categoria": None,
            "stockActual": None,
            "stockMinimo": None,
            "pedidoClientes": g["cantidadTotal"],
            "sugerido": g["cantidadTotal"],
            "motivos": ["No existe en el catálogo"],
            "ultimoCosto": None,
            "costoEstimado": 0,
            "faltanteIds": g["ids"],
        })

    resultado = sorted(
        grupos.values(),
        key=lambda g: (g["proveedorId"] is None, g["proveedorNombre"].lower()),
    )
    for g in resultado:
        g["items"].sort(key=lambda item: (-item["sugerido"], item["nombre"].lower()))
    return {
        "proveedores": resultado,
        "totalItems": sum(len(g["items"]) for g in resultado),
        "costoEstimadoTotal": sum(g["costoEstimado"] for g in resultado),
    }
