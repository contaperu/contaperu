"""La detracción del comprobante, contrastada con la tabla del contribuyente.

Existe por un error concreto y caro: las IAs que leen facturas confunden la **retención del
IGV** —el 3 % que retiene un agente de retención cuando la factura pasa de S/ 700, y que no
toca el registro de compras ni el asiento— con una **detracción**, y devuelven un código
inventado, casi siempre «000». Ese código llegaba al asiento como si fuera real.

La regla, de un contador: **si el código no está en la tabla de detracciones del contribuyente,
la detracción queda en blanco**. Nada se adivina; si toca, la elige una persona.

**La tabla vive en el motor** (John, 15-sep-2026): el código, el nombre y la tasa de cada detracción, con su fuente, en
`datos/sunat/detracciones.json`. El ERP que integra el motor puede sobreescribirla en lo general de su configuración:
`detraccion_tasas` cambia la tasa de un código o suma uno (`null`: se reconoce sin tasa, y la toma del comprobante), y
`detraccion_nombres` cambia el nombre de uno que ya está. Hasta la 1.0 la tabla entera vivía en la configuración de
cada empresa, y antes del 13-sep-2026 la daba `detraccion_codigos`, el código interno de CONCAR.

**Y el monto lo calcula el motor, una sola vez** (10-sep-2026). Hasta ese día había dos cifras: la
del asiento (total × tasa en soles enteros) y la que enseñaba el portal —calculada en el navegador con
decimales, o la que la IA leyó del PDF—, y no siempre coincidían. Ahora `monto_detraccion()` es la única: la usan
el asiento y `normalizar()`, y lo que ve la persona es lo que va a CONCAR.
"""
from __future__ import annotations

import copy
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Any, Iterable

from . import _datos
from .configuracion import NUMERO_DETRACCION_PENDIENTE
from .modelo import CENTIMO, Comprobante, a_decimal, texto_tasa

# La tabla oficial que trae el motor: código SUNAT → nombre y tasa, con la fuente de donde sale.
TABLA_DEL_MOTOR = "datos/sunat/detracciones.json"


@lru_cache(maxsize=1)
def _datos_de_la_tabla() -> dict:
    datos = _datos.leer_json(TABLA_DEL_MOTOR)
    if not datos or not str(datos.get("fuente") or "").strip():
        raise FileNotFoundError(f"No encuentro la tabla de detracciones con su fuente ({TABLA_DEL_MOTOR})")
    return datos


def tabla_del_motor() -> dict:
    """La tabla de detracciones que trae el motor, tal como viaja: `{fuente, nota, codigos: {codigo: {nombre, tasa}}}`.
    Cada llamada devuelve una copia."""
    return copy.deepcopy(_datos_de_la_tabla())


def tabla_de_detracciones(config: dict | None = None) -> dict[str, dict]:
    """La tabla con la que se trabaja: la del motor, con lo que sobreescribe el ERP en su configuración encima.

    `{codigo: {"nombre": str, "tasa": Decimal | None}}`, donde `None` es un código que se reconoce sin tasa. Una tasa de
    `detraccion_tasas` cambia la del motor o suma el código; un nombre de `detraccion_nombres` cambia el de un código que
    ya está, y no suma ninguno: para sumarlo se le da su tasa."""
    tabla = {codigo: {"nombre": str(fila.get("nombre") or ""),
                      "tasa": None if fila.get("tasa") in (None, "") else a_decimal(fila["tasa"])}
             for codigo, fila in _datos_de_la_tabla()["codigos"].items()}
    config = config or {}
    for codigo, tasa in (config.get("detraccion_tasas") or {}).items():
        fila = tabla.setdefault(str(codigo), {"nombre": "", "tasa": None})
        fila["tasa"] = None if tasa is None else a_decimal(tasa)
    for codigo, nombre in (config.get("detraccion_nombres") or {}).items():
        if str(codigo) in tabla:
            tabla[str(codigo)]["nombre"] = str(nombre)
    return tabla


def codigos_de(config: dict) -> set[str]:
    """Los códigos de detracción que se reconocen: los de la tabla del motor más los que suma el ERP, tengan tasa o no."""
    return set(tabla_de_detracciones(config))


def normalizar_una(det, codigos: set[str]) -> dict | None:
    """El bloque de detracción con el código a 3 dígitos si está en la tabla; si no, `None`."""
    if not isinstance(det, dict):
        return None
    cod = str(det.get("codigo") or "").strip()
    if cod.isdigit():
        cod = cod.zfill(3)
    if not cod or cod not in codigos:
        return None
    return dict(det, codigo=cod)


def tasa_de_tabla(codigo: Any, config: dict) -> Decimal:
    """La tasa de ese código en la tabla con la que se trabaja —la del ERP si la sobreescribe, si no la del motor—; 0 si
    no la tiene."""
    fila = tabla_de_detracciones(config).get(str(codigo or "").strip()) or {}
    return fila.get("tasa") or Decimal(0)


def tasa_detraccion(c: Comprobante, config: dict) -> Decimal:
    """La tasa con la que se calcula: la del comprobante y, si no la trae, la de la tabla."""
    d = c.detraccion if isinstance(c.detraccion, dict) else {}
    t = a_decimal(d.get("porcentaje"))
    return t if t > 0 else tasa_de_tabla(d.get("codigo"), config)


