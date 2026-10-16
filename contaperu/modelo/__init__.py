"""Modelo canónico del motor: un `Comprobante` = una fila del registro de compras o ventas.

Aquí está TODO lo que necesitan las salidas —el SIRE (Anexos 3 y 11) y los sistemas contables—; los drivers
solo ordenan y formatean. Reglas:

- Importes en `Decimal` con 2 decimales y SIEMPRE positivos: el signo de las
  notas de crédito lo pone el driver, no el dato (así la celda editable del
  portal no obliga a escribir negativos).
- Fechas como `date`; los drivers las escriben en el formato que toque.
- Los campos de revisión (`estado`, `observaciones`, `excluida`) los rellenan
  `validar.py` y el usuario; el motor nunca los inventa.
Era un módulo de 466 líneas que mezclaba tres cosas —las coerciones de tipo, las dataclasses y la identidad de
un comprobante—, y desde la 6.2.0 es un paquete con un fichero por tema. **Lo que se importa no cambió**: este
`__init__` reexporta los mismos nombres, y el test de la superficie pública lo demuestra al seguir pasando sin
regenerarse.

**Desde la 12.11 el comprobante vive en `contaperu/comprobantes/`** —su paquete, espejo de `tesoreria/`— y de
aquí se sigue pidiendo igual. Los trece nombres que trae de allá se resuelven **perezosamente**, por el
`__getattr__` de abajo, y eso tampoco es estilo: `comprobantes/comprobante.py` necesita `modelo.coerciones` y
`modelo.libro`, y pedirle a Python un módulo hoja despierta a su paquete, así que un `from ..comprobantes import
…` en la cabecera de este fichero cerraría el círculo y reventaría según quién importase primero. Perezoso, este
`__init__` no importa nada hacia arriba y el orden deja de importar. `__all__` no se movió: son los mismos
nombres de siempre.
"""
from __future__ import annotations

import importlib

from .coerciones import (CENTIMO, CERO, a_decimal, fecha, monto, numero_sin_ceros, serie_y_numero,
                         solo_digitos, texto_tasa, tipo_cambio)
from .libro import (ORIGENES_DE_LIBRO, POR_OPERACION, RASGOS, TIPOS_LIBRO, Libro, LibroSinRasgos, Rasgos,
                    SentidoNoLoDiceElLibro, rasgos_de)

# Lo que ahora vive en `contaperu.comprobantes` y se sigue pidiendo aquí. El valor es el módulo de verdad, para
# que el aviso de dónde está cada cosa sea el propio diccionario y no un comentario que se despiste.
_DEL_COMPROBANTE = {
    nombre: "contaperu.comprobantes.comprobante" for nombre in (
        "CAMPOS_DEL_DOCUMENTO", "CAMPOS_DEL_SISTEMA", "CAMPOS_DE_LA_REVISION", "CONDICIONES_PAGO", "NOTAS",
        "NOTAS_CREDITO", "NOTAS_DEBITO", "ORIGENES", "RETIRADOS_EN_0_3", "Comprobante", "Observacion",
        "clave_de", "identidad_de",
    )
}

# Los mismos nombres que exponía el módulo, escritos a mano: lo que un consumidor importa no depende de en
# qué fichero acabó cada cosa.
__all__ = [
    "CAMPOS_DEL_DOCUMENTO", "CAMPOS_DEL_SISTEMA", "CAMPOS_DE_LA_REVISION", "CENTIMO", "CERO", "CONDICIONES_PAGO",
    "Comprobante", "Libro", "LibroSinRasgos", "NOTAS", "NOTAS_CREDITO", "NOTAS_DEBITO", "ORIGENES", "Observacion",
    "ORIGENES_DE_LIBRO", "POR_OPERACION", "RASGOS", "RETIRADOS_EN_0_3", "Rasgos",
    "SentidoNoLoDiceElLibro", "rasgos_de",
    "ROUND_HALF_UP", "TIPOS_LIBRO", "a_decimal", "clave_de", "fecha", "identidad_de", "monto", "numero_sin_ceros",
    "serie_y_numero", "solo_digitos", "texto_tasa", "tipo_cambio", "vocabulario",
]


def __getattr__(nombre: str):
    if nombre in _DEL_COMPROBANTE:
        return getattr(importlib.import_module(_DEL_COMPROBANTE[nombre]), nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_DEL_COMPROBANTE))
