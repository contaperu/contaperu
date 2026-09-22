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

from decimal import Decimal
from typing import Any

from ...asiento.indice import Cabecera
from ...modelo import numero_sin_ceros
from ...asiento.lineas import LineaDiario
from . import datos
from .datos import ORDEN_DE_LAS_FILAS, ROLES_DE_LA_DETRACCION

LARGO_SERIE = 4       # F001 · 001 + espacio: la serie ocupa cuatro en la plantilla
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

    **Esto SÍ se rellena**, y no es lo mismo que el número: el manual dice que «los 4 primeros son la serie; si es
    de 3, un espacio en blanco y el numero desde la quinta», así que el hueco es dónde empieza el número, no
    cosmética. Sus ejemplos lo confirman: `001 000005` y `0001000004`.
    """
    return f"{(serie or '').strip():<{LARGO_SERIE}}"[:LARGO_SERIE]


def numero_del_documento(cab: Cabecera) -> str:
    """Serie y número pegados: `F136` + `431`, `001 ` + `36207`.

    **El número va SIN ceros a la izquierda** (John, 22-sep-2026, viéndolo dentro de su STARSOFT): en la columna
    Documento del asiento salía `E00100000105` y él lo quiere `E001105`. Con esto STARSOFT deja de ser la
    excepción — el SIRE, CONCAR y CONTASIS ya escriben el número así, y era la regla de la casa desde antes.

    Hasta la 2.5 se rellenaba a ocho, tomado de una captura de la hoja PLANTILLA donde los números se veían con
    ceros; pero eso es cómo los guarda **esa** instalación, no lo que el formato exige. La serie sí se rellena,
    que ahí el hueco marca dónde empieza el número (`serie_a_cuatro`).
    """
    return f"{serie_a_cuatro(cab.serie)}{numero_sin_ceros(cab.numero)}"


def con_dos_decimales(valor: Any) -> str:
    """Un importe o un porcentaje como los escribe STARSOFT: `18.00`, `0.00`, `4.00`.

    Sus ejemplos oficiales los llevan SIEMPRE con dos decimales —incluso los que no aplican, que salen `0.00` y
    no vacíos— y el nuestro escribía `18` y dejaba en blanco los que no aplicaban (John, 22-sep-2026). Vacío o
    None da `0.00`: en las columnas donde esto se usa, «no aplica» se dice con un cero."""
    if valor in (None, ""):
        return "0.00"
    try:
        return f"{Decimal(str(valor)):.2f}"
    except (ArithmeticError, ValueError):
        return str(valor)


def glosa_del_documento(ln: LineaDiario, cab: Cabecera) -> str:
    """La columna `GLOSA`: el tipo y el número, no el concepto —que va en `GLOSA MOVIMIENTO`—.

    Así lo traen los doce ejemplos oficiales de ventas y los dieciocho de compras: `FT 002-000085 /`, con el
    concepto en la columna de al lado. Esta función existió hasta la 2.1 y se quitó el 21-sep-2026 por parecer
    que repetía el tipo y el número, que ya viajan en sus propias columnas; **el manual la devuelve**, y entre
    parecerlo y lo que hace su sistema gana lo segundo (John, 22-sep-2026).

    La serie va a cuatro y el número **sin ceros**, igual que en `numero_del_documento`: lo que no se puede es
    que una columna diga `E001-105` y la otra `E00100000105` hablando del mismo documento.

    ⚠️ El ` /` final está en todos los ejemplos y **no consta** si lo pide el formato o lo dejó quien llenó la
    hoja; se conserva porque es lo que se ve."""
    tipo = (ln.documento or {}).get("tipo", "")
    return f"{tipo} {serie_a_cuatro(cab.serie)}-{numero_sin_ceros(cab.numero)} /".strip()


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


def fila(ln: LineaDiario, cab: Cabecera, libro: Any, config: dict,
         detraccion: LineaDiario | None = None) -> dict[str, Any]:
    """Una línea neutral → una fila del archivo, con las claves del libro que toca (`datos.COLUMNAS`).

    **Compras y ventas no comparten ni las cabeceras**: son dos plantillas y se calca cada una de su fuente, así
    que aquí solo se reparte. La de ventas sale de las capturas de la hoja real; la de compras, del vídeo.
    """
    arma = _fila_venta if libro.tipo == "venta" else _fila_compra
    todo = arma(ln, cab, libro, config, detraccion)
    return {cabecera: todo.get(cabecera, "") for _, cabecera, _ in datos.COLUMNAS[libro.tipo]}


def _fila_compra(ln: LineaDiario, cab: Cabecera, libro: Any, config: dict,
                 detraccion: LineaDiario | None = None) -> dict[str, Any]:
    """Las 38 columnas de la plantilla de compras, con sus nombres literales.

    `IGV` y `TASA IGV` van **solo en la fila del total** —la del rol `tercero`—, como en la captura: las otras
    dos filas del asiento las llevan vacías. Es para lo que existe el rol.
    """
    doc, ref = ln.documento or {}, ln.referencia or {}
    det = (detraccion.detraccion if detraccion is not None else None) or {}
    es_total = ln.rol == "tercero"
    return {
        "CTA CONTABLE": ln.cuenta,
        "AÑO Y MES PROCESO": libro.periodo,
        "SUBDIARIO": ln.sub_diario,
        "COMPROBANTE": voucher(ln.correlativo),
        "FECHA DOCUMENTO": doc.get("fecha_emision", "") or ln.fecha,
        "TIPO ANEXO": config.get("tipo_anexo_proveedor") or "",
        "CODIGO PROVEEDOR": cab.contraparte_doc,
        "TIPO DOCUMENTO": doc.get("tipo", ""),
        "NRO DOCUMENTO": numero_del_documento(cab),
        "FECHA VENCIMIENTO": doc.get("fecha_vencimiento", ""),
        "IGV": cab.igv if es_total else "",
        "TASA IGV": con_dos_decimales(ln.tasa_igv) if es_total else "",
        "IMPORTE": ln.importe,
        "CONV": config.get("tipo_conversion") or "",
        "FECHA REGISTRO": ln.fecha,
        "TIPO CAMBIO": ln.tipo_cambio or "",
        # El DOCUMENTO, y el concepto en `GLOSA MOVIMIENTO`: así lo traen los ejemplos oficiales
        # (John, 22-sep-2026). Del 21 al 22-sep las dos dijeron el concepto, por parecer que repetir
        # el tipo y el número gastaba la glosa; el manual dice otra cosa, y manda el manual.
        "GLOSA": glosa_del_documento(ln, cab),
        "DESTINO": destino_de(cab),
        "TIPO DOC REF": ref.get("tipo", ""),
        "NRO DOC REF": ref.get("serie_numero", ""),
        "FECHA DOC REF": ref.get("fecha", ""),
        "CENTRO DE COSTOS": ln.centro_costo or ln.anexo_auxiliar or "",
        "GLOSA MOVIMIENTO": ln.glosa,
        "DOCUMENTO ANULADO": datos.NO_ANULADO,
        "IMPORTACION": "1" if (cab.anio_dua or cab.cod_dep_aduanera) else "0",
        "DEBE / HABER": ln.debe_haber,
        # --- la detracción: en la fila del PROVEEDOR, y sin fila propia (2.5) ---------------------------
        # STARSOFT **no asienta la detracción**: la lleva como datos del documento, en los campos 24, 25, 26, 31,
        # 34 y 35 de su tabla. Por eso una compra con detracción sale con las mismas TRES filas que una sin ella
        # (John, 22-sep-2026, contra el manual), y el traslado a la cuenta de detracciones —que en CONCAR son dos
        # líneas más— no se escribe: lo hace su propio sistema al registrar el depósito. Las líneas siguen
        # existiendo en el asiento del motor, que es el mismo para todos; lo que cambia es lo que este driver
        # proyecta. La bandera va en las TRES filas, no solo en la del proveedor (John, 22-sep-2026).
        "DETRACCION": "1" if detraccion is not None else "0",
        # La constancia del depósito (2.6). Se paga después del registro —«casi pasando el otro mes» (John,
        # 22-sep-2026)—, así que lo normal al exportar el mes es que no exista todavía: en ese caso el NÚMERO sale
        # con el comodín, que lo decide el núcleo y no este driver (`asiento.NUMERO_DETRACCION_PENDIENTE`). La
        # FECHA no tiene comodín: una fecha inventada es peor que ninguna. Hasta la 2.5 las dos iban en blanco.
        "NRO DOC DETRACCION": det.get("nro_constancia", "") if es_total else "",
        "FECHA DETRACCION": det.get("fecha_constancia", "") if es_total else "",
        # El código de SUNAT (`027`), no el interno que CONCAR mapea en su tabla (`02702`): el vídeo dice «el
        # código de la detracción… para indicar el tipo de operación afecta» (10:49), y eso es el Catálogo 54.
        # Los tres van SOLO en la fila del proveedor, como el IGV y su tasa: es para lo que existe el rol.
        "CODIGO DETRACCION": det.get("codigo", "") if es_total else "",
        # Las dos de detracción van con dos decimales y `0.00` donde no aplican —en las otras dos filas y en
        # toda compra sin detracción—, como los ejemplos oficiales.
        "TASA DETRACCION": con_dos_decimales(det.get("tasa")) if es_total else "0.00",
        # Lo DETRAÍDO —«cuánto ha sido el importe que se ha detraído» (10:58)—, que es el importe de la línea que
        # ya no se escribe, no `det["base"]`, que es el total sobre el que se calcula.
        "IMPORTE DETRACCION": con_dos_decimales(
            detraccion.importe if (detraccion is not None and es_total) else None),
        # --- declaradas y vacías: existen y no consta cómo se llenan ------------------------------------
        # `PORC OPE MIXTA` sale con 60 en la captura, en una compra de destino 002 (uso mixto), pero de dónde
        # sale ese 60 no consta: el estándar no tiene el porcentaje de la operación mixta. Van a `0.00` y no
        # vacías porque es lo que escriben los ejemplos oficiales cuando no aplican (John, 22-sep-2026); en
        # VENTAS no, que ahí los suyos van en blanco.
        "PORC OPE MIXTA": "0.00",
        "VALOR CIF": "0.00",
        # `0` = el IGV NO está pendiente de aplicación. Estuvo vacía mientras la única fuente era la narración
        # del vídeo; la captura de la hoja real la muestra con `0` en todas las filas y eso la cerró.
        "IGV POR APLICAR": datos.IGV_NO_PENDIENTE,
    }


def _fila_venta(ln: LineaDiario, cab: Cabecera, libro: Any, config: dict,
                detraccion: LineaDiario | None = None) -> dict[str, Any]:
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
        "FECHA REGISTRO": ln.fecha,
        "TIPO ANEXO": config.get("tipo_anexo_cliente") or "",
        "CODIGO CLIENTE": cab.contraparte_doc,
        "TIPO DOCUMENTO": doc.get("tipo", ""),
        "NRO DOCUMENTO": numero_del_documento(cab),
        "FECHA EMISION": doc.get("fecha_emision", ""),
        "DOC REFERENCIA": ref.get("tipo", ""),
        "NRO DOC REF": ref.get("serie_numero", ""),
        "IGV": cab.igv if es_total else "",
        "TASA IGV": con_dos_decimales(ln.tasa_igv) if es_total else "",
        "IMPORTE": ln.importe,
        "CONV": config.get("tipo_conversion") or "",
        "TIPO CAMBIO": ln.tipo_cambio or "",
        # El DOCUMENTO, y el concepto en `GLOSA MOVIMIENTO`: así lo traen los ejemplos oficiales
        # (John, 22-sep-2026). Del 21 al 22-sep las dos dijeron el concepto, por parecer que repetir
        # el tipo y el número gastaba la glosa; el manual dice otra cosa, y manda el manual.
        "GLOSA": glosa_del_documento(ln, cab),
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
    }


def filas(cab: Cabecera, lineas: list[LineaDiario], libro: Any, config: dict) -> list[dict]:
    """Las líneas de UN comprobante → sus filas.

    Aquí se ven todas las del comprobante, y por eso aquí se decide lo que ninguna línea sabe por su cuenta:

    - **la detracción no se escribe como filas** (2.5). STARSOFT la lleva en campos de la fila del proveedor, así
      que sus dos líneas del asiento —el traslado a la cuenta de detracciones— se apartan y viajan como datos.
      Una compra con detracción sale con las mismas tres filas que una sin ella;
    - **la bandera `DETRACCION` es del COMPROBANTE**, no de la línea: va en las tres, no solo en la del
      proveedor;
    - **y el orden es el de sus ejemplos** —IGV, proveedor, gasto en una compra; cliente, IGV, ingreso en una
      venta—, no el del asiento del motor (`datos.ORDEN_DE_LAS_FILAS`). En ventas coincidían salvo en la NOTA DE
      CRÉDITO, donde al invertirse los sentidos el núcleo la sacaba al revés y el manual la escribe como
      cualquier otra venta."""
    de_la_detraccion = next((ln for ln in lineas if ln.rol == "detraccion"), None)
    del_asiento = [ln for ln in lineas if ln.rol not in ROLES_DE_LA_DETRACCION]
    orden = ORDEN_DE_LAS_FILAS.get(libro.tipo, ())
    del_asiento.sort(key=lambda ln: orden.index(ln.rol) if ln.rol in orden else len(orden))
    return [fila(ln, cab, libro, config, de_la_detraccion) for ln in del_asiento]


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
