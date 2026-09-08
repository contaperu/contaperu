"""Reglas de negocio deterministas sobre un `Comprobante` (la IA nunca decide esto).

Cada regla deja una `Observacion` con nivel `error` (bloquea la exportación
hasta corregir o excluir la fila) o `aviso` (se exporta igual, pero el usuario
lo ve). Los códigos son estables: quien los muestre los traduce y los tests los buscan.

`revisar()` es la entrada normal: limpia las observaciones anteriores (todas
son del sistema), valida cada comprobante, marca duplicados dentro del lote y
contra las claves ya anotadas en otros periodos del mismo RUC, y fija `estado`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from . import catalogos as cat
from .modelo import Comprobante, Libro, solo_digitos

TOLERANCIA = Decimal("0.05")


def _cuadra(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCIA


def validar(c: Comprobante, libro: Libro) -> None:
    """Aplica todas las reglas a un comprobante (añade observaciones, no las borra)."""
    e, a = (lambda cod, txt: c.observar(cod, "error", txt)), (lambda cod, txt: c.observar(cod, "aviso", txt))

    # --- Identificación ------------------------------------------------------
    if c.tipo_cp not in cat.TIPOS_CP:
        a("TIPO_CP_DESCONOCIDO", f"Tipo de comprobante {c.tipo_cp!r} no está en el catálogo")
    if not c.numero:
        e("NUMERO_FALTA", "Falta el número del comprobante")
    if not c.serie and c.tipo_cp in ("01", "03", "07", "08"):
        e("SERIE_FALTA", "Falta la serie del comprobante")

    # La propuesta del SIRE es el REGISTRO, no el comprobante: trae importes y partes,
    # pero no el detalle. Se avisa aquí para que no se descubra al exportar a CONCAR.
    if c.origen == "sire":
        a("SIRE_SIN_DETALLE", "Importado de la propuesta del SIRE: SUNAT da los importes y las partes, "
                              "pero no el detalle del comprobante (falta el concepto y la cuenta contable)")

    # --- Fechas ---------------------------------------------------------------
    if c.fecha_emision is None:
        e("FECHA_FALTA", "Falta la fecha de emisión")
    else:
        ym = (c.fecha_emision.year, c.fecha_emision.month)
        if ym > (libro.anio, libro.mes):
            e("FECHA_POSTERIOR", f"Emitido el {c.fecha_emision:%d/%m/%Y}, después del periodo {libro.periodo}")
        elif ym < (libro.anio, libro.mes):
            a("PERIODO_ANTERIOR", f"Emitido en un periodo anterior ({c.fecha_emision:%m/%Y}); se anota como extemporáneo (al Excel de CONCAR va con fecha 01/{libro.mes:02d}/{libro.anio})")
    if not libro.es_venta:
        # Retención de 4ta: solo existe en el recibo por honorarios y nunca puede
        # pasarse del total (el neto que se paga saldría negativo en el asiento).
        if c.retencion > 0:
            if c.tipo_cp != "02":
                a("RETENCION_NO_APLICA", "La retención de 4ta solo se registra en recibos por honorarios; aquí no se usará")
            elif c.retencion > c.total:
                e("RETENCION_MAYOR", f"La retención ({c.retencion}) es mayor que el total del recibo ({c.total})")
            elif c.total > 0:
                # La retención de 4ta es el 8 % del honorario BRUTO. Si el porcentaje sale
                # lejos de 8, casi siempre es que el total quedó con el NETO recibido (que
                # ya tiene la retención descontada): 26.09 sobre 300 da 8.7 %, sobre 326.09 da 8.
                tasa = (c.retencion / c.total * 100).quantize(Decimal("0.01"))
                if abs(tasa - Decimal("8")) > Decimal("0.5"):
                    a("RETENCION_TASA", f"La retención es el {tasa} % del total: revisa que el total sea el honorario bruto, no el neto recibido")
        if c.tipo_cp in cat.EXIGEN_VENCIMIENTO and c.fecha_vencimiento is None:
            e("VENCIMIENTO_FALTA", f"El tipo {c.tipo_cp} exige fecha de vencimiento o de pago")
        if c.tipo_cp in cat.ADUANEROS and not c.anio_dua:
            e("ANIO_DUA_FALTA", "Los documentos aduaneros llevan el año de la DUA")

    # --- Contraparte ------------------------------------------------------------
    doc = solo_digitos(c.contraparte_doc) if c.contraparte_tipo_doc in ("1", "6") else c.contraparte_doc
    quien = "cliente" if libro.es_venta else "proveedor"
    if not doc:
        if c.tipo_cp not in cat.SIN_CONTRAPARTE_OK:
            e("CONTRAPARTE_FALTA", f"Falta el documento del {quien}")
        elif libro.es_venta and c.total >= Decimal("700.00") and c.tipo_cp == "03" and not c.numero_final:
            a("BOLETA_SIN_DOC", "Boleta de S/ 700 o más sin identificar al cliente (SUNAT la exige)")
    elif c.contraparte_tipo_doc == "6" and not cat.ruc_valido(doc):
        e("RUC_INVALIDO", f"El RUC del {quien} ({c.contraparte_doc}) no es válido")
    elif c.contraparte_tipo_doc == "1" and len(doc) != 8:
        e("DNI_INVALIDO", f"El DNI del {quien} ({c.contraparte_doc}) debe tener 8 dígitos")
    if not libro.es_venta and c.tipo_cp == "03" and c.igv > 0 and c.destino_igv != "DNG":
        a("COMPRA_BOLETA", "Boleta de venta recibida: no da crédito fiscal, su IGV es costo. En el lápiz, 'Uso de la compra' → 'Solo para ventas sin IGV'")
    if not c.contraparte_nombre and c.tipo_cp not in cat.SIN_CONTRAPARTE_OK:
        a("NOMBRE_FALTA", f"Falta la razón social del {quien}")

    # --- Moneda -------------------------------------------------------------------
    if len(c.moneda) != 3 or not c.moneda.isalpha():
        e("MONEDA_INVALIDA", f"Moneda {c.moneda!r} no es un código ISO")
    elif c.moneda != "PEN" and not c.tipo_cambio:
        e("TC_FALTA", f"Comprobante en {c.moneda}: falta el tipo de cambio (SUNAT lo exige)")

    # --- Importes --------------------------------------------------------------------
    if c.base_gravada > 0 or c.igv > 0:
        esperado = c.base_gravada * Decimal(cat.TASA_IGV)
        if not _cuadra(c.igv, esperado):
            reducida = next((t for t in cat.TASAS_IGV_REDUCIDAS if _cuadra(c.igv, c.base_gravada * Decimal(t))), None)
            if reducida:
                a("IGV_TASA_REDUCIDA", f"IGV al {Decimal(reducida) * 100:.1f} % (tasa reducida); verifica que corresponda")
            else:
                e("IGV_NO_CUADRA", f"IGV {c.igv} no es el 18 % de la base {c.base_gravada} (esperado {esperado:.2f})")
    esperado_total = (
        c.base_gravada + c.igv + c.exonerado + c.inafecto + c.exportacion + c.isc
        + c.base_ivap + c.ivap + c.icbper + c.otros - c.dscto_base - c.dscto_igv
    )
    if not _cuadra(c.total, esperado_total):
        anticipo = Decimal(str(c.datos_raw.get("anticipo") or "0"))
        if anticipo > 0 and _cuadra(c.total, esperado_total - anticipo):
            a("ANTICIPO", f"El total descuenta un anticipo de {anticipo}; revisa la base a anotar")
        else:
            e("TOTAL_NO_CUADRA", f"Total {c.total} no cuadra con base + IGV + no gravado + otros ({esperado_total:.2f})")
    if c.total == 0 and not c.es_nota:
        a("TOTAL_CERO", "Importe total en cero")

    # --- Notas de crédito / débito -------------------------------------------------------
    if c.es_nota:
        if not (c.ref_tipo_cp and c.ref_numero):
            e("NOTA_SIN_REFERENCIA", "La nota no indica el comprobante que modifica (tipo, serie y número)")
        if c.ref_fecha is None:
            e("NOTA_SIN_FECHA_REF", "Falta la fecha del comprobante modificado (el XML no la trae; complétala)")

    # --- Procedencia -------------------------------------------------------------------------
    if c.origen == "xml":
        emisor = solo_digitos((c.datos_raw.get("emisor") or {}).get("doc", ""))
        adquirente = solo_digitos((c.datos_raw.get("adquirente") or {}).get("doc", ""))
        if libro.es_venta and emisor and emisor != libro.ruc:
            e("XML_DE_OTRO_RUC", f"El XML lo emitió el RUC {emisor}, no {libro.ruc}: no es una venta de este cliente")
        if not libro.es_venta and adquirente and adquirente != libro.ruc:
            e("XML_PARA_OTRO_RUC", f"El XML está emitido al RUC {adquirente}, no a {libro.ruc}: no es una compra de este cliente")
        gratuitas = Decimal(str(c.datos_raw.get("gratuitas") or "0"))
        if gratuitas > 0:
            a("GRATUITAS", f"Incluye operaciones gratuitas por {gratuitas} (no van al registro)")
    if c.origen in ("pdf_texto", "vision"):
        # La IA puede confundir emisor y cliente o leer mal un dígito: se avisa, no se bloquea.
        emisor = solo_digitos((c.datos_raw.get("emisor") or {}).get("doc", ""))
        adquirente = solo_digitos((c.datos_raw.get("adquirente") or {}).get("doc", ""))
        if libro.es_venta and len(emisor) == 11 and emisor != libro.ruc:
            a("EMISOR_NO_COINCIDE", f"La IA leyó como emisor el RUC {emisor}, no {libro.ruc}: ¿es una venta de este cliente?")
        if not libro.es_venta and len(adquirente) == 11 and adquirente != libro.ruc:
            a("ADQUIRENTE_NO_COINCIDE", f"La IA leyó que está emitido al RUC {adquirente}, no a {libro.ruc}: ¿es una compra de este cliente?")
        # Que un comprobante no lleve IGV NO es una observación (regla de contabilidad): la
        # columna "Afecto a IGV" ya lo dice en la propia tabla y se corrige ahí mismo con
        # el desplegable. Avisarlo además convertía en "observado" —el color de "esto
        # necesita que lo mires"— lo que solo era una clasificación correcta y visible.
        # La reclasificación a inafecto sigue haciéndose en `ia.py`: eso evita el error
        # falso de IGV_NO_CUADRA, que es lo que de verdad importaba.
    # La confianza de la IA tampoco es una observación (regla de contabilidad): observado
    # es un campo requerido sin llenar o un dato que no cuadra, no "revísame por si
    # acaso". La confianza ya tiene su propia señal en la aplicación que lo use —el semáforo por fila
    # y el filtro "Baja confianza" leen `confianza` directo— así que avisarla aquí
    # convertía en "observado" comprobantes completos (CONFIANZA_BAJA/_MEDIA fuera).


def marcar_duplicados(comprobantes: Iterable[Comprobante], claves_previas: Iterable[tuple] = (),
                      claves_proceso: Iterable[tuple] = ()) -> int:
    """Marca como `duplicada` la 2.ª y siguientes apariciones de una misma clave
    dentro del lote (o ya guardadas en este proceso: `claves_proceso`), y
    cualquier aparición de una clave ya anotada en OTRO periodo del mismo RUC
    (`claves_previas`; SUNAT la rechazaría: error 452). Las filas excluidas no
    cuentan. Devuelve cuántas marcó."""
    previas = set(claves_previas)
    vistas: set[tuple] = set(claves_proceso)
    n = 0
    for c in comprobantes:
        if c.excluida:
            continue
        k = c.clave
        if k in previas:
            c.estado = "duplicada"
            c.observar("DUPLICADO_PERIODO_ANTERIOR", "error", "Ya fue anotado en otro periodo de este RUC (SUNAT lo rechaza: error 452)")
            n += 1
        elif k in vistas:
            c.estado = "duplicada"
            c.observar("DUPLICADO", "error", "Comprobante repetido en este proceso")
            n += 1
        else:
            vistas.add(k)
    return n


def fijar_estado(c: Comprobante) -> None:
    if c.estado == "duplicada":
        return
    c.estado = "observada" if c.observaciones else "ok"


def revisar(comprobantes: list[Comprobante], libro: Libro, claves_previas: Iterable[tuple] = (),
            claves_proceso: Iterable[tuple] = ()) -> list[Comprobante]:
    """Revisión completa de un lote (idempotente: se puede repetir antes de exportar)."""
    for c in comprobantes:
        c.observaciones = []
        c.estado = "ok"
        validar(c, libro)
    marcar_duplicados(comprobantes, claves_previas, claves_proceso)
    for c in comprobantes:
        fijar_estado(c)
    return comprobantes
