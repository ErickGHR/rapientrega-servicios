import unittest
from datetime import datetime, timedelta, timezone

from rapientrega import (
    EstadoPedido,
    LineaPedido,
    crear_demo,
)


class RapiEntregaTests(unittest.TestCase):
    def setUp(self):
        self.pedidos, self.reparto, self.eventos, _ = crear_demo()
        self.ahora = datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc)

    def test_flujo_completo(self):
        creado = self.pedidos.crearPedido(
            "CLI-1", "REST-1", [LineaPedido("PIZZA", 1)], "tok_ok", self.ahora
        )
        pedido_id = creado["pedidoId"]
        aceptado = self.pedidos.responderPedido(pedido_id, True, self.ahora + timedelta(minutes=1))
        self.assertEqual(EstadoPedido.ACEPTADO.value, aceptado["estado"])
        self.reparto.asignarRepartidor(pedido_id, 19.43, -99.13)
        self.reparto.actualizarUbicacion(pedido_id, "REP-1", 19.431, -99.132)
        entregado = self.reparto.completarEntrega(pedido_id)
        self.assertEqual(EstadoPedido.ENTREGADO.value, entregado["estado"])
        self.assertEqual(5, self.pedidos.calificarServicio(pedido_id, 5)["calificacion"])

    def test_timeout_cancela_y_reembolsa(self):
        creado = self.pedidos.crearPedido(
            "CLI-1", "REST-1", [LineaPedido("AGUA", 2)], "tok_ok", self.ahora
        )
        cancelados = self.pedidos.expirarPedidos(self.ahora + timedelta(minutes=6))
        self.assertEqual(1, len(cancelados))
        self.assertEqual(EstadoPedido.CANCELADO.value, cancelados[0]["estado"])
        pago_id = creado["pagoId"]
        self.assertEqual("REEMBOLSADO", self.pedidos.pagos.pagos[pago_id])


if __name__ == "__main__":
    unittest.main()

