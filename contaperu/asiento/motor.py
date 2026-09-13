"""El asiento en líneas neutrales: la contabilidad, sin el vocabulario de ningún ERP.

Aquí vive la LÓGICA del asiento —qué cuentas, qué sentido, cuántas líneas, en qué fecha— y sale ya
en el bloque `asiento` del estándar `open-accounting`. Las reglas, con su fuente al lado, están en el
docstring del paquete (`__init__.py`); este módulo las aplica.

Hasta el 11-sep-2026 esta lógica escribía directamente las columnas del Excel de CONCAR ('A'..'AO')
y la línea neutral se sacaba después, releyendo esas columnas. Era al revés de lo que el proyecto
quiere ser: la línea «neutral» heredaba los cortes de glosa y las siglas de un ERP concreto, y un
segundo driver de asientos habría tenido que reinterpretar columnas de CONCAR. Ahora la línea neutral
es la fuente y CONCAR es una proyección más (`drivers/concar/proyeccion.py`), con prohibido cambiar
una sola celda del Excel validado: lo vigila `tests/test_snapshot_concar.py`.

Lo que la línea sigue llevando de «sistema contable» es contabilidad peruana, no formato de un ERP:
el sub-diario y su correlativo, la cuenta, el centro de costo y en qué línea va. La sigla del
documento (`documento.tipo`) se conserva por compatibilidad —la leían los consumidores de la 0.6—,
pero al lado viaja `tipo_cp`, el código SUNAT, que es el que manda.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..catalogos import TIPO_HONORARIOS, TIPOS_INVIERTEN, TIPOS_NOTA
from ..configuracion import CONFIG_POR_DEFECTO
from ..detracciones import monto_detraccion, tasa_detraccion
from ..formato import Opciones, formatear_numero
from ..igv import base_imputable, igv_del_asiento, tasa_calculada
from ..modelo import CENTIMO, Comprobante, Libro, serie_y_numero, texto_tasa
from .configuracion import NUMERO_DETRACCION_PENDIENTE, TIPO_DOC_DETRACCION
from .faltas import RepartoNoCuadra, SinCuenta
from .resolucion import (cuenta_por_pagar_detraccion, cuenta_tercero, equivalencia_tipo, limites_del_periodo,
                         lleva_centro, numerar, partes_de, reparto_no_cuadra, sigla_documento, sub_diario,
                         tiene_detraccion)
from .lineas import LineaDiario

# El papel de cada línea en el asiento. Es lo que un driver necesita para traducir sin adivinar: un
# ERP que pida el IGV en una columna aparte encuentra esa línea por su rol, no por su cuenta, que la
# elige cada empresa.
ROLES = ("principal", "igv", "retencion_4ta", "tercero", "detraccion_tercero", "detraccion")
# Las líneas que llevan además el centro de costo en su anexo auxiliar. Lo del estándar es la del tercero —el «doble
# anexo», también en la línea que le descuenta la detracción—; cada driver lo cambia con las columnas que su sistema
# elige (`drivers.contrato.centro_en_anexo`). La principal lo lleva ahí solo cuando su cuenta no lo lleva en la suya.
CENTRO_EN_ANEXO = frozenset({"tercero"})


def glosa_de(c: Comprobante) -> str:
    """La glosa del comprobante: su concepto o, si no trae, el nombre de la contraparte —para que
    ninguna línea salga sin glosa—. En mayúsculas y SIN cortar: el largo lo decide cada ERP."""
    return ((c.concepto or "").strip() or (c.contraparte_nombre or "").strip()).upper()


def _iso(fecha: date | None) -> str:
    return fecha.isoformat() if fecha else ""


def _limpio(campos: dict) -> dict:
    """Sin las claves vacías: un documento `open-accounting` no lleva ruido."""
    return {k: v for k, v in campos.items() if v not in ("", None)}


def _detraccion(c: Comprobante, config: dict, total: Decimal) -> dict:
    """El bloque de la línea de detracción: el código SUNAT, el interno del contribuyente (T.G. 28 de
    CONCAR: el de SUNAT + 2 propios, o SUNAT + "01" si no lo configuró), la tasa —la misma con la que
    se calcula el monto, que decide `detracciones.tasa_detraccion`— y el total del documento como base."""
    bloque = c.detraccion or {}
    sunat = str(bloque.get("codigo") or "").strip()
    interno = str((config.get("detraccion_codigos") or {}).get(sunat) or (f"{sunat}01" if sunat else ""))
    tasa = tasa_detraccion(c, config)
    return _limpio({"codigo": sunat, "codigo_interno": interno,
                    "tasa": float(tasa) if tasa > 0 else "", "base": str(total)})


def lineas_del_comprobante(c: Comprobante, config: dict, limites: tuple[date, date], correlativo: str,
                           opciones: Opciones = Opciones(), es_venta: bool = False,
                           centro_en_anexo: frozenset[str] = CENTRO_EN_ANEXO) -> list[LineaDiario]:
    """Un comprobante → sus líneas de diario (de 2 a 5, más una por parte si la base va repartida), en el orden
    del manual de asientos. `centro_en_anexo` dice qué líneas llevan además el centro en su anexo auxiliar
    (`principal`, `tercero`)."""
    moneda = (c.moneda or "PEN").upper()
    # A qué cuentas va la base: lo decide la imputación del documento, que llega aparte (una línea por parte si
    # trae reparto), o lo de siempre (`partes_de`). Una parte sin cuenta detiene el asiento igual que una fila sin
    # ella, y un reparto que no suma la base también: ese asiento no cuadraría.
    partes = partes_de(c, config, es_venta)
    if not all(cuenta for cuenta, _, _ in partes):
        raise SinCuenta([c])
    if reparto_no_cuadra(c, config, es_venta):
        raise RepartoNoCuadra([c])
    es_usd = moneda == "USD"
    es_honorarios = not es_venta and c.tipo_cp == TIPO_HONORARIOS
    invierte = c.tipo_cp in TIPOS_INVIERTEN
    total = Decimal(c.total or 0).quantize(CENTIMO)
    # Compras: boleta y recibo por honorarios no dan crédito fiscal → todo al gasto, sin línea de IGV. En
    # VENTAS la boleta emitida SÍ lleva su IGV (débito fiscal del emisor). La regla vive en `igv.py`: la
    # comprobación de que un reparto cuadra con la base la necesita igual.
    igv = igv_del_asiento(c, es_venta)
    base = base_imputable(c, es_venta)
    ruc = (c.contraparte_doc or "").strip()
    usa_centros = config.get("usa_centros_costo", True)                                   # apagado: sin centro
    # El doble anexo del tercero lleva el centro del comprobante; con la base repartida, solo si todas las
    # partes comparten uno: con dos centros distintos no hay uno que poner.
    centros = {(centro or "").strip() for _, centro, _ in partes}
    centro_comun = (next(iter(centros)) if len(centros) == 1 else "") if usa_centros else ""
    serie, numero = (c.serie or "").strip(), formatear_numero(c.numero, opciones)
    serie_numero = serie_y_numero(serie, numero)
    # UNA sola glosa para todas las líneas (confirmado por un contador, 2026); las derivadas anteponen lo
    # que las identifica —`IGV - `, `RET 4TA - `, `DETRACCION - `—. Cortarla es cosa del driver.
    glosa = glosa_de(c)
    tasa_leida = tasa_calculada(igv, Decimal(c.base_gravada or 0))
    tasa = "" if tasa_leida is None else texto_tasa(tasa_leida)
    tc = float(c.tipo_cambio) if es_usd and c.tipo_cambio else ""
    emision = c.fecha_emision
    vencimiento = c.fecha_vencimiento or emision
    # Cada comprobante se asienta con SU fecha de emisión; el extemporáneo (mes anterior) cae al
    # primer día del periodo, y uno emitido después del periodo (error FECHA_POSTERIOR, que no bloquea
    # el Excel) al último: el asiento cae en el mes de esta fecha y todo debe caer en el mes del
    # proceso (un contador, 30-ago-2026). La fecha del documento se conserva aparte, siempre.
    primero, ultimo = limites
    fecha_asiento = min(max(emision, primero), ultimo) if emision else primero
    # Sentido de la partida: compras = gasto D / proveedor H; ventas = ingreso H / cliente D.
    # La nota de crédito invierte el caso que toque.
    normal = ("H", "D") if es_venta else ("D", "H")
    sentido_base, sentido_tercero = (normal[::-1] if invierte else normal)
    sub_diario_asiento = sub_diario(c, config, es_venta)

    documento = {"tipo": sigla_documento(c, config), "tipo_cp": c.tipo_cp, "serie_numero": serie_numero,
                 "fecha_emision": _iso(emision), "fecha_vencimiento": _iso(vencimiento)}
    referencia: dict[str, str] = {}
    if c.tipo_cp in TIPOS_NOTA and (c.ref_serie or c.ref_numero):
        numero_ref = formatear_numero(c.ref_numero, opciones)
        equivalencia_ref = equivalencia_tipo(c, config, c.ref_tipo_cp)
        referencia = {"tipo": str(equivalencia_ref["sigla"]) if equivalencia_ref else "", "tipo_cp": c.ref_tipo_cp,
                      "serie_numero": serie_y_numero(c.ref_serie, numero_ref),
                      "fecha": _iso(c.ref_fecha)}

    def linea(rol: str, importe: Decimal, cuenta_linea: str, sentido: str, glosa_linea: str = glosa,
              **extra) -> LineaDiario:
        campos = dict(cuenta=cuenta_linea, debe_haber=sentido, importe=str(Decimal(importe).quantize(CENTIMO)),
                      rol=rol, sub_diario=sub_diario_asiento, correlativo=correlativo, fecha=_iso(fecha_asiento),
                      moneda=moneda, tipo_cambio=tc, glosa=glosa_linea, documento=_limpio(documento),
                      referencia=_limpio(referencia), tasa_igv=tasa)
        campos.update(extra)
        return LineaDiario(**campos)

    # Recibo por honorarios con retención de 4ta: el gasto va por el TOTAL, la retención al Haber en
    # su cuenta de tributos, y a la cuenta por pagar solo el NETO que se le paga al profesional (regla
    # de contabilidad). Sin retención —lo normal con suspensión— el total completo va a la cuenta por pagar.
    retenido = Decimal(c.retencion or 0).quantize(CENTIMO) if es_honorarios else Decimal(0)
    if retenido > total:
        retenido = total
    # La CUENTA decide dónde va el centro (el contador, 09-sep-2026): en su línea si la cuenta lo lleva
    # habilitado, y si no, como referencia (anexo auxiliar) cuando el sistema lo elige así. Nunca en los
    # dos. El doble anexo del tercero es otra cosa y no depende de esto.
    def principal(cuenta: str, centro: str, importe: Decimal) -> LineaDiario:   # gasto (compras) / ingreso (ventas)
        centro = (centro or "").strip() if usa_centros else ""
        en_linea = lleva_centro(cuenta, config)
        return linea("principal", importe, cuenta, sentido_base, centro_costo=centro if en_linea else "",
                     anexo_auxiliar=centro if (not en_linea and "principal" in centro_en_anexo) else "")

    principales = [principal(cuenta, centro, base if importe is None else importe)
                   for cuenta, centro, importe in partes]
    linea_igv = (linea("igv", igv, str(config["cuentas"]["igv"]), sentido_base, f"IGV - {glosa}")
                 if igv > 0 else None)
    cuenta_retencion = str((config.get("cuentas") or {}).get("retencion_4ta") or CONFIG_POR_DEFECTO["cuentas"]["retencion_4ta"])
    linea_retencion = (linea("retencion_4ta", retenido, cuenta_retencion, sentido_tercero, f"RET 4TA - {glosa}")
                       if retenido > 0 else None)
    cuenta_del_tercero = cuenta_tercero(c, config, es_venta)
    anexo_tercero = centro_comun if ("tercero" in centro_en_anexo and not es_honorarios) else ""
    # El tercero: el proveedor en compras, el cliente en ventas.
    tercero = linea("tercero", total - retenido, cuenta_del_tercero, sentido_tercero,
                    contraparte_doc=ruc, anexo_auxiliar=anexo_tercero)

    # La detracción, calcada del Excel real validado en CONCAR (2026): el total COMPLETO queda en el
    # proveedor y se añaden DOS líneas por el monto detraído — el proveedor al Debe (se le pagará menos)
    # y la cuenta de detracciones al Haber, con su propio tipo de documento y el comodín 9999999999
    # (la constancia no existe todavía al provisionar). Lo dispara que la factura TENGA detracción, no
    # el sub-diario. Solo compras; el recibo por honorarios nunca.
    linea_detraccion_tercero = linea_detraccion = None
    if not es_venta and not es_honorarios and tiene_detraccion(c):
        _, detraido = monto_detraccion(c, config)
        if detraido > 0:
            linea_detraccion_tercero = linea("detraccion_tercero", detraido, cuenta_del_tercero, sentido_base,
                                             contraparte_doc=ruc, anexo_auxiliar=anexo_tercero)
            # De QUÉ documento sale esta detracción: en una factura, del propio comprobante (lo que
            # CONCAR aceptó). En una NOTA que ya referencia la factura que corrige se RESPETA esa
            # referencia: ningún archivo validado dice otra cosa. Pendiente de una NC real.
            referencia_detraccion = referencia if referencia.get("tipo") else {
                "tipo": sigla_documento(c, config), "tipo_cp": c.tipo_cp,
                "serie_numero": serie_numero, "fecha": _iso(emision)}
            cuenta_detraccion = cuenta_por_pagar_detraccion(config["cuentas"], moneda)
            documento_detraccion = {"tipo": str(config.get("detraccion_tipo_doc") or TIPO_DOC_DETRACCION),
                                    "serie_numero": NUMERO_DETRACCION_PENDIENTE,
                                    "fecha_emision": _iso(emision), "fecha_vencimiento": _iso(vencimiento)}
            linea_detraccion = linea("detraccion", detraido, cuenta_detraccion, sentido_tercero,
                                     f"DETRACCION - {glosa}", contraparte_doc=ruc,
                                     documento=_limpio(documento_detraccion), referencia=_limpio(referencia_detraccion),
                                     detraccion=_detraccion(c, config, total))

    if es_venta and not invierte:
        # Venta normal: cliente (D) · ingreso (H) · IGV (H) — el orden del manual de asientos.
        orden = [tercero, *principales, linea_igv]
    else:
        # Compras (y NC de venta, que invierte): principal · IGV · retención · tercero · detracción.
        orden = [*principales, linea_igv, linea_retencion, tercero, linea_detraccion_tercero, linea_detraccion]
    return [ln for ln in orden if ln is not None]


def lineas_del_libro(libro: Libro, comprobantes: list[Comprobante], config: dict, correlativos: dict[str, int],
                     opciones: Opciones = Opciones(), centro_en_anexo: frozenset[str] = CENTRO_EN_ANEXO,
                     ) -> tuple[list[LineaDiario], dict[str, dict]]:
    """Todos los comprobantes de un libro → sus líneas, numeradas por sub-diario (`MMNNNN`).

    Devuelve también el rango de correlativos que usó cada sub-diario, que es lo que se recuerda
    para proponer el siguiente. Es la entrada de cualquier driver de asientos."""
    es_venta = libro.es_venta
    numeros, rangos = numerar(comprobantes, config, libro.periodo, correlativos, es_venta)
    limites = limites_del_periodo(libro)
    lineas: list[LineaDiario] = []
    for c in comprobantes:
        lineas.extend(lineas_del_comprobante(c, config, limites, numeros[id(c)], opciones, es_venta, centro_en_anexo))
    return lineas, rangos
