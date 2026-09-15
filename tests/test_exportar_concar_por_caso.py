"""El Excel de CONCAR congelado también por el camino de producción, caso por caso.

`test_snapshot_concar` congela las filas de `drivers.concar.filas_de_comprobante`, la función que usa la vista previa del
portal. Lo que se importa en CONCAR sale de otro camino: `operaciones.exportar`, con su preparación, lo que exige el
destino, la numeración y la escritura del .xlsx. Este test lleva cada caso de ese snapshot, como un documento de un solo
comprobante, por `exportar`, y compara las celdas del Excel con el mismo `concar_filas.json`.

Existe para que la 1.0 pueda llevar CONCAR a la forma `desde_lineas` sin cambiar una celda de lo que de verdad se
importa (etapa 1 de la rama `motor-v1`, 14-sep-2026).

Normaliza lo que el .xlsx no conserva: una celda vacía se lee como `None`, una fecha como `datetime`, y un número pierde
su tipo de Python al guardarse (openpyxl lee `100.0` como `100`). El tipo exacto de cada celda lo sigue vigilando el
snapshot.
"""
from __future__ import annotations

import base64
import io
import json
from datetime import date, datetime

import pytest

from contaperu import asiento as asi
from contaperu import api
from test_snapshot_concar import CASOS, FILAS, armar

openpyxl = pytest.importorskip("openpyxl")

LETRAS = tuple(openpyxl.utils.get_column_letter(i) for i in range(1, 42))
PRIMERA_FILA_DE_DATOS = 4        # las tres primeras son la cabecera de la plantilla
# El snapshot numera cada caso como 080001: correlativo 1 en todo sub-diario que un caso pueda usar.
CORRELATIVOS = {"05": 1, "10": 1, "11": 1, "12": 1, "13": 1, "15": 1}
LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608"}

# Los casos que la vista previa arma y `exportar` se niega a escribir, con su motivo. Son exigencias del destino que
# `filas_de_comprobante` no hace cumplir: la exportación a CONCAR exige el centro de costo desde la 0.8.0.
RECHAZADOS = {
    "reparto_boleta_con_igv_al_gasto": (asi.SinCentro, "la parte de 18 va a 659999 sin centro, y la 65 lo lleva"),
    "venta_reparto": (asi.SinCentro, "las partes van a 701101 y 704101 sin centro, y la 70 lo lleva"),
}
EXPORTABLES = [caso for caso in CASOS if caso[0] not in RECHAZADOS]


def exportar_caso(caso) -> dict:
    """El caso como documento de un comprobante, exportado a CONCAR con la configuración y la imputación del caso."""
    _, _, es_venta, extra = caso
    c, config, _ = armar(caso)
    configuracion = {clave: valor for clave, valor in (extra or {}).items() if clave != "imputaciones"}
    documento = {"open_accounting": "0.3", "libro": dict(LIBRO, tipo="venta" if es_venta else "compra"),
                 "comprobantes": [c.a_dict()]}
    return api.exportar(documento, driver="concar", configuracion=configuracion, correlativos=CORRELATIVOS, incluir_observados=True, fecha=None, imputacion=config.get("imputaciones"))


def _normal(valor):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    return valor


def filas_del_excel(respuesta: dict) -> list[dict]:
    hoja = openpyxl.load_workbook(io.BytesIO(base64.b64decode(respuesta["contenido_base64"])))["CONCAR"]
    return [{letra: _normal(hoja[f"{letra}{n}"].value) for letra in LETRAS}
            for n in range(PRIMERA_FILA_DE_DATOS, hoja.max_row + 1)]


def filas_congeladas(nombre: str) -> list[dict]:
    """Las filas del snapshot: cada celda es `[tipo, valor]`, y una columna que no está es una celda vacía."""
    return [{letra: _normal(fila[letra][1]) if letra in fila else "" for letra in LETRAS}
            for fila in json.loads(FILAS.read_text(encoding="utf-8"))[nombre]]


def test_los_rechazados_son_casos_del_snapshot():
    assert set(RECHAZADOS) <= {caso[0] for caso in CASOS}


@pytest.mark.parametrize("caso", EXPORTABLES, ids=[caso[0] for caso in EXPORTABLES])
def test_lo_que_se_importa_en_concar_es_el_snapshot(caso):
    obtenidas = filas_del_excel(exportar_caso(caso))
    esperadas = filas_congeladas(caso[0])
    assert len(obtenidas) == len(esperadas), f"{caso[0]}: {len(obtenidas)} filas, se esperaban {len(esperadas)}"
    for i, (fila, esperada) in enumerate(zip(obtenidas, esperadas)):
        distintas = {letra: (fila[letra], esperada[letra]) for letra in LETRAS if fila[letra] != esperada[letra]}
        assert not distintas, f"{caso[0]}, fila {i}: celdas distintas (obtenido, esperado) {distintas}"


@pytest.mark.parametrize("nombre", sorted(RECHAZADOS))
def test_lo_que_exportar_se_niega_a_escribir(nombre):
    caso = next(caso for caso in CASOS if caso[0] == nombre)
    excepcion, _motivo = RECHAZADOS[nombre]
    with pytest.raises(excepcion):
        exportar_caso(caso)
