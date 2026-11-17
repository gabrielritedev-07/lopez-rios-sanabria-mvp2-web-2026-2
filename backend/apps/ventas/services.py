"""
Casos de uso de ventas. Aquí vive la lógica de negocio; las vistas solo validan la
entrada con serializers, llaman a estas funciones y responden.

Reglas de dinero (pesos enteros):
- Los precios de los productos YA incluyen IVA.
- subtotal = suma de (precio unitario x cantidad), con precios tomados de la base de datos.
  Los ítems libres (servicios rápidos sin código) usan el valor que digita el cajero.
- descuento: porcentaje del subtotal, o valor fijo. Nunca puede superar el subtotal.
- total = subtotal - descuento.
- iva (informativo) = total - total / (1 + IVA%), es decir, el IVA que ya está dentro del total.
- El backend ignora cualquier subtotal, total, precio de producto o cambio que envíe el frontend.

Cada función que toca ventas e inventario a la vez corre dentro de transaction.atomic():
si algo falla a la mitad, PostgreSQL deshace todo y no quedan datos a medias.
Cada movimiento de stock queda en el kardex del producto.
"""
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.catalogo.inventario import bloquear_productos, mover_stock, validar_stock
from apps.catalogo.models import Descuento, MovimientoInventario

from .models import DetalleReembolso, DetalleVenta, Reembolso, Venta

Mov = MovimientoInventario.Tipo


