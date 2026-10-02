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
# Privados a propósito: la superficie pública de este módulo se congela, y un import no es un nombre que este
# módulo ofrezca. Mismo patrón que `asiento/motor.py` con `clase_de`.
from .modelo import a_decimal as _a_decimal
from .modelo import clave_de as _clave_de
from .modelo import serie_y_numero as _serie_y_numero

TOLERANCIA = cat.TOLERANCIA_IGV

# Plazo para anotar una compra en el Registro de Compras: «el mes de su emisión o del pago del
# Impuesto, según sea el caso, o … los 12 (doce) meses siguientes» (Ley 29215, art. 2, texto del
# D.Leg. 1116). Dentro del plazo no hay observación: el extemporáneo se anota en este periodo y el
# crédito fiscal se ejerce aquí. El D.Leg. 1669 (28-sep-2024) lo baja a 0 meses (electrónicos), 2
# (físicos) y 3 (con detracción), pero rige recién con la R.S. que SUNAT no ha publicado (verificado
# el 12-sep-2026); lo emitido antes de esa vigencia conserva los 12. Ese día cambia esta constante
# y entra la distinción por `origen`/`detraccion`, con su cita al lado.
PLAZO_ANOTACION_MESES = 12


def _cuadra(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCIA


def _meses_hasta(libro: Libro, fecha) -> int:
    """Meses enteros desde el mes de `fecha` hasta el periodo del libro (0 = el mismo mes)."""
    return (libro.anio - fecha.year) * 12 + (libro.mes - fecha.month)


def validar(c: Comprobante, libro: Libro) -> None:
    """Aplica todas las reglas a un comprobante (añade observaciones, no las borra)."""
    def error(codigo: str, texto: str) -> None:
        c.observar(codigo, "error", texto)

    def aviso(codigo: str, texto: str) -> None:
        c.observar(codigo, "aviso", texto)

    # --- Identificación ------------------------------------------------------
    if c.tipo_cp not in cat.TIPOS_CP:
        aviso("TIPO_CP_DESCONOCIDO", f"Tipo de comprobante {c.tipo_cp!r} no está en el catálogo")
    if not c.numero:
        error("NUMERO_FALTA", "Falta el número del comprobante")
    if not c.serie and c.tipo_cp in ("01", "03", "07", "08"):
        error("SERIE_FALTA", "Falta la serie del comprobante")

    # La propuesta del SIRE es el REGISTRO, no el comprobante: trae importes y partes,
    # pero no el detalle. Se avisa aquí para que no se descubra al exportar a CONCAR.
    if c.origen == "sire":
        aviso("SIRE_SIN_DETALLE", "Importado de la propuesta del SIRE: SUNAT da los importes y las partes, "
                                  "pero no el detalle del comprobante (falta el concepto y la cuenta contable)")

    # --- Fechas ---------------------------------------------------------------
    if c.fecha_emision is None:
        error("FECHA_FALTA", "Falta la fecha de emisión")
    else:
        anio_mes = (c.fecha_emision.year, c.fecha_emision.month)
        if anio_mes > (libro.anio, libro.mes):
            error("FECHA_POSTERIOR", f"Emitido el {c.fecha_emision:%d/%m/%Y}, después del periodo {libro.periodo}")
        elif anio_mes < (libro.anio, libro.mes):
            if libro.es_venta:
                # En ventas no hay plazo de anotación: la obligación nace con la emisión (Ley del IGV,
                # art. 4), así que una venta del mes pasado anotada aquí es IGV del mes pasado.
                aviso("PERIODO_ANTERIOR", f"Emitido en {c.fecha_emision:%m/%Y}: en ventas el IGV nace en la fecha de emisión (Ley del IGV, art. 4), no en la de anotación")
            else:
                # Compras: dentro del plazo se anota aquí y no hay nada que observar (PLAZO_ANOTACION_MESES).
                # La referencia es la emisión; en un documento aduanero, la fecha de pago del impuesto
                # («o del pago del Impuesto»), que el RCE lleva en el campo 6.
                fecha_referencia = (c.fecha_vencimiento if c.tipo_cp in cat.ADUANEROS and c.fecha_vencimiento
                                    else c.fecha_emision)
                if _meses_hasta(libro, fecha_referencia) > PLAZO_ANOTACION_MESES:
                    aviso("CREDITO_FISCAL_FUERA_DE_PLAZO", f"Emitido en {c.fecha_emision:%m/%Y}, hace más de {PLAZO_ANOTACION_MESES} meses: fuera del plazo de anotación en el Registro de Compras (Ley 29215, art. 2)")
    if not libro.es_venta:
        # Retención de 4ta: solo existe en el recibo por honorarios y nunca puede
        # pasarse del total (el neto que se paga saldría negativo en el asiento).
        if c.retencion > 0:
            if c.tipo_cp != "02":
                aviso("RETENCION_NO_APLICA", "La retención de 4ta solo se registra en recibos por honorarios; aquí no se usará")
            elif c.retencion > c.total:
                error("RETENCION_MAYOR", f"La retención ({c.retencion}) es mayor que el total del recibo ({c.total})")
            elif c.total > 0:
                # La retención de 4ta es el 8 % del honorario BRUTO. Si el porcentaje sale
                # lejos de 8, casi siempre es que el total quedó con el NETO recibido (que
                # ya tiene la retención descontada): 26.09 sobre 300 da 8.7 %, sobre 326.09 da 8.
                tasa = (c.retencion / c.total * 100).quantize(Decimal("0.01"))
                if abs(tasa - Decimal("8")) > Decimal("0.5"):
                    aviso("RETENCION_TASA", f"La retención es el {tasa} % del total: revisa que el total sea el honorario bruto, no el neto recibido")
        if c.tipo_cp in cat.EXIGEN_VENCIMIENTO and c.fecha_vencimiento is None:
            error("VENCIMIENTO_FALTA", f"El tipo {c.tipo_cp} exige fecha de vencimiento o de pago")
        if c.tipo_cp in cat.ADUANEROS and not c.anio_dua:
            error("ANIO_DUA_FALTA", "Los documentos aduaneros llevan el año de la DUA")

    # --- Contraparte ------------------------------------------------------------
    documento = solo_digitos(c.contraparte_doc) if c.contraparte_tipo_doc in ("1", "6") else c.contraparte_doc
    quien = "cliente" if libro.es_venta else "proveedor"
    if not documento:
        if c.tipo_cp not in cat.SIN_CONTRAPARTE_OK:
            error("CONTRAPARTE_FALTA", f"Falta el documento del {quien}")
        elif libro.es_venta and c.total >= Decimal("700.00") and c.tipo_cp == "03" and not c.numero_final:
            aviso("BOLETA_SIN_DOC", "Boleta de S/ 700 o más sin identificar al cliente (SUNAT la exige)")
    elif c.contraparte_tipo_doc == "6" and not cat.ruc_valido(documento):
        error("RUC_INVALIDO", f"El RUC del {quien} ({c.contraparte_doc}) no es válido")
    elif c.contraparte_tipo_doc == "1" and len(documento) != 8:
        error("DNI_INVALIDO", f"El DNI del {quien} ({c.contraparte_doc}) debe tener 8 dígitos")
    if not libro.es_venta and c.tipo_cp == "03" and c.igv > 0 and c.destino_igv != "DNG":
        aviso("COMPRA_BOLETA", "Boleta de venta recibida: no da crédito fiscal, su IGV es costo. En el lápiz, 'Uso de la compra' → 'Solo para ventas sin IGV'")
    if not c.contraparte_nombre and c.tipo_cp not in cat.SIN_CONTRAPARTE_OK:
        aviso("NOMBRE_FALTA", f"Falta la razón social del {quien}")

    # --- Moneda -------------------------------------------------------------------
    if len(c.moneda) != 3 or not c.moneda.isalpha():
        error("MONEDA_INVALIDA", f"Moneda {c.moneda!r} no es un código ISO")
    elif c.moneda != "PEN" and not c.tipo_cambio:
        error("TC_FALTA", f"Comprobante en {c.moneda}: falta el tipo de cambio (SUNAT lo exige)")

    # --- Importes --------------------------------------------------------------------
    # Un descuadre bloquea, **salvo que el descuadre lo haya escrito SUNAT**. El motor no es el auditor de lo que la
    # Administración ya aceptó: si su propuesta trae una nota de crédito con la base sin declarar —caso real: base 0,
    # IGV 4 546.31 y total 29 803.61—, corregir la copia no cambia el registro, y el arreglo de verdad es que el emisor
    # emita otra nota. Bloquear el mes le pediría al contador algo que no puede hacer, y de paso impediría generar un
    # TXT que sería idéntico al que SUNAT ya tiene. Es el mismo criterio con el que `MEDIO_PAGO_DESCONOCIDO` y
    # `CREDITO_FISCAL_FUERA_DE_PLAZO` son avisos: nadie se queda sin cerrar su mes por algo que no está en su mano.
    #
    # En cualquier otro origen sigue siendo error, y eso es el alcance entero: en un XML, en un PDF o en un dictado el
    # descuadre se corrige ANTES de declarar, así que ahí sí tiene que detener la exportación.
    #
    # OJO al tocar esto: el nivel va en una variable pero **el código queda literal** en la llamada a `c.observar`. El
    # test que comprueba que `PEDIR_A` cubre todos los códigos (`test_diagnosticar.py`) es un `ast.walk` que solo
    # reconoce `error(...)`, `aviso(...)` y `.observar(...)` con el código como primera constante; si el nivel variable
    # se esconde en un helper propio, estos dos códigos se caen de esa comprobación **en verde**.
    de_la_propuesta = c.origen == "sire"
    nivel_descuadre = "aviso" if de_la_propuesta else "error"
    ya_declarado = " — así lo tiene SUNAT en su propuesta, así que no detiene la exportación" if de_la_propuesta else ""
    if c.base_gravada > 0 or c.igv > 0:
        esperado = c.base_gravada * Decimal(cat.TASA_IGV)
        if not _cuadra(c.igv, esperado):
            reducida = next((candidata for candidata in cat.TASAS_IGV_REDUCIDAS
                             if _cuadra(c.igv, c.base_gravada * Decimal(candidata))), None)
            if reducida:
                aviso("IGV_TASA_REDUCIDA", f"IGV al {Decimal(reducida) * 100:.1f} % (tasa reducida); verifica que corresponda")
            else:
                c.observar("IGV_NO_CUADRA", nivel_descuadre,
                           f"IGV {c.igv} no es el 18 % de la base {c.base_gravada} "
                           f"(esperado {esperado:.2f}){ya_declarado}")
    # Sin los descuentos: la base y el IGV ya son netos (estandar/LEEME.md, open-accounting 0.2).
    #
    # Lo no gravado entra por `adquisiciones_no_gravadas` y NO como `exonerado + inafecto`, que es lo que
    # ponia aqui hasta la 3.5.1. Los dos libros no informan lo mismo: el RVIE separa exonerado (campo 19) e
    # inafecto (campo 20), pero el RCE tiene UNA sola columna, «Valor de las adquisiciones no gravadas»
    # (campo 21), y el lector la deja en `valor_no_gravado` porque el archivo no dice cual de los dos es.
    # Sumando solo los otros dos, una compra no gravada daba esperado 0.00 teniendo total: en el enero real
    # de un contribuyente eran **460 de 1116 filas**, el 41 % del mes, todas avisando «no cuadra» por un
    # dato correcto — y el propio texto del aviso ya enumeraba «no gravado» entre los sumandos.
    #
    # La propiedad del modelo decide cual de los dos toca (`valor_no_gravado` si el comprobante lo declara,
    # `exonerado + inafecto` si no), asi que en ventas y en cualquier otro origen esto es **equivalente
    # exacto** y ningun comprobante cambia de veredicto. Y los tres campos NO se suman a la vez a proposito:
    # en el RCE son la misma cosa informada una vez, y sumarlos contaria el importe dos veces en cuanto
    # alguien rellene el desglose a mano. Era ademas el ULTIMO sitio del motor con la cuenta escrita aparte:
    # el driver del SIRE, CONTASIS y la cabecera del asiento ya usaban la propiedad.
    # `dscto_otros` RESTA: es la parte de «otros conceptos» que el registro informa en negativo, o sea un
    # descuento global. Al revés que `dscto_base` y `dscto_igv`, que no tocan el total.
    esperado_total = (
        c.base_gravada + c.igv + c.adquisiciones_no_gravadas + c.exportacion + c.isc
        + c.base_ivap + c.ivap + c.icbper + c.otros - c.dscto_otros
    )
    if not _cuadra(c.total, esperado_total):
        anticipo = Decimal(str(c.datos_originales.get("anticipo") or "0"))
        if anticipo > 0 and _cuadra(c.total, esperado_total - anticipo):
            aviso("ANTICIPO", f"El total descuenta un anticipo de {anticipo}; revisa la base a anotar")
        else:
            c.observar("TOTAL_NO_CUADRA", nivel_descuadre,
                       f"Total {c.total} no cuadra con base + IGV + no gravado + otros "
                       f"({esperado_total:.2f}){ya_declarado}")
    # En una NC los descuentos van con el mismo signo que la base (SIRE, campos 15 y 16): son la parte de la
    # base y del IGV que se informa aparte, así que no pueden pasarlos, o el campo 15 cambiaría de signo.
    if c.es_nota_credito and (c.dscto_base > c.base_gravada or c.dscto_igv > c.igv):
        error("DSCTO_MAYOR_QUE_BASE", f"La parte que va como descuento ({c.dscto_base}; IGV {c.dscto_igv}) no puede "
                                      f"ser mayor que la base ({c.base_gravada}) y el IGV ({c.igv}) de la nota")
    # Un comprobante en cero. Dos avisos y no uno, porque no significan lo mismo:
    #
    # - Si viene de la PROPUESTA DEL SIRE, el cero no puede ser un despiste: **lo escribió SUNAT**. Es como declara los
    #   comprobantes que el contribuyente da de baja —todos los importes en cero, hasta el tipo de cambio— para que el
    #   correlativo no quede con huecos, así que hay que anotarlo igual. El texto lo dice y no traduce nada: se cita el
    #   «Est. Comp» tal como viene, **sin decir qué significa**, porque la norma no publica su tabla de valores.
    # - En cualquier otro origen sigue siendo `TOTAL_CERO`, que es lo que era: un total que quizá falta por rellenar.
    #
    # Y **se le quitó la mordaza `and not c.es_nota`** (3.5.0): una nota en cero no decía nada, así que en un mes real
    # dos notas dadas de baja salían `estado="ok"` sin una palabra. Esa condición venía del commit inicial del núcleo,
    # sin test que la defendiera ni motivo escrito, y una nota en cero merece la misma mirada que una factura en cero.
    if c.total == 0:
        if c.origen == "sire":
            estado = f", con estado «{c.estado_sunat}»" if c.estado_sunat else ""
            aviso("TOTAL_CERO_EN_LA_PROPUESTA",
                  f"SUNAT lo informa con todos los importes en cero{estado}: así declara lo que se da de baja, y el "
                  f"registro lo lleva igual. No pide cuenta ni entra al asiento; si ya no tiene efecto, exclúyelo")
        else:
            aviso("TOTAL_CERO", "Importe total en cero")

    # --- Detracción ------------------------------------------------------------------------------
    # La tasa con la que va a salir, contra la de la tabla del contribuyente para ese código (la anota
    # `detracciones.normalizar`). Si no coinciden, casi siempre es que la IA leyó mal la tasa —John,
    # 10-sep-2026: «la IA lee un 10 % y el código es del 12 %»—. Aviso y no error: la del comprobante
    # puede ser legítima. Desaparece en cuanto se vuelve a elegir el código, que aplica la de la tabla.
    detraccion = c.detraccion if isinstance(c.detraccion, dict) else None
    if detraccion and detraccion.get("porcentaje") not in (None, "") and detraccion.get("_tasa_tabla") not in (None, ""):
        try:
            leida, de_tabla = Decimal(str(detraccion["porcentaje"])), Decimal(str(detraccion["_tasa_tabla"]))
        except Exception:  # noqa: BLE001 — una tasa ilegible no es motivo para romper la validación
            leida = de_tabla = None
        if leida is not None and leida != de_tabla:
            aviso("DETRACCION_TASA_DISTINTA",
                  f"La detracción {detraccion.get('codigo')} va al {format(leida.normalize(), 'f')} % y tu tabla dice "
                  f"{format(de_tabla.normalize(), 'f')} %: si es la de la tabla, vuelve a elegir el código")

    # --- Medio de pago ---------------------------------------------------------------------------
    # El código contra el catálogo de SUNAT (`catalogos.MEDIOS_PAGO`). **Aviso y no error, y el valor se respeta**
    # (John, 25-sep-2026): el medio de pago no cambia ningún asiento ni ningún importe, así que un código que este
    # motor todavía no conoce —SUNAT puede añadir uno— no puede impedirle a nadie cerrar su mes. La forma la cuida
    # el esquema del estándar (tres dígitos); esto cuida el significado.
    if c.medio_pago and c.medio_pago not in cat.MEDIOS_PAGO:
        aviso("MEDIO_PAGO_DESCONOCIDO",
              f"El medio de pago {c.medio_pago} no está en la tabla de SUNAT: sale igual, compruébalo")

    # --- Notas de crédito / débito -------------------------------------------------------
    if c.es_nota:
        if not (c.ref_tipo_cp and c.ref_numero):
            error("NOTA_SIN_REFERENCIA", "La nota no indica el comprobante que modifica (tipo, serie y número)")
        if c.ref_fecha is None:
            error("NOTA_SIN_FECHA_REF", "Falta la fecha del comprobante modificado (el XML no la trae; complétala)")

    # El motivo de la nota, contra el catálogo que le toca (`catalogos.motivos_de_nota`: el 09 si es de crédito, el 10
    # si es de débito). **Aviso y no error, y el valor se respeta**, por lo mismo que el medio de pago: no cambia
    # ningún asiento ni ningún importe, y SUNAT amplía estas tablas —al 09 le añadió cuatro códigos en 2020—, así que
    # un código que este motor no conoce no puede impedirle a nadie cerrar su mes.
    #
    # **No existe un `TIPO_NOTA_FALTA`, y es a propósito**: una nota sin motivo no es un defecto. La norma dice que ese
    # campo «no es considerado para la construcción del archivo de texto», y el propio TXT que este motor genera lo
    # manda vacío, así que avisar de su ausencia observaría el mes entero por un dato que el archivo no pide.
    motivos = cat.motivos_de_nota(c.tipo_cp)
    if c.tipo_nota and motivos and c.tipo_nota not in motivos:
        aviso("TIPO_NOTA_DESCONOCIDO",
              f"El motivo {c.tipo_nota} no está en la tabla de SUNAT para este tipo de nota: sale igual, compruébalo")
    elif c.tipo_nota and not motivos:
        aviso("TIPO_NOTA_NO_APLICA", "Solo una nota de crédito o de débito lleva motivo: en este comprobante se ignora")

    # --- Procedencia -------------------------------------------------------------------------
    if c.origen == "xml":
        emisor = solo_digitos((c.datos_originales.get("emisor") or {}).get("doc", ""))
        adquirente = solo_digitos((c.datos_originales.get("adquirente") or {}).get("doc", ""))
        if libro.es_venta and emisor and emisor != libro.ruc:
            error("XML_DE_OTRO_RUC",
                  f"El XML lo emitió el RUC {emisor}, no {libro.ruc}: no es una venta de este cliente")
        if not libro.es_venta and adquirente and adquirente != libro.ruc:
            error("XML_PARA_OTRO_RUC", f"El XML está emitido al RUC {adquirente}, no a {libro.ruc}: no es una compra de este cliente")
        gratuitas = Decimal(str(c.datos_originales.get("gratuitas") or "0"))
        if gratuitas > 0:
            aviso("GRATUITAS", f"Incluye operaciones gratuitas por {gratuitas} (no van al registro)")
    if c.origen in ("pdf_texto", "vision"):
        # La IA puede confundir emisor y cliente o leer mal un dígito: se avisa, no se bloquea.
        emisor = solo_digitos((c.datos_originales.get("emisor") or {}).get("doc", ""))
        adquirente = solo_digitos((c.datos_originales.get("adquirente") or {}).get("doc", ""))
        if libro.es_venta and len(emisor) == 11 and emisor != libro.ruc:
            aviso("EMISOR_NO_COINCIDE", f"La IA leyó como emisor el RUC {emisor}, no {libro.ruc}: ¿es una venta de este cliente?")
        if not libro.es_venta and len(adquirente) == 11 and adquirente != libro.ruc:
            aviso("ADQUIRENTE_NO_COINCIDE", f"La IA leyó que está emitido al RUC {adquirente}, no a {libro.ruc}: ¿es una compra de este cliente?")
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
                      claves_proceso: Iterable[tuple] = (), sin_contraparte: bool = False) -> int:
    """Marca como `duplicada` la 2.ª y siguientes apariciones de una misma clave
    dentro del lote (o ya guardadas en este proceso: `claves_proceso`), y
    cualquier aparición de una clave ya anotada en OTRO periodo del mismo RUC
    (`claves_previas`; SUNAT la rechazaría: error 452). Las filas excluidas no
    cuentan. Devuelve cuántas marcó.

    Con `sin_contraparte` —en ventas, donde la identidad no lleva al cliente (`estandar/LEEME.md`, «La identidad de un
    comprobante»)— dos comprobantes con el mismo tipo, serie y número son el mismo aunque el cliente difiera."""
    def identidad(clave: tuple) -> tuple:
        return (*tuple(clave)[:3], "") if sin_contraparte else tuple(clave)

    previas = {identidad(k) for k in claves_previas}
    vistas: set[tuple] = {identidad(k) for k in claves_proceso}
    n = 0
    for c in comprobantes:
        if c.excluida:
            continue
        k = identidad(c.clave)
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


