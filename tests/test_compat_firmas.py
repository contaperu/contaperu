"""Lo que usa `contab-core` en producción sigue funcionando igual durante la 1.x.

`contab-core` (Contabilidad Inteligente, otro repositorio) instala el motor como paquete. La lista exacta de lo que
importa vive en su `api/CLAUDE.md`, fuera de este repositorio. Aquí se fija lo que este repositorio documenta que usa
(`ARQUITECTURA.md`, `CLAUDE.md`, `CHANGELOG.md` y los docstrings que nombran al portal): cada símbolo se importa por su
ruta de la 0.10, sus parámetros siguen en el mismo orden (una llamada por posición sigue valiendo), y exportar a
CONCAR devuelve el `resumen` que el portal guarda tal cual.

Si la 1.0 mueve algo de aquí, la ruta vieja tiene que seguir resolviendo, aunque avise (rama `motor-v1`, etapa 1,
14-sep-2026).
"""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
import warnings

import pytest

from util import GOLDEN

SIN_CENTROS = {"cuentas": {"gasto": "659999"}, "usa_centros_costo": False}

# (módulo, nombre, los primeros parámetros en el orden de la 0.10)
USADOS = [
    ("contaperu.operaciones", "exportar",
     ("doc", "driver", "configuracion", "correlativos", "incluir_observados", "fecha", "imputacion")),
    ("contaperu.operaciones", "generar_asiento",
     ("doc", "configuracion", "correlativos", "incluir_observados", "imputacion", "driver")),
    ("contaperu.operaciones", "diagnosticar", ("doc", "configuracion", "correlativos", "driver", "imputacion")),
    ("contaperu.operaciones", "revisar", ("doc", "configuracion")),
    ("contaperu.operaciones", "leer_xml", ("contenido", "libro", "es_base64")),
    ("contaperu.operaciones", "config_aplicada", ("configuracion", "driver")),
    ("contaperu.operaciones", "con_imputacion", ("config", "imputacion", "comprobantes")),
    ("contaperu.operaciones", "libro_de", ("doc",)),
    ("contaperu.operaciones", "comprobantes_de", ("doc",)),
    ("contaperu.drivers.concar", "filas_de_comprobante",
     ("c", "config", "limites", "correlativo", "opciones", "es_venta")),
    ("contaperu.igv", "aplicar_igv", ("c", "igv")),
    ("contaperu.igv", "aplicar_total", ("c", "total")),
    ("contaperu.detracciones", "normalizar", ("comprobantes", "config")),
    ("contaperu.detracciones", "monto_detraccion", ("c", "config")),
    ("contaperu.validar", "marcar_duplicados", ("comprobantes", "claves_previas", "claves_proceso")),
    ("contaperu.validar", "revisar", ("comprobantes", "libro", "claves_previas", "claves_proceso")),
    ("contaperu.modelo", "clave_de", ("tipo_cp", "serie", "numero", "contraparte_doc")),
    ("contaperu.asiento", "comprobantes_sin_centro", ("comprobantes", "config", "es_venta")),
    ("contaperu.asiento", "etiquetas_sub_diario", ("config",)),
    ("contaperu.asiento", "numerar", ("comprobantes", "config", "periodo", "correlativos", "es_venta")),
    ("contaperu.asiento", "correlativos_de_partida", ("comprobantes", "config", "es_venta", "dados")),
    ("contaperu.asiento", "huella", ("lineas",)),
]

# Las clases que el portal captura o construye.
CLASES = [
    ("contaperu.generar", "Exportado"), ("contaperu.generar", "ErroresBloqueantes"),
    ("contaperu.operaciones", "DocumentoInvalido"), ("contaperu.drivers.concar", "CorrelativoDesborda"),
    ("contaperu.asiento", "NoExportable"), ("contaperu.asiento", "SinCentro"), ("contaperu.asiento", "SinCuenta"),
    ("contaperu.igv", "IgvImposible"), ("contaperu.igv", "TotalImposible"),
]


def _obtener(modulo: str, nombre: str):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return getattr(importlib.import_module(modulo), nombre)


@pytest.mark.parametrize("modulo,nombre,parametros", USADOS, ids=[f"{m.split('.', 1)[1]}.{n}" for m, n, _ in USADOS])
def test_se_importa_por_su_ruta_y_sus_parametros_siguen_en_orden(modulo, nombre, parametros):
    funcion = _obtener(modulo, nombre)
    assert list(inspect.signature(funcion).parameters)[:len(parametros)] == list(parametros)


@pytest.mark.parametrize("modulo,nombre", CLASES, ids=[f"{m.split('.', 1)[1]}.{n}" for m, n in CLASES])
def test_las_clases_que_captura_o_construye_siguen_ahi(modulo, nombre):
    assert isinstance(_obtener(modulo, nombre), type)


def test_exportado_conserva_sus_campos():
    """El portal guarda `archivo` y `contenido` en Storage, y lee el resto al mostrar la exportación."""
    campos = [campo.name for campo in dataclasses.fields(_obtener("contaperu.generar", "Exportado"))]
    assert campos[:11] == ["nombre", "nombre_comprimido", "formato", "driver", "texto", "comprimido", "comprobantes",
                           "resumen", "archivo", "contenido", "content_type"]


def test_exportar_a_concar_por_posicion_devuelve_el_resumen_que_el_portal_guarda():
    exportar = _obtener("contaperu.operaciones", "exportar")
    documento = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    respuesta = exportar(documento, "concar", SIN_CENTROS, {"11": 7}, False, "2026-09-14", None)
    resumen = respuesta["resumen"]
    assert resumen["sub_diarios"]["11"]["desde"] == 7 and resumen["sub_diarios"]["11"]["hasta"] == 9
    assert {"desde_codigo", "hasta_codigo", "comprobantes", "desborda", "etiqueta"} <= set(resumen["sub_diarios"]["11"])
    assert {"filas", "fechas", "debe", "haber", "huella", "comprobantes", "excluidos", "duplicados", "con_aviso",
            "con_error", "fuera_del_destino", "total", "igv"} <= set(resumen)
    assert len(resumen["huella"]) == 64 and respuesta["_exportacion"]["huella"] == resumen["huella"]
    assert respuesta["_exportacion"]["fecha"] == "2026-09-14"


def test_numerar_devuelve_los_numeros_por_identidad_del_comprobante():
    """El portal recuerda los rangos para proponer el siguiente, y lee el número de cada comprobante por `id()`."""
    comprobantes = _obtener("contaperu.operaciones", "comprobantes_de")(
        json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8")))
    config = _obtener("contaperu.operaciones", "config_aplicada")(SIN_CENTROS, "concar")
    numeros, rangos = _obtener("contaperu.asiento", "numerar")(comprobantes, config, "202601", {"11": 1})
    assert [numeros[id(c)] for c in comprobantes] == ["010001", "010002", "010003"]
    assert rangos["11"]["hasta"] == 3
