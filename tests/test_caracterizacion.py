"""Lo que responde hoy la fachada, congelado por documento y por destino.

La 1.0 reescribe cómo se preparan y se exportan los meses: un solo pipeline para diagnosticar, generar el asiento y
exportar. Este test guarda, con el código de la v0.10.0, la respuesta de `operaciones.revisar`, `diagnosticar`,
`generar_asiento` y `exportar` para tres documentos —los dos golden y `casos_202608.json`, que pasa por dólares, notas,
detracción, honorarios, boleta, reparto y extemporáneo— contra cada driver de serie, también cuando la operación se
niega. Guarda además lo que imprime `contaperu diagnosticar`.

Desde la etapa 3 de la 1.0 se caracteriza por las dos rutas: la API nueva (`contaperu.api`, con el documento primero y
lo demás por su nombre) y la de la 0.10 (`contaperu.operaciones`, con sus firmas posicionales), que tienen que responder
lo mismo. Cada diferencia que la 1.0 introduzca tiene que aparecer aquí y estar anunciada en el CHANGELOG, en el commit
que la trae. Regenerar es una decisión, no un trámite: se mira el diff del JSON respuesta por respuesta.

Del Excel se guardan las celdas leídas con su tipo, no los bytes (openpyxl pone la fecha del reloj en el archivo); del
SIRE y del CSV, el texto.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_caracterizacion as t; t.regenerar()"
"""
from __future__ import annotations

import base64
import copy
import io
import json
import tempfile
import warnings
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path

import pytest

from contaperu import api
from contaperu._obsoleto import RutaObsoleta
from contaperu.puertas import cli
from util import GOLDEN

CARACTERIZACION = Path(__file__).parent / "fixtures" / "caracterizacion"
DRIVERS = ("concar", "contasis", "csv", "sire")
SIN_CENTROS = {"cuentas": {"gasto": "659999"}, "usa_centros_costo": False}

# La imputación de cada documento de `casos_202608.json`: la cuenta y el centro de siempre, la de honorarios para los
# recibos y un reparto de la base entre dos cuentas y dos centros.
IMPUTACION_CASOS: dict[str, dict] = {
    **{f"c{n:02d}": {"cuenta_contable": "631101", "centro_costo": "OBRA01"} for n in range(1, 13)},
    "c07": {"cuenta_contable": "632101", "centro_costo": "OBRA01"},
    "c08": {"cuenta_contable": "632101", "centro_costo": "OBRA01"},
    "c11": {"reparto": [{"importe": "600.00", "cuenta_contable": "636301", "centro_costo": "SISTEMAS"},
                        {"importe": "400.00", "cuenta_contable": "632201", "centro_costo": "DESARROLLO"}]},
}

# nombre → (archivo del golden, configuración, imputación)
DOCUMENTOS: dict[str, tuple[str, dict, dict | None]] = {
    "compras_202601": ("compras_202601.json", SIN_CENTROS, None),
    "ventas_202512": ("ventas_202512.json", SIN_CENTROS, None),
    "casos_202608": ("casos_202608.json", {}, IMPUTACION_CASOS),
}


def cargar_documento(archivo: str) -> dict:
    return json.loads((GOLDEN / archivo).read_text(encoding="utf-8"))


def _celda(valor):
    if isinstance(valor, datetime):
        return ["datetime", valor.isoformat()]
    if isinstance(valor, date):
        return ["date", valor.isoformat()]
    return [type(valor).__name__, valor]


def _hojas(contenido: bytes) -> dict:
    import openpyxl
    libro = openpyxl.load_workbook(io.BytesIO(contenido))
    return {hoja.title: [[_celda(celda.value) for celda in fila] for fila in hoja.iter_rows()]
            for hoja in libro.worksheets}


def _respuesta(respuesta: dict) -> dict:
    """La respuesta sin los bytes: el Excel se lee como celdas, y el ZIP del SIRE ya viene como texto."""
    respuesta = copy.deepcopy(respuesta)
    contenido = respuesta.pop("contenido_base64", None)
    respuesta.pop("zip_base64", None)
    if contenido is not None and str(respuesta.get("content_type", "")).endswith("spreadsheetml.sheet"):
        respuesta["_hojas"] = _hojas(base64.b64decode(contenido))
    return respuesta


def _llamar(funcion) -> dict:
    try:
        return funcion()
    except Exception as error:                     # lo que se niega también es comportamiento
        return {"_error": type(error).__name__, "_mensaje": str(error)}


