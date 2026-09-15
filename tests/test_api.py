"""La API pública de la 1.0: lo que promete sobre sí misma.

- Lo que declara en `__all__` se importa.
- El documento va primero y todo lo demás por su nombre; `driver` no tiene valor por defecto.
- La tabla de operaciones es la fuente de las puertas: el MCP expone exactamente sus herramientas y sus recursos.
- Las rutas de la 0.10 resuelven al MISMO objeto y avisan con la ruta nueva.
- Un error se dice como «problem details» (RFC 9457) sin enseñar lo que no es del motor.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect

import pytest

from contaperu import api

CON_DOCUMENTO = ("revisar", "normalizar_detracciones", "diagnosticar", "generar_asiento", "exportar", "exportar_archivo")
HACIA_UN_DRIVER = ("diagnosticar", "generar_asiento", "exportar", "exportar_archivo")


def test_lo_que_declara_se_puede_importar():
    assert [nombre for nombre in api.__all__ if not hasattr(api, nombre)] == []
    assert len(api.__all__) == len(set(api.__all__))


@pytest.mark.parametrize("nombre", CON_DOCUMENTO)
def test_el_documento_va_primero_y_lo_demas_por_su_nombre(nombre):
    parametros = list(inspect.signature(getattr(api, nombre)).parameters.values())
    assert parametros[0].name == "documento"
    assert all(p.kind is p.KEYWORD_ONLY for p in parametros[1:]), f"{nombre}: solo el documento va por posición"


@pytest.mark.parametrize("nombre", HACIA_UN_DRIVER)
def test_el_driver_no_se_supone(nombre):
    driver = inspect.signature(getattr(api, nombre)).parameters["driver"]
    assert driver.default is inspect.Parameter.empty


def test_cada_operacion_de_la_tabla_existe_y_tiene_su_ruta():
    rutas = [op.ruta for op in api.OPERACIONES]
    assert len(rutas) == len(set(rutas))
    for op in api.OPERACIONES:
        assert op.funcion is getattr(api, op.nombre)
        assert op.ruta.startswith("/v1/") and op.descripcion
        parametros = list(inspect.signature(op.funcion).parameters.values())
        if op.metodo == "GET":
            assert all(p.default is not inspect.Parameter.empty for p in parametros), f"{op.nombre}: GET no exige nada"
        else:
            assert op.metodo == "POST" and parametros, f"{op.nombre}: POST recibe un cuerpo"
        assert bool(op.herramienta) != bool(op.recurso), f"{op.nombre}: en el MCP es herramienta o recurso"


def test_el_mcp_expone_exactamente_la_tabla():
    pytest.importorskip("mcp")
    from contaperu.puertas.servidor_mcp import mcp

    herramientas = {h.name for h in asyncio.run(mcp.list_tools())}
    recursos = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    assert herramientas == {op.herramienta for op in api.OPERACIONES if op.herramienta}
    assert recursos == {op.recurso for op in api.OPERACIONES if op.recurso}


def test_verificar_un_driver_no_se_expone_por_ninguna_puerta_de_red():
    """Importa código por su nombre: sirve en Python y en la línea de comandos, nunca por HTTP ni por MCP."""
    assert "verificar_driver" in api.__all__
    assert "verificar_driver" not in {op.nombre for op in api.OPERACIONES}


def test_cada_driver_dice_su_grupo():
    """Lo que sale va al SIRE, a un sistema legacy o a un ERP (John, 15-sep-2026): el grupo sale del canal."""
    assert {nombre: datos["grupo"] for nombre, datos in api.drivers_disponibles().items()} == {
        "sire": "sire", "concar": "legacy", "contasis": "legacy", "csv": "erp"}


def test_verificar_un_driver_dice_lo_que_le_falta():
    bien = api.verificar_driver("drivers_de_prueba.diario_json")
    assert bien["cumple"] and bien["incumplimientos"] == [] and (bien["canal"], bien["grupo"]) == ("legacy", "legacy")
    with pytest.raises(ImportError, match="no_existe_este_driver"):
        api.verificar_driver("no_existe_este_driver")


@pytest.mark.parametrize("vieja,nueva", [
    ("contaperu.operaciones:exportar", None),
    ("contaperu.operaciones:DocumentoInvalido", "contaperu.api:DocumentoInvalido"),
    ("contaperu.operaciones:config_aplicada", "contaperu.pipeline.preparacion:config_aplicada"),
    ("contaperu.generar:Exportado", "contaperu.api:Exportado"),
    ("contaperu.generar:ErroresBloqueantes", "contaperu.api:ErroresBloqueantes"),
    ("contaperu.cli:main", "contaperu.puertas.cli:main"),
])
def test_la_ruta_vieja_avisa_y_resuelve_al_mismo_objeto(vieja, nueva):
    modulo, _, nombre = vieja.partition(":")
    with pytest.warns(api.RutaObsoleta, match="se retira en la 2.0"):
        objeto = getattr(importlib.import_module(modulo), nombre)
    if nueva:
        modulo_nuevo, _, nombre_nuevo = nueva.partition(":")
        assert objeto is getattr(importlib.import_module(modulo_nuevo), nombre_nuevo)


def test_el_aviso_dice_que_usar():
    viejo = importlib.import_module("contaperu.operaciones")
    with pytest.warns(api.RutaObsoleta, match="usa `contaperu.api.exportar`"):
        getattr(viejo, "exportar")


def test_importar_una_ruta_vieja_no_avisa():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        importlib.reload(importlib.import_module("contaperu.operaciones"))
        importlib.reload(importlib.import_module("contaperu.generar"))


def test_la_ruta_vieja_da_lo_mismo_que_la_nueva():
    import json
    import warnings

    from util import GOLDEN

    documento = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    config = {"cuentas": {"gasto": "659999"}, "usa_centros_costo": False}
    viejo = importlib.import_module("contaperu.operaciones")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", api.RutaObsoleta)
        exportar_viejo = getattr(viejo, "exportar")
    assert exportar_viejo(documento, "csv", config) == api.exportar(documento, driver="csv", configuracion=config)


def test_un_error_del_motor_se_dice_con_su_clave():
    problema = api.problema(api.DocumentoInvalido("Falta el bloque `libro`"))
    assert problema == {"type": "about:blank", "status": 422, "title": "El motor no puede hacerlo",
                        "detail": "Falta el bloque `libro`", "clave": "documento_invalido"}
    assert api.problema(api.ErroresBloqueantes([{"indice": 0}]))["errores"] == [{"indice": 0}]


def test_un_error_que_no_es_del_motor_no_ensena_su_texto():
    problema = api.problema(RuntimeError("C:/ruta/interna/secreta"))
    assert problema["status"] == 500 and "secreta" not in str(problema)