def avisar_de_facturas_con_nota(comprobantes: list[Comprobante]) -> int:
    """Avisa en cada factura a la que una NOTA DE CRÉDITO del mismo lote anula su total (5.3). Devuelve cuántas.

    **Es el primer cruce de dos comprobantes del motor**, y hacía falta porque el enlace es de una sola dirección: la
    nota dice a qué factura apunta y la factura no dice nada. Medido sobre un RCE real de setiembre de 2026, **ninguna
    de sus 41 columnas** distingue las cuatro facturas que tienen nota de las otras diecinueve.

    **Avisa y no decide**, que es la diferencia que importa. Que una factura tenga nota de crédito no significa que
    esté anulada: puede ser un descuento, una devolución parcial o una corrección de datos. Lo que sí significa es que
    **conviene mirarla**, porque si está anulada su detracción no debería provisionarse
    (`imputacion.anulada_por_nota`) y, si no se marca, el par deja colgado el recorte y la provisión del depósito.

    Solo cuando el importe de la nota **anula el total exacto**: una nota parcial es otra cosa y la factura conserva
    sus cinco líneas. Los importes del estándar van siempre en positivo, así que se comparan tal cual.

    Y solo mira el lote: una nota del mes siguiente no está aquí, y entonces no hay dato del que deducirlo — el
    contador lo marca a mano, que es para lo que el campo existe."""
    por_identidad = {_clave_de(c.tipo_cp, c.serie, c.numero, c.contraparte_doc): c
                     for c in comprobantes if not c.excluida and not c.es_nota}
    n = 0
    for nota in comprobantes:
        if nota.excluida or not nota.es_nota_credito or not (nota.ref_serie or nota.ref_numero):
            continue
        factura = por_identidad.get(_clave_de(nota.ref_tipo_cp, nota.ref_serie, nota.ref_numero, nota.contraparte_doc))
        if factura is None or _a_decimal(nota.total) != _a_decimal(factura.total):
            continue
        factura.observar(
            "FACTURA_CON_NOTA_DE_CREDITO", "aviso",
            f"La nota de crédito {_serie_y_numero(nota.serie, nota.numero)} de este lote anula su total. Si la "
            "factura quedó anulada, márcala en su imputación (`anulada_por_nota`) para que no provisione su "
            "detracción; si la nota es un descuento o una corrección, déjala como está")
        n += 1
    return n


def revisar(comprobantes: list[Comprobante], libro: Libro, claves_previas: Iterable[tuple] = (),
            claves_proceso: Iterable[tuple] = ()) -> list[Comprobante]:
    """Revisión completa de un lote (idempotente: se puede repetir antes de exportar)."""
    for c in comprobantes:
        c.observaciones = []
        c.estado = "ok"
        validar(c, libro)
    marcar_duplicados(comprobantes, claves_previas, claves_proceso, sin_contraparte=libro.es_venta)
    # Después de marcar duplicados, para no avisar sobre una factura que ya se descartó por repetida.
    if not libro.es_venta:
        avisar_de_facturas_con_nota(comprobantes)
    for c in comprobantes:
        fijar_estado(c)
    return comprobantes
