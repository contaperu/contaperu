"""El formato de las hojas de Excel, congelado: lo que el snapshot de celdas no ve.

Los snapshots de CONCAR y de CONTASIS congelan el valor y el tipo de cada celda. Un Excel que se importa depende también
de su forma: el nombre de la hoja, las tres filas de cabecera de la plantilla de CONCAR (títulos, notas y formatos, con
su relleno, su fuente y su alto), el panel congelado, el autofiltro, los anchos de columna y el formato de número, la
fuente y la alineación de las celdas de datos.

La 1.0 pasa la escritura de los dos Excel a un escritor común (`drivers/kit/xlsx.py`): este test es lo que garantiza que
el archivo sale con la misma forma (rama `motor-v1`, etapa 1, 14-sep-2026). Las pruebas de plantilla de CONTASIS se
omiten sin `privado/`, así que en CI esto las sustituye en lo que toca a la forma.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_formato_xlsx as t; t.regenerar()"
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest

from contaperu import operaciones as op
from test_caracterizacion import IMPUTACION_CASOS, SIN_CENTROS, cargar_documento

openpyxl = pytest.importorskip("openpyxl")

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshot"
# driver → (archivo del snapshot, filas de cabecera de su plantilla, meses: (golden, configuración, imputación))
EXCEL = {
    "concar": ("concar_formato.json", 3, (("casos_202608.json", {}, IMPUTACION_CASOS),
                                         ("ventas_202512.json", SIN_CENTROS, None))),
    "contasis": ("contasis_formato.json", 0, (("compras_202601.json", SIN_CENTROS, None),
                                             ("ventas_202512.json", SIN_CENTROS, None))),
}
FILAS_DE_DATOS = 3          # con tres filas de datos se ven todas las clases de celda de cada columna


def _color(color) -> str | None:
    return str(color.rgb) if color is not None and getattr(color, "type", None) == "rgb" else None


def _estilo(celda, con_valor: bool) -> dict:
    fuente, relleno, alineacion = celda.font, celda.fill, celda.alignment
    estilo = {
        "formato": celda.number_format,
        "fuente": [fuente.name, fuente.sz, bool(fuente.b), _color(fuente.color)],
        "relleno": [relleno.patternType, _color(relleno.fgColor)],
        "alineacion": [alineacion.horizontal, alineacion.vertical, bool(alineacion.wrap_text)],
    }
    if con_valor:
        estilo["valor"] = celda.value
    return estilo


def forma(contenido: bytes, filas_de_cabecera: int) -> dict:
    libro = openpyxl.load_workbook(io.BytesIO(contenido))
    salida = {}
    for hoja in libro.worksheets:
        ultima = min(hoja.max_row, filas_de_cabecera + FILAS_DE_DATOS)
        salida[hoja.title] = {
            "columnas": hoja.max_column,
            "panel": hoja.freeze_panes,
            "autofiltro": hoja.auto_filter.ref,
            "anchos": {letra: dim.width for letra, dim in sorted(hoja.column_dimensions.items()) if dim.customWidth},
            "altos": {str(n): dim.height for n, dim in sorted(hoja.row_dimensions.items())
                      if dim.height is not None and n <= ultima},
            "celdas": [[_estilo(celda, n <= filas_de_cabecera) for celda in fila]
                       for n, fila in enumerate(hoja.iter_rows(min_row=1, max_row=ultima), start=1)],
        }
    return salida


def formas_de(driver: str) -> dict:
    _, cabecera, meses = EXCEL[driver]
    salida = {}
    for archivo, configuracion, imputacion in meses:
        respuesta = op.exportar(cargar_documento(archivo), driver, configuracion, None, True, None, imputacion)
        salida[archivo] = forma(base64.b64decode(respuesta["contenido_base64"]), cabecera)
    return json.loads(json.dumps(salida, ensure_ascii=False, default=str))


def regenerar() -> None:
    """Reescribe los dos snapshots de forma con el código de hoy. Ver el docstring del módulo antes de usarlo."""
    for driver, (archivo, _, _) in EXCEL.items():
        (SNAPSHOT / archivo).write_bytes((json.dumps(formas_de(driver), ensure_ascii=False, indent=1) + "\n")
                                         .encode("utf-8"))


@pytest.mark.parametrize("driver", sorted(EXCEL))
def test_la_forma_del_excel_no_cambia(driver):
    esperado = json.loads((SNAPSHOT / EXCEL[driver][0]).read_text(encoding="utf-8"))
    obtenido = formas_de(driver)
    for mes in esperado:
        for hoja, forma_esperada in esperado[mes].items():
            forma_obtenida = obtenido[mes].get(hoja)
            assert forma_obtenida is not None, f"{driver}, {mes}: falta la hoja {hoja!r}"
            distintas = [clave for clave in forma_esperada if forma_obtenida.get(clave) != forma_esperada[clave]]
            assert not distintas, f"{driver}, {mes}, hoja {hoja!r}: cambió {distintas}"
        assert set(obtenido[mes]) == set(esperado[mes]), f"{driver}, {mes}: cambiaron las hojas"


def test_la_cabecera_de_concar_es_la_de_la_plantilla():
    """Una comprobación legible de lo que el snapshot guarda: tres filas de cabecera y los datos desde la cuarta."""
    hoja = json.loads((SNAPSHOT / "concar_formato.json").read_text(encoding="utf-8"))["casos_202608.json"]["CONCAR"]
    assert hoja["columnas"] == 41 and hoja["panel"] == "A4" and hoja["autofiltro"] == "A3:AO3"
    assert hoja["celdas"][0][0]["valor"] == "WE" and "valor" not in hoja["celdas"][3][0]