# --------------------------------------------------------------------------
# Utilidades de cálculo
# --------------------------------------------------------------------------
def redondear(valor):
    """Redondeo comercial a pesos enteros (0,5 sube)."""
    return int(Decimal(valor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def pesos(valor):
    return "$" + f"{valor:,}".replace(",", ".")


def separar_items(items):
    """
    Divide las líneas validadas en:
    - productos: {producto_id: cantidad}
    - libres: [{"nombre", "precio", "costo", "cantidad"}]  (servicios / ítems rápidos)
    """
    productos, libres = {}, []
    for item in items:
        if item.get("producto") is not None:
            productos[item["producto"].pk] = item["cantidad"]
        else:
            libres.append({
                "nombre": item["descripcion"],
                "precio": item["precio"],
                "costo": 0,
                "cantidad": item["cantidad"],
            })
    return productos, libres


def libres_de(detalles):
    return [
        {"nombre": d.nombre_producto, "precio": d.precio_unitario, "costo": d.costo_unitario, "cantidad": d.cantidad}
        for d in detalles
        if d.producto_id is None
    ]


def detalle_libre(venta, libre):
    return DetalleVenta(
        venta=venta,
        producto=None,
        nombre_producto=libre["nombre"],
        precio_unitario=libre["precio"],
        costo_unitario=libre["costo"],
        cantidad=libre["cantidad"],
        subtotal=libre["precio"] * libre["cantidad"],
    )


def subtotal_libres(libres):
    return sum(libre["precio"] * libre["cantidad"] for libre in libres)


def aplicar_descuento(venta, descuento):
    """Guarda la referencia y una fotografía del descuento (o lo quita si es None)."""
    venta.descuento = descuento
    if descuento is None:
        venta.descuento_nombre = ""
        venta.descuento_tipo = ""
        venta.descuento_valor = 0
    else:
        venta.descuento_nombre = descuento.nombre
        venta.descuento_tipo = descuento.tipo
        venta.descuento_valor = descuento.valor


def calcular_totales(venta, subtotal):
    """Calcula descuento, total e IVA incluido a partir del subtotal y la fotografía del descuento."""
    if venta.descuento_tipo == Descuento.Tipo.PORCENTAJE:
        monto = redondear(Decimal(subtotal) * venta.descuento_valor / 100)
    elif venta.descuento_tipo == Descuento.Tipo.VALOR_FIJO:
        monto = venta.descuento_valor
    else:
        monto = 0

    if monto > subtotal:
        raise ValidationError({
            "descuentoId": (
                f"El descuento {venta.descuento_nombre} ({pesos(monto)}) supera el subtotal "
                f"de la venta ({pesos(subtotal)}). El total no puede quedar negativo."
            )
        })

    venta.subtotal = subtotal
    venta.descuento_monto = monto
    venta.total = subtotal - monto
    # Una venta ya cerrada conserva el porcentaje de IVA con el que se registró.
    if venta.estado != Venta.Estado.CERRADA:
        venta.iva_porcentaje = settings.POS_IVA_PORCENTAJE
    base_sin_iva = redondear(Decimal(venta.total) * 100 / (100 + venta.iva_porcentaje))
    venta.iva = venta.total - base_sin_iva


def validar_pago(venta, valor_recibido):
    """Reglas de pago para cerrar o corregir una venta."""
    if venta.metodo_pago == Venta.MetodoPago.DEBE and venta.cliente_id is None:
        raise ValidationError({"clienteId": "Selecciona un cliente para las ventas con pago Debe."})

    if venta.metodo_pago == Venta.MetodoPago.EFECTIVO:
        if valor_recibido is None:
            raise ValidationError({"valorRecibido": "Indica el valor recibido en efectivo."})
        if valor_recibido < venta.total:
            faltante = pesos(venta.total - valor_recibido)
            raise ValidationError({"valorRecibido": f"El valor recibido no alcanza. Faltan {faltante}."})
        venta.valor_recibido = valor_recibido
        venta.cambio = valor_recibido - venta.total
    else:
        venta.valor_recibido = 0
        venta.cambio = 0


def valor_recibido_de(datos, venta):
    valor = datos.get("valor_recibido")
    if valor is not None:
        return valor
    return venta.valor_recibido or None


# --------------------------------------------------------------------------
# Crear, guardar y cerrar ventas
# --------------------------------------------------------------------------
@transaction.atomic
def guardar_venta(*, usuario, datos, venta=None, cerrar=False):
    """
    Crea una venta nueva o actualiza una venta abierta. Si cerrar=True además:
    valida stock y pago, marca la venta como cerrada y descuenta el inventario.
    Los precios de los productos se toman SIEMPRE de la base de datos
    (así una edición en caliente del producto se refleja al guardar o cerrar).
    """
    if venta is None:
        venta = Venta(creada_por=usuario)
    else:
        venta = Venta.objects.select_for_update().get(pk=venta.pk)
        if venta.estado != Venta.Estado.ABIERTA:
            raise ValidationError({
                "detail": f"La venta {venta.numero} ya está cerrada. Para modificarla usa la corrección de ventas."
            })

    if "cliente" in datos:
        venta.cliente = datos["cliente"]
    if "metodo_pago" in datos:
        venta.metodo_pago = datos["metodo_pago"]
    if "descuento" in datos:
        aplicar_descuento(venta, datos["descuento"])

    if "items" in datos:
        cantidades, libres = separar_items(datos["items"])
    elif venta.pk:
        detalles = list(venta.items.all())
        cantidades = {d.producto_id: d.cantidad for d in detalles if d.producto_id}
        libres = libres_de(detalles)
    else:
        cantidades, libres = {}, []
    if not cantidades and not libres:
        raise ValidationError({"items": "La venta debe tener al menos un producto."})

    productos = bloquear_productos(cantidades)
    if cerrar:
        validar_stock(productos, cantidades)

    calcular_totales(
        venta,
        sum(productos[pid].precio * cantidad for pid, cantidad in cantidades.items()) + subtotal_libres(libres),
    )

    if cerrar:
        validar_pago(venta, valor_recibido_de(datos, venta))
        ahora = timezone.now()
        venta.estado = Venta.Estado.CERRADA
        venta.fecha = ahora
        venta.cerrada_en = ahora
        venta.cerrada_por = usuario
    elif datos.get("valor_recibido") is not None:
        venta.valor_recibido = datos["valor_recibido"]
    venta.save()

    # Las líneas de una venta abierta se reemplazan completas con la fotografía actual.
    venta.items.all().delete()
    DetalleVenta.objects.bulk_create(
        [
            DetalleVenta(
                venta=venta,
                producto=productos[pid],
                nombre_producto=productos[pid].nombre,
                precio_unitario=productos[pid].precio,
                costo_unitario=productos[pid].costo,
                cantidad=cantidad,
                subtotal=productos[pid].precio * cantidad,
            )
            for pid, cantidad in cantidades.items()
        ]
        + [detalle_libre(venta, libre) for libre in libres]
    )

    if cerrar:
        for pid, cantidad in cantidades.items():
            mover_stock(productos[pid], -cantidad, tipo=Mov.VENTA, usuario=usuario, referencia=venta.numero)
    return venta


# --------------------------------------------------------------------------
# Corrección de ventas cerradas
# --------------------------------------------------------------------------
@transaction.atomic
def corregir_venta(*, usuario, venta, datos):
    """
    Modifica productos, cantidades, cliente, método de pago y descuento de una venta
    cerrada, conservando su id. Ajusta el inventario solo por la DIFERENCIA entre la
    venta original y la corregida. Los productos que ya estaban conservan el precio
    con el que se vendieron; los nuevos toman el precio actual. Los ítems libres se
    reemplazan por los que lleguen en la corrección.
    """
    venta = Venta.objects.select_for_update().get(pk=venta.pk)
    if venta.estado != Venta.Estado.CERRADA:
        raise ValidationError({"detail": "Solo se pueden corregir ventas cerradas."})
    if venta.reembolsos.exists():
        raise ValidationError({
            "detail": f"La venta {venta.numero} tiene reembolsos y ya no se puede corregir."
        })

    detalles = list(venta.items.all())
    anteriores = {d.producto_id: d for d in detalles if d.producto_id}
    if "items" in datos:
        nuevas, libres = separar_items(datos["items"])
    else:
        nuevas = {pid: d.cantidad for pid, d in anteriores.items()}
        libres = libres_de(detalles)
    if not nuevas and not libres:
        raise ValidationError({"items": "La venta corregida debe tener al menos un producto."})

    productos = bloquear_productos(set(anteriores) | set(nuevas))
    diferencias = {
        pid: nuevas.get(pid, 0) - (anteriores[pid].cantidad if pid in anteriores else 0)
        for pid in productos
    }
    validar_stock(
        productos,
        {pid: dif for pid, dif in diferencias.items() if dif > 0},
        etiqueta="unidades adicionales",
    )

    if "cliente" in datos:
        venta.cliente = datos["cliente"]
    if "metodo_pago" in datos:
        venta.metodo_pago = datos["metodo_pago"]
    if "descuento" in datos:
        aplicar_descuento(venta, datos["descuento"])
    # Si no se envía descuentoId se conserva la fotografía original del descuento,
    # aunque ese descuento ya no exista en el catálogo.

    def precio(pid):
        return anteriores[pid].precio_unitario if pid in anteriores else productos[pid].precio

    calcular_totales(
        venta,
        sum(precio(pid) * cantidad for pid, cantidad in nuevas.items()) + subtotal_libres(libres),
    )
    validar_pago(venta, valor_recibido_de(datos, venta))

    venta.corregida = True
    venta.corregida_por = usuario
    venta.corregida_en = timezone.now()
    venta.save()

    for pid, detalle in anteriores.items():
        if pid not in nuevas:
            detalle.delete()
    for pid, cantidad in nuevas.items():
        if pid in anteriores:
            detalle = anteriores[pid]
            if detalle.cantidad != cantidad:
                detalle.cantidad = cantidad
                detalle.subtotal = detalle.precio_unitario * cantidad
                detalle.save(update_fields=["cantidad", "subtotal"])
        else:
            producto = productos[pid]
            DetalleVenta.objects.create(
                venta=venta,
                producto=producto,
                nombre_producto=producto.nombre,
                precio_unitario=producto.precio,
                costo_unitario=producto.costo,
                cantidad=cantidad,
                subtotal=producto.precio * cantidad,
            )
    DetalleVenta.objects.filter(venta=venta, producto__isnull=True).delete()
    DetalleVenta.objects.bulk_create([detalle_libre(venta, libre) for libre in libres])

    # Más unidades que antes -> sale stock; menos unidades -> el stock vuelve.
    for pid, diferencia in diferencias.items():
        mover_stock(
            productos[pid], -diferencia, tipo=Mov.CORRECCION, usuario=usuario, referencia=venta.numero
        )
    return venta


# --------------------------------------------------------------------------
# Reembolsos
# --------------------------------------------------------------------------
def repartir_total(detalles, total, subtotal):
    """
    Reparte el total pagado (ya con descuento) entre las líneas, en proporción a su
    subtotal, de forma que la suma sea exactamente el total. Así, reembolsar todo
    devuelve exactamente lo que pagó el cliente, sin errores de redondeo.
    """
    if subtotal == 0:
        return {d.pk: 0 for d in detalles}
    exactos = {d.pk: Decimal(d.subtotal) * total / subtotal for d in detalles}
    asignado = {pk: int(valor.to_integral_value(rounding=ROUND_FLOOR)) for pk, valor in exactos.items()}
    sobrante = total - sum(asignado.values())
    por_fraccion = sorted(exactos, key=lambda pk: (exactos[pk] - asignado[pk], -pk), reverse=True)
    for pk in por_fraccion[:sobrante]:
        asignado[pk] += 1
    return asignado


@transaction.atomic
def registrar_reembolso(*, usuario, venta, datos):
    """
    Reembolso parcial o total. Valida que no se reembolse más de lo vendido
    (descontando reembolsos previos), calcula el valor respetando el descuento de la
    venta y devuelve stock solo si se indica que el producto retorna al inventario.
    Cada línea se identifica por detalleId (sirve también para ítems libres) o productoId.
    """
    venta = Venta.objects.select_for_update().get(pk=venta.pk)
    if venta.estado != Venta.Estado.CERRADA:
        raise ValidationError({"detail": "Solo se pueden reembolsar productos de ventas cerradas."})

    detalles = list(DetalleVenta.objects.select_for_update().filter(venta=venta).order_by("pk"))
    ya_reembolsado = dict(
        DetalleReembolso.objects.filter(detalle_venta__venta=venta)
        .values("detalle_venta")
        .annotate(total=Sum("cantidad"))
        .values_list("detalle_venta", "total")
    )
    disponible = {d.pk: d.cantidad - ya_reembolsado.get(d.pk, 0) for d in detalles}
    por_id = {d.pk: d for d in detalles}
    por_producto = {d.producto_id: d for d in detalles if d.producto_id}

    solicitudes = []  # (detalle, cantidad, retorna_inventario)
    if datos.get("todo"):
        retorna = datos.get("retorna_inventario", True)
        solicitudes = [(d, disponible[d.pk], retorna) for d in detalles if disponible[d.pk] > 0]
        if not solicitudes:
            raise ValidationError({"detail": f"La venta {venta.numero} ya fue reembolsada en su totalidad."})
    else:
        for item in datos["items"]:
            if item.get("detalle_id"):
                detalle = por_id.get(item["detalle_id"])
                referencia = f"la línea {item['detalle_id']}"
            else:
                detalle = por_producto.get(item.get("producto_id"))
                referencia = f"el producto con id {item.get('producto_id')}"
            if detalle is None:
                raise ValidationError({"items": f"{referencia.capitalize()} no pertenece a la venta {venta.numero}."})
            if item["cantidad"] > disponible[detalle.pk]:
                raise ValidationError({
                    "items": (
                        f"Solo se pueden reembolsar {disponible[detalle.pk]} unidad(es) de "
                        f"{detalle.nombre_producto} (vendidas: {detalle.cantidad})."
                    )
                })
            solicitudes.append((detalle, item["cantidad"], item["retorna_inventario"]))

    netos = repartir_total(detalles, venta.total, venta.subtotal)
    lineas = []
    for detalle, cantidad, retorna in solicitudes:
        previo = ya_reembolsado.get(detalle.pk, 0)
        neto = Decimal(netos[detalle.pk])
        # Valor acumulado tras el reembolso menos valor acumulado antes: evita descuadres.
        valor = redondear(neto * (previo + cantidad) / detalle.cantidad) - redondear(
            neto * previo / detalle.cantidad
        )
        lineas.append(
            DetalleReembolso(
                detalle_venta=detalle,
                cantidad=cantidad,
                valor=valor,
                retorna_inventario=bool(retorna and detalle.producto_id),
            )
        )

    reembolso = Reembolso.objects.create(
        venta=venta,
        usuario=usuario,
        total=sum(linea.valor for linea in lineas),
        motivo=datos.get("motivo", ""),
    )
    for linea in lineas:
        linea.reembolso = reembolso
    DetalleReembolso.objects.bulk_create(lineas)

    a_retornar = {}
    for detalle, cantidad, retorna in solicitudes:
        disponible[detalle.pk] -= cantidad
        if retorna and detalle.producto_id:
            a_retornar[detalle.producto_id] = a_retornar.get(detalle.producto_id, 0) + cantidad
    if a_retornar:
        productos = bloquear_productos(a_retornar)
        for pid, cantidad in a_retornar.items():
            mover_stock(
                productos[pid], cantidad, tipo=Mov.REEMBOLSO, usuario=usuario, referencia=venta.numero,
                nota=datos.get("motivo", ""),
            )

    venta.estado_reembolso = (
        Venta.EstadoReembolso.TOTAL
        if all(pendiente == 0 for pendiente in disponible.values())
        else Venta.EstadoReembolso.PARCIAL
    )
    venta.save(update_fields=["estado_reembolso", "actualizado_en"])
    return reembolso
