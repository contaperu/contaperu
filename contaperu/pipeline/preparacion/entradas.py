"""Lo que llega por parámetro y hay que normalizar antes de usarlo: las claves ya anotadas en otros periodos,
un archivo en base64 y la fecha.

Los tres tienen la misma forma: alguien de fuera manda algo con la forma que le viene bien, y aquí se convierte
en lo que el motor usa — o se rechaza diciendo qué se esperaba. **La fecha la pone quien llama**: el motor no
mira el reloj.
"""
from __future__ import annotations

import base64
from datetime import date
from typing import Any

from ...errores import DocumentoInvalido
from ...modelo import clave_de

# El tope de lo ya anotado en otros periodos: años de un RUC con mucho movimiento caben holgados.
# Vive aquí, al lado de la comprobación que lo usa, y no en `documento`, para que un monkeypatch
# tenga un solo sitio donde morder.
MAXIMO_CLAVES_PREVIAS = 50000

# --- lo que llega por parámetro ----------------------------------------------------

def claves_previas_de(claves: Any) -> list[tuple[str, str, str, str]]:
    """Lo ya anotado en otros periodos del mismo RUC, como lo compara la validación: cada clave viaja en JSON como
    `[tipo_cp, serie, numero, contraparte_doc]` y se normaliza igual que la del comprobante (`modelo.clave_de`), así que
    «00000123» es «123». En ventas el cliente no cuenta (`estandar/LEEME.md`, «La identidad de un comprobante»)."""
    if claves is None:
        return []
    if isinstance(claves, (str, bytes, dict)) or not isinstance(claves, (list, tuple)):
        raise DocumentoInvalido("`claves_previas` es una lista de [tipo_cp, serie, numero, contraparte_doc].")
    if len(claves) > MAXIMO_CLAVES_PREVIAS:
        raise DocumentoInvalido(f"{len(claves)} claves previas en una sola llamada; el tope es {MAXIMO_CLAVES_PREVIAS}. "
                                "Pasa solo las del RUC y de los periodos en que se pueden repetir.")
    normalizadas = []
    for clave in claves:
        if (not isinstance(clave, (list, tuple)) or len(clave) != 4
                or not all(parte is None or isinstance(parte, (str, int)) for parte in clave)):
            raise DocumentoInvalido(f"Una clave previa no se pudo leer ({clave!r}): es [tipo_cp, serie, numero, "
                                    "contraparte_doc].")
        normalizadas.append(clave_de(*("" if parte is None else str(parte) for parte in clave)))
    return normalizadas


def bytes_de(contenido: str, es_base64: bool) -> bytes:
    if es_base64:
        try:
            return base64.b64decode(contenido, validate=True)
        except Exception as e:
            raise DocumentoInvalido(f"El contenido no es base64 válido: {e}") from None
    return contenido.encode("utf-8")


def fecha_de(fecha: str | None) -> str | None:
    """La fecha de una exportación la pone quien llama —el núcleo no mira el reloj— y solo se
    comprueba que sea una fecha (`AAAA-MM-DD`): es una anotación, no un dato contable."""
    if fecha in (None, ""):
        return None
    try:
        return date.fromisoformat(str(fecha)).isoformat()
    except ValueError:
        raise DocumentoInvalido(f"`fecha` tiene que ser AAAA-MM-DD, no {fecha!r}.") from None


