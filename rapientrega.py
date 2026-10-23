"""Prototipo de servicios y eventos para el caso RapiEntrega."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import hypot
from typing import Callable, Dict, List
from uuid import uuid4


class ErrorServicio(Exception):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


class EstadoPedido(str, Enum):
    PAGO_AUTORIZADO = "PAGO_AUTORIZADO"
    ACEPTADO = "ACEPTADO"
    EN_REPARTO = "EN_REPARTO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


@dataclass(frozen=True)
class Producto:
    productoId: str
    restauranteId: str
    nombre: str
    precioCentavos: int
    disponible: bool = True


@dataclass(frozen=True)
class LineaPedido:
    productoId: str
    cantidad: int


@dataclass
class Repartidor:
    repartidorId: str
    latitud: float
    longitud: float
    disponible: bool = True


@dataclass
class Pedido:
    pedidoId: str
    clienteId: str
    restauranteId: str
    lineas: List[LineaPedido]
    totalCentavos: int
    pagoId: str
    creadoEn: datetime
    limiteAceptacion: datetime
    estado: EstadoPedido = EstadoPedido.PAGO_AUTORIZADO
    repartidorId: str | None = None
    calificacion: int | None = None


class BusEventos:
    """Publicación-suscripción síncrona en memoria para demostrar el contrato."""

    def __init__(self) -> None:
        self.suscriptores: Dict[str, List[Callable[[dict], None]]] = {}
        self.historial: List[dict] = []

    def suscribir(self, tipo: str, manejador: Callable[[dict], None]) -> None:
        self.suscriptores.setdefault(tipo, []).append(manejador)

    def publicar(self, tipo: str, datos: dict) -> None:
        evento = {
            "eventoId": str(uuid4()),
            "tipo": tipo,
            "ocurrioEn": datetime.now(timezone.utc).isoformat(),
            "datos": datos,
        }
        self.historial.append(evento)
        for manejador in self.suscriptores.get(tipo, []):
            manejador(evento)


class FachadaPagos:
    """Contrato estable que aísla la API de la pasarela externa."""

    def __init__(self) -> None:
        self.pagos: Dict[str, str] = {}

    def autorizarPago(self, pedidoId: str, montoCentavos: int, tokenTarjeta: str) -> dict:
        if montoCentavos <= 0:
            raise ErrorServicio("MONTO_INVALIDO", "El monto debe ser positivo.")
        if not tokenTarjeta.startswith("tok_"):
            raise ErrorServicio("PAGO_RECHAZADO", "La pasarela rechazó la tarjeta.")
        pago_id = f"PAY-{uuid4().hex[:10]}"
        self.pagos[pago_id] = "AUTORIZADO"
        return {"pagoId": pago_id, "estado": "AUTORIZADO"}

    def reembolsarPago(self, pagoId: str, motivo: str) -> dict:
        if self.pagos.get(pagoId) != "AUTORIZADO":
            raise ErrorServicio("PAGO_NO_REEMBOLSABLE", "El pago no puede reembolsarse.")
        self.pagos[pagoId] = "REEMBOLSADO"
        return {"pagoId": pagoId, "estado": "REEMBOLSADO", "motivo": motivo}


class EnvoltorioFacturacionHeredada:
    """Traduce el contrato canónico a la interfaz simulada del sistema de 2012."""

    def __init__(self) -> None:
        self.facturas: Dict[str, dict] = {}

    def emitirFactura(self, pedido: Pedido, rfc: str) -> dict:
        folio = f"FAC-{len(self.facturas) + 1:06d}"
        registro_2012 = {
            "FOL": folio,
            "RFC_CTE": rfc,
            "IMP_CTV": pedido.totalCentavos,
            "REF_PED": pedido.pedidoId,
        }
        self.facturas[folio] = registro_2012
        return {"folioFactura": folio, "estado": "EMITIDA"}


class ServicioPedidos:
    """Abstracción de proceso: coordina catálogo, pago y ciclo del pedido."""

    def __init__(
        self,
        productos: Dict[str, Producto],
        pagos: FachadaPagos,
        eventos: BusEventos,
    ) -> None:
        self.productos = productos
        self.pagos = pagos
        self.eventos = eventos
        self.pedidos: Dict[str, Pedido] = {}

    def crearPedido(
        self,
        clienteId: str,
        restauranteId: str,
        lineas: List[LineaPedido],
        tokenTarjeta: str,
        ahora: datetime | None = None,
    ) -> dict:
        ahora = ahora or datetime.now(timezone.utc)
        if not lineas:
            raise ErrorServicio("PEDIDO_VACIO", "El pedido debe contener productos.")
        total = 0
        for linea in lineas:
            producto = self.productos.get(linea.productoId)
            if not producto or not producto.disponible:
                raise ErrorServicio("PRODUCTO_NO_DISPONIBLE", linea.productoId)
            if producto.restauranteId != restauranteId:
                raise ErrorServicio("RESTAURANTE_INCONSISTENTE", linea.productoId)
            if linea.cantidad <= 0:
                raise ErrorServicio("CANTIDAD_INVALIDA", linea.productoId)
            total += producto.precioCentavos * linea.cantidad

        pedido_id = f"PED-{uuid4().hex[:10]}"
        pago = self.pagos.autorizarPago(pedido_id, total, tokenTarjeta)
        pedido = Pedido(
            pedido_id,
            clienteId,
            restauranteId,
            list(lineas),
            total,
            pago["pagoId"],
            ahora,
            ahora + timedelta(minutes=5),
        )
        self.pedidos[pedido_id] = pedido
        self.eventos.publicar(
            "pedidoCreado",
            {
                "pedidoId": pedido_id,
                "restauranteId": restauranteId,
                "limiteAceptacion": pedido.limiteAceptacion.isoformat(),
            },
        )
        return self._resumen(pedido)

    def responderPedido(
        self, pedidoId: str, aceptar: bool, ahora: datetime | None = None
    ) -> dict:
        ahora = ahora or datetime.now(timezone.utc)
        pedido = self._obtener(pedidoId)
        if pedido.estado != EstadoPedido.PAGO_AUTORIZADO:
            raise ErrorServicio("ESTADO_INVALIDO", "El pedido ya fue respondido.")
        if ahora > pedido.limiteAceptacion:
            return self._cancelarYReembolsar(pedido, "TIEMPO_AGOTADO")
        if not aceptar:
            return self._cancelarYReembolsar(pedido, "RECHAZADO_RESTAURANTE")
        pedido.estado = EstadoPedido.ACEPTADO
        self.eventos.publicar("pedidoAceptado", {"pedidoId": pedido.pedidoId})
        return self._resumen(pedido)

    def expirarPedidos(self, ahora: datetime | None = None) -> List[dict]:
        ahora = ahora or datetime.now(timezone.utc)
        cancelados = []
        for pedido in self.pedidos.values():
            if pedido.estado == EstadoPedido.PAGO_AUTORIZADO and ahora > pedido.limiteAceptacion:
                cancelados.append(self._cancelarYReembolsar(pedido, "TIEMPO_AGOTADO"))
        return cancelados

    def calificarServicio(self, pedidoId: str, calificacion: int) -> dict:
        pedido = self._obtener(pedidoId)
        if pedido.estado != EstadoPedido.ENTREGADO:
            raise ErrorServicio("PEDIDO_NO_ENTREGADO", "Solo se califican pedidos entregados.")
        if calificacion not in range(1, 6):
            raise ErrorServicio("CALIFICACION_INVALIDA", "La calificación debe ser 1 a 5.")
        pedido.calificacion = calificacion
        self.eventos.publicar(
            "servicioCalificado", {"pedidoId": pedidoId, "calificacion": calificacion}
        )
        return {"pedidoId": pedidoId, "calificacion": calificacion}

    def _cancelarYReembolsar(self, pedido: Pedido, motivo: str) -> dict:
        self.pagos.reembolsarPago(pedido.pagoId, motivo)
        pedido.estado = EstadoPedido.CANCELADO
        self.eventos.publicar(
            "pedidoCancelado", {"pedidoId": pedido.pedidoId, "motivo": motivo}
        )
        return self._resumen(pedido)

    def _obtener(self, pedidoId: str) -> Pedido:
        pedido = self.pedidos.get(pedidoId)
        if not pedido:
            raise ErrorServicio("PEDIDO_NO_ENCONTRADO", "El pedido no existe.")
        return pedido

    @staticmethod
    def _resumen(pedido: Pedido) -> dict:
        return {
            "pedidoId": pedido.pedidoId,
            "estado": pedido.estado.value,
            "totalCentavos": pedido.totalCentavos,
            "pagoId": pedido.pagoId,
            "limiteAceptacion": pedido.limiteAceptacion.isoformat(),
        }


class ServicioReparto:
    def __init__(
        self,
        pedidos: ServicioPedidos,
        repartidores: Dict[str, Repartidor],
        eventos: BusEventos,
    ) -> None:
        self.pedidos = pedidos
        self.repartidores = repartidores
        self.eventos = eventos

    def asignarRepartidor(self, pedidoId: str, latitud: float, longitud: float) -> dict:
        pedido = self.pedidos._obtener(pedidoId)
        if pedido.estado != EstadoPedido.ACEPTADO:
            raise ErrorServicio("PEDIDO_NO_ASIGNABLE", "El pedido debe estar aceptado.")
        disponibles = [r for r in self.repartidores.values() if r.disponible]
        if not disponibles:
            raise ErrorServicio("SIN_REPARTIDOR", "No hay repartidores disponibles.")
        elegido = min(disponibles, key=lambda r: hypot(r.latitud - latitud, r.longitud - longitud))
        elegido.disponible = False
        pedido.repartidorId = elegido.repartidorId
        pedido.estado = EstadoPedido.EN_REPARTO
        self.eventos.publicar(
            "repartidorAsignado",
            {"pedidoId": pedidoId, "repartidorId": elegido.repartidorId},
        )
        return {"pedidoId": pedidoId, "repartidorId": elegido.repartidorId}

    def actualizarUbicacion(
        self, pedidoId: str, repartidorId: str, latitud: float, longitud: float
    ) -> None:
        pedido = self.pedidos._obtener(pedidoId)
        if pedido.estado != EstadoPedido.EN_REPARTO or pedido.repartidorId != repartidorId:
            raise ErrorServicio("SEGUIMIENTO_NO_AUTORIZADO", "Asignación no válida.")
        repartidor = self.repartidores[repartidorId]
        repartidor.latitud, repartidor.longitud = latitud, longitud
        self.eventos.publicar(
            "ubicacionActualizada",
            {"pedidoId": pedidoId, "repartidorId": repartidorId, "latitud": latitud, "longitud": longitud},
        )

    def completarEntrega(self, pedidoId: str) -> dict:
        pedido = self.pedidos._obtener(pedidoId)
        if pedido.estado != EstadoPedido.EN_REPARTO:
            raise ErrorServicio("ENTREGA_INVALIDA", "El pedido no está en reparto.")
        pedido.estado = EstadoPedido.ENTREGADO
        self.repartidores[pedido.repartidorId].disponible = True
        self.eventos.publicar("pedidoEntregado", {"pedidoId": pedidoId})
        return {"pedidoId": pedidoId, "estado": pedido.estado.value}


def crear_demo():
    productos = {
        "PIZZA": Producto("PIZZA", "REST-1", "Pizza mediana", 15900),
        "AGUA": Producto("AGUA", "REST-1", "Agua", 2500),
    }
    eventos = BusEventos()
    notificaciones: List[dict] = []
    for tipo in ["pedidoCreado", "pedidoAceptado", "pedidoCancelado", "repartidorAsignado", "ubicacionActualizada", "pedidoEntregado"]:
        eventos.suscribir(tipo, notificaciones.append)
    pedidos = ServicioPedidos(productos, FachadaPagos(), eventos)
    reparto = ServicioReparto(
        pedidos,
        {"REP-1": Repartidor("REP-1", 19.4326, -99.1332)},
        eventos,
    )
    return pedidos, reparto, eventos, notificaciones


if __name__ == "__main__":
    pedidos, reparto, _, avisos = crear_demo()
    pedido = pedidos.crearPedido("CLI-1", "REST-1", [LineaPedido("PIZZA", 1)], "tok_demo")
    pedidos.responderPedido(pedido["pedidoId"], True)
    reparto.asignarRepartidor(pedido["pedidoId"], 19.43, -99.13)
    reparto.actualizarUbicacion(pedido["pedidoId"], "REP-1", 19.431, -99.132)
    print(reparto.completarEntrega(pedido["pedidoId"]))
    print(f"Eventos emitidos: {len(avisos)}")

