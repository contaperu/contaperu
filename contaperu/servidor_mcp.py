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
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent

from . import __version__, catalogos, detracciones, drivers, operaciones, pcge
from .operaciones import DocumentoInvalido


def _ruta_del_esquema() -> pathlib.Path:
    """Instalado, el esquema viaja dentro del paquete; en el repositorio vive en la raiz."""
    aqui = pathlib.Path(__file__).resolve().parent
    for candidata in (aqui / "estandar" / "pe-ledger.schema.json",
                      aqui.parent / "estandar" / "pe-ledger.schema.json"):
        if candidata.exists():
            return candidata
    raise FileNotFoundError("No encuentro pe-ledger.schema.json")


ESQUEMA = _ruta_del_esquema()

# Tope del archivo que se devuelve por el protocolo. Un Excel de un mes normal pesa unas
# decenas de kilobytes; varios megas casi siempre significan que había que partir el lote.
MAXIMO_ARCHIVO = 4 * 1024 * 1024


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

INSTRUCCIONES = """\
Núcleo contable del Perú. Convierte comprobantes de SUNAT en asientos y en los archivos que
importan los sistemas contables peruanos. Todo es determinista y sin estado.

El camino normal:
  1. `leer_xml_ubl` o `leer_propuesta_sire` si tienes archivos de SUNAT; si ya tienes los datos
     estructurados, arma tú el documento `pe-ledger` (mira el recurso del esquema).
  2. `validar_comprobantes` para ver qué observaciones hay antes de nada.
  3. `generar_asiento` para las líneas de diario, o `exportar` directamente al formato del ERP.

Reglas que conviene tener claras antes de armar un documento:
  - Los importes van SIEMPRE en positivo. Una nota de crédito se marca con `tipo_cp: "07"`,
    nunca con importes negativos.
  - `tipo_cp` es el código de la Tabla 10 de SUNAT, no la sigla del sistema contable.
  - La `retencion` de un comprobante es la de renta de 4ta de un recibo por honorarios. La
    retención del IGV del 3 % NO es una detracción y no entra en el asiento.
  - Cada contribuyente tiene su plan de cuentas y sus sub-diarios: van en `configuracion`.
    `configuracion_por_defecto` devuelve un punto de partida razonable, no la verdad de nadie.
  - Antes de inventar una cuenta contable, `buscar_cuenta_pcge`. Que una cuenta no esté en el PCGE
    no la invalida —las divisionarias las abre cada empresa—, pero conviene saberlo.

Si algo no se puede hacer bien, la herramienta falla y dice por qué. No se inventa una cuenta,
ni un tipo de documento, ni una equivalencia del PCGE.
"""

mcp = FastMCP("contaperu", instructions=INSTRUCCIONES)
# FastMCP no deja poner la version en su constructor y, sin esto, el servidor se presenta en el
# saludo con la version del SDK: «contaperu 1.30.0», que no es ninguna version de contaperu.
mcp._mcp_server.version = __version__


# --- recursos: lo que conviene leer antes de llamar a nada -------------------------

@mcp.resource("contaperu://estandar/pe-ledger", mime_type="application/schema+json")
def esquema_pe_ledger() -> str:
    """El esquema JSON del documento contable `pe-ledger`, con cada campo documentado."""
    return ESQUEMA.read_text(encoding="utf-8")


@mcp.resource("contaperu://catalogos/sunat", mime_type="application/json")
def catalogos_sunat() -> str:
    """Los catálogos de SUNAT que entiende el motor: tipos de comprobante, tipos de documento
    de identidad y monedas."""
    return json.dumps({
        "tipos_comprobante": catalogos.TIPOS_CP,
        "tipos_documento_identidad": catalogos.TIPOS_DOC_IDENTIDAD,
        "monedas": sorted(catalogos.MONEDAS),
        "notas": sorted(catalogos.NOTAS),
        "fuera_del_registro_sunat": sorted(catalogos.FUERA_DEL_REGISTRO_SUNAT),
    }, ensure_ascii=False, indent=1)


