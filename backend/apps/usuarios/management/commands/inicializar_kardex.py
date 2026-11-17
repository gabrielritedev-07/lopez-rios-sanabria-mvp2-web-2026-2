"""
Crea el movimiento "Saldo inicial" en el kardex de los productos que ya tenían stock
antes de activar el historial de movimientos.

Uso (una sola vez, después de migrar):
    python manage.py inicializar_kardex

Es idempotente: no toca productos que ya tienen movimientos.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalogo.models import MovimientoInventario, Producto


class Command(BaseCommand):
    help = "Registra el saldo inicial en el kardex de los productos con stock y sin movimientos."

    @transaction.atomic
    def handle(self, *args, **options):
        productos = Producto.objects.filter(seguimiento_inventario=True, stock__gt=0, movimientos__isnull=True)
        creados = 0
        for producto in productos:
            MovimientoInventario.objects.create(
                producto=producto,
                tipo=MovimientoInventario.Tipo.INICIAL,
                cantidad=producto.stock,
                stock_anterior=0,
                stock_resultante=producto.stock,
                nota="Saldo inicial al activar el kardex",
            )
            creados += 1
        self.stdout.write(self.style.SUCCESS(f"Kardex inicializado en {creados} producto(s)."))
