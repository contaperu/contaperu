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
from ...modelo import clave_de, monto

# Los cuatro que identifican un comprobante, en el orden de `modelo.clave_de`.
CLAVES_DE_UN_COMPROBANTE = ("tipo_cp", "serie", "numero", "contraparte_doc")

# El tope de lo ya anotado en otros periodos: años de un RUC con mucho movimiento caben holgados.
# Vive aquí, al lado de la comprobación que lo usa, y no en `documento`, para que un monkeypatch
# tenga un solo sitio donde morder.
MAXIMO_CLAVES_PREVIAS = 50000

# Y el de las partidas abiertas que vienen de otros meses. Más bajo que el de las claves previas a propósito: una
# clave previa es una comparación y una partida abierta es un saldo, y nadie lleva cien mil facturas abiertas.
MAXIMO_PARTIDAS_PREVIAS = 20000

# Lo que lleva una partida previa, además de los cuatro de su identidad. `aplicado` es lo que ya se le había
# aplicado ANTES de este documento, y es el único que no se puede derivar de nada de aquí.
CAMPOS_DE_UNA_PARTIDA = ("total", "aplicado", "moneda", "vence")

# --- lo que llega por parámetro ----------------------------------------------------


def partidas_previas_de(partidas: Any) -> dict:
    """Las partidas abiertas de otros meses, que **las pone quien llama**: el molde de `claves_previas`.

    Una factura de enero pagada en marzo vive en dos documentos —el de enero la tiene, el de marzo tiene su pago—,
    y el libro del motor es mensual. Esto es lo que cierra ese hueco **sin que el motor guarde nada**: cada partida
    es la identidad del comprobante más lo que ya se sabía de él.

        [{"tipo_cp": "01", "serie": "F001", "numero": "123", "contraparte_doc": "20602222226",
          "total": "1280.00", "aplicado": "400.00", "moneda": "PEN", "vence": "2026-02-10"}]

    Devuelve un mapa por la clave normalizada del comprobante —la misma de `modelo.clave_de`, así que «00000123»
    es «123»— para que buscarla no dependa de cómo la escribió quien llama."""
    if partidas is None:
        return {}
    if isinstance(partidas, (str, bytes, dict)) or not isinstance(partidas, (list, tuple)):
        raise DocumentoInvalido("`partidas_previas` es una lista de objetos con la identidad del comprobante, su "
                                f"total y lo aplicado: {', '.join(CAMPOS_DE_UNA_PARTIDA)}.")
    if len(partidas) > MAXIMO_PARTIDAS_PREVIAS:
        raise DocumentoInvalido(f"{len(partidas)} partidas previas en una sola llamada; el tope es "
                                f"{MAXIMO_PARTIDAS_PREVIAS}. Pasa solo las que siguen abiertas.")
    leidas: dict = {}
    for partida in partidas:
        if not isinstance(partida, dict):
            raise DocumentoInvalido(f"Una partida previa no se pudo leer ({partida!r}): es un objeto.")
        sobran = sorted(set(partida) - set(CLAVES_DE_UN_COMPROBANTE) - set(CAMPOS_DE_UNA_PARTIDA))
        if sobran:
            raise DocumentoInvalido(f"Claves que no son de una partida previa: {', '.join(sobran)}. Lleva "
                                    f"{', '.join(CLAVES_DE_UN_COMPROBANTE + CAMPOS_DE_UNA_PARTIDA)}.")
        clave = clave_de(*(str(partida.get(c) or "") for c in CLAVES_DE_UN_COMPROBANTE))
        if clave in leidas:
            raise DocumentoInvalido(f"Dos partidas previas del mismo comprobante ({'-'.join(clave[1:3])}): "
                                    "una partida abierta es una por documento, y dos esconderían un saldo.")
        leidas[clave] = {"clave": clave, "total": monto(partida.get("total")),
                         "aplicado": monto(partida.get("aplicado")),
                         "moneda": str(partida.get("moneda") or "PEN").upper(),
                         "fecha_vencimiento": partida.get("vence") or ""}
    return leidas

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