def monto_detraccion(c: Comprobante, config: dict) -> tuple[Decimal, Decimal]:
    """El monto de la detracción (Excel real validado en CONCAR, 2026): total × tasa en SOLES ENTEROS —
    la detracción se deposita en soles (4 956 × 4 % = 198.24 → 198). En dólares la base se convierte
    con el T.C. del comprobante y el monto vuelve a dólares para la línea, porque el asiento va en US.
    Devuelve (soles, en la moneda del comprobante); (0, 0) si no hay tasa o falta el T.C."""
    t = tasa_detraccion(c, config)
    es_usd = (c.moneda or "PEN").upper() == "USD"
    tc = c.tipo_cambio if es_usd and c.tipo_cambio else None
    if t <= 0 or (es_usd and not tc):
        return Decimal(0), Decimal(0)
    total = Decimal(c.total or 0).quantize(CENTIMO)
    cambio = Decimal(str(tc)) if es_usd else Decimal(1)
    base_soles = (total * cambio).quantize(CENTIMO, rounding=ROUND_HALF_UP)
    soles = (base_soles * t / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    en_moneda = (soles / cambio).quantize(CENTIMO, rounding=ROUND_HALF_UP) if es_usd else soles
    return soles, en_moneda


def normalizar(comprobantes: Iterable[Comprobante], config: dict) -> list[Comprobante]:
    """Deja en blanco la detracción cuyo código no reconoce el contribuyente, y a la que queda le
    anota lo que dice el motor: su `monto` (soles enteros, lo que va a CONCAR) y la tasa de la tabla
    para ese código (`tasa_tabla`), que `validar` compara con la del comprobante.

    **La tasa del comprobante no se toca**: es la que leyó la IA o la que eligió la persona, y la
    huella con que se sabe si un comprobante cambió después de exportarse depende de ella.

    Devuelve **solo los comprobantes que cambió**, para que quien llame sepa qué guardar. Es
    idempotente: repetirla sobre lo ya normalizado no cambia nada.
    """
    con = [c for c in comprobantes if c.detraccion]
    if not con:
        return []
    codigos = codigos_de(config)
    cambiados = []
    for c in con:
        antes = c.detraccion
        nuevo = normalizar_una(c.detraccion, codigos)
        if nuevo is not None:
            c.detraccion = nuevo
            soles, _ = monto_detraccion(c, config)
            nuevo = dict(nuevo, monto=str(soles) if soles > 0 else "")
            de_tabla = tasa_de_tabla(nuevo["codigo"], config)
            if de_tabla > 0:
                nuevo["tasa_tabla"] = texto_tasa(de_tabla)
            else:
                nuevo.pop("tasa_tabla", None)
        c.detraccion = nuevo
        if nuevo != antes:
            cambiados.append(c)
    return cambiados


# --- los dos tiempos: provisionado y pagado ---------------------------------------------------------------------

# Los dos estados que declara el estándar (`detraccion.estado`). Se nombran aquí para que nadie escriba la cadena a
# mano, y `tests/test_detracciones.py` los ancla al `enum` del esquema: dos listas que dicen lo mismo en dos sitios
# acaban diciendo cosas distintas.
PROVISIONADO = "PROVISIONADO"
PAGADO = "PAGADO"


def numero_pendiente(config: dict | None = None) -> str:
    """El COMODÍN del número de constancia: el del contribuyente si lo configuró
    (`detraccion_numero_pendiente`, 3.1) y el de partida si no.

    Vive aquí, y no en el asiento, que es donde se leía hasta la 3.1: lo necesitan los dos lados —la línea comodín
    del asiento y el estado de la detracción, que no arma ningún asiento— y una sola fuente es lo que evita que un
    contribuyente configure el suyo y el motor siga comparando contra otro."""
    return str((config or {}).get("detraccion_numero_pendiente") or NUMERO_DETRACCION_PENDIENTE)


def estado_de(c: Comprobante, config: dict | None = None) -> str:
    """En qué tiempo está la detracción de ese comprobante: `PAGADO`, `PROVISIONADO`, o vacío si no tiene ninguna.

    **PAGADO exige las dos cosas** (John, 25-sep-2026): un número de constancia que no sea el comodín **y** la
    fecha del depósito. Con el número solo —lo normal cuando alguien lo pega y se deja la fecha— sigue
    PROVISIONADO: el archivo ya sale con el número de verdad, y el mes lo sigue listando como pendiente, que es
    justo lo que hace que alguien vuelva a poner la fecha.

    **El `estado` que traiga el documento no se lee.** Es un campo informativo (John, 25-sep-2026): lo escribe
    quien quiera para que se vea, y el motor lo deduce de los dos datos que no se pueden inventar. Un productor que
    lo declare PAGADO sin constancia no consigue que el motor se lo crea.

    Se descartan los DOS comodines, el que está en vigor y el de partida: un contribuyente que configuró el suyo
    puede tener guardado el de fábrica de una exportación anterior, y ese número tampoco es un depósito.
    """
    bloque = c.detraccion if isinstance(c.detraccion, dict) else {}
    if not str(bloque.get("codigo") or "").strip():
        return ""
    numero = str(bloque.get("nro_constancia") or "").strip()
    fecha = str(bloque.get("fecha_constancia") or "").strip()
    comodines = {numero_pendiente(config), NUMERO_DETRACCION_PENDIENTE}
    return PAGADO if (numero and numero not in comodines and fecha) else PROVISIONADO


def esta_pendiente(c: Comprobante, config: dict | None = None) -> bool:
    """¿Esta detracción espera todavía su depósito documentado? Un comprobante sin detracción no espera nada."""
    return estado_de(c, config) == PROVISIONADO


# Lo que sigue pendiente es CONCILIAR con el banco: leer el archivo de constancias del Banco de la Nación y casar
# cada depósito con su comprobante, sin que nadie teclee. Hace falta un archivo real para saber su formato exacto, y
# en este proyecto ninguna regla se escribe de memoria. Lo que ya no falta es el estado: se deduce de lo que haya
# pegado una persona (`estado_de`), y el estándar tiene desde siempre el hueco donde se guarda.
