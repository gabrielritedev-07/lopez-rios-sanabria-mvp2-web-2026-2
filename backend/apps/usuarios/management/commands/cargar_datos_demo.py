"""
Carga un catálogo de ejemplo para probar o demostrar el POS.

Uso:
    python manage.py cargar_datos_demo

Es idempotente: si un registro ya existe (por nombre) no lo duplica ni modifica su stock.
No crea ventas ni compras: esas se registran desde la aplicación.
"""
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalogo.models import Categoria, Cliente, Descuento, Producto, Proveedor

CATEGORIAS = ["Cuadernos", "Lápices y colores", "Papelería", "Servicios", "Dulcería"]

# (nombre, categoría, código, precio con IVA, costo, lleva inventario, stock)
PRODUCTOS = [
    ("Cuaderno cuadriculado 100 hojas", "Cuadernos", "CU-100", 6500, 4200, True, 30),
    ("Cuaderno rayado 50 hojas", "Cuadernos", "CU-050", 3800, 2300, True, 25),
    ("Lápiz HB", "Lápices y colores", "LA-HB", 1200, 500, True, 60),
    ("Caja de colores x 12", "Lápices y colores", "CO-12", 9500, 6200, True, 4),
    ("Esfero negro", "Lápices y colores", "ES-NE", 1500, 700, True, 40),
    ("Resma papel carta", "Papelería", "PA-CAR", 21000, 16500, True, 8),
    ("Cartulina blanca", "Papelería", "CA-BL", 1000, 450, True, 50),
    ("Impresión blanco y negro", "Servicios", "SV-IBN", 300, 80, False, 0),
    ("Fotocopia", "Servicios", "SV-FOT", 200, 60, False, 0),
    ("Chocolatina", "Dulcería", "DU-CHO", 2500, 1600, True, 20),
    ("Gomitas surtidas", "Dulcería", "DU-GOM", 1800, 1000, True, 15),
]

# Fechas de vencimiento de ejemplo (días desde hoy) para ver el semáforo de la dulcería.
VENCIMIENTOS = {"Chocolatina": 10, "Gomitas surtidas": 60}

PROVEEDORES = [
    ("Distribuidora Andina", "601 555 0101", "ventas@andina.example"),
    ("Papeles del Norte", "604 555 0202", "pedidos@papelesnorte.example"),
]

CLIENTES = [
    ("Ana Pérez", "300 123 4567", "ana@example.com"),
    ("Colegio San José", "601 555 0303", "compras@colegio.example"),
]

DESCUENTOS = [
    ("Estudiantes 10 %", Descuento.Tipo.PORCENTAJE, 10),
    ("Bono $2.000", Descuento.Tipo.VALOR_FIJO, 2000),
]


class Command(BaseCommand):
    help = "Carga categorías, productos, proveedores, clientes y descuentos de ejemplo."

    @transaction.atomic
    def handle(self, *args, **options):
        categorias = {}
        for nombre in CATEGORIAS:
            categorias[nombre], _ = Categoria.objects.get_or_create(nombre=nombre)

        creados = 0
        for nombre, categoria, codigo, precio, costo, inventario, stock in PRODUCTOS:
            vence = VENCIMIENTOS.get(nombre)
            _, creado = Producto.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "categoria": categorias[categoria],
                    "codigo": codigo,
                    "precio": precio,
                    "costo": costo,
                    "seguimiento_inventario": inventario,
                    "stock": stock,
                    "fecha_vencimiento": timezone.localdate() + timedelta(days=vence) if vence else None,
                },
            )
            creados += creado

        for nombre, telefono, correo in PROVEEDORES:
            Proveedor.objects.get_or_create(nombre=nombre, defaults={"telefono": telefono, "correo": correo})
        for nombre, telefono, correo in CLIENTES:
            Cliente.objects.get_or_create(nombre=nombre, defaults={"telefono": telefono, "correo": correo})
        for nombre, tipo, valor in DESCUENTOS:
            Descuento.objects.get_or_create(nombre=nombre, defaults={"tipo": tipo, "valor": valor})

        call_command("inicializar_kardex", stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS(f"Datos de ejemplo listos ({creados} productos nuevos)."))
