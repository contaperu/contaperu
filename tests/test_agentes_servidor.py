"""La base MCP sobre el SDK (`contaperu.agentes.servidor`): lo que un servidor montado encima recibe hecho.

Se prueba con un servidor de ejemplo —una familia de tres modos y una herramienta que escribe— y con el del motor, y
cada regla se vio caer quitándola. Las llamadas van por `call_tool` y, donde importa lo que ve un cliente, por el
protocolo con el cliente en memoria del SDK.
"""
from __future__ import annotations

import asyncio
import json
import threading

import pytest
from mcp import Client

from contaperu import api
from contaperu.agentes import Catalogo, CatalogoInvalido, Ficha, Retirada, Riesgo
from contaperu.agentes.servidor import (ChoqueDeNombres, Servidor, crear_servidor, en_curso, familia, registrar,
                                        registrar_del_motor)

ESCRIBE = Riesgo(escribe=True, huella=True)


def catalogo(**opciones) -> Catalogo:
    return Catalogo([
        Ficha("informe", "informe", modo="resumen", titulo="Un informe"),
        Ficha("los_totales", "informe", modo="totales"),
        Ficha("por_cuenta", "informe", modo="cuentas"),
        Ficha("guardar", "guardar", riesgo=ESCRIBE),
    ], **opciones)


def resumen(periodo: str) -> dict:
    return {"que": "resumen", "periodo": periodo, "siguiente": "Para el detalle, `por_cuenta`."}


async def totales(periodo: str, moneda: str = "PEN") -> dict:
    return {"que": "totales", "periodo": periodo, "moneda": moneda}


def por_cuenta(periodo: str, cuenta: str) -> dict:
    return {"que": "cuentas", "cuenta": cuenta, "hilo": threading.current_thread() is threading.main_thread()}


def guardar(nombre: str, confirmo: bool = False, huella: str = "") -> dict:
    """Guarda un nombre. Antes, mira el `informe`."""
    return {"guardado": nombre, "confirmo": confirmo}


FUNCIONES = {"informe": familia("Un informe del mes. `que` elige cuál.",
                                {"resumen": resumen, "totales": totales, "cuentas": por_cuenta}),
             "guardar": guardar}


def servidor(**opciones) -> Servidor:
    s = Servidor("ejemplo", version="1.0", **opciones)
    registrar(s, catalogo(), FUNCIONES)
    return s


def llamar(s: Servidor, cual: str, /, **argumentos):
    return asyncio.run(s.call_tool(cual, argumentos))


def datos(resultado) -> dict:
    assert not resultado.is_error, resultado.content[0].text
    return json.loads(resultado.content[0].text)


def herramientas(s: Servidor) -> dict:
    return {h.name: h for h in asyncio.run(s.list_tools())}


# --- la familia ----------------------------------------------------------------------------------------------------

def test_una_familia_es_una_herramienta_con_que():
    h = herramientas(servidor())["informe"]
    propiedades = h.input_schema["properties"]
    assert propiedades["que"]["enum"] == ["resumen", "totales", "cuentas"]
    assert propiedades["que"]["default"] == "resumen", "la que se llama como la herramienta es la de por defecto"
    assert set(propiedades) == {"que", "periodo", "moneda", "cuenta"}, "la unión de los parámetros de sus modos"
    assert h.input_schema.get("required", []) == [], "lo obligatorio de un modo lo exige el despacho, no el esquema"
    assert h.title == "Un informe" and h.annotations.read_only_hint is True


def test_que_elige_y_el_despacho_dice_lo_que_no_va():
    s = servidor()
    assert datos(llamar(s, "informe", periodo="202611"))["que"] == "resumen"
    assert datos(llamar(s, "informe", que="totales", periodo="202611")) == {"que": "totales", "periodo": "202611",
                                                                           "moneda": "PEN"}
    for argumentos, frase in (({"que": "proveedores", "periodo": "202611"}, "`que` es uno de: resumen, totales, cuentas"),
                              ({"que": "totales", "periodo": "202611", "cuenta": "6011"}, "no van `cuenta`"),
                              ({"que": "cuentas", "periodo": "202611"}, "hace falta `cuenta`")):
        rechazo = llamar(s, "informe", **argumentos)
        problema = json.loads(rechazo.content[0].text)
        assert rechazo.is_error and problema["clave"] == "entrada_invalida" and frase in problema["detail"], problema


def test_un_modo_sincrono_corre_fuera_del_hilo_del_bucle():
    assert datos(llamar(servidor(), "informe", que="cuentas", periodo="202611", cuenta="6011"))["hilo"] is False


