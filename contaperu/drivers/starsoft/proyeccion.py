"""De una línea neutral a una fila de STARSOFT.

El motor pone la contabilidad —qué cuentas, qué sentido, qué importes, la numeración— y aquí solo se traduce
vocabulario. Las líneas llegan cuadradas y numeradas; este módulo no decide ni una cuenta.

**Va en código y no en una tabla declarativa** (`kit/columnas`) por la misma razón que CONCAR y CONTASIS: sus
columnas mezclan datos de la línea con datos de la CABECERA del comprobante —el IGV, el destino de la
adquisición, el número sin partir—, y una tabla de rutas solo alcanza la línea.

Las traducciones que hacen a STARSOFT distinto de CONCAR, con el mismo documento delante:

    sub-diario      11  ->  04         el de STARSOFT, que va en la configuración
    comprobante     070001  ->  0001   el correlativo sin el mes, con sus cuatro dígitos
    nro documento   F136-431  ->  F13600000431    serie a cuatro y número a ocho
    conversión      V  ->  VTA
    destino         DGNG  ->  002      la columna que CONCAR no tiene

La glosa NO se traduce: las dos columnas que la llevan —`GLOSA` y `GLOSA MOVIMIENTO`— dicen el concepto del
comprobante, el mismo que trae la línea.
"""
from __future__ import annotations

from typing import Any

from ...asiento.indice import Cabecera
from ...asiento.lineas import LineaDiario
from . import datos

LARGO_SERIE = 4       # F001 · 001 + espacio: la serie ocupa cuatro en la plantilla
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


def serie_a_cuatro(serie: str) -> str:
    """La serie a CUATRO caracteres, rellenando con espacios por la derecha: `F001` se queda, `001` pasa a `001 `.

    Sale de la plantilla real de ventas (capturas de John, 21-sep-2026), donde el número ocupa 12 caracteres
    siempre: `F00100000202` en una factura y `001 00036207` en una boleta. Sin el relleno, la boleta saldría con
    11 y la columna dejaría de cuadrar.
    """
    return f"{(serie or '').strip():<{LARGO_SERIE}}"[:LARGO_SERIE]


def numero_del_documento(cab: Cabecera) -> str:
    """Serie y número pegados, 12 caracteres: `F136` + `00000431`, `001 ` + `00036207`.

    ⚠️ Es lo contrario de la regla de CONCAR y del SIRE, donde el número va SIN ceros a la izquierda.
    """
    return f"{serie_a_cuatro(cab.serie)}{(cab.numero or '').zfill(LARGO_NUMERO)}"


