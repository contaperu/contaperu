"""El catálogo de la base MCP (`contaperu.agentes`), sin el SDK del protocolo.

Lo que se prueba es lo que hace segura una familia de operaciones detrás de una sola herramienta: un nivel de riesgo
por herramienta, el modo por defecto, los nombres que se retiraron, la traducción de nombres a la puerta y el despacho
que el esquema no hace. Cada regla se vio caer quitándola.
"""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import pytest

from contaperu import agentes
from contaperu.agentes import (DEL_MOTOR, MIRA, Catalogo, CatalogoInvalido, EntradaInvalida, Ficha, Retirada, Riesgo,
                               nombre_valido, operacion_del_modo, recortar, solo_los_de_su_modo)

ESCRIBE = Riesgo(escribe=True, huella=True)


def familia() -> Catalogo:
    """Un servidor de ejemplo: una herramienta con tres modos —la que conserva su nombre va SEGUNDA en la lista, a
    propósito— y otra sola."""
    return Catalogo([
        Ficha("los_totales", "informe", modo="totales", titulo="Los totales"),
        Ficha("informe", "informe", modo="resumen", titulo="El resumen"),
        Ficha("por_cuenta", "informe", modo="cuentas"),
        Ficha("guardar", "guardar", riesgo=ESCRIBE, grupo="configuracion", perfil="integrador"),
    ], titulos={"informe": "Un informe del mes"})


# --- las reglas del catálogo ---------------------------------------------------------------------------------------

def test_una_herramienta_no_mezcla_dos_niveles_de_riesgo():
    with pytest.raises(CatalogoInvalido, match="más de un nivel de riesgo"):
        Catalogo([Ficha("mirar", "cosas", modo="mirar"), Ficha("borrar", "cosas", modo="borrar",
                                                                   riesgo=Riesgo(escribe=True, borra=True))])


def test_ni_dos_grupos_ni_dos_perfiles():
    with pytest.raises(CatalogoInvalido) as error:
        Catalogo([Ficha("a", "x", modo="a", grupo="uno"), Ficha("b", "x", modo="b", grupo="dos", perfil="integrador")])
    assert len(error.value.faltas) == 2, "dice todas las faltas a la vez"


def test_lo_que_no_cuadra_en_una_familia_se_dice_al_construirla():
    casos = {
        "repite un modo": [Ficha("a", "x", modo="m"), Ficha("b", "x", modo="m")],
        "no todas dicen su modo": [Ficha("a", "x", modo="m"), Ficha("b", "x")],
        "una sola operación y le pone modo": [Ficha("a", "a", modo="m")],
        "no vale como nombre de herramienta": [Ficha("a", "servidor.a")],
        "no vale como nombre de operación": [Ficha("Leer-XML", "leer")],
        "no es uno de": [Ficha("a", "a", perfil="privado")],
        "pide huella sin escribir": [Ficha("a", "a", riesgo=Riesgo(huella=True))],
        "está dos veces": [Ficha("a", "a"), Ficha("a", "b")],
    }
    for falta, fichas in casos.items():
        with pytest.raises(CatalogoInvalido, match=falta):
            Catalogo(fichas)


def test_el_nombre_de_una_herramienta_es_el_que_acepta_claude():
    """El protocolo admite el punto y hasta 128 caracteres; el API de Claude, no."""
    assert nombre_valido("contaperu_exportar") and nombre_valido("a-b")
    assert not nombre_valido("contaperu.exportar") and not nombre_valido("x" * 65) and not nombre_valido("")


def test_la_que_se_llama_como_la_herramienta_va_primero_y_es_la_de_por_defecto():
    informe = familia().herramienta("informe")
    assert informe.principal.operacion == "informe" and informe.por_defecto == "resumen"
    assert informe.modos == ("resumen", "totales", "cuentas"), "las demás siguen en el orden de la tabla"
    assert informe.titulo == "Un informe del mes", "el del catálogo manda sobre el de la operación"
    sin_defecto = Catalogo([Ficha("los_totales", "informe", modo="totales"), Ficha("por_cuenta", "informe",
                                                                                     modo="cuentas")])
    assert sin_defecto.herramienta("informe").por_defecto == "", "sin una que se llame como ella, `que` es obligatorio"


