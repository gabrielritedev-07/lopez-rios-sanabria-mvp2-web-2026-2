"""Ítems libres, costos ocultos y cartera de clientes con abonos. Ejecutar: python manage.py test apps.ventas"""
from rest_framework import status

from .tests import BaseVentasTest


class ItemsLibresTests(BaseVentasTest):
    def libre(self, descripcion="Anillado", precio=3500, cantidad=2):
        return {"descripcion": descripcion, "precio": precio, "cantidad": cantidad}

    def test_venta_con_item_libre_no_mueve_inventario(self):
        venta = self.crear_cerrada(items=[{"productoId": self.cuaderno.id, "cantidad": 1}, self.libre()])
        self.assertEqual(venta["total"], 17000)
        libre = next(i for i in venta["items"] if i["esLibre"])
        self.assertIsNone(libre["productoId"])
        self.assertEqual((libre["nombre"], libre["subtotal"]), ("Anillado", 7000))
        self.assertEqual(self.stock(self.cuaderno), 9)

    def test_item_libre_requiere_descripcion_y_valor(self):
        for linea in ({"precio": 100, "cantidad": 1}, {"descripcion": "Copia", "cantidad": 1},
                      {"descripcion": "Copia", "precio": 0, "cantidad": 1}):
            with self.subTest(linea=linea):
                respuesta = self.crear(items=[linea])
                self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reembolso_de_item_libre_por_detalle(self):
        venta = self.crear_cerrada(items=[self.libre()])
        detalle = venta["items"][0]["id"]
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(
            f"/api/ventas/{venta['id']}/reembolsos/", {"items": [{"detalleId": detalle, "cantidad": 1}]}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(respuesta.data["reembolsos"][0]["total"], 3500)
        self.assertFalse(respuesta.data["reembolsos"][0]["items"][0]["retornaInventario"])

    def test_correccion_conserva_items_libres(self):
        venta = self.crear_cerrada(items=[{"productoId": self.cuaderno.id, "cantidad": 1}, self.libre()])
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(
            f"/api/ventas/{venta['id']}/corregir/", {"metodoPago": "Efectivo", "valorRecibido": 20000}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.assertEqual(respuesta.data["total"], 17000)
        self.assertEqual(sum(1 for i in respuesta.data["items"] if i["esLibre"]), 1)

    def test_el_cajero_no_ve_el_costo_de_las_lineas(self):
        venta = self.crear_cerrada()
        self.assertNotIn("costoUnitario", venta["items"][0])
        self.client.force_authenticate(self.admin)
        detalle = self.client.get(f"/api/ventas/{venta['id']}/").data
        self.assertEqual(detalle["items"][0]["costoUnitario"], 6000)


class CarteraTests(BaseVentasTest):
    def setUp(self):
        super().setUp()
        self.venta = self.crear_cerrada(metodoPago="Debe", clienteId=self.cliente.id)  # 22.000 fiados
        self.url = f"/api/clientes/{self.cliente.id}"

    def abonar(self, **datos):
        return self.client.post(f"{self.url}/abonos/", datos, format="json")

    def test_saldo_en_listado_y_en_cartera(self):
        clientes = self.client.get("/api/clientes/").data
        self.assertEqual(clientes[0]["saldo"], 22000)
        cartera = self.client.get(f"{self.url}/cartera/").data
        self.assertEqual(cartera["saldo"], 22000)
        self.assertEqual(cartera["totalFiado"], 22000)
        self.assertEqual(len(cartera["ventas"]), 1)

    def test_venta_de_contado_no_genera_deuda(self):
        self.crear_cerrada(metodoPago="Nequi", clienteId=self.cliente.id)
        self.assertEqual(self.client.get(f"{self.url}/cartera/").data["saldo"], 22000)

    def test_abonos_parcial_y_total(self):
        parcial = self.abonar(valor=10000, metodoPago="Efectivo", nota="Primer pago")
        self.assertEqual(parcial.status_code, status.HTTP_201_CREATED, parcial.data)
        self.assertEqual(parcial.data["saldo"], 12000)
        self.assertEqual(parcial.data["abonos"][0]["usuario"], "cajero_test")
        total = self.abonar(valor=12000, metodoPago="Nequi")
        self.assertEqual(total.data["saldo"], 0)
        self.assertEqual(len(total.data["abonos"]), 2)
        self.assertEqual(self.abonar(valor=1).status_code, status.HTTP_400_BAD_REQUEST)

    def test_validaciones_del_abono(self):
        self.assertEqual(self.abonar(valor=30000).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.abonar(valor=0).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.abonar(valor=100, metodoPago="Debe").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post("/api/clientes/9999/abonos/", {"valor": 1}, format="json").status_code, 404)

    def test_reembolso_de_venta_fiada_reduce_la_deuda(self):
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/ventas/{self.venta['id']}/reembolsos/", {"todo": True}, format="json")
        self.assertEqual(self.client.get(f"{self.url}/cartera/").data["saldo"], 0)

    def test_cliente_con_deuda_no_se_elimina(self):
        self.abonar(valor=1000)
        respuesta = self.client.delete(f"{self.url}/")
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