def voucher(correlativo: str) -> str:
    """El correlativo tal como lo numera STARSOFT: `0001`, no `070001`. Alimenta la columna `CORRELATIVO`.

    **La columna se llama `CORRELATIVO` y la función `voucher`**, y no es un descuido: la columna la renombró John
    el 21-sep-2026 porque «ahí se entiende mejor» —en la captura del vídeo era `VOUCHER`—, y el nombre de la
    función es superficie pública congelada (`fixtures/superficie/1.0.json`), que solo se quita en una mayor.

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


def fila(ln: LineaDiario, cab: Cabecera, libro: Any, config: dict, fecha_registro: str,
         hay_detraccion: bool = False) -> dict[str, Any]:
    """Una línea neutral → una fila del archivo, con las claves del libro que toca (`datos.COLUMNAS`).

    **Compras y ventas no comparten ni las cabeceras**: son dos plantillas y se calca cada una de su fuente, así
    que aquí solo se reparte. La de ventas sale de las capturas de la hoja real; la de compras, del vídeo.
    """
    arma = _fila_venta if libro.tipo == "venta" else _fila_compra
    todo = arma(ln, cab, libro, config, fecha_registro, hay_detraccion)
    return {cabecera: todo.get(cabecera, "") for _, cabecera, _ in datos.COLUMNAS[libro.tipo]}


def _fila_compra(ln: LineaDiario, cab: Cabecera, libro: Any, config: dict, fecha_registro: str,
                 hay_detraccion: bool = False) -> dict[str, Any]:
    """Las 38 columnas de la plantilla de compras, con sus nombres literales.

    `IGV` y `TASA IGV` van **solo en la fila del total** —la del rol `tercero`—, como en la captura: las otras
    dos filas del asiento las llevan vacías. Es para lo que existe el rol.
    """
    doc, ref, det = ln.documento or {}, ln.referencia or {}, ln.detraccion or {}
    es_total = ln.rol == "tercero"
    return {
        "CTA CONTABLE": ln.cuenta,
        "AÑO Y MES PROCESO": libro.periodo,
        "SUBDIARIO": ln.sub_diario,
        "COMPROBANTE": voucher(ln.correlativo),
        "FECHA DOCUMENTO": ln.fecha,
        "TIPO ANEXO": config.get("tipo_anexo_proveedor") or "",
        "CODIGO PROVEEDOR": cab.contraparte_doc,
        "TIPO DOCUMENTO": doc.get("tipo", ""),
        "NRO DOCUMENTO": numero_del_documento(cab),
        "FECHA VENCIMIENTO": doc.get("fecha_vencimiento", ""),
        "IGV": cab.igv if es_total else "",
        "TASA IGV": ln.tasa_igv if es_total else "",
        "IMPORTE": ln.importe,
        "CONV": config.get("tipo_conversion") or "",
        "FECHA REGISTRO": fecha_registro,
        "TIPO CAMBIO": ln.tipo_cambio or "",
        # LA MISMA que la de movimiento (John, 21-sep-2026): las dos dicen el concepto del
        # comprobante. Hasta la 2.1 esta llevaba el documento —`FT F001-00000202 /`—, que es lo que
        # muestra una de las hojas; pero el tipo y el número ya viajan en sus propias columnas, así
        # que repetirlos aquí gastaba la glosa en decir dos veces lo mismo.
        "GLOSA": ln.glosa,
        "DESTINO": destino_de(cab),
        "TIPO DOC REF": ref.get("tipo", ""),
        "NRO DOC REF": ref.get("serie_numero", ""),
        "FECHA DOC REF": ref.get("fecha", ""),
        "CENTRO DE COSTOS": ln.centro_costo or ln.anexo_auxiliar or "",
        "GLOSA MOVIMIENTO": ln.glosa,
        "DOCUMENTO ANULADO": datos.NO_ANULADO,
        "IMPORTACION": "1" if (cab.anio_dua or cab.cod_dep_aduanera) else "0",
        "DEBE / HABER": ln.debe_haber,
        # --- la detracción: cuatro columnas juntas más las tres de después ------------------------------
        # La bandera del comprobante, no de la línea: «1 sí · blanco o 0 no» dice su hoja, y se elige afirmar,
        # como en `DOCUMENTO ANULADO` e `IMPORTACION`.
        "DETRACCION": "1" if hay_detraccion else "0",
        # La constancia del depósito NO se conoce al provisionar: se paga días después. Por eso el motor pone el
        # comodín en el documento de la línea, y estas dos van vacías hasta que alguien las traiga.
        "NRO DOC DETRACCION": "",
        "FECHA DETRACCION": "",
        # El código de SUNAT (`027`), no el interno que CONCAR mapea en su tabla (`02702`): el vídeo dice «el
        # código de la detracción… para indicar el tipo de operación afecta» (10:49), y eso es el Catálogo 54.
        "CODIGO DETRACCION": det.get("codigo", ""),
        "TASA DETRACCION": det.get("tasa", ""),
        # Lo DETRAÍDO, que es el importe de esta línea —«cuánto ha sido el importe que se ha detraído» (10:58)—,
        # no `det["base"]`, que es el total sobre el que se calcula.
        "IMPORTE DETRACCION": ln.importe if ln.rol == "detraccion" else "",
        # --- declaradas y vacías: existen y no consta cómo se llenan ------------------------------------
        # `PORC OPE MIXTA` sale con 60 en la captura, en una compra de destino 002 (uso mixto), pero de dónde
        # sale ese 60 no consta: el estándar no tiene el porcentaje de la operación mixta.
        "PORC OPE MIXTA": "",
        "VALOR CIF": "",
        # `0` = el IGV NO está pendiente de aplicación. Estuvo vacía mientras la única fuente era la narración
        # del vídeo; la captura de la hoja real la muestra con `0` en todas las filas y eso la cerró.
        "IGV POR APLICAR": datos.IGV_NO_PENDIENTE,
        "NRO FILE": "",
        "OTROS TRIBUTOS": "",
        "IMP BOLSA": "",
    }


def _fila_venta(ln: LineaDiario, cab: Cabecera, libro: Any, config: dict, fecha_registro: str,
                hay_detraccion: bool = False) -> dict[str, Any]:
    """Las 34 columnas de la plantilla de ventas, con sus nombres literales.

    Dos reglas salen de la captura y no del vídeo: **`IGV` y `TASA IGV` van solo en la fila del cliente** —la del
    rol `tercero`, que es la primera del asiento—, y **`RUC CLIENTE` y `RAZON SOCIAL` también**, no repetidos en
    las demás filas como se hacía hasta ahora.
    """
    doc, ref = ln.documento or {}, ln.referencia or {}
    es_total = ln.rol == "tercero"
    return {
        "CTA CONTABLE": ln.cuenta,
        "AÑO Y MES PROCESO": libro.periodo,
        "SUBDIARIO": ln.sub_diario,
        "COMPROBANTE": voucher(ln.correlativo),
        "FECHA REGISTRO": fecha_registro,
        "TIPO ANEXO": config.get("tipo_anexo_cliente") or "",
        "CODIGO CLIENTE": cab.contraparte_doc,
        "TIPO DOCUMENTO": doc.get("tipo", ""),
        "NRO DOCUMENTO": numero_del_documento(cab),
        "NRO DOC FINAL": cab.numero_final,
        "FECHA EMISION": doc.get("fecha_emision", ""),
        "DOC REFERENCIA": ref.get("tipo", ""),
        "NRO DOC REF": ref.get("serie_numero", ""),
        "IGV": cab.igv if es_total else "",
        "TASA IGV": ln.tasa_igv if es_total else "",
        "IMPORTE": ln.importe,
        "CONV": config.get("tipo_conversion") or "",
        "TIPO CAMBIO": ln.tipo_cambio or "",
        # LA MISMA que la de movimiento (John, 21-sep-2026): las dos dicen el concepto del
        # comprobante. Hasta la 2.1 esta llevaba el documento —`FT F001-00000202 /`—, que es lo que
        # muestra una de las hojas; pero el tipo y el número ya viajan en sus propias columnas, así
        # que repetirlos aquí gastaba la glosa en decir dos veces lo mismo.
        "GLOSA": ln.glosa,
        "GLOSA MOVIMIENTO": ln.glosa,
        "DOCUMENTO ANULADO": datos.NO_ANULADO,
        "DEBE / HABER": ln.debe_haber,
        "RUC CLIENTE": cab.contraparte_doc if es_total else "",
        "RAZON SOCIAL": cab.contraparte_nombre if es_total else "",
        "CENTRO DE COSTOS": ln.centro_costo or ln.anexo_auxiliar or "",
        "FECHA VENCIMIENTO": doc.get("fecha_vencimiento", ""),
        "FECHA DOC REFERENCIA": ref.get("fecha", ""),
        "EXPORTACION": "1" if not _es_cero(cab.exportacion) else "0",
        # Declaradas y vacías: existen en la plantilla y no consta cómo se llenan. En la captura de John van en
        # blanco incluso en la venta EXONERADA, que es el caso donde más se esperaría un número.
        "VALOR ISC": "",
        "OTROS TRIB": "",
        "NRO FILE": "",
        "EXONERADO": "",
        "OTROS CARGOS": "",
        "IMP BOLSA": "",
    }


def filas(cab: Cabecera, lineas: list[LineaDiario], libro: Any, config: dict, fecha_registro: str) -> list[dict]:
    """Las líneas de UN comprobante → sus filas.

    La bandera `DETRACCION` es del COMPROBANTE y no de la línea —va en las tres o cuatro filas, no solo en la
    suya—, así que se mira aquí, que es donde se ven todas, y no dentro de `fila()`."""
    hay_detraccion = any(ln.rol == "detraccion" for ln in lineas)
    return [fila(ln, cab, libro, config, fecha_registro, hay_detraccion) for ln in lineas]


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