def _cli_diagnosticar(documento: dict, configuracion: dict, imputacion: dict | None, driver: str) -> dict:
    with tempfile.TemporaryDirectory() as carpeta:
        rutas = {}
        for nombre, datos in (("documento", documento), ("config", configuracion), ("imputacion", imputacion)):
            if datos is not None:
                rutas[nombre] = Path(carpeta) / f"{nombre}.json"
                rutas[nombre].write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        argumentos = ["diagnosticar", str(rutas["documento"]), "--driver", driver, "--config", str(rutas["config"])]
        if "imputacion" in rutas:
            argumentos += ["--imputacion", str(rutas["imputacion"])]
        salida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with redirect_stdout(salida):
            codigo = cli.main(argumentos)
        salida.flush()
        texto = salida.buffer.getvalue().decode("utf-8").replace(carpeta, "<carpeta>")
    return {"codigo": codigo, "salida": texto.replace("\r\n", "\n")}


RUTAS = ("api", "0.10")


def _operaciones(ruta: str, configuracion: dict, imputacion: dict | None) -> dict:
    """Las cuatro operaciones que se caracterizan, por la API nueva o por la ruta de la 0.10 con sus firmas."""
    if ruta == "0.10":
        viejo = __import__("contaperu.operaciones", fromlist=["exportar"])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RutaObsoleta)
            revisar, diagnosticar = viejo.revisar, viejo.diagnosticar
            generar_asiento, exportar = viejo.generar_asiento, viejo.exportar
        return {
            "revisar": lambda doc: revisar(doc, configuracion),
            "diagnosticar": lambda doc, driver: diagnosticar(doc, configuracion, None, driver, imputacion),
            "generar_asiento": lambda doc, driver: generar_asiento(doc, configuracion, None, False, imputacion, driver),
            "exportar": lambda doc, driver, observados: exportar(doc, driver, configuracion, None, observados, None,
                                                                 imputacion),
        }
    return {
        "revisar": lambda doc: api.revisar(doc, configuracion=configuracion),
        "diagnosticar": lambda doc, driver: api.diagnosticar(doc, driver=driver, configuracion=configuracion,
                                                             imputacion=imputacion),
        "generar_asiento": lambda doc, driver: api.generar_asiento(doc, driver=driver, configuracion=configuracion,
                                                                   imputacion=imputacion),
        "exportar": lambda doc, driver, observados: api.exportar(doc, driver=driver, configuracion=configuracion,
                                                                 imputacion=imputacion, incluir_observados=observados),
    }


def caracterizar(nombre: str, ruta: str = "api") -> dict:
    archivo, configuracion, imputacion = DOCUMENTOS[nombre]
    op = _operaciones(ruta, configuracion, imputacion)

    def doc() -> dict:
        return cargar_documento(archivo)

    salida = {"revisar": _llamar(lambda: op["revisar"](doc()))}
    for driver in DRIVERS:
        salida[f"diagnosticar/{driver}"] = _llamar(lambda: op["diagnosticar"](doc(), driver))
        salida[f"generar_asiento/{driver}"] = _llamar(lambda: op["generar_asiento"](doc(), driver))
        salida[f"exportar/{driver}"] = _llamar(lambda: _respuesta(op["exportar"](doc(), driver, False)))
        salida[f"exportar_con_observados/{driver}"] = _llamar(lambda: _respuesta(op["exportar"](doc(), driver, True)))
    salida["cli_diagnosticar/concar"] = _llamar(lambda: _cli_diagnosticar(doc(), configuracion, imputacion, "concar"))
    return json.loads(json.dumps(salida, ensure_ascii=False, default=str))


def _ruta(nombre: str) -> Path:
    return CARACTERIZACION / f"{nombre}.json"


def regenerar() -> None:
    """Reescribe la caracterización con el código de hoy. Ver el docstring del módulo antes de usarlo."""
    CARACTERIZACION.mkdir(parents=True, exist_ok=True)
    for nombre in DOCUMENTOS:
        _ruta(nombre).write_bytes((json.dumps(caracterizar(nombre), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def _cargar(nombre: str) -> dict:
    return json.loads(_ruta(nombre).read_text(encoding="utf-8"))


@pytest.mark.parametrize("ruta", RUTAS)
@pytest.mark.parametrize("nombre", sorted(DOCUMENTOS))
def test_la_fachada_responde_lo_mismo_que_quedo_congelado(nombre, ruta):
    pytest.importorskip("openpyxl")
    esperado = _cargar(nombre)
    obtenido = caracterizar(nombre, ruta)
    assert set(obtenido) == set(esperado), f"{nombre}: cambió qué se caracteriza"
    distintas = [clave for clave in esperado if obtenido[clave] != esperado[clave]]
    assert not distintas, f"{nombre}: cambió la respuesta de {distintas}"


def test_la_caracterizacion_pasa_por_lo_que_importa():
    """No sirve de red si todo se negara: cada driver exporta al menos uno de los tres documentos."""
    for driver in DRIVERS:
        exportados = [nombre for nombre in DOCUMENTOS if "_error" not in _cargar(nombre)[f"exportar/{driver}"]]
        assert exportados, f"{driver} no exporta ningún documento de la caracterización"
