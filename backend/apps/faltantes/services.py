"""
Agrupación de faltantes para decidir próximas compras y para el reporte de faltantes frecuentes.

Regla de agrupación:
- Si el faltante está ligado a un producto del catálogo, se agrupa por ese producto.
- Si es un producto descrito en texto, se agrupa por su nombre normalizado
  (minúsculas, sin tildes y plural simple; ver utils.py). Así "Lápices de colores"
  y "lapiz de color" cuentan como el mismo producto.
"""
from .models import Faltante


def clave_producto(faltante):
    if faltante.producto_id:
        return ("producto", faltante.producto_id)
    return ("texto", faltante.nombre_normalizado)


def agrupar_faltantes(consulta, por_proveedor=False):
    """
    Devuelve una lista de grupos ordenada por número de solicitudes (mayor primero).
    Con por_proveedor=True separa cada producto por proveedor (vista para compras).
    """
    grupos = {}
    for faltante in consulta.select_related("producto", "proveedor").order_by("fecha", "id"):
        clave = (clave_producto(faltante), faltante.proveedor_id if por_proveedor else None)
        grupo = grupos.get(clave)
        if grupo is None:
            grupo = {
                "productoId": faltante.producto_id,
                "nombre": "",
                "nombreNormalizado": faltante.nombre_normalizado,
                "solicitudes": 0,
                "cantidadTotal": 0,
                "pendientes": 0,
                "tipos": set(),
                "primeraSolicitud": faltante.fecha,
                "ultimaSolicitud": faltante.fecha,
                "stockActual": None,
                "ids": [],
            }
            if por_proveedor:
                grupo["proveedorId"] = faltante.proveedor_id
                grupo["proveedorNombre"] = faltante.proveedor.nombre if faltante.proveedor else None
            grupos[clave] = grupo

        grupo["solicitudes"] += 1
        grupo["cantidadTotal"] += faltante.cantidad
        grupo["tipos"].add(faltante.tipo)
        grupo["ultimaSolicitud"] = faltante.fecha
        if faltante.estado == Faltante.Estado.PENDIENTE:
            grupo["pendientes"] += 1
            grupo["ids"].append(faltante.id)
        if faltante.producto_id:
            grupo["nombre"] = faltante.producto.nombre
            grupo["stockActual"] = (
                faltante.producto.stock if faltante.producto.seguimiento_inventario else None
            )
        else:
            grupo["nombre"] = faltante.nombre_original  # el más reciente

    resultado = []
    for grupo in grupos.values():
        grupo["tipos"] = sorted(grupo["tipos"])
        resultado.append(grupo)
    resultado.sort(key=lambda g: (-g["solicitudes"], -g["cantidadTotal"], g["nombre"].lower()))
    return resultado