def test_las_anotaciones_salen_del_riesgo():
    c = familia()
    assert c.herramienta("informe").anotaciones() == {"title": "Un informe del mes", "readOnlyHint": True,
                                                       "destructiveHint": None, "idempotentHint": None,
                                                       "openWorldHint": False}
    guardar = c.herramienta("guardar").anotaciones()
    assert guardar["readOnlyHint"] is False and guardar["destructiveHint"] is False
    borra = Riesgo(escribe=True, borra=True, sale_a_la_red=None).anotaciones()
    assert borra["destructiveHint"] is True and borra["openWorldHint"] is None, "None es «no se declara»"


# --- los nombres que se retiraron ----------------------------------------------------------------------------------

def test_un_modo_con_otro_nombre_fue_una_herramienta_y_se_retira_solo():
    retiradas = familia().retiradas
    assert set(retiradas) == {"los_totales", "por_cuenta"}, "`informe` sigue siendo una herramienta"
    assert retiradas["por_cuenta"] == Retirada("por_cuenta", "informe", "cuentas")
    assert retiradas["por_cuenta"].frase() == "`por_cuenta` ya no es una herramienta: ahora es `informe` con `que: cuentas`."
    assert retiradas["por_cuenta"].frase("p_") == "`p_por_cuenta` ya no es una herramienta: ahora es `p_informe` con `que: cuentas`."


def test_una_operacion_que_solo_se_publica_con_otro_nombre_no_es_una_retirada():
    """`leer_xml` se publica como `leer_xml_ubl` desde siempre: ese nombre nunca fue de una herramienta."""
    assert DEL_MOTOR.retiradas == {}
    assert DEL_MOTOR.por_operacion["leer_xml"].herramienta == "leer_xml_ubl"


def test_una_retirada_declarada_tiene_que_apuntar_a_algo_que_existe():
    base = [Ficha("a", "a")]
    with pytest.raises(CatalogoInvalido, match="no es una herramienta"):
        Catalogo(base, retiradas=[Retirada("vieja", "nueva")])
    with pytest.raises(CatalogoInvalido, match="sigue siendo una herramienta"):
        Catalogo(base, retiradas=[Retirada("a", "a")])
    with pytest.raises(CatalogoInvalido, match="no lo tiene"):
        Catalogo([Ficha("x", "f", modo="x"), Ficha("y", "f", modo="y")], retiradas=[Retirada("vieja", "f", "z")])
    declarada = Catalogo(base, retiradas=[Retirada("vieja", "a", ejecuta=True)]).retiradas
    assert declarada == {"vieja": Retirada("vieja", "a", ejecuta=True)}


# --- la traducción a la puerta -------------------------------------------------------------------------------------

def test_una_operacion_citada_se_dice_como_se_alcanza():
    c = familia()
    assert c.en_la_puerta("Pide `por_cuenta` antes.") == "Pide `informe` (`que: cuentas`) antes."
    assert c.en_la_puerta("Pide `informe`.") == "Pide `informe`.", "la de por defecto se llama como la herramienta"
    assert c.en_la_puerta("`guardar` y `otra_cosa`") == "`guardar` y `otra_cosa`", "lo que no conoce no lo toca"
    assert DEL_MOTOR.en_la_puerta("Llama a `revisar`.") == "Llama a `validar_comprobantes`."


def test_con_prefijo_cada_herramienta_lleva_el_del_servidor():
    c = familia()
    assert c.en_la_puerta("`informe`, `por_cuenta` y `guardar`", "p_") == (
        "`p_informe`, `p_informe` (`que: cuentas`) y `p_guardar`")
    # Y una herramienta que no se llama como ninguna de sus operaciones, que es la que nace al juntar una familia.
    nueva = Catalogo([Ficha("los_totales", "informe", modo="totales"), Ficha("por_cuenta", "informe", modo="cuentas")])
    assert nueva.en_la_puerta("Usa `informe`.", "p_") == "Usa `p_informe`."


def test_la_traduccion_llega_a_cualquier_profundidad():
    c = familia()
    valor = {"siguiente": ["usa `por_cuenta`", ("y `los_totales`", 3)], "n": 7, "sin": "nada que ver"}
    assert c.traducido(valor) == {"siguiente": ["usa `informe` (`que: cuentas`)",
                                                ("y `informe` (`que: totales`)", 3)], "n": 7, "sin": "nada que ver"}


