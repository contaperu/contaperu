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
que es un paquete de primer nivel con ese mismo nombre. Cada herramienta y cada recurso es una operación de la api
(`api.OPERACIONES`), con el nombre de siempre.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent, ToolAnnotations

from .. import _datos, api
from .comun import LOCALES, MAXIMO_ARCHIVO, hosts_permitidos, origenes_permitidos, peso_de_base64

__all__ = ["INSTRUCCIONES", "LOCALES", "MAXIMO_ARCHIVO", "SOLO_LECTURA", "main", "mcp", "seguridad"]


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
     estructurados, arma tú el documento `open-accounting` (mira el recurso del esquema).
  2. `validar_comprobantes` para ver qué observaciones hay antes de nada.
  3. `generar_asiento` para las líneas de diario, o `exportar` directamente al formato del ERP.

Reglas que conviene tener claras antes de armar un documento:
  - Los importes van SIEMPRE en positivo. Una nota de crédito se marca con `tipo_cp: "07"`,
    nunca con importes negativos.
  - `tipo_cp` es el código de la Tabla 10 de SUNAT, no la sigla del sistema contable.
  - La `retencion` de un comprobante es la de renta de 4ta de un recibo por honorarios. La
    retención del IGV del 3 % NO es una detracción y no entra en el asiento.
  - Cada contribuyente tiene su plan de cuentas y sus sub-diarios: van en `configuracion`, con lo
    general en la raíz y lo de cada sistema contable en su sección (`concar`, `csv`, `contasis`).
    `configuracion_por_defecto` devuelve un punto de partida razonable, no la verdad de nadie.
  - La cuenta, el centro de costo, la cuenta del total y el reparto de CADA comprobante los decide
    quien revisa, y no van en el documento: llegan aparte, en `imputacion`, por el `id_externo` del
    comprobante — {"fila-8": {"cuenta_contable": "636301", "centro_costo": "OBRA01"}}. Lo que no
    traiga sale de la `configuracion`.
  - Lo ya anotado en otros periodos del mismo RUC llega en `claves_previas`, cada uno como
    [tipo_cp, serie, numero, contraparte_doc]: un comprobante que coincide sale con
    DUPLICADO_PERIODO_ANTERIOR, porque SUNAT lo rechazaría. En ventas el cliente no cuenta.
  - Antes de inventar una cuenta contable, `buscar_cuenta_pcge`. Que una cuenta no esté en el PCGE
    no la invalida —las divisionarias las abre cada empresa—, pero conviene saberlo.

