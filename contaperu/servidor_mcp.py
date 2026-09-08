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

from . import __version__, catalogos, detracciones, drivers, operaciones
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

Si algo no se puede hacer bien, la herramienta falla y dice por qué. No se inventa una cuenta,
ni un tipo de documento, ni una equivalencia del PCGE.
"""

mcp = FastMCP("contaperu", instructions=INSTRUCCIONES)


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


@mcp.resource("contaperu://drivers", mime_type="application/json")
def drivers_disponibles() -> str:
    """Los formatos de salida disponibles y qué libros genera cada uno."""
    return json.dumps({
        nombre: {"formatos": mod.FORMATOS,
                 "tipo": "archivo" if hasattr(mod, "construir") else "texto",
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
             correlativos: dict | None = None, incluir_observados: bool = False) -> dict:
    """Genera el archivo que espera un sistema contable, ya listo para importar.

    Drivers disponibles (ver el recurso `contaperu://drivers`):
      - `concar` — el Excel de asientos de 41 columnas. Vuelve en `contenido_base64`.
      - `sire`   — el TXT para reemplazar la propuesta del RVIE o del RCE en SUNAT. Vuelve en
                   `texto`, y su ZIP en `zip_base64`.
      - `csv`    — las líneas de diario en columnas, para cualquier otro destino.

    Antes de escribir nada comprueba que el asiento cuadre; si no cuadra, falla.
    """
    resultado = operaciones.exportar(documento, driver, configuracion, correlativos, incluir_observados)
    b64 = resultado.get("contenido_base64") or resultado.get("zip_base64") or ""
    pesa = len(b64) * 3 // 4          # el base64 abulta un tercio mas que los bytes
    if pesa > MAXIMO_ARCHIVO:
        raise DocumentoInvalido(
            f"El archivo pesa {pesa // (1024 * 1024)} MB y el tope por llamada es "
            f"{MAXIMO_ARCHIVO // (1024 * 1024)} MB. Divide el periodo en lotes mas pequenos.")
    return resultado


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
def adaptar_pcge2026(asiento: list[dict]) -> dict:
    """Adapta las cuentas de un asiento al Plan Contable General Empresarial 2026.

    **Aviso importante: la tabla de equivalencias está vacía.** Mientras no se publiquen con la
    cita del artículo de la resolución que las respalda, esta herramienta devuelve el asiento
    intacto y lo dice en su informe. Es deliberado: una equivalencia inventada produce estados
    financieros incorrectos en la contabilidad de quien confíe en ella.
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

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="contaperu-mcp",
        description="Servidor MCP del núcleo contable del Perú. Sin estado, sin red, sin base de datos.")
    ap.add_argument("--transporte", default="stdio", choices=["stdio", "http", "sse"],
                    help="stdio (por defecto) para un cliente local; http para servirlo en red")
    ap.add_argument("--host", default="127.0.0.1", help="solo con --transporte http")
    ap.add_argument("--puerto", type=int, default=8000, help="solo con --transporte http")
    ap.add_argument("--version", action="version", version=f"contaperu {__version__}")
    args = ap.parse_args(argv)

    if args.transporte in ("http", "sse"):
        mcp.settings.host = args.host
        mcp.settings.port = args.puerto
    transporte: Any = {"http": "streamable-http"}.get(args.transporte, args.transporte)
    mcp.run(transport=transporte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