# --- el despacho ---------------------------------------------------------------------------------------------------

def test_que_elige_la_ficha_y_un_valor_que_no_existe_dice_cuales_hay():
    informe = familia().herramienta("informe")
    assert operacion_del_modo(informe, " Cuentas ").operacion == "por_cuenta"
    assert operacion_del_modo(informe, "").operacion == "informe", "sin `que`, la de por defecto"
    with pytest.raises(EntradaInvalida, match="`que` es uno de: resumen, totales, cuentas") as error:
        operacion_del_modo(informe, "proveedores")
    assert error.value.clave == "entrada_invalida"
    assert operacion_del_modo(familia().herramienta("guardar"), "").operacion == "guardar"


def test_un_parametro_de_otro_modo_se_rechaza():
    por_modo = {"cuentas": {"cuenta"}, "totales": set()}
    solo_los_de_su_modo("cuentas", por_modo, cuenta="6011", proveedor="", quitar=False, lista=[])
    with pytest.raises(EntradaInvalida, match="Con `que: totales` no van `cuenta`"):
        solo_los_de_su_modo("totales", por_modo, cuenta="6011", proveedor=None)


def test_una_lista_recortada_dice_cuanto_le_falta():
    assert recortar(list(range(80))) == (list(range(50)), 30)
    assert recortar([1, 2], tope=5) == ([1, 2], 0)


# --- el catálogo del motor -----------------------------------------------------------------------------------------

def test_el_catalogo_del_motor_es_lo_que_publica_su_servidor():
    """Mismas herramientas, mismo orden y mismas anotaciones que el servidor de hoy: el catálogo se deriva de la tabla y
    el servidor también, así que tienen que decir lo mismo. Las anotaciones se comparan con la foto congelada."""
    from contaperu.puertas.servidor_mcp import mcp

    publicadas = [h.name for h in asyncio.run(mcp.list_tools())]
    assert list(DEL_MOTOR.herramientas) == publicadas
    foto = json.loads((Path(__file__).parent / "fixtures" / "mcp" / "publicado.json").read_text(encoding="utf-8"))
    for nombre, h in DEL_MOTOR.herramientas.items():
        assert h.anotaciones() == foto["herramientas"][nombre]["anotaciones"], nombre


def test_lo_publico_y_lo_de_un_integrador_se_eligen():
    c = familia()
    assert list(c.elegir(perfil="publico").herramientas) == ["informe"]
    assert list(c.elegir().herramientas) == ["informe", "guardar"], "el perfil integrador incluye al público"
    assert list(c.elegir(solo_lectura=True).herramientas) == ["informe"]
    assert list(c.elegir(grupos=["configuracion"]).herramientas) == ["guardar"]
    assert set(c.elegir(herramientas=["informe"]).retiradas) == {"los_totales", "por_cuenta"}
    with pytest.raises(CatalogoInvalido, match="`borrar` no es una herramienta"):
        c.elegir(herramientas=["borrar"])
    with pytest.raises(CatalogoInvalido, match="«bancos» no es un grupo"):
        c.elegir(grupos=["bancos"])


# --- lo que no puede importar --------------------------------------------------------------------------------------

def test_el_catalogo_no_depende_del_sdk_ni_de_pydantic():
    """Es lo que permite cambiar de versión mayor del SDK tocando solo `agentes.servidor`: el resto de la base se
    sostiene con la biblioteca estándar."""
    carpeta = Path(agentes.__file__).parent
    culpables = []
    for archivo in sorted(carpeta.rglob("*.py")):
        if archivo.name == "servidor.py":
            continue
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            modulos = ([a.name for a in nodo.names] if isinstance(nodo, ast.Import)
                       else [nodo.module or ""] if isinstance(nodo, ast.ImportFrom) and not nodo.level else [])
            culpables += [f"{archivo.name}: {m}" for m in modulos if m.split(".")[0] in {"mcp", "pydantic"}]
    assert culpables == [], f"el catálogo depende del SDK: {culpables}"


def test_mira_es_el_riesgo_de_lo_que_no_cambia_nada():
    assert MIRA == Riesgo() and not MIRA.escribe and MIRA.sale_a_la_red is False
