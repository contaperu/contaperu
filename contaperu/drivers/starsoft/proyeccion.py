"""De una línea neutral a una fila de STARSOFT.

El motor pone la contabilidad —qué cuentas, qué sentido, qué importes, la numeración— y aquí solo se traduce
vocabulario. Las líneas llegan cuadradas y numeradas; este módulo no decide ni una cuenta.

**Va en código y no en una tabla declarativa** (`kit/columnas`) por la misma razón que CONCAR y CONTASIS: sus
columnas mezclan datos de la línea con datos de la CABECERA del comprobante —el IGV, el destino de la
adquisición, el número sin partir—, y una tabla de rutas solo alcanza la línea.

Las seis traducciones que hacen a STARSOFT distinto de CONCAR, con el mismo documento delante:

    sub-diario      11  ->  4          el de STARSOFT, que va en la configuración
    voucher         070001  ->  0001   el correlativo sin el mes, con sus cuatro dígitos
    nro documento   F136-431  ->  F13600000431    pegado y con ceros
    conversión      V  ->  VTA
    glosa           CELULARES  ->  FT F136-00000431
    destino         DGNG  ->  002      la columna que CONCAR no tiene
"""
from __future__ import annotations

from typing import Any

from ...asiento.indice import Cabecera
from ...asiento.lineas import LineaDiario
from . import datos

LARGO_NUMERO = 8       # F136 + 00000431: el número a ocho, visto en la captura de la hoja PLANTILLA
LARGO_VOUCHER = 4      # 0001: los cuatro dígitos con los que numera el motor, sin el mes delante


def destino_de(cab: Cabecera) -> str:
    """El destino de la adquisición, la columna R: qué se hace con el IGV de esta compra.

    Los tres primeros valores son `destino_igv` del estándar traducido. Los otros dos no están en ese campo y se
    deducen del comprobante, porque STARSOFT mete en una sola columna dos preguntas distintas: a qué se destina
    el IGV, y qué clase de operación es.

    **No se puede traducir `DG` a `001` a secas**: el modelo pone `DG` por defecto a TODO comprobante, también a
    una compra exonerada que no tiene IGV que destinar. Por eso se mira primero lo que descarta.

    ⚠️ `[por confirmar]` contra un archivo que STARSOFT haya aceptado: la precedencia entre importación y destino
    —hoy gana la importación— y el umbral del 004. Es de los errores que no dan error: el archivo se importa y
    clasifica mal el crédito fiscal.
    """
    if cab.anio_dua or cab.cod_dep_aduanera:
        return datos.DESTINO_IMPORTACION
    if _es_cero(cab.base_gravada) and _es_cero(cab.igv):
        return datos.DESTINO_NO_GRAVADA
    return datos.DESTINO.get(cab.destino_igv, datos.DESTINO["DG"])


def _es_cero(texto: str) -> bool:
    return not (texto or "").strip("0.-")


def numero_del_documento(cab: Cabecera) -> str:
    """Serie y número pegados y con ceros: `F136` + `00000431`.

    ⚠️ Es lo contrario de la regla de CONCAR y del SIRE, donde el número va SIN ceros a la izquierda. Sale de la
    captura de la hoja `PLANTILLA` de compras, que muestra `F13600000431` en la columna I mientras la glosa de la
    misma fila lleva el guion. `[por confirmar]` contra la plantilla oficial.
    """
    return f"{cab.serie}{(cab.numero or '').zfill(LARGO_NUMERO)}"


def glosa_del_documento(ln: LineaDiario, cab: Cabecera) -> str:
    """La glosa de la columna Q: el tipo y el documento, no el concepto del comprobante.

    En la captura es `FT F136-00000431` mientras el concepto («CELULARES») va a la glosa de movimiento. Aquí el
    número SÍ lleva guion, a diferencia de la columna del número.
    """
    tipo = (ln.documento or {}).get("tipo", "")
    return f"{tipo} {cab.serie}-{(cab.numero or '').zfill(LARGO_NUMERO)}".strip()


def voucher(correlativo: str) -> str:
    """El correlativo tal como lo numera STARSOFT: `0001`, no `070001`.

    El motor numera con el mes delante y cuatro dígitos (`asiento.numerar`), que es lo que piden CONCAR y el CSV.
    STARSOFT empieza en 1 y sigue («el correlativo de comprobantes o vouchers debe iniciar siempre en el número
    uno», compras 6:15), así que se le quita el mes. Mismo recorte que hace CONCAR en su propio resumen.

    **Los cuatro dígitos se conservan** (John, 21-sep-2026). Hasta la 2.0 esto pasaba por `int()` y salía `1`: el
    recorte del mes se llevaba por delante los ceros, que no son adorno sino el ancho del campo.

    ⚠️ En el CSV la celda va `0001` sin comillas, así que **Excel, al abrirlo para revisarlo, mostrará `1`**. El
    archivo es correcto; lo que engaña es el visor. Si el día de la primera importación real STARSOFT rechazara el
    texto con ceros, es este `zfill` lo que se quita.
    """
    sin_mes = (correlativo or "")[2:] or "0"
    return sin_mes.zfill(LARGO_VOUCHER) if sin_mes.isdigit() else correlativo


