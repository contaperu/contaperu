"""Servidor MCP: el núcleo contable como herramientas para un agente de IA.

Un modelo de lenguaje sabe leer una factura en PDF; lo que no sabe es si el asiento que
propone cuadra, qué sub-diario le toca, cómo se provisiona una detracción o qué columnas
espera un CONCAR. Esa parte tiene que ser determinista, y es la que hay aquí.

**Sin estado, y a propósito.** No hay base de datos, ni sesión, ni archivos, ni una sola
llamada a la red. Cada herramienta recibe todo lo que necesita y devuelve todo lo que produce,
así que dos llamadas iguales dan el mismo resultado y ninguna deja rastro. Se puede levantar,
usar y tirar.

Se arranca así:

    contaperu-mcp                      # por entrada y salida estándar (Claude Desktop, IDEs)
    contaperu-mcp --transporte http    # por HTTP, para servirlo a varios

o en Docker, sin instalar nada:

    docker run -i --rm contaperu-mcp

El módulo se llama `servidor_mcp` y no `mcp` para que no se confunda con el SDK del protocolo,
que es un paquete de primer nivel con ese mismo nombre.

**Las herramientas y los recursos no se escriben aquí: se derivan de `api.OPERACIONES`** (6.2.0). Hasta la
6.1.0 cada uno era una función con su firma escrita a mano, y de ahí salió la única divergencia contable que
ha tenido este servidor: tres herramientas suponiendo CONCAR porque el MCP escribía sus parámetros en
anotaciones de Python mientras la puerta HTTP los derivaba de la tabla. **Dos fuentes para un mismo contrato
divergen solas**, y lo que las ataba era un test; ahora hay una sola y el test sobra como red.

**Y desde la 16.0 este servidor es una aplicación de la base MCP**, como lo sería el de cualquiera que la integre:
`mcp = crear_servidor()`, con el catálogo del motor (`agentes.DEL_MOTOR`) proyectado por `agentes.servidor`, que es
donde viven ahora el envoltorio de los adjuntos, el «problem details» de un error, el tipo de cada parámetro y el
arranque. Aquí quedan la instancia que sirve `contaperu-mcp`, su línea de comandos y los nombres que se importaban de
este módulo, reexportados: `INTEGRAR.md` los enseña y su test los fija.
"""
from __future__ import annotations

import argparse
import sys

from .. import api
from ..agentes import PERFILES, CatalogoInvalido
from ..agentes.servidor import SOLO_LECTURA, contesta, crear_servidor, seguridad, servir
from .comun import LOCALES, MAXIMO_ARCHIVO

__all__ = ["INSTRUCCIONES", "LOCALES", "MAXIMO_ARCHIVO", "REGLAS", "SOLO_LECTURA", "contesta", "main", "mcp",
           "seguridad"]

# Lo que este servidor le dice al agente: la presentación, el camino de SUS herramientas y las reglas del
# dominio. **Vive en `api.instrucciones` desde la 3.4.0**, y `REGLAS` está aparte porque quien monta su
# propia capa de agente encima del motor se trae las reglas y NO el camino: sus herramientas son otras, y
# prometerle a un modelo un `leer_xml_ubl` que no existe es peor que no decirle nada. Se reexporta aquí
# —está en el `__all__`— para que el import que `INTEGRAR.md` enseña siga valiendo.
INSTRUCCIONES = api.INSTRUCCIONES
REGLAS = api.REGLAS

# El servidor abierto: las herramientas del perfil público, sin prefijo, con sus recursos. Se presenta con la versión de
# contaperu y no con la del SDK (`test_el_servidor_se_presenta_con_SU_version`).
mcp = crear_servidor()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="contaperu-mcp",
        description="Servidor MCP del núcleo contable del Perú. Sin estado, sin red, sin base de datos.")
    # `sse` estuvo aqui hasta la 1.3.0 y se retiro: quedaba fuera del bloque que pone `--dominio`, asi que lo
    # ignoraba en silencio y acumulaba sesiones; nunca se documento ni se probo, y el transporte esta obsoleto en la
    # especificacion desde 2025-03-26. El que sirve en red es `http`, que es streamable-http.
    ap.add_argument("--transporte", default="stdio", choices=["stdio", "http"],
                    help="stdio (por defecto) para un cliente local; http para servirlo en red")
    ap.add_argument("--host", default="127.0.0.1", help="solo con --transporte http")
    ap.add_argument("--puerto", type=int, default=8000, help="solo con --transporte http")
    ap.add_argument("--dominio", action="append", default=[], metavar="NOMBRE",
                    help="nombre publico por el que se sirve, si va detras de un proxy "
                         "(repetible). Sin esto solo se atienden peticiones a localhost")
    # Las perillas (16.0): qué parte del motor se publica. Por defecto, lo de siempre: todo lo del perfil público.
    ap.add_argument("--perfil", default="publico", choices=PERFILES,
                    help="publico (por defecto), lo que sirve el servidor abierto; integrador suma lo que no sale en él")
    ap.add_argument("--grupo", action="append", default=[], metavar="GRUPO",
                    help="publica solo las herramientas de ese grupo (repetible): leer, validar, asentar, informes, "
                         "tesoreria, pcge, catalogos")
    ap.add_argument("--herramienta", action="append", default=[], metavar="NOMBRE",
                    help="publica solo esa herramienta (repetible)")
    ap.add_argument("--solo-lectura", action="store_true",
                    help="deja fuera lo que escribe (hoy ninguna herramienta del motor escribe)")
    ap.add_argument("--version", action="version", version=f"contaperu {api.__version__}")
    args = ap.parse_args(argv)
    servidor = mcp
    if args.perfil != "publico" or args.grupo or args.herramienta or args.solo_lectura:
        try:
            servidor = crear_servidor(perfil=args.perfil, grupos=args.grupo or None,
                                      herramientas=args.herramienta or None, solo_lectura=args.solo_lectura)
        except CatalogoInvalido as error:
            ap.error("; ".join(error.faltas))
    servir(servidor, transporte=args.transporte, host=args.host, puerto=args.puerto, dominios=args.dominio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