@mcp.resource("contaperu://catalogos/pcge2026", mime_type="application/json")
def catalogo_pcge2026() -> str:
    """El catálogo oficial de cuentas del Plan Contable General Empresarial 2026: cada cuenta con
    su nombre y la página de la norma que lo dice.

    Sirve para dos cosas: poner el nombre de una cuenta, y comprobar que la cuenta que se va a
    escribir existe. **Que una cuenta no esté aquí no la invalida**: el PCGE llega a cinco dígitos
    y cada empresa abre sus divisionarias debajo — `603201` es válida y no aparece en la norma.
    """
    return json.dumps(pcge.catalogo.cargar(), ensure_ascii=False, indent=1)


@mcp.resource("contaperu://drivers", mime_type="application/json")
def drivers_disponibles() -> str:
    """Los formatos de salida disponibles y qué libros genera cada uno."""
    return json.dumps({
        nombre: {"formatos": mod.FORMATOS,
                 "tipo": "texto" if drivers.contrato.forma(mod) == "linea" else "archivo",
                 "forma": drivers.contrato.forma(mod),
                 "descripcion": (mod.__doc__ or "").strip().splitlines()[0]}
        for nombre, mod in drivers.DRIVERS.items()
    }, ensure_ascii=False, indent=1)


# --- herramientas ------------------------------------------------------------------

@mcp.tool()
def configuracion_por_defecto() -> dict:
    """La configuración contable de partida: cuentas, sub-diarios, equivalencias de tipos de
    comprobante y la tabla de detracciones.

    Es un punto de partida razonable, no la verdad de ningún contribuyente: el plan de cuentas
    y los sub-diarios los decide cada empresa. Cópiala, cámbiale lo que toque y pásala como
    `configuracion` en las demás herramientas.
    """
    return operaciones.configuracion()


@mcp.tool()
def validar_comprobantes(documento: dict, configuracion: dict | None = None) -> dict:
    """Revisa los comprobantes de un documento `pe-ledger` y devuelve el mismo documento con
    `estado` y `observaciones` puestos en cada uno.

    Comprueba lo que se puede comprobar sin salir a ningún sitio: que el RUC sea un RUC, que el
    IGV cuadre con la base, que el total sea la suma de sus partes, que la fecha caiga en el
    periodo, que no haya duplicados. Las observaciones de nivel `error` bloquean la exportación;
    las de nivel `aviso` no.

    También descarta las detracciones cuyo código no está en la tabla del contribuyente, que es
    de donde salen los códigos inventados cuando una IA confunde la retención del IGV con una
    detracción.
    """
    return operaciones.revisar(documento, configuracion)


@mcp.tool()
def validar_partida_doble(asiento: list[dict]) -> dict:
    """Comprueba que la suma del Debe sea exactamente igual a la del Haber.

    Sin tolerancia: un céntimo de diferencia es un asiento mal armado. Devuelve las dos sumas,
    la diferencia y cuántas líneas no dicen si son Debe o Haber.
    """
    return operaciones.cuadrar(asiento)


@mcp.tool()
def generar_asiento(documento: dict, configuracion: dict | None = None,
                    correlativos: dict | None = None, incluir_observados: bool = False) -> dict:
    """Convierte los comprobantes en líneas de diario, sin el formato de ningún sistema.

    Devuelve el bloque `asiento` del estándar: cuenta, debe o haber, importe, moneda, glosa,
    centro de costo y el documento que lo respalda. Es lo que sirve para revisar el asiento, o
    para cargarlo en un sistema que no tenga driver todavía.

    `correlativos` dice por qué número empieza cada sub-diario ({"11": 1}); si no se pasa,
    empieza en 1. Con `incluir_observados` se genera aunque haya comprobantes con errores —
    útil para ver qué saldría, arriesgado para presentar.
    """
    return operaciones.generar_asiento(documento, configuracion, correlativos, incluir_observados)