def test_una_familia_tiene_que_traer_los_modos_del_catalogo():
    with pytest.raises(CatalogoInvalido, match="trae los modos"):
        registrar(Servidor("x"), catalogo(), {**FUNCIONES, "informe": familia("d", {"resumen": resumen})})
    with pytest.raises(CatalogoInvalido, match="necesita una `familia`"):
        registrar(Servidor("x"), catalogo(), {**FUNCIONES, "informe": resumen})
    with pytest.raises(CatalogoInvalido, match="faltan \\['guardar'\\]"):
        registrar(Servidor("x"), catalogo(), {"informe": FUNCIONES["informe"]})


# --- lo que pasa en cada llamada -----------------------------------------------------------------------------------

def test_la_guarda_corre_antes_y_niega_con_su_clave():
    llamadas = []

    def guarda(nombre: str, modo: str, argumentos: dict) -> None:
        llamadas.append((nombre, modo))
        if nombre == "guardar":
            raise api.DocumentoInvalido("Esta llave es de solo lectura.")

    s = Servidor("x", guarda=guarda)
    espia = []
    registrar(s, catalogo(), {**FUNCIONES, "guardar": lambda nombre: espia.append(nombre)})
    negado = llamar(s, "guardar", nombre="a")
    assert negado.is_error and json.loads(negado.content[0].text)["clave"] == "documento_invalido"
    assert espia == [], "una llamada negada no ejecuta la herramienta"
    datos(llamar(s, "informe", que="totales", periodo="202611"))
    assert llamadas == [("guardar", ""), ("informe", "totales")]


def test_la_guarda_puede_ser_asincrona():
    async def guarda(nombre: str, modo: str, argumentos: dict) -> None:
        raise api.DocumentoInvalido("no")

    assert llamar(servidor(guarda=guarda), "informe", periodo="202611").is_error


def test_lo_que_no_se_ve_tampoco_se_llama():
    s = servidor(visibles=lambda nombres: [n for n in nombres if n != "guardar"])
    assert set(herramientas(s)) == {"informe"}
    oculta = llamar(s, "guardar", nombre="a")
    assert oculta.is_error and oculta.content[0].text == "Unknown tool: guardar", "lo oculto no se distingue de lo que no existe"


def test_en_curso_se_ve_desde_dentro():
    visto = []
    s = Servidor("x")
    registrar(s, Catalogo([Ficha("mirar", "mirar")]), {"mirar": lambda: visto.append(en_curso()) or {}})
    datos(llamar(s, "mirar"))
    assert visto == [("mirar", "")] and en_curso() == ("", ""), "y se limpia al salir"


def test_un_error_de_la_herramienta_llega_entero_y_con_su_clave():
    """La v2 del SDK solo copia el texto de un `ToolError`: el de cualquier otra excepción llegaría como «Error executing
    tool X». La base dice la causa, con el «problem details» del motor; y lo que no es del motor no enseña su texto."""
    def falla(cual: str) -> dict:
        raise api.DocumentoInvalido("El libro no trae periodo.") if cual == "motor" else RuntimeError("C:/secreto")

    s = Servidor("x")
    registrar(s, Catalogo([Ficha("falla", "falla")]), {"falla": falla})
    del_motor = json.loads(llamar(s, "falla", cual="motor").content[0].text)
    assert del_motor["clave"] == "documento_invalido" and del_motor["detail"] == "El libro no trae periodo."
    interno = json.loads(llamar(s, "falla", cual="otro").content[0].text)
    assert interno["clave"] == "error_interno" and "secreto" not in json.dumps(interno)
    propio = Servidor("y", decir_error=lambda e: f"{type(e).__name__}: {e}")
    registrar(propio, Catalogo([Ficha("falla", "falla")]), {"falla": falla})
    assert llamar(propio, "falla", cual="motor").content[0].text == "DocumentoInvalido: El libro no trae periodo."


def test_lo_que_contesta_nombra_las_operaciones_como_se_alcanzan():
    assert datos(llamar(servidor(), "informe", periodo="202611"))["siguiente"] == (
        "Para el detalle, `informe` (`que: cuentas`).")


# --- los nombres retirados -----------------------------------------------------------------------------------------

def test_un_nombre_retirado_dice_donde_esta_y_no_ejecuta():
    s = servidor()
    retirada = llamar(s, "por_cuenta", periodo="202611", cuenta="6011")
    assert retirada.is_error and retirada.content[0].text == (
        "`por_cuenta` ya no es una herramienta: ahora es `informe` con `que: cuentas`.")
    propia = servidor(decir_retirada=lambda r, prefijo: r.frase(prefijo) + " Vuelve a conectar.")
    assert llamar(propia, "por_cuenta").content[0].text.endswith("Vuelve a conectar.")


