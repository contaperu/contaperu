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

Lo que sigue siendo de esta puerta, y por eso sigue escrito: el envoltorio que convierte un archivo en
adjunto, el que dice un error como un «problem details», el tipo Python con que se describe cada parámetro
—que es lo que el SDK publica como `inputSchema`— y el arranque. Los textos que lee el agente viven en
`api.textos`.
"""
from __future__ import annotations

import argparse
import functools
import inspect
import json
import sys
from typing import Annotated, Any, Callable, get_type_hints

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field

from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent, ToolAnnotations

from .. import _datos, api
from ..api import textos
from .comun import LOCALES, MAXIMO_ARCHIVO, hosts_permitidos, origenes_permitidos, peso_de_base64

__all__ = ["INSTRUCCIONES", "LOCALES", "MAXIMO_ARCHIVO", "REGLAS", "SOLO_LECTURA", "contesta", "main", "mcp",
           "seguridad"]


def _adjunto(nombre: str, b64: str, mime: str) -> EmbeddedResource:
    """Devuelve un archivo COMO ARCHIVO, no como una tira de texto dentro de un campo.

    El protocolo habla JSON y un `.xlsx` es un ZIP: no cabe tal cual, hay que meterlo en base64.
    Pero eso no es «otro formato» —al decodificarlo vuelve el mismo archivo, byte a byte—, y la
    diferencia entre que el cliente lo ofrezca para guardar o lo enseñe como un muro de letras
    está en el envoltorio: un recurso incrustado con su `blob` y su `mimeType`, en vez de un
    campo `contenido_base64` que nadie sabe reconocer.
    """
    return EmbeddedResource(
        type="resource",
        resource=BlobResourceContents(
            uri=f"contaperu://salida/{nombre}",
            mimeType=mime.split(";")[0].strip() or "application/octet-stream",
            blob=b64,
        ),
    )


def _dicho(valor: Any) -> CallToolResult:
    """Lo que devuelve una operación, como el JSON que el agente lee."""
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(valor, ensure_ascii=False, indent=1))])


def _rechazo(error: BaseException) -> CallToolResult:
    """Un rechazo dicho como lo dice la puerta HTTP: un «problem details» del RFC 9457, con su `clave` estable.

    Es la misma `api.problema` que responde por HTTP, y por dos motivos. El primero es que una `clave` se
    puede ramificar y una frase no: un cliente que recibe «Error executing tool exportar: 3 comprobantes
    tienen observaciones que bloquean» no sabe distinguir eso de que el motor haya reventado. El segundo
    pesa más: un error que NO es del motor puede llevar pegada una ruta o un dato interno, y `api.problema`
    lo enmascara. Sin esto, lo que la puerta HTTP se cuida de no enseñar salía entero por la puerta MCP,
    que además es la que está publicada sin autenticación.
    """
    return CallToolResult(isError=True, content=[
        TextContent(type="text", text=json.dumps(api.problema(error), ensure_ascii=False, indent=1))])


def contesta(funcion: Callable[..., Any]) -> Callable[..., CallToolResult]:
    """Hace que una herramienta conteste con esa forma, pase lo que pase.

    La firma se conserva tal cual —es lo que el agente ve como `inputSchema`— y solo se cambia lo que
    devuelve, porque `CallToolResult` es la anotación con la que el SDK entrega la respuesta sin tocarla.
    Que la firma siga intacta después de decorar no es confianza: lo comprueba
    `test_la_puerta_mcp_recibe_lo_mismo_que_la_http`, que las compara contra `api.OPERACIONES`.
    """
    @functools.wraps(funcion)
    def herramienta(*posicionales: Any, **argumentos: Any) -> CallToolResult:
        try:
            resultado = funcion(*posicionales, **argumentos)
        except Exception as error:      # cualquiera se dice igual: `api.problema` decide cuánto se enseña
            return _rechazo(error)
        return resultado if isinstance(resultado, CallToolResult) else _dicho(resultado)

    # La firma se entrega ya resuelta. Este módulo aplaza las anotaciones (`from __future__ import annotations`),
    # así que `inspect.signature` las devuelve como texto, y un alias declarado aquí —`FECHA`— deja de resolverse
    # al mirarlas desde el envoltorio. Con las pistas resueltas, el SDK ve exactamente los mismos tipos que veía
    # antes de decorar.
    firma = inspect.signature(funcion)
    pistas = get_type_hints(funcion, include_extras=True)
    parametros = [p.replace(annotation=pistas.get(p.name, p.annotation)) for p in firma.parameters.values()]
    herramienta.__signature__ = firma.replace(parameters=parametros, return_annotation=CallToolResult)
    return herramienta


# Lo que este servidor le dice al agente: la presentación, el camino de SUS herramientas y las reglas del
# dominio. **Vive en `api.instrucciones` desde la 3.4.0**, y `REGLAS` está aparte porque quien monta su
# propia capa de agente encima del motor se trae las reglas y NO el camino: sus herramientas son otras, y
# prometerle a un modelo un `leer_xml_ubl` que no existe es peor que no decirle nada. Se reexporta aquí
# —está en el `__all__`— para que el import que `INTEGRAR.md` enseña siga valiendo.
INSTRUCCIONES = api.INSTRUCCIONES
REGLAS = api.REGLAS

mcp = FastMCP("contaperu", instructions=INSTRUCCIONES)
# FastMCP no deja poner la version en su constructor y, sin esto, el servidor se presenta en el
# saludo con la version del SDK: «contaperu 1.30.0», que no es ninguna version de contaperu.
mcp._mcp_server.version = api.__version__

# Hito 0.2: cada herramienta se anuncia de solo lectura y sin salir a ningún sitio —no guarda nada, no toca el disco ni
# la red—, así que un cliente puede llamarla sin pedir confirmación por un efecto que no tiene.
SOLO_LECTURA = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

# Una fecha del calendario, no una cadena cualquiera: `api/tabla.py` ya lo declara asi para la puerta HTTP y
# el contrato, y las dos puertas describen lo que reciben con las mismas palabras.
FECHA = Annotated[str | None, Field(json_schema_extra={"format": "date"})]


# --- de la tabla a las herramientas y los recursos ---------------------------------
#
# Lo único que esta puerta declara de cada parámetro es su TIPO PYTHON, porque es de lo que el SDK deriva el
# `inputSchema` que ve el agente. El nombre, si es obligatorio y su valor por defecto NO se declaran: salen de
# la firma de la operación en `contaperu.api`, que es la misma de la que sale el esquema de la puerta HTTP.
# Así la pregunta «¿reciben lo mismo las dos puertas?» deja de tener respuesta posible.
#
# Un tipo opcional se deriva: con valor por defecto `None` es `T | None`; con cualquier otro —`False`, `""`—
# es `T` a secas, que es lo que estaba escrito a mano en las 14 firmas.
TIPOS: dict[str, Any] = {
    "documento": dict,
    "contenido": str,
    "libro": dict,
    "es_base64": bool,
    "driver": str,
    "configuracion": dict,
    "imputacion": dict,
    "correlativos": dict,
    "claves_previas": list[list[str | int | None]],
    "incluir_observados": bool,
    "lineas": list[dict],
    "agrupar_por": str,
    "texto": str,
    "codigo": str,
    # `fecha` ya trae su `| None` dentro del alias, con el `format: date` que la tabla declara para el contrato.
    "fecha": FECHA,
}

# El nombre con que un parámetro sale por esta puerta, cuando no es el de la api. `lineas` son las líneas del
# asiento, y para un agente «asiento» dice de qué está hablando; la api lo llama por lo que es. Vivía en una
# constante de `tests/test_servidor_mcp.py`, que es un sitio raro para un contrato.
RENOMBRA = {"lineas": "asiento"}

# Los recursos que no sirven JSON. Un esquema se anuncia como esquema para que un cliente sepa que puede
# validar con él.
MIMES = {
    "contaperu://estandar/open-accounting": "application/schema+json",
    "contaperu://esquemas/diagnostico": "application/schema+json",
}

# El nombre de un recurso cuando no es el de su operación: los dos que se nombraron por lo que son y no por la
# función que los devuelve, y el de `drivers`, que tiene que decirlo porque su nombre choca con la herramienta.
NOMBRES_DE_RECURSO = {
    "contaperu://catalogos/pcge2026": "catalogo_pcge2026",
    "contaperu://configuracion": "configuracion_declarada",
    "contaperu://drivers": "drivers_disponibles",
}

# De qué claves del resultado sale un archivo: la que lleva los bytes en base64, la que lleva su nombre, y su
# tipo —el de una clave del resultado, o fijo—. Es lo que antes preguntaba `if op.nombre == "exportar"` en las
# dos puertas.
ARCHIVOS = (("contenido_base64", "archivo", "content_type"),
            ("zip_base64", "archivo_zip", "application/zip"))


def _firma_de(operacion: api.Operacion) -> inspect.Signature:
    """La firma con que esta puerta publica una operación: sus nombres y defaults, con el tipo de `TIPOS`."""
    parametros = []
    for p in inspect.signature(operacion.funcion).parameters.values():
        tipo = TIPOS[p.name]
        if p.default is None and tipo is not FECHA:
            tipo = tipo | None
        parametros.append(inspect.Parameter(RENOMBRA.get(p.name, p.name), inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                            default=p.default, annotation=tipo))
    return inspect.Signature(parametros, return_annotation=CallToolResult)


def _llamada(operacion: api.Operacion) -> Callable[..., Any]:
    """La función que llama a la operación por la FACHADA, deshaciendo los renombres de esta puerta.

    Se resuelve `getattr(api, …)` en cada llamada y no se guarda la función: `op.funcion` apunta al módulo
    interno `api.operaciones`, y una puerta habla con `api` y nada más (`tests/test_frontera.py`). Además es
    lo que hacían las catorce escritas a mano, así que quien sustituya una operación de la fachada —la
    batería lo hace— sigue viendo el mismo efecto por esta puerta.
    """
    nombres = tuple(inspect.signature(operacion.funcion).parameters)

    def llamar(**argumentos: Any) -> Any:
        return getattr(api, operacion.nombre)(**{p: argumentos[RENOMBRA.get(p, p)] for p in nombres})
    return llamar


def _con_adjuntos(resultado: dict) -> CallToolResult:
    """El resumen en JSON y, aparte, los archivos como archivos. Rechaza por encima del tope de la llamada."""
    bytes_ = [(resultado.pop(clave, "") or "", nombre, tipo) for clave, nombre, tipo in ARCHIVOS]
    pesa = peso_de_base64(*(b for b, _, _ in bytes_))
    if pesa > MAXIMO_ARCHIVO:
        raise api.DocumentoInvalido(
            f"El archivo pesa {pesa // (1024 * 1024)} MB y el tope por llamada es "
            f"{MAXIMO_ARCHIVO // (1024 * 1024)} MB. Divide el periodo en lotes mas pequenos.")
    adjuntos = [_adjunto(resultado[nombre], b64, resultado.get(tipo) or tipo or "application/octet-stream")
                for b64, nombre, tipo in bytes_ if b64]
    resumen = TextContent(type="text", text=json.dumps(resultado, ensure_ascii=False, indent=1))
    return CallToolResult(content=[resumen, *adjuntos])


def _herramienta_de(operacion: api.Operacion) -> Callable[..., CallToolResult]:
    """Una operación como herramienta: su firma, su texto y, si devuelve un archivo, su adjunto."""
    llamar = _llamada(operacion)

    def herramienta(**argumentos: Any) -> Any:
        resultado = llamar(**argumentos)
        return _con_adjuntos(resultado) if operacion.archivo else resultado

    herramienta.__name__ = operacion.herramienta
    herramienta.__doc__ = textos.PARA_HERRAMIENTA[operacion.herramienta]
    firma = _firma_de(operacion)
    herramienta.__signature__ = firma
    herramienta.__annotations__ = {p.name: p.annotation for p in firma.parameters.values()}
    herramienta.__annotations__["return"] = CallToolResult
    return contesta(herramienta)


def _recurso_de(operacion: api.Operacion) -> Callable[[], str]:
    """Una operación sin argumentos como recurso. El esquema del estándar sale tal cual: son sus bytes."""
    if operacion.recurso == "contaperu://estandar/open-accounting":
        def recurso() -> str:
            return _datos.texto_del_esquema()
    else:
        def recurso() -> str:
            return json.dumps(getattr(api, operacion.nombre)(), ensure_ascii=False, indent=1)

    recurso.__name__ = NOMBRES_DE_RECURSO.get(operacion.recurso, operacion.nombre)
    recurso.__doc__ = textos.PARA_RECURSO[operacion.recurso]
    return recurso


for _op in api.OPERACIONES:
    if _op.recurso:
        mcp.resource(_op.recurso, mime_type=MIMES.get(_op.recurso, "application/json"),
                     name=NOMBRES_DE_RECURSO.get(_op.recurso))(_recurso_de(_op))
    if _op.herramienta:
        mcp.tool(annotations=SOLO_LECTURA)(_herramienta_de(_op))


# --- arranque ----------------------------------------------------------------------

def seguridad(dominios: list[str]) -> TransportSecuritySettings:
    """Los nombres de host por los que este servidor acepta que le llamen.

    El SDK rechaza con un 421 cualquier peticion cuyo `Host` no reconozca. Es la defensa
    contra el *DNS rebinding*: una pagina cualquiera hace que el navegador de la victima
    resuelva un dominio suyo a la direccion del servidor y le hable como si fuera del mismo
    origen. Por eso publicarlo detras de un proxy obliga a decir el nombre publico: sin
    `--dominio`, el servidor solo se reconoce a si mismo como «localhost» y desde fuera todo
    da 421 aunque el proxy y el certificado esten perfectos.
    """
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts_permitidos(dominios),
        allowed_origins=origenes_permitidos(dominios),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="contaperu-mcp",
        description="Servidor MCP del núcleo contable del Perú. Sin estado, sin red, sin base de datos.")
    # `sse` estuvo aqui hasta la 1.3.0 y se retiro: quedaba fuera del bloque de abajo, asi que ignoraba `--dominio`
    # en silencio y acumulaba sesiones; nunca se documento ni se probo, y el transporte esta obsoleto en la
    # especificacion desde 2025-03-26. El que sirve en red es `http`, que es streamable-http.
    ap.add_argument("--transporte", default="stdio", choices=["stdio", "http"],
                    help="stdio (por defecto) para un cliente local; http para servirlo en red")
    ap.add_argument("--host", default="127.0.0.1", help="solo con --transporte http")
    ap.add_argument("--puerto", type=int, default=8000, help="solo con --transporte http")
    ap.add_argument("--dominio", action="append", default=[], metavar="NOMBRE",
                    help="nombre publico por el que se sirve, si va detras de un proxy "
                         "(repetible). Sin esto solo se atienden peticiones a localhost")
    ap.add_argument("--version", action="version", version=f"contaperu {api.__version__}")
    args = ap.parse_args(argv)

    if args.transporte == "http":
        mcp.settings.host = args.host
        mcp.settings.port = args.puerto
        # Sin sesiones: cada peticion se atiende sola y el servidor no guarda nada entre una y
        # otra, que es lo que este modulo dice de si mismo. Ademas quita de en medio el unico
        # recurso que un desconocido podria ir acumulando en un servidor sin autenticacion:
        # sesiones abiertas (el SDK admite 10.000 y las mantiene media hora).
        mcp.settings.stateless_http = True
        mcp.settings.transport_security = seguridad(args.dominio)
        if not args.dominio and args.host not in ("127.0.0.1", "localhost", "::1"):
            print("aviso: sin --dominio solo se atienden peticiones cuyo Host sea localhost; "
                  "desde fuera responde 421. Al publicarlo detras de un proxy hay que declarar "
                  "el nombre publico:  --dominio contaperu.ejemplo.com", file=sys.stderr)
    transporte: Any = "streamable-http" if args.transporte == "http" else args.transporte
    mcp.run(transport=transporte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
