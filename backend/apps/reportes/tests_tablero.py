"""KPIs del día, top de productos, tendencia y sugerencia de pedido. Ejecutar: python manage.py test apps.reportes"""
from rest_framework import status

from apps.catalogo.models import Proveedor
from apps.ventas.tests import BaseVentasTest


class TableroTests(BaseVentasTest):
    """
    Ventas del día (precios: Cuaderno 10.000 / costo 6.000; Lápiz 2.000 / costo 800):
    - V1: 2 cuadernos + 1 lápiz, Efectivo  -> 22.000 (costo 12.800)
    - V2: 2 lápices, Nequi                 ->  4.000 (costo  1.600)
    - V3: 1 cuaderno, Debe (Ana)           -> 10.000 (costo  6.000)
    - Abono de Ana: 3.000 en efectivo
    """

    def setUp(self):
        super().setUp()
        self.v1 = self.crear_cerrada(metodoPago="Efectivo", valorRecibido=22000)
        self.crear_cerrada(items=[{"productoId": self.lapiz.id, "cantidad": 2}], metodoPago="Nequi")
        self.crear_cerrada(
            items=[{"productoId": self.cuaderno.id, "cantidad": 1}], metodoPago="Debe", clienteId=self.cliente.id
        )
        self.client.post(f"/api/clientes/{self.cliente.id}/abonos/", {"valor": 3000}, format="json")
        self.client.force_authenticate(self.admin)

    def test_kpis_del_dia(self):
        datos = self.client.get("/api/reportes/resumen-dia/").data
        self.assertEqual(datos["totalVendido"], 36000)
        self.assertEqual(datos["cantidadVentas"], 3)
        self.assertEqual(datos["ticketPromedio"], 12000)
        self.assertEqual(datos["costoVendido"], 20400)
        self.assertEqual(datos["gananciaEstimada"], 15600)
        metodos = {m["metodoPago"]: m for m in datos["porMetodoPago"]}
        self.assertEqual(metodos["Efectivo"]["total"], 22000)
        self.assertEqual(metodos["Efectivo"]["abonos"], 3000)
        self.assertEqual(metodos["Nequi"]["total"], 4000)
        self.assertEqual(metodos["Debe"]["total"], 10000)
        self.assertEqual(datos["dineroRecibido"], 29000)

    def test_reembolso_descuenta_ingreso_y_costo(self):
        self.client.post(
            f"/api/ventas/{self.v1['id']}/reembolsos/", {"items": [{"productoId": self.lapiz.id, "cantidad": 1}]},
            format="json",
        )
        datos = self.client.get("/api/reportes/resumen-dia/").data
        self.assertEqual(datos["totalReembolsado"], 2000)
        self.assertEqual(datos["gananciaEstimada"], 14400)  # (36.000 - 2.000) - (20.400 - 800)

    def test_top_productos_por_unidades_y_por_ganancia(self):
        datos = self.client.get("/api/reportes/top-productos/?periodo=hoy").data
        self.assertEqual([p["nombre"] for p in datos["porUnidades"]], ["Cuaderno", "Lápiz"])
        primero = datos["porGanancia"][0]
        self.assertEqual((primero["nombre"], primero["ganancia"], primero["margen"]), ("Cuaderno", 12000, 40.0))
        for periodo in ("semana", "mes"):
            with self.subTest(periodo=periodo):
                self.assertEqual(self.client.get(f"/api/reportes/top-productos/?periodo={periodo}").status_code, 200)
        self.assertEqual(self.client.get("/api/reportes/top-productos/?periodo=anio").status_code, 400)

    def test_tendencia_de_7_y_30_dias(self):
        siete = self.client.get("/api/reportes/tendencia/?dias=7").data["dias"]
        self.assertEqual(len(siete), 7)
        self.assertEqual((siete[-1]["ingresos"], siete[-1]["costos"], siete[-1]["ganancia"]), (36000, 20400, 15600))
        self.assertEqual(siete[0]["ingresos"], 0)
        self.assertEqual(len(self.client.get("/api/reportes/tendencia/?dias=30").data["dias"]), 30)
        self.assertEqual(self.client.get("/api/reportes/tendencia/?dias=10").status_code, 400)

    def test_cajero_no_ve_el_tablero_financiero(self):
        self.client.force_authenticate(self.cajero)
        for ruta in ("reportes/resumen-dia/", "reportes/top-productos/", "reportes/tendencia/", "compras/sugerencia-pedido/"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(f"/api/{ruta}").status_code, status.HTTP_403_FORBIDDEN)

    def test_sugerencia_de_pedido(self):
        # Tras las ventas: Lápiz 5 - 1 - 2 = 2 (mínimo 5) y Cuaderno 10 - 3 = 7.
        proveedor = Proveedor.objects.create(nombre="Papeles del Norte")
        self.client.force_authenticate(self.cajero)
        self.client.post(
            "/api/faltantes/",
            {"productoId": self.cuaderno.id, "tipo": "agotado", "cantidad": 4, "proveedorId": proveedor.id},
            format="json",
        )
        self.client.post("/api/faltantes/", {"nombre": "Témperas", "tipo": "inexistente", "cantidad": 6}, format="json")
        self.client.force_authenticate(self.admin)
        datos = self.client.get("/api/compras/sugerencia-pedido/").data
        items = {i["nombre"]: (g["proveedorNombre"], i) for g in datos["proveedores"] for i in g["items"]}
        self.assertEqual(items["Lápiz"][1]["sugerido"], 8)  # reponer hasta 2 x 5
        self.assertEqual(items["Lápiz"][0], "Sin proveedor asignado")
        self.assertEqual(items["Cuaderno"][1]["sugerido"], 7)  # (10 - 7) + 4 pedidos por clientes
        self.assertEqual(items["Cuaderno"][0], "Papeles del Norte")
        self.assertEqual(items["Témperas"][1]["sugerido"], 6)
        self.assertNotIn("Impresión", items)
