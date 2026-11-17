"""Turnos de caja y arqueo. Ejecutar: python manage.py test apps.caja"""
from rest_framework import status

from apps.ventas.tests import BaseVentasTest


class CajaTests(BaseVentasTest):
    def abrir(self, base):
        return self.client.post("/api/caja/abrir/", {"baseInicial": base}, format="json")

    def cerrar(self, contado, observaciones=""):
        return self.client.post(
            "/api/caja/cerrar/", {"efectivoContado": contado, "observaciones": observaciones}, format="json"
        )

    def actual(self):
        return self.client.get("/api/caja/turno-actual/").data

    def test_flujo_completo_con_faltante(self):
        self.assertFalse(self.actual()["abierto"])
        self.assertEqual(self.abrir(50000).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.abrir(10).status_code, status.HTTP_400_BAD_REQUEST)

        self.crear_cerrada(metodoPago="Efectivo", valorRecibido=30000)  # 22.000 en efectivo
        self.crear_cerrada(items=[{"productoId": self.cuaderno.id, "cantidad": 1}], metodoPago="Nequi")
        self.crear_cerrada(
            items=[{"productoId": self.lapiz.id, "cantidad": 1}], metodoPago="Debe", clienteId=self.cliente.id
        )
        self.client.post(f"/api/clientes/{self.cliente.id}/abonos/", {"valor": 1000, "metodoPago": "Efectivo"}, format="json")

        turno = self.actual()["turno"]
        self.assertEqual(turno["cantidadVentas"], 3)
        self.assertEqual(turno["ventasEfectivo"], 22000)
        self.assertEqual(turno["ventasNequi"], 10000)
        self.assertEqual(turno["ventasDebe"], 2000)
        self.assertEqual(turno["abonosEfectivo"], 1000)
        self.assertEqual(turno["efectivoEsperado"], 73000)  # 50.000 + 22.000 + 1.000

        cierre = self.cerrar(72000, "Faltó un billete")
        self.assertEqual(cierre.status_code, status.HTTP_200_OK, cierre.data)
        self.assertEqual(cierre.data["turno"]["diferencia"], -1000)
        self.assertEqual(cierre.data["turno"]["resultado"], "faltante")
        self.assertEqual(cierre.data["turno"]["estado"], "cerrado")
        self.assertFalse(self.actual()["abierto"])

    def test_cuadrado_y_sobrante(self):
        self.abrir(0)
        self.assertEqual(self.cerrar(0).data["turno"]["resultado"], "cuadrado")
        self.abrir(1000)
        cierre = self.cerrar(1500).data["turno"]
        self.assertEqual((cierre["resultado"], cierre["diferencia"]), ("sobrante", 500))

    def test_reembolso_en_efectivo_sale_de_la_caja(self):
        self.client.force_authenticate(self.admin)
        self.abrir(10000)
        venta = self.crear_cerrada(metodoPago="Efectivo", valorRecibido=22000)
        self.client.post(
            f"/api/ventas/{venta['id']}/reembolsos/", {"items": [{"productoId": self.lapiz.id, "cantidad": 1}]},
            format="json",
        )
        turno = self.actual()["turno"]
        self.assertEqual(turno["reembolsosEfectivo"], 2000)
        self.assertEqual(turno["efectivoEsperado"], 30000)  # 10.000 + 22.000 - 2.000

    def test_ventas_de_otro_usuario_no_cuentan(self):
        self.abrir(0)
        self.client.force_authenticate(self.admin)
        self.crear_cerrada(metodoPago="Efectivo", valorRecibido=22000)
        self.client.force_authenticate(self.cajero)
        self.assertEqual(self.actual()["turno"]["ventasEfectivo"], 0)

    def test_cerrar_sin_turno_y_validaciones(self):
        self.assertEqual(self.cerrar(0).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.abrir(-5).status_code, status.HTTP_400_BAD_REQUEST)

    def test_historial_segun_rol(self):
        self.abrir(0)
        self.cerrar(0)
        self.client.force_authenticate(self.admin)
        self.abrir(5000)
        self.assertEqual(len(self.client.get("/api/caja/turnos/").data), 2)
        self.client.force_authenticate(self.cajero)
        propios = self.client.get("/api/caja/turnos/").data
        self.assertEqual(len(propios), 1)
        self.assertEqual(propios[0]["usuario"], "cajero_test")