@mcp.tool()
def exportar(documento: dict, driver: str = "concar", configuracion: dict | None = None,
             correlativos: dict | None = None, incluir_observados: bool = False) -> CallToolResult:
    """Genera el archivo que espera un sistema contable, ya listo para importar.

    Devuelve dos cosas: un resumen en JSON (nombre del archivo, filas, debe y haber) y **el
    archivo adjunto**, para guardarlo tal cual.

    Drivers disponibles (ver el recurso `contaperu://drivers`):
      - `concar` — el Excel de asientos de 41 columnas, adjunto como `.xlsx`.
      - `sire`   — el TXT para reemplazar la propuesta del RVIE o del RCE en SUNAT: el contenido
                   va en `texto` y el ZIP que sube a SUNAT, adjunto.
      - `csv`    — las líneas de diario en columnas, en `texto` y también adjunto.

    Antes de escribir nada comprueba que el asiento cuadre; si no cuadra, falla.
    """
    resultado = operaciones.exportar(documento, driver, configuracion, correlativos, incluir_observados)
    # Los bytes salen del resumen y entran en los adjuntos: repetirlos en el JSON seria mandar
    # el archivo dos veces, y la copia en texto es justo la que el cliente no sabe guardar.
    contenido = resultado.pop("contenido_base64", "") or ""
    zip_b64 = resultado.pop("zip_base64", "") or ""
    pesa = (len(contenido) + len(zip_b64)) * 3 // 4   # el base64 abulta un tercio mas que los bytes
    if pesa > MAXIMO_ARCHIVO:
        raise DocumentoInvalido(
            f"El archivo pesa {pesa // (1024 * 1024)} MB y el tope por llamada es "
            f"{MAXIMO_ARCHIVO // (1024 * 1024)} MB. Divide el periodo en lotes mas pequenos.")

    adjuntos = []
    if contenido:
        adjuntos.append(_adjunto(resultado["archivo"], contenido,
                                 resultado.get("content_type") or "application/octet-stream"))
    if zip_b64:
        adjuntos.append(_adjunto(resultado["archivo_zip"], zip_b64, "application/zip"))
    resumen = TextContent(type="text",
                          text=json.dumps(resultado, ensure_ascii=False, indent=1))
    return CallToolResult(content=[resumen, *adjuntos])


