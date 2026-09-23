"""Utilidades compartidas por los tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from contaperu.configuracion import CONFIGURACION_GENERAL
from contaperu.modelo import Comprobante, Libro

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "golden"
XML = FIXTURES / "xml"

def cargar_golden(nombre_json: str) -> tuple[Libro, list[Comprobante]]:
    datos = json.loads((GOLDEN / nombre_json).read_text(encoding="utf-8"))
    libro = Libro(**datos["libro"])
    return libro, [Comprobante.de_dict(d) for d in datos["comprobantes"]]


def campos(linea: str, palote_final: bool) -> list[str]:
    """Separa una línea en campos. Con palote final (PLE), el último '|' cierra
    la línea y no abre un campo más."""
    if palote_final:
        assert linea.endswith("|"), linea
        linea = linea[:-1]
    return linea.split("|")


# ── La cuenta y el centro de los comprobantes de prueba ──────────────────────────────────────────────────────
# Desde open-accounting 0.3 no son campos del comprobante: llegan en la imputación, por `id_externo`. Las pruebas del
# asiento los siguen escribiendo al armar un comprobante —es justo lo que prueban—, así que `comprobante()` los aparta
# en IMPUTACIONES con un `id_externo` propio, y `con_imputaciones(config)` los entrega en la configuración, que es por
# donde los recibe el núcleo. Es el MISMO diccionario, no una copia: un comprobante armado después encuentra la suya.
LEGADO = ("cuenta_contable", "centro_costo")
IMPUTACIONES: dict[str, dict] = {}


def imputar(c: Comprobante, **imputacion) -> Comprobante:
    """Le da a `c` su imputación de prueba, y un `id_externo` si no lo tiene."""
    c.id_externo = c.id_externo or f"prueba-{len(IMPUTACIONES) + 1}"
    IMPUTACIONES[c.id_externo] = {k: v for k, v in imputacion.items() if str(v or "").strip()}
    return c


def comprobante(**campos) -> Comprobante:
    """Un comprobante de prueba: la cuenta y el centro que traiga `campos` pasan a su imputación."""
    imputacion = {k: campos.pop(k) for k in LEGADO if k in campos}
    c = Comprobante(**campos)
    return imputar(c, **imputacion) if any(str(v or "").strip() for v in imputacion.values()) else c


def con_imputaciones(config: dict) -> dict:
    """La configuración con las imputaciones de los comprobantes de prueba."""
    return {**config, "imputaciones": IMPUTACIONES}


def en_secciones(config: dict | None, sistema: str) -> dict | None:
    """Una configuración de prueba escrita plana, como la lee el núcleo → como se guarda desde el 13-sep-2026: lo
    general en la raíz y lo demás en la sección de `sistema`. Las pruebas del asiento prueban reglas, no la forma."""
    if config is None:
        return None
    generales = {c.clave for c in CONFIGURACION_GENERAL}
    salida = {clave: valor for clave, valor in config.items() if clave in generales}
    propias = {clave: valor for clave, valor in config.items() if clave not in generales}
    return {**salida, sistema: propias} if propias else salida


def separar_imputacion(documento: dict) -> tuple[dict, dict]:
    """Un documento de prueba que escribe cuenta y centro en sus comprobantes → el documento sin ellos y su imputación,
    por `id_externo` (se le pone uno a quien no lo tenga)."""
    documento = copy.deepcopy(documento)
    imputacion = {}
    for n, c in enumerate(documento.get("comprobantes") or [], 1):
        propia = {k: v for k in LEGADO if str(v := c.pop(k, "") or "").strip()}
        if propia:
            c.setdefault("id_externo", f"prueba-{n}")
            imputacion[c["id_externo"]] = propia
    return documento, imputacion


def imputando(documento: dict, cuenta: str, centro: str = "") -> dict:
    """El documento con su bloque `imputaciones`: la MISMA cuenta para todos sus comprobantes, por `id_externo` (se
    le pone uno a quien no lo tenga).

    Hasta la 3.0 esto se conseguía con `cuentas.gasto` en la configuración —la cuenta que el motor le ponía a quien
    no traía ninguna—, y por eso los documentos de prueba que vienen de SUNAT no imputan nada. Desde la 3.0 **la
    cuenta es del comprobante**, así que los documentos que solo quieren exportar la traen por aquí; los que prueban
    qué pasa SIN cuenta, a propósito, no llaman a esto.
    """
    documento = copy.deepcopy(documento)
    imputaciones = dict(documento.get("imputaciones") or {})
    propia = {"cuenta_contable": cuenta, **({"centro_costo": centro} if centro else {})}
    for n, c in enumerate(documento.get("comprobantes") or [], 1):
        c.setdefault("id_externo", f"fila-{n}")
        imputaciones.setdefault(c["id_externo"], propia)
    documento["imputaciones"] = imputaciones
    return documento


def por_la_fachada(operacion):
    """Una operación de la fachada (`diagnosticar`, `exportar`…) para documentos de prueba que escriben la cuenta y el
    centro en cada comprobante: se apartan como su imputación antes de llamar."""
    def llamada(documento, *args, **kwargs):
        documento, imputacion = separar_imputacion(documento)
        if imputacion or kwargs.get("imputacion"):
            kwargs["imputacion"] = {**imputacion, **(kwargs.get("imputacion") or {})}
        return operacion(documento, *args, **kwargs)
    return llamada


def construir_concar(libro: Libro, comprobantes: list[Comprobante], config: dict, correlativos: dict[str, int],
                     opciones=None) -> tuple[bytes, dict]:
    """El Excel de CONCAR y su resumen para comprobantes ya seleccionados, como hacía `drivers.concar.construir` en la
    0.10: el mismo camino del pipeline (exigir, lo que no cabe, numerar, cuadrar, proyectar), sin revisar ni
    seleccionar."""
    from contaperu.drivers import concar
    from contaperu.pipeline import armado
    return armado.desde_lineas(concar, libro, comprobantes, opciones or concar.OPCIONES, config, correlativos)