Si algo no se puede hacer bien, la herramienta falla y dice por qué. No se inventa una cuenta,
ni un tipo de documento, ni una equivalencia del PCGE.
"""

mcp = FastMCP("contaperu", instructions=INSTRUCCIONES)
# FastMCP no deja poner la version en su constructor y, sin esto, el servidor se presenta en el
# saludo con la version del SDK: «contaperu 1.30.0», que no es ninguna version de contaperu.
mcp._mcp_server.version = api.__version__

# Hito 0.2: cada herramienta se anuncia de solo lectura y sin salir a ningún sitio —no guarda nada, no toca el disco ni
# la red—, así que un cliente puede llamarla sin pedir confirmación por un efecto que no tiene.
SOLO_LECTURA = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


# --- recursos: lo que conviene leer antes de llamar a nada -------------------------

@mcp.resource("contaperu://estandar/open-accounting", mime_type="application/schema+json")
def esquema_open_accounting() -> str:
    """El esquema JSON del documento contable `open-accounting`, con cada campo documentado."""
    return _datos.texto_del_esquema()


@mcp.resource("contaperu://catalogos/sunat", mime_type="application/json")
def catalogos_sunat() -> str:
    """Los catálogos de SUNAT que entiende el motor: tipos de comprobante, tipos de documento
    de identidad y monedas."""
    return json.dumps(api.catalogos_sunat(), ensure_ascii=False, indent=1)


@mcp.resource("contaperu://catalogos/estandar", mime_type="application/json")
def catalogos_del_estandar() -> str:
    """Los catálogos que este estándar inventa: los roles de una línea del asiento, las cinco clases contables y
    los tipos de libro, cada uno con su fuente y su versión."""
    return json.dumps(api.catalogos_del_estandar(), ensure_ascii=False, indent=1)


@mcp.resource("contaperu://catalogos/pcge2026", mime_type="application/json")
def catalogo_pcge2026() -> str:
    """El catálogo oficial de cuentas del Plan Contable General Empresarial 2026: cada cuenta con
    su nombre y la página de la norma que lo dice.

    Sirve para dos cosas: poner el nombre de una cuenta, y comprobar que la cuenta que se va a
    escribir existe. **Que una cuenta no esté aquí no la invalida**: el PCGE llega a cinco dígitos
    y cada empresa abre sus divisionarias debajo — `603201` es válida y no aparece en la norma.
    """
    return json.dumps(api.catalogo_pcge(), ensure_ascii=False, indent=1)


@mcp.resource("contaperu://drivers", mime_type="application/json")
def drivers_disponibles() -> str:
    """Los formatos de salida disponibles y qué libros genera cada uno."""
    return json.dumps(api.drivers_disponibles(), ensure_ascii=False, indent=1)


@mcp.resource("contaperu://configuracion", mime_type="application/json")
def configuracion_declarada() -> str:
    """Qué se configura y cómo: lo general y la sección de cada sistema contable, cada clave con su tipo, su valor
    por defecto, su patrón y sus textos, y en qué columnas de su archivo puede ir cada dato (el centro de costo, por
    ejemplo). Es lo que una aplicación lee para pintar su pantalla de configuración, y contra lo que se valida la
    `configuracion` de las herramientas."""
    return json.dumps(api.describir_configuracion(), ensure_ascii=False, indent=1)


@mcp.resource("contaperu://esquemas/diagnostico", mime_type="application/schema+json")
def esquema_diagnostico() -> str:
    """El JSON Schema de la respuesta de `diagnosticar`, también cuando la configuración no se puede aplicar. El SDK no
    deja declararlo como `outputSchema` de la herramienta sin cambiar lo que responde, así que viaja como recurso."""
    return json.dumps(api.esquema_diagnostico(), ensure_ascii=False, indent=1)


# --- herramientas ------------------------------------------------------------------

@mcp.tool(annotations=SOLO_LECTURA)
def configuracion_por_defecto() -> dict:
    """La configuración contable de partida: lo general en la raíz —cuentas, centros de costo, tasas
    de detracción— y una sección por sistema contable con lo suyo (`concar`: siglas y sub-diarios,
    códigos, columnas del centro de costo; `csv`: siglas, sub-diarios y códigos de la detracción;
    `contasis`: medio de pago y columnas del centro de costo).

    Es un punto de partida razonable, no la verdad de ningún contribuyente: el plan de cuentas
    y los sub-diarios los decide cada empresa. Cópiala, cámbiale lo que toque y pásala como
    `configuracion` en las demás herramientas: se valida entera, y lo que no existe se dice.
    """
    return api.configuracion_por_defecto()


@mcp.tool(annotations=SOLO_LECTURA)
def validar_comprobantes(documento: dict, configuracion: dict | None = None,
                         claves_previas: list[list[str]] | None = None) -> dict:
    """Revisa los comprobantes de un documento `open-accounting` y devuelve el mismo documento con
    `estado` y `observaciones` puestos en cada uno.

    Comprueba lo que se puede comprobar sin salir a ningún sitio: que el RUC sea un RUC, que el
    IGV cuadre con la base, que el total sea la suma de sus partes, que la fecha no sea posterior
    al periodo (error; una venta de un mes anterior solo avisa, y una compra anterior, solo pasados
    los 12 meses del plazo de anotación), que no haya duplicados —en el lote y, con `claves_previas`, contra lo ya
    anotado en otros periodos—. Las observaciones de nivel `error`
    bloquean la exportación; las de nivel `aviso` no.

    También descarta las detracciones cuyo código no está en la tabla del contribuyente, que es
    de donde salen los códigos inventados cuando una IA confunde la retención del IGV con una
    detracción.
    """
    return api.revisar(documento, configuracion=configuracion, claves_previas=claves_previas)


@mcp.tool(annotations=SOLO_LECTURA)
def validar_partida_doble(asiento: list[dict]) -> dict:
    """Comprueba que la suma del Debe sea exactamente igual a la del Haber.

    Sin tolerancia: un céntimo de diferencia es un asiento mal armado. Devuelve las dos sumas,
    la diferencia y cuántas líneas no dicen si son Debe o Haber.
    """
    return api.cuadrar(asiento)


@mcp.tool(annotations=SOLO_LECTURA)
def generar_asiento(documento: dict, configuracion: dict | None = None,
                    correlativos: dict | None = None, incluir_observados: bool = False,
                    imputacion: dict | None = None, driver: str = "concar",
                    claves_previas: list[list[str]] | None = None) -> dict:
    """Convierte los comprobantes en líneas de diario, sin el formato de ningún sistema.

    Devuelve el bloque `asiento` del estándar: cuenta, debe o haber, importe, moneda, glosa,
    centro de costo y el documento que lo respalda. Es lo que sirve para revisar el asiento, o
    para cargarlo en un sistema que no tenga driver todavía.

    `correlativos` dice por qué número empieza cada sub-diario ({"11": 1}); si no se pasa,
    empieza en 1. Con `incluir_observados` se genera aunque haya comprobantes con errores —
    útil para ver qué saldría, arriesgado para presentar.

    `imputacion` trae lo que se decidió para cada comprobante, por su `id_externo`: su
    `cuenta_contable`, su `centro_costo`, la `cuenta_tercero` (la del total) o un `reparto` de la base
    entre cuentas ([{importe, cuenta_contable, centro_costo}], que tiene que sumar la base). Lo que no
    traiga sale de la configuración.

    `driver` es el sistema de asientos cuya sección de la configuración se aplica (`concar` o `csv`):
    sus siglas, sus sub-diarios y las columnas en que pone el centro de costo. Exige lo mismo que
    `exportar` hacia ese sistema —en CONCAR, el centro de costo y una moneda con código—; para ver qué
    falta sin que se niegue, `diagnosticar`.
    """
    return api.generar_asiento(documento, driver=driver, configuracion=configuracion, imputacion=imputacion,
                               correlativos=correlativos, incluir_observados=incluir_observados,
                               claves_previas=claves_previas)


@mcp.tool(annotations=SOLO_LECTURA)
def diagnosticar(documento: dict, configuracion: dict | None = None, correlativos: dict | None = None,
                 driver: str = "concar", imputacion: dict | None = None,
                 claves_previas: list[list[str]] | None = None) -> dict:
    """Dice todo lo que hay que mirar de un mes ANTES de exportarlo. **Llámala antes de `exportar`.**

    En una sola respuesta: si el mes está listo (`listo_para_exportar`) y, si no, por qué
    (`por_que_no`); qué comprobantes tienen observaciones que bloquean y cuáles solo avisos, por su
    serie-número; qué falta para el sistema de destino —cuenta contable, centro de costo, tipos de
    comprobante sin sigla, monedas que no admite, un reparto entre cuentas que no admite
    (`reparto_no_admitido`), lo que no cabe en su formato (`no_cabe`), sub-diarios sin correlativo—; qué
    detracciones esperan todavía su constancia; un resumen por proveedor o cliente; desde qué
    correlativo arrancaría cada sub-diario; y la lista de lo que saldría.

    `exige` dice qué pide ese destino (el CSV no exige centro de costo; CONCAR sí), y `que_falta`
    agrupa por motivo lo que de verdad bloquea, con **`pedir_a`**: `contador` si se resuelve mirando
    el documento o el plan de cuentas, `sistema` si es configuración del destino o un dato público
    que no está en el papel. Úsalo para redactar la pregunta a quien toca, en vez de adivinar.

    No corrige nada ni inventa nada: un comprobante sin cuenta se arregla donde se revisa, y aquí
    solo se dice cuál es. Es la herramienta para enseñarle a la persona qué va a salir antes de
    generar un archivo que luego se importa en su sistema contable. `imputacion` es la misma de
    `generar_asiento`: un reparto que no suma la base sale en `faltantes.reparto_que_no_cuadra`.
    Si la `configuracion` no cumple lo que se declara en `contaperu://configuracion`, lo dice en
    `errores_de_configuracion`, cada error con su ruta. La forma de la respuesta está en el recurso
    `contaperu://esquemas/diagnostico`.
    """
    return api.diagnosticar(documento, driver=driver, configuracion=configuracion, imputacion=imputacion,
                            correlativos=correlativos, claves_previas=claves_previas)


@mcp.tool(annotations=SOLO_LECTURA)
def exportar(documento: dict, driver: str = "concar", configuracion: dict | None = None,
             correlativos: dict | None = None, incluir_observados: bool = False,
             fecha: str = "", imputacion: dict | None = None,
             claves_previas: list[list[str]] | None = None) -> CallToolResult:
    """Genera el archivo que espera un sistema contable, ya listo para importar.

    Devuelve dos cosas: un resumen en JSON (nombre del archivo, comprobantes, debe y haber, y en
    `_exportacion` la **huella** del asiento que salió: si vuelves a exportar lo mismo, la huella se
    repite, y el Excel de CONCAR se SUMA al importarlo dos veces) y **el archivo adjunto**, para
    guardarlo tal cual. `fecha` (AAAA-MM-DD) es opcional y la pones tú: este servidor no mira el reloj.
    `imputacion` es la misma de `generar_asiento`.

    Drivers disponibles, por grupo (el recurso `contaperu://drivers` dice el grupo de cada uno):
      - SIRE:   `sire` — el TXT para reemplazar la propuesta del RVIE o del RCE en SUNAT: el
                contenido va en `texto` y el ZIP que sube a SUNAT, adjunto.
      - Legacy: `concar` — el Excel de asientos de 41 columnas, adjunto como `.xlsx`.
                `contasis` — el registro de compras o de ventas que importa CONTASIS, adjunto como
                `.xlsx`: una fila por comprobante, sin sub-diario (se elige al importar).
      - ERP:    `csv` — las líneas de diario en columnas, en `texto` y también adjunto.
                `asiento_neutral` — el documento del estándar con su asiento, sin siglas, sub-diarios ni
                correlativos de ningún sistema legacy, adjunto como `.json`.

    Antes de escribir nada, en los drivers que arman asiento (`concar`, `csv`) comprueba que cuadre; si
    no cuadra, falla. `contasis` y `sire` no arman asiento: `contasis` se niega antes por lo que exige y
    por lo que no cabe en su formato (`no_cabe`).
    """
    resultado = api.exportar(documento, driver=driver, configuracion=configuracion, imputacion=imputacion,
                             correlativos=correlativos, incluir_observados=incluir_observados, fecha=fecha or None,
                             claves_previas=claves_previas)
    # Los bytes salen del resumen y entran en los adjuntos: repetirlos en el JSON seria mandar
    # el archivo dos veces, y la copia en texto es justo la que el cliente no sabe guardar.
    contenido = resultado.pop("contenido_base64", "") or ""
    zip_b64 = resultado.pop("zip_base64", "") or ""
    pesa = peso_de_base64(contenido, zip_b64)
    if pesa > MAXIMO_ARCHIVO:
        raise api.DocumentoInvalido(
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


@mcp.tool(annotations=SOLO_LECTURA)
def leer_xml_ubl(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """Lee el XML UBL 2.1 de la factura electrónica de SUNAT y devuelve un documento `open-accounting`.

    Acepta un XML suelto como texto, o un ZIP en base64 con varios dentro (`es_base64: true`).
    Descarta lo que no es un comprobante — las constancias de recepción (CDR) y las hojas de
    estilo— y avisa de lo que no pudo leer. `libro` es la cabecera: RUC, periodo y si son
    ventas o compras.
    """
    return api.leer_xml(contenido, libro, es_base64=es_base64)


@mcp.tool(annotations=SOLO_LECTURA)
def leer_propuesta_sire(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """Lee el TXT de la propuesta que SUNAT entrega en el SIRE y devuelve un documento
    `open-accounting`.

    Es lo que el contribuyente descarga de su SIRE con lo que SUNAT cree que compró o vendió;
    a partir de ahí se compara con la realidad y se corrige. Acepta el TXT como texto o el ZIP
    tal cual lo entrega SUNAT (`es_base64: true`).
    """
    return api.leer_propuesta_sire(contenido, libro, es_base64=es_base64)


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_cuenta_pcge(texto: str = "", codigo: str = "") -> dict:
    """Busca una cuenta en el Plan Contable General Empresarial 2026, por nombre o por código.

    Con `texto` devuelve las cuentas cuyo nombre lo contiene (sin distinguir tildes ni mayúsculas).
    Con `codigo` devuelve esa cuenta y, si no está en la norma, **la cuenta madre que la gobierna**:
    de `603201` sale `6032 Suministros`, porque el PCGE llega a cinco dígitos y las divisionarias
    las abre cada empresa. Un código que no resuelve ni por su elemento está mal escrito.

    Úsala antes de decidir la `cuenta_contable` de un comprobante: es la diferencia entre elegir
    una cuenta que existe y proponer uno que suena bien.
    """
    return api.buscar_cuenta_pcge(texto=texto, codigo=codigo)


@mcp.tool(annotations=SOLO_LECTURA)
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
    return api.adaptar_pcge(asiento)


@mcp.tool(annotations=SOLO_LECTURA)
def normalizar_detracciones(documento: dict, configuracion: dict | None = None) -> dict:
    """Contrasta la detracción de cada comprobante con la tabla del contribuyente y deja en
    blanco la que no reconozca.

    Sirve sobre todo después de leer comprobantes con un modelo de lenguaje: la confusión más
    común es tomar la **retención del IGV** (el 3 % que retiene un agente de retención cuando la
    factura pasa de S/ 700, y que no toca el registro de compras) por una detracción.
    """
    return api.normalizar_detracciones(documento, configuracion=configuracion)


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
    ap.add_argument("--transporte", default="stdio", choices=["stdio", "http", "sse"],
                    help="stdio (por defecto) para un cliente local; http para servirlo en red")
    ap.add_argument("--host", default="127.0.0.1", help="solo con --transporte http")
    ap.add_argument("--puerto", type=int, default=8000, help="solo con --transporte http")
    ap.add_argument("--dominio", action="append", default=[], metavar="NOMBRE",
                    help="nombre publico por el que se sirve, si va detras de un proxy "
                         "(repetible). Sin esto solo se atienden peticiones a localhost")
    ap.add_argument("--version", action="version", version=f"contaperu {api.__version__}")
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
