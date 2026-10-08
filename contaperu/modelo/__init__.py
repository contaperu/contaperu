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
"""
from __future__ import annotations

from .coerciones import (CENTIMO, CERO, a_decimal, fecha, monto, numero_sin_ceros, serie_y_numero,
                         solo_digitos, texto_tasa, tipo_cambio)
from .comprobante import (CAMPOS_DEL_DOCUMENTO, CAMPOS_DEL_SISTEMA, CAMPOS_DE_LA_REVISION, CONDICIONES_PAGO,
                          NOTAS, NOTAS_CREDITO, NOTAS_DEBITO, ORIGENES, RETIRADOS_EN_0_3, Comprobante,
                          Observacion, clave_de, identidad_de)
from .libro import TIPOS_LIBRO, Libro

# Los mismos nombres que exponía el módulo, escritos a mano: lo que un consumidor importa no depende de en
# qué fichero acabó cada cosa.
__all__ = [
    "CAMPOS_DEL_DOCUMENTO", "CAMPOS_DEL_SISTEMA", "CAMPOS_DE_LA_REVISION", "CENTIMO", "CERO", "CONDICIONES_PAGO",
    "Comprobante", "Libro", "NOTAS", "NOTAS_CREDITO", "NOTAS_DEBITO", "ORIGENES", "Observacion", "RETIRADOS_EN_0_3",
    "ROUND_HALF_UP", "TIPOS_LIBRO", "a_decimal", "clave_de", "fecha", "identidad_de", "monto", "numero_sin_ceros",
    "serie_y_numero", "solo_digitos", "texto_tasa", "tipo_cambio", "vocabulario",
]
