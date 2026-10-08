"""La API pública: lo que promete sobre sí misma.

- Lo que declara en `__all__` se importa.
- El documento va primero y todo lo demás por su nombre; `driver` no tiene valor por defecto.
- La tabla de operaciones es la fuente de las puertas: el MCP expone exactamente sus herramientas y sus recursos.
- El circuito con que se deprecia un nombre sigue en pie, aunque la 2.0 dejara el paquete sin ninguno.
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
        # Herramienta, recurso o las dos: lo que no vale es que una operación no salga por ninguna parte del MCP.
        assert op.herramienta or op.recurso, f"{op.nombre}: en el MCP no sale por ninguna parte"


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
        "sire": "sire", "concar": "legacy", "contasis": "legacy", "starsoft": "legacy", "ple": "sire", "ple_plan": "sire", "csv": "erp",
        "asiento_contable": "erp"}


def test_verificar_un_driver_dice_lo_que_le_falta():
    bien = api.verificar_driver("drivers_de_prueba.diario_json")
    assert bien["cumple"] and bien["incumplimientos"] == [] and (bien["canal"], bien["grupo"]) == ("legacy", "legacy")
    with pytest.raises(ImportError, match="no_existe_este_driver"):
        api.verificar_driver("no_existe_este_driver")


def test_no_queda_ninguna_ruta_de_la_0_x():
    """La 2.0 las retiró todas. Lo que una aplicación importaba en la 0.10 ya no resuelve."""
    for modulo in ("contaperu.operaciones", "contaperu.generar", "contaperu.cli", "contaperu.formato",
                   "contaperu.servidor_mcp", "contaperu._compat"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(modulo)


def test_no_queda_ninguno_de_los_puentes_de_la_6_4():
    """La 6.4.0 mudó el núcleo a `tributos/` y `contable/` y dejó seis puentes en la raíz, que avisaban con
    `RutaObsoleta` durante toda la 6.x. La 7.0 los retira, que es lo que `_obsoleto.RETIRO` prometía.

    Se comprueba que el módulo **no resuelve**, no que el fichero no esté: borrar el `.py` y dejarse el `.pyc`
    deja a Python importando el directorio como paquete de espacio de nombres, y entonces un test que mirara el
    disco pasaría en verde con el módulo todavía vivo. Es la trampa que la 4.0 documentó."""
    for modulo, nueva in (("contaperu.igv", "contaperu.tributos.igv"),
                          ("contaperu.detracciones", "contaperu.tributos.detracciones"),
                          ("contaperu.validar", "contaperu.tributos.validar"),
                          ("contaperu.comparar_sire", "contaperu.tributos.comparar_sire"),
                          ("contaperu.partida_doble", "contaperu.contable.partida_doble"),
                          ("contaperu.resumen", "contaperu.contable.resumen")):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(modulo)
        assert importlib.import_module(nueva), f"{modulo} se retiró pero {nueva} tiene que estar"


def test_el_paquete_raiz_no_ofrece_lo_retirado():
    """El puente se importaba también por atributo del paquete (`from contaperu import igv`), que lo resuelve
    `_SUBMODULOS`. Un nombre que se queda ahí después de borrar el fichero da `ModuleNotFoundError` desde dentro
    de `__getattr__`, que es un sitio peor para enterarse."""
    import contaperu
    for nombre in ("igv", "detracciones", "validar", "comparar_sire", "partida_doble", "resumen"):
        assert nombre not in contaperu._SUBMODULOS
        assert nombre not in contaperu.__all__
        with pytest.raises(AttributeError):
            getattr(contaperu, nombre)
    # Y los paquetes que los sustituyen sí salen por los dos sitios.
    for nombre in ("tributos", "contable"):
        assert nombre in contaperu._SUBMODULOS and nombre in contaperu.__all__
        assert getattr(contaperu, nombre)


def test_el_mecanismo_de_deprecacion_sigue_en_pie():
    """No queda ningún nombre deprecado —la 7.0 cobró los seis puentes de la 6.4.0—, pero el circuito con que se deprecia uno tiene que seguir funcionando: es
    lo que se usará la próxima vez que algo cambie de sitio. Se prueba sobre un módulo de mentira, para no tener
    que deprecar nada de verdad solo por cubrirlo.

    Lo que se comprueba es lo que costó acertar: que el aviso salga al PEDIR el nombre —no al crear el
    `__getattr__`—, que diga la ruta nueva y la versión en que desaparece, y que un nombre que no está siga dando
    el `AttributeError` de siempre."""
    from contaperu._obsoleto import RETIRO, reexportar

    obtener, listar = reexportar("paquete.viejo", {"Comprobante": "contaperu.modelo:Comprobante"},
                                 nuevas={"Comprobante": "contaperu.api.Comprobante"})
    assert listar() == ["Comprobante"]
    with pytest.warns(api.RutaObsoleta, match=f"usa `contaperu.api.Comprobante`.*|se retira en la {RETIRO}"):
        assert obtener("Comprobante") is api.Comprobante
    with pytest.raises(AttributeError):
        obtener("nombre_que_no_existe")


def test_un_error_del_motor_se_dice_con_su_clave():
    problema = api.problema(api.DocumentoInvalido("Falta el bloque `libro`"))
    assert problema == {"type": "about:blank", "status": 422, "title": "El motor no puede hacerlo",
                        "detail": "Falta el bloque `libro`", "clave": "documento_invalido"}
    assert api.problema(api.ErroresBloqueantes([{"indice": 0}]))["errores"] == [{"indice": 0}]


def test_un_error_que_no_es_del_motor_no_ensena_su_texto():
    problema = api.problema(RuntimeError("C:/ruta/interna/secreta"))
    assert problema["status"] == 500 and "secreta" not in str(problema)