def fila(ln: LineaDiario, cab: Cabecera, libro: Any, config: dict, fecha_registro: str) -> dict[str, Any]:
    """Una línea neutral → una fila del archivo, con las claves del libro que toca (`datos.COLUMNAS`).

    `IGV` y `TASA IGV` van **solo en la línea del total** —la del rol `tercero`—, como en la captura: las otras
    dos filas del asiento las llevan vacías. Es para lo que existe el rol.
    """
    columnas = datos.COLUMNAS[libro.tipo]
    doc, ref = ln.documento or {}, ln.referencia or {}
    es_total = ln.rol == "tercero"
    centro = ln.centro_costo or ln.anexo_auxiliar or ""
    comun = {
        "CUENTA": ln.cuenta,
        "PERIODO": libro.periodo,
        "SUBDIARIO": ln.sub_diario,
        "VOUCHER": voucher(ln.correlativo),
        "FECHA": ln.fecha,
        "TIPO DOCUMENTO": doc.get("tipo", ""),
        "NRO DOCUMENTO": numero_del_documento(cab),
        "FECHA VENCIMIENTO": doc.get("fecha_vencimiento", ""),
        "IGV": cab.igv if es_total else "",
        "TASA IGV": ln.tasa_igv if es_total else "",
        "IMPORTE": ln.importe,
        "CONV": config.get("tipo_conversion") or "",
        "TIPO CAMBIO": ln.tipo_cambio or "",
        "GLOSA": glosa_del_documento(ln, cab),
        "GLOSA MOVIMIENTO": ln.glosa,
        "DEBE HABER": ln.debe_haber,
        "CENTRO COSTO": centro,
        "NRO DOC REF": ref.get("serie_numero", ""),
    }
    if libro.tipo == "compra":
        det = ln.detraccion or {}
        propio = {
            "TIPO ANEXO": config.get("tipo_anexo") or "",
            "CODIGO PROVEEDOR": cab.contraparte_doc,
            "FECHA REGISTRO": fecha_registro,
            "DESTINO": destino_de(cab),
            # Las dos que el estándar no tiene. Vacías y declaradas: una columna que existe y va en blanco dice
            # «este comprobante no lo trae»; una que falta diría «este motor no lo sabe».
            "PORC OPE MIXTA": "",
            "VALOR CIF": "",
            "TIPO DOC REF": ref.get("tipo", ""),
            # La detracción: el motor la pone en la línea que le toca (`rol` detraccion) y aquí se transcribe.
            # ⚠️ `[por confirmar]` Y ES LA DUDA MÁS GRANDE DEL DRIVER: en los vídeos la detracción se registra
            # como DATOS de la fila —el asiento típico de compras tiene tres cuentas, sin línea de detracción—,
            # mientras el motor genera dos líneas más para ella, que es lo que pide CONCAR. Si STARSOFT las
            # rearma a partir de estas columnas, el asiento saldría duplicado. Se sabrá con un archivo aceptado
            # que lleve detracción; hasta entonces salen las dos cosas, que es lo que el motor produce hoy.
            # El código de SUNAT (`027`), no el interno que CONCAR mapea en su tabla (`02702`): el vídeo dice
            # «el código de la detracción… para indicar el tipo de operación afecta a la detracción» (10:49), y
            # eso es el Catálogo 54. Si STARSOFT tuviera códigos propios, saldría de su `detraccion_codigos`.
            "CODIGO DETRACCION": det.get("codigo", ""),
            "TASA DETRACCION": det.get("tasa", ""),
            # Lo DETRAÍDO, que es el importe de esta línea —«cuánto ha sido el importe que se ha detraído»
            # (10:58)—, no `det["base"]`, que es el total sobre el que se calcula.
            "IMPORTE DETRACCION": ln.importe if ln.rol == "detraccion" else "",
            # Sin fuente todavía: la columna existe y va vacía, que dice «este comprobante no lo trae».
            "ANULADO": "",
            "IGV POR APLICAR": "",
            "IMPORTACION": "1" if (cab.anio_dua or cab.cod_dep_aduanera) else "0",
            "NUMERO FILE": "",
        }
    else:
        propio = {
            "FECHA EMISION": doc.get("fecha_emision", ""),
            "NRO DOC FINAL": cab.numero_final,
            "DOC REFERENCIA": ref.get("tipo", ""),
            "RUC CLIENTE": cab.contraparte_doc,
            "RAZON SOCIAL": cab.contraparte_nombre,
            "ANULADO": "",
            "EXPORTACION": "1" if not _es_cero(cab.exportacion) else "0",
        }
    todo = {**comun, **propio}
    return {cabecera: todo.get(cabecera, "") for _, cabecera, _ in columnas}


def filas(cab: Cabecera, lineas: list[LineaDiario], libro: Any, config: dict, fecha_registro: str) -> list[dict]:
    return [fila(ln, cab, libro, config, fecha_registro) for ln in lineas]


def no_caben(libro: Any, comprobantes: list, config: dict) -> dict[str, list]:
    """Lo que la plantilla de STARSOFT no puede llevar, por motivo (`datos.MOTIVOS`).

    Hoy solo la glosa, y es el único límite que consta de verdad: está escrito en la cabecera de la propia hoja
    `PARAMETROS` de los dos aplicativos. Se mira aquí y no se corta, porque una glosa cortada sigue siendo
    legible pero una que se pasa hace que STARSOFT rechace la fila.

    **No entra el límite de «4 cuentas por asiento»** que sugiere `PARAMETROS` con sus cuatro pares de columnas:
    esa hoja es de la macro de Excel y no viaja al archivo, así que no consta que sea un límite del formato. Una
    compra con detracción produce cinco líneas pero solo cuatro cuentas distintas, así que hoy ni lo rozaría.
    """
    largas = [c for c in comprobantes if len((c.concepto or "").strip()) > datos.LARGO_GLOSA]
    return {datos.MOTIVOS["glosa"]: largas} if largas else {}