def test_una_retirada_que_ejecuta_es_un_alias():
    s = Servidor("x")
    registrar(s, catalogo(retiradas=[Retirada("cuentas_del_mes", "informe", "cuentas", ejecuta=True)]), FUNCIONES)
    assert datos(llamar(s, "cuentas_del_mes", periodo="202611", cuenta="6011"))["cuenta"] == "6011"
    assert "cuentas_del_mes" not in herramientas(s), "un alias no se anuncia"


# --- registrar, el prefijo y lo fijado -----------------------------------------------------------------------------

def test_dos_herramientas_con_el_mismo_nombre_no_conviven():
    s = servidor()
    with pytest.raises(ChoqueDeNombres, match="`guardar`"):
        registrar(s, Catalogo([Ficha("guardar", "guardar", riesgo=ESCRIBE)]), {"guardar": guardar})
    with pytest.raises(ChoqueDeNombres):
        s.tool(name="informe")(resumen)


def test_el_motor_en_el_servidor_de_otro_va_con_prefijo():
    """`exportar` es un nombre que cualquiera tiene: sin prefijo chocaría, y con el de por defecto convive."""
    s = Servidor("mi-erp")
    s.tool(name="exportar")(lambda mes: {"mes": mes})
    with pytest.raises(ChoqueDeNombres, match="`exportar`"):
        registrar_del_motor(s, prefijo="")
    otro = Servidor("mi-erp")
    otro.tool(name="exportar")(lambda mes: {"mes": mes})
    publicadas = registrar_del_motor(otro)
    assert "contaperu_exportar" in publicadas and len(publicadas) == 18
    nombres = herramientas(otro)
    assert "exportar" in nombres and "contaperu_validar_comprobantes" in nombres
    assert len(asyncio.run(otro.list_resources())) == 14, "los recursos no llevan prefijo: su dirección ya es única"


def test_con_prefijo_las_citas_tambien_lo_llevan():
    s = Servidor("x")
    registrar(s, catalogo(), FUNCIONES, prefijo="p_")
    nombres = herramientas(s)
    assert set(nombres) == {"p_informe", "p_guardar"}
    assert "`p_informe`" in nombres["p_guardar"].description
    assert datos(llamar(s, "p_informe", periodo="202611"))["siguiente"].endswith("`p_informe` (`que: cuentas`).")
    assert llamar(s, "p_por_cuenta").content[0].text.startswith("`p_por_cuenta` ya no es una herramienta")


def test_lo_fijado_no_se_ve_y_llega_en_cada_llamada():
    vistos = iter(["202610", "202611"])
    s = Servidor("x")
    registrar(s, catalogo(), FUNCIONES, fijar={"periodo": lambda: next(vistos)})
    propiedades = herramientas(s)["informe"].input_schema["properties"]
    assert "periodo" not in propiedades, "el agente no ve lo que pone la aplicación"
    assert datos(llamar(s, "informe", que="totales"))["periodo"] == "202610"
    assert datos(llamar(s, "informe", que="totales"))["periodo"] == "202611", "una función se llama en cada petición"


# --- el servidor del motor -----------------------------------------------------------------------------------------

def test_dos_servidores_no_comparten_nada():
    uno, otro = crear_servidor(), crear_servidor()
    uno.tool(name="mio")(lambda: {})
    assert "mio" in herramientas(uno) and "mio" not in herramientas(otro)
    assert len(herramientas(otro)) == 18


def test_un_servidor_propio_elige_lo_del_motor():
    s = crear_servidor(nombre="mio", herramientas=["diagnosticar", "exportar"], prefijo="cp_", recursos=False)
    assert list(herramientas(s)) == ["cp_diagnosticar", "cp_exportar"]
    assert asyncio.run(s.list_resources()) == []
    assert "`cp_exportar`" in s.instructions and "`exportar`" not in s.instructions, "las instrucciones citan con prefijo"


def test_por_el_protocolo_un_rechazo_de_la_guarda_es_un_is_error():
    """Lo que ve un cliente: la guarda niega dentro de la petición y la respuesta es un `is_error` con la clave."""
    def guarda(nombre: str, modo: str, argumentos: dict) -> None:
        raise api.DocumentoInvalido("Sin permiso.")

    s = crear_servidor(guarda=guarda)

    async def por_el_protocolo():
        async with Client(s) as cliente:
            return await cliente.call_tool("drivers_disponibles", {})

    resultado = asyncio.run(por_el_protocolo())
    assert resultado.is_error and json.loads(resultado.content[0].text)["detail"] == "Sin permiso."
