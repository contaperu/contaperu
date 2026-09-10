"""La frontera entre el núcleo y sus puertas, comprobada por dependencia y no por buena voluntad.

`contaperu` es un núcleo de reglas contables con varias **puertas** delgadas encima: la línea de
comandos (`cli.py`), el servidor MCP (`servidor_mcp.py`) y —desde otro repositorio— el API del portal
contable. La propiedad que lo hace valer para los tres a la vez es que **el núcleo no sabe que las
puertas existen**: si mañana `asiento/` importara `servidor_mcp`, instalar la librería para hacer un
Excel arrastraría el SDK del protocolo, y una corrección del MCP podría cambiar un asiento.

Hasta hoy eso se sostenía por convención. Estos tests lo convierten en algo que se rompe solo.
"""
from __future__ import annotations

import ast
import asyncio
import pathlib

import pytest

PAQUETE = pathlib.Path(__file__).resolve().parents[1] / "contaperu"

# Las puertas: módulos que el núcleo NO puede importar. Son adaptadores — hablan un protocolo de
# fuera (argv y stdout; JSON-RPC) y dependen de cosas que el núcleo no necesita.
PUERTAS = {"cli", "servidor_mcp"}

# Lo único que la fachada puede necesitar de fuera del núcleo. `_version` es un módulo hoja.
FACHADA = "operaciones"


def modulos_del_nucleo() -> list[pathlib.Path]:
    """Todo `contaperu/**.py` menos las puertas y menos la fachada."""
    fuera = PUERTAS | {FACHADA}
    return [f for f in sorted(PAQUETE.rglob("*.py")) if f.stem not in fuera]


def importa(archivo: pathlib.Path) -> set[str]:
    """Los nombres de módulo que este archivo importa, relativos o absolutos."""
    salida: set[str] = set()
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            salida.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                salida.add(n.module.split(".")[0])
            # `from . import cli` — el nombre viaja en los alias, no en `module`
            if n.level and not n.module:
                salida.update(a.name for a in n.names)
    return salida


def test_el_nucleo_no_importa_ninguna_puerta():
    """Ni el asiento, ni los drivers, ni los lectores pueden depender del CLI o del MCP.

    El sentido de la flecha es toda la arquitectura: las puertas conocen el núcleo, nunca al revés.
    """
    culpables = {}
    for f in modulos_del_nucleo():
        malos = importa(f) & PUERTAS
        if malos:
            culpables[str(f.relative_to(PAQUETE)).replace("\\", "/")] = sorted(malos)
    assert culpables == {}, f"el núcleo importa una puerta: {culpables}"


def test_el_nucleo_no_importa_el_sdk_del_protocolo():
    """`mcp` es una dependencia OPCIONAL (extra `[mcp]`) y solo la puerta puede tocarla.

    Si se colara en el núcleo, `pip install contaperu` dejaría de bastar para generar un asiento —y
    el contenedor del portal, que instala solo `[excel]`, reventaría al importar.
    """
    culpables = [str(f.relative_to(PAQUETE)) for f in modulos_del_nucleo() if "mcp" in importa(f)]
    assert culpables == [], f"estos módulos del núcleo importan el SDK de MCP: {culpables}"


def test_el_nucleo_no_sale_a_la_red_ni_lee_el_entorno():
    """Un núcleo contable es una función: mismos datos, mismo resultado, aquí y en el servidor.

    Una llamada de red lo haría fallar sin internet y una variable de entorno lo haría dar
    resultados distintos en dos máquinas. `socket` entra por `zipfile`/`io`: no se busca aquí.
    """
    prohibidos = {"requests", "httpx", "urllib", "urllib3", "http", "socket", "subprocess"}
    culpables = {}
    for f in modulos_del_nucleo():
        malos = importa(f) & prohibidos
        if malos:
            culpables[str(f.relative_to(PAQUETE)).replace("\\", "/")] = sorted(malos)
    assert culpables == {}, f"el núcleo sale de su caja: {culpables}"

    entorno = [str(f.relative_to(PAQUETE)) for f in modulos_del_nucleo()
               if "os.environ" in f.read_text(encoding="utf-8") or "getenv" in f.read_text(encoding="utf-8")]
    assert entorno == [], f"el núcleo lee variables de entorno: {entorno}"


def test_el_nucleo_no_usa_el_reloj():
    """Todas las fechas entran por parámetro, y por eso un asiento de agosto sale igual en octubre.

    Un `date.today()` escondido haría que el mismo comprobante generase un archivo distinto según
    el día en que se exportara — y que un test pasara hoy y fallara en enero.
    """
    culpables = []
    for f in modulos_del_nucleo():
        src = f.read_text(encoding="utf-8")
        for aguja in ("date.today(", "datetime.now(", "datetime.today(", "time.time("):
            if aguja in src:
                culpables.append(f"{f.relative_to(PAQUETE)}: {aguja})")
    assert culpables == [], f"el núcleo mira el reloj: {culpables}"