@mcp.tool()
def leer_xml_ubl(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """Lee el XML UBL 2.1 de la factura electrónica de SUNAT y devuelve un documento `pe-ledger`.

    Acepta un XML suelto como texto, o un ZIP en base64 con varios dentro (`es_base64: true`).
    Descarta lo que no es un comprobante — las constancias de recepción (CDR) y las hojas de
    estilo— y avisa de lo que no pudo leer. `libro` es la cabecera: RUC, periodo y si son
    ventas o compras.
    """
    return operaciones.leer_xml(contenido, libro, es_base64)


@mcp.tool()
def leer_propuesta_sire(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """Lee el TXT de la propuesta que SUNAT entrega en el SIRE y devuelve un documento
    `pe-ledger`.

    Es lo que el contribuyente descarga de su SIRE con lo que SUNAT cree que compró o vendió;
    a partir de ahí se compara con la realidad y se corrige. Acepta el TXT como texto o el ZIP
    tal cual lo entrega SUNAT (`es_base64: true`).
    """
    return operaciones.leer_propuesta_sire(contenido, libro, es_base64)


@mcp.tool()
def buscar_cuenta_pcge(texto: str = "", codigo: str = "") -> dict:
    """Busca una cuenta en el Plan Contable General Empresarial 2026, por nombre o por código.

    Con `texto` devuelve las cuentas cuyo nombre lo contiene (sin distinguir tildes ni mayúsculas).
    Con `codigo` devuelve esa cuenta y, si no está en la norma, **la cuenta madre que la gobierna**:
    de `603201` sale `6032 Suministros`, porque el PCGE llega a cinco dígitos y las divisionarias
    las abre cada empresa. Un código que no resuelve ni por su elemento está mal escrito.

    Úsala antes de decidir la `cuenta_contable` de un comprobante: es la diferencia entre elegir
    una cuenta que existe y proponer uno que suena bien.
    """
    norma = pcge.catalogo.cargar()
    salida: dict = {"version": norma.get("version", ""), "fuente": norma.get("fuente", "")}
    if codigo:
        salida["cuenta"] = pcge.resolver(codigo)
    if texto:
        salida["encontradas"] = pcge.buscar(texto)
    if not codigo and not texto:
        raise DocumentoInvalido("Dime qué buscar: un `texto` del nombre o un `codigo` de cuenta.")
    return salida


@mcp.tool()
def adaptar_pcge2026(asiento: list[dict]) -> dict:
    """Adapta las cuentas de un asiento al Plan Contable General Empresarial 2026.

    **La tabla de equivalencias está vacía, y hoy eso es lo correcto**: este proyecto nace en 2026
    y trabaja con el PCGE 2026 desde el primer asiento, así que no hay plan anterior del que
    traducir. La herramienta existe como riel para el día que una modificatoria sustituya cuentas;
    mientras tanto devuelve el asiento intacto y lo dice en su informe (`sin_tabla`).

    Cuando llegue esa modificatoria, cada equivalencia entrará **con la cita del artículo que la
    respalda** —el cargador se niega a leer un mapeo sin ella—, porque una equivalencia inventada
    produce estados financieros incorrectos en la contabilidad de quien confíe en esto.

    Para saber si una cuenta existe o cómo se llama, la herramienta es `buscar_cuenta_pcge`; esta
    no es esa.
    """
    return operaciones.adaptar_pcge(asiento)


@mcp.tool()
def normalizar_detracciones(documento: dict, configuracion: dict | None = None) -> dict:
    """Contrasta la detracción de cada comprobante con la tabla del contribuyente y deja en
    blanco la que no reconozca.

    Sirve sobre todo después de leer comprobantes con un modelo de lenguaje: la confusión más
    común es tomar la **retención del IGV** (el 3 % que retiene un agente de retención cuando la
    factura pasa de S/ 700, y que no toca el registro de compras) por una detracción.
    """
    comprobantes = operaciones.comprobantes_de(documento)
    conf = operaciones.configuracion(configuracion)
    limpiadas = detracciones.normalizar(comprobantes, conf)
    salida = operaciones.documento(operaciones.libro_de(documento), comprobantes)
    salida["_detracciones"] = {
        "revisadas": sum(1 for c in comprobantes if c.detraccion) + len(limpiadas),
        "descartadas": len(limpiadas),
        "codigos_reconocidos": sorted(detracciones.codigos_de(conf)),
    }
    return salida


# --- arranque ----------------------------------------------------------------------

# Nombres por los que un servidor local se deja llamar. El SDK los pone solo cuando se escucha
# en 127.0.0.1; aqui se mantienen tambien al escuchar en 0.0.0.0, que es lo normal dentro de un
# contenedor, para que `curl localhost:8000/mcp` siga sirviendo para comprobar que esta vivo.
LOCALES = ["127.0.0.1:*", "localhost:*", "[::1]:*"]


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
        allowed_hosts=[*LOCALES, *dominios, *(f"{d}:*" for d in dominios)],
        allowed_origins=[f"http://{h}" for h in LOCALES] + [f"https://{d}" for d in dominios],
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="contaperu-mcp",
        description="Servidor MCP del núcleo contable del Perú. Sin estado, sin red, sin base de datos.")
    ap.add_argument("--transporte", default="stdio", choices=["stdio", "http", "sse"],
                    help="stdio (por defecto) para un cliente local; http para servirlo en red")
    ap.add_argument("--host", default="127.0.0.1", help="solo con --transporte http")
    ap.add_argument("--puerto", type=int, default=8000, help="solo con --transporte http")
    ap.add_argument("--dominio", action="append", default=[], metavar="NOMBRE",
                    help="nombre publico por el que se sirve, si va detras de un proxy "
                         "(repetible). Sin esto solo se atienden peticiones a localhost")
    ap.add_argument("--version", action="version", version=f"contaperu {__version__}")
    args = ap.parse_args(argv)

    if args.transporte in ("http", "sse"):
        mcp.settings.host = args.host
        mcp.settings.port = args.puerto
    if args.transporte == "http":
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
    transporte: Any = {"http": "streamable-http"}.get(args.transporte, args.transporte)
    mcp.run(transport=transporte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
