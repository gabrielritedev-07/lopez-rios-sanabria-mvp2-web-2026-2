"""
Formato único de errores de la API.

Toda respuesta de error tiene esta forma, para que el frontend muestre siempre
`detail` al usuario:

    {
      "detail": "precio: El precio no puede ser negativo.",   # mensaje principal
      "codigo": "token_not_valid",                             # opcional
      "errores": {"precio": ["El precio no puede ser negativo."]}  # opcional, por campo
    }
"""
from collections import Counter

from django.db.models import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

CLAVES_GENERALES = {"detail", "non_field_errors"}


def primer_mensaje(datos, campo=""):
    """Busca el primer mensaje legible dentro de la estructura de errores de DRF."""
    if isinstance(datos, dict):
        for clave, valor in datos.items():
            if clave in {"code", "messages"}:
                continue
            mensaje = primer_mensaje(valor, "" if clave in CLAVES_GENERALES else clave)
            if mensaje:
                return mensaje
        return None
    if isinstance(datos, list):
        for valor in datos:
            mensaje = primer_mensaje(valor, campo)
            if mensaje:
                return mensaje
        return None
    if datos in (None, ""):
        return None
    return f"{campo}: {datos}" if campo else str(datos)


def mensaje_registros_asociados(exc):
    objetos = getattr(exc, "protected_objects", None) or getattr(exc, "restricted_objects", None) or []
    conteo = Counter(str(obj._meta.verbose_name_plural) for obj in objetos)
    detalle = ", ".join(f"{cantidad} {nombre}" for nombre, cantidad in conteo.items())
    sufijo = f" ({detalle})" if detalle else ""
    return f"No se puede eliminar porque tiene registros asociados{sufijo}."


def manejar_excepcion(exc, context):
    # Eliminar algo protegido por on_delete=PROTECT (ej. categoría con productos).
    if isinstance(exc, (ProtectedError, RestrictedError)):
        return Response(
            {"detail": mensaje_registros_asociados(exc), "codigo": "registros_asociados"},
            status=status.HTTP_409_CONFLICT,
        )

    response = exception_handler(exc, context)
    if response is None:
        return None  # Error inesperado: Django responde 500 (y en DEBUG muestra el detalle).

    datos = response.data
    cuerpo = {"detail": primer_mensaje(datos) or "Ocurrió un error al procesar la solicitud."}
    if isinstance(datos, dict):
        if datos.get("code"):
            cuerpo["codigo"] = datos["code"]
        errores = {k: v for k, v in datos.items() if k not in {"detail", "code", "messages"}}
        if errores:
            cuerpo["errores"] = errores
    elif isinstance(datos, list):
        cuerpo["errores"] = {"non_field_errors": datos}
    response.data = cuerpo
    return response