@pytest.mark.parametrize("puerta", sorted(PUERTAS))
def test_cada_puerta_pasa_por_la_fachada(puerta):
    """Una puerta traduce un protocolo; no reimplementa el trabajo.

    Cuando una se salta `operaciones` y arma los objetos por su cuenta, deja de haber una capa sobre
    otra y pasa a haber dos clientes paralelos del núcleo — que es como el CLI acabó emitiendo un
    JSON sin la clave `pe_ledger` que el MCP sí ponía.
    """
    assert FACHADA in importa(PAQUETE / f"{puerta}.py"), (
        f"{puerta}.py no importa `operaciones`: está hablando con el núcleo por su cuenta")


def test_el_guardian_de_la_red_muerde(sin_red):
    """El propio candado de `conftest.py`, probado — un guardián que nadie prueba no guarda nada.

    Se usa una IP y no un nombre a propósito: con un nombre, la resolución DNS falla antes en una
    máquina sin red y el test pasaría en verde sin haber ejercitado el guardián ni una vez.
    """
    import socket

    from conftest import RedProhibida

    s = socket.socket()
    try:
        with pytest.raises(RedProhibida):
            s.connect(("93.184.216.34", 80))
    finally:
        s.close()

    # Y localhost sigue permitido: el MCP se prueba contra sí mismo.
    s2 = socket.socket()
    s2.settimeout(0.2)
    try:
        with pytest.raises(OSError) as e:
            s2.connect(("127.0.0.1", 65001))
        assert not isinstance(e.value, RedProhibida), "el guardián bloqueó localhost"
    finally:
        s2.close()


def test_las_dos_puertas_producen_el_MISMO_documento(tmp_path):
    """El mismo XML por la línea de comandos y por el MCP tiene que dar el mismo documento.

    Es la prueba de que las puertas son adaptadores y no dos programas parecidos. **Antes no lo
    daban**: el CLI construía `Libro` y `Comprobante` por su cuenta y serializaba a mano, así que su
    JSON salía SIN la clave `pe_ledger` —la que dice contra qué versión del estándar se escribió—
    mientras el MCP sí la ponía. El mismo comprobante, dos documentos distintos según la puerta.

    Se comparan enteros, no campo elegido: un documento que difiere en cualquier cosa ya no es el
    mismo documento.
    """
    import json

    from contaperu import cli
    from contaperu.servidor_mcp import mcp
    from util import XML

    fuente = XML / "20131312955-01-F001-123.xml"
    libro = {"ruc": "20131312955", "razon_social": "EMISOR DE PRUEBA S.A.C.",
             "periodo": "202601", "tipo": "venta"}

    # Puerta 1 — la línea de comandos, que escribe el documento a un archivo.
    destino = tmp_path / "cli.json"
    cli.main(["generar", "--tipo", "venta", "--ruc", libro["ruc"], "--razon", libro["razon_social"],
              "--periodo", libro["periodo"], "--salida", str(tmp_path / "s"),
              "--json", str(destino), str(fuente)])
    del_cli = json.loads(destino.read_text(encoding="utf-8"))

    # Puerta 2 — el MCP, que lo devuelve por el protocolo.
    bloques = asyncio.run(mcp.call_tool("leer_xml_ubl", {
        "contenido": fuente.read_text(encoding="utf-8"), "libro": libro}))
    del_mcp = json.loads(bloques[0].text)

    # Dos campos dependen legítimamente de la puerta y se normalizan antes de comparar:
    #  · `_lectura` — cuántos archivos ignoró: es el parte de la lectura, no del libro.
    #  · `archivo_nombre` — la PROCEDENCIA. El CLI recibe una ruta y sabe cómo se llamaba el
    #    archivo; el MCP recibe bytes por el protocolo y no puede saberlo. Que difieran es correcto;
    #    lo que no valdría es que difiriera cualquier otra cosa.
    del_mcp.pop("_lectura", None)
    assert del_cli["comprobantes"][0]["archivo_nombre"] != del_mcp["comprobantes"][0]["archivo_nombre"]
    for doc in (del_cli, del_mcp):
        for c in doc["comprobantes"]:
            c["archivo_nombre"] = ""

    assert del_cli == del_mcp, "las dos puertas ya no producen el mismo documento"
    assert del_cli["pe_ledger"], "el documento salió sin la versión del estándar"
