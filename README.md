# RapiEntrega · Plataforma de pedidos y reparto

Prototipo académico de servicios para una plataforma que conecta clientes,
restaurantes y repartidores. Implementa el ciclo del pedido, pago, aceptación del
restaurante, cancelación con reembolso, asignación del repartidor, seguimiento,
entrega y calificación.

## Integrantes

- Erick Gabriel Hernández Rebolledo
- Jack Brandon Espinoza Nuñez

## Funcionalidad

- Creación y validación de pedidos de un solo restaurante.
- Autorización de pago mediante una fachada de proveedor externo.
- Límite de cinco minutos para aceptar el pedido.
- Cancelación y reembolso automático por rechazo o tiempo agotado.
- Selección del repartidor disponible más cercano.
- Publicación de ubicaciones y estados mediante eventos.
- Finalización y calificación del servicio.
- Envoltorio para adaptar el sistema de facturación heredado de 2012.

## Patrones demostrados

- **Process Abstraction:** `ServicioPedidos` coordina el proceso completo.
- **Service Façade:** `FachadaPagos` aísla la API de la pasarela.
- **Legacy Wrapper:** `EnvoltorioFacturacionHeredada` adapta campos antiguos.
- **Canonical Schema:** los eventos comparten identificador, tipo, fecha y datos.
- **Publish-Subscribe:** `BusEventos` desacopla pedido, reparto y notificaciones.

## Requisitos

- Python 3.10 o superior.
- Git, únicamente para clonar el repositorio.
- No requiere base de datos, broker ni pasarela real.

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/ErickGHR/rapientrega-servicios.git
cd rapientrega-servicios
```

### 2. Crear un entorno virtual

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux o macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar el proyecto

```bash
python -m pip install --upgrade pip setuptools
python -m pip install -e .
```

El proyecto usa solamente la biblioteca estándar de Python.

## Ejecución

```bash
python rapientrega.py
```

La demostración crea un pedido, lo acepta, asigna un repartidor, publica una
ubicación y completa la entrega.

## Pruebas

```bash
python -m unittest -v
```

Casos cubiertos:

1. Flujo exitoso desde la creación hasta la calificación.
2. Cancelación y reembolso después de superar los cinco minutos.

## Ejemplo de uso

```python
from rapientrega import LineaPedido, crear_demo

pedidos, reparto, eventos, notificaciones = crear_demo()
pedido = pedidos.crearPedido(
    "CLI-1",
    "REST-1",
    [LineaPedido("PIZZA", 1)],
    "tok_demo",
)

pedidos.responderPedido(pedido["pedidoId"], True)
reparto.asignarRepartidor(pedido["pedidoId"], 19.43, -99.13)
```

## Estructura

```text
rapientrega-servicios/
├── rapientrega.py          # Dominio, servicios, patrones y demostración
├── test_rapientrega.py     # Pruebas automatizadas
├── pyproject.toml          # Metadatos e instalación editable
├── requirements.txt       # Dependencias de ejecución
└── README.md               # Instalación y uso
```

## Modelo de eventos

Cada evento contiene:

```python
{
    "eventoId": "uuid",
    "tipo": "pedidoAceptado",
    "ocurrioEn": "2026-10-23T18:00:00+00:00",
    "datos": {"pedidoId": "PED-..."},
}
```

El prototipo publica `pedidoCreado`, `pedidoAceptado`, `pedidoCancelado`,
`repartidorAsignado`, `ubicacionActualizada`, `pedidoEntregado` y
`servicioCalificado`.

## Alcance del prototipo

Las integraciones están simuladas en memoria para que el proyecto sea reproducible.
En producción se reemplazarían por bases de datos por dominio, un broker de mensajes,
un proveedor de pagos, autenticación OAuth 2.0, idempotencia persistente,
observabilidad y despliegue en contenedores.

