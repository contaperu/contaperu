"""El asiento en líneas neutrales: la contabilidad, sin el vocabulario de ningún ERP.

Aquí vive la LÓGICA del asiento —qué cuentas, qué sentido, cuántas líneas, en qué fecha— y sale ya
en el bloque `asiento` del estándar `pe-ledger`. Las reglas, con su fuente al lado, están en el
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
from decimal import ROUND_HALF_UP, Decimal

from ..detracciones import monto as monto_detraccion
from ..detracciones import tasa as tasa_detraccion
from ..formato import Opciones, fmt_numero
from ..igv import tasa as tasa_de_importes
from ..modelo import Comprobante, Libro
from .construir import (SinCuenta, _cuenta_por_moneda, _mapa, cuenta_de_fila, cuenta_honorarios,
                        lleva_centro, mes_del_libro, numerar, resolve_cxp_account,
                        resolve_cxp_detraccion_account, sub_diario, tiene_detraccion, tipo_concar)
from .datos import (D2, DEFAULTS, NUMERO_DETRACCION_PENDIENTE, OPCIONES, TIPO_BOLETA, TIPO_DOC_DETRACCION,
                    TIPO_HONORARIOS, TIPOS_INVIERTEN, TIPOS_NOTA)
from .lineas import LineaDiario

# El papel de cada línea en el asiento. Es lo que un driver necesita para traducir sin adivinar: un
# ERP que pida el IGV en una columna aparte encuentra esa línea por su rol, no por su cuenta, que la
# elige cada empresa.
ROLES = ("principal", "igv", "retencion_4ta", "tercero", "detraccion_tercero", "detraccion")


def glosa_de(c: Comprobante) -> str:
    """La glosa del comprobante: su concepto o, si no trae, el nombre de la contraparte —para que
    ninguna línea salga sin glosa—. En mayúsculas y SIN cortar: el largo lo decide cada ERP."""
    return ((c.concepto or "").strip() or (c.contraparte_nombre or "").strip()).upper()


def _iso(d: date | None) -> str:
    return d.isoformat() if d else ""


def _texto_tasa(t: Decimal) -> str:
    """18 → «18», 10.5 → «10.5»: la tasa del comprobante a 2 decimales, sin ceros de más."""
    return format(t.quantize(D2, rounding=ROUND_HALF_UP).normalize(), "f")


def _limpio(d: dict) -> dict:
    """Sin las claves vacías: un documento `pe-ledger` no lleva ruido."""
    return {k: v for k, v in d.items() if v not in ("", None)}


def _detraccion(c: Comprobante, contab: dict, total: Decimal) -> dict:
    """El bloque de la línea de detracción: el código SUNAT, el interno del contribuyente (T.G. 28 de
    CONCAR: el de SUNAT + 2 propios, o SUNAT + "01" si no lo configuró), la tasa —la misma con la que
    se calcula el monto, que decide `detracciones.tasa`— y el total del documento como base."""
    d = c.detraccion or {}
    sunat = str(d.get("codigo") or "").strip()
    interno = str((contab.get("detraccion_codigos") or {}).get(sunat) or (f"{sunat}01" if sunat else ""))
    t = tasa_detraccion(c, contab)
    return _limpio({"codigo": sunat, "codigo_interno": interno,
                    "tasa": float(t) if t > 0 else "", "base": str(total)})


def asiento_neutral(c: Comprobante, contab: dict, mes: tuple[date, date], numero_comprobante: str,
                    op: Opciones = OPCIONES, venta: bool = False) -> list[LineaDiario]:
    """Un comprobante → sus líneas de diario (de 2 a 5), en el orden del manual de asientos."""
    moneda = (c.moneda or "PEN").upper()
    cuenta = cuenta_de_fila(c, contab, venta)
    if not cuenta:
        raise SinCuenta([c])
    es_usd = moneda == "USD"
    es_honorarios, es_boleta = (not venta and c.tipo_cp == TIPO_HONORARIOS), (not venta and c.tipo_cp == TIPO_BOLETA)
    invierte = c.tipo_cp in TIPOS_INVIERTEN
    total = Decimal(c.total or 0).quantize(D2)
    # Compras: boleta y recibo por honorarios no dan crédito fiscal → todo al gasto, sin línea
    # de IGV. En VENTAS la boleta emitida SÍ lleva su IGV (débito fiscal del emisor).
    igv = Decimal(0) if (es_boleta or es_honorarios) else Decimal(c.igv or 0).quantize(D2)
    base = (total - igv).quantize(D2)
    ruc = (c.contraparte_doc or "").strip()
    cc = (c.centro_costo or "").strip() if contab.get("usa_centros_costo", True) else ""      # apagado: sin centro
    serie, num = (c.serie or "").strip(), fmt_numero(c.numero, op)
    serie_numero = f"{serie}-{num}" if serie and num else (serie or num)
    # UNA sola glosa para todas las líneas (confirmado por un contador, 2026); las derivadas anteponen lo
    # que las identifica —`IGV - `, `RET 4TA - `, `DETRACCION - `—. Cortarla es cosa del driver.
    glosa = glosa_de(c)
    t = tasa_de_importes(igv, Decimal(c.base_gravada or 0))
    tasa = "" if t is None else _texto_tasa(t)
    tc = float(c.tipo_cambio) if es_usd and c.tipo_cambio else ""
    f_emision = c.fecha_emision
    f_venc = c.fecha_vencimiento or f_emision
    # Cada comprobante se asienta con SU fecha de emisión; el extemporáneo (mes anterior) cae al
    # primer día del periodo, y uno emitido después del periodo (error FECHA_POSTERIOR, que no bloquea
    # el Excel) al último: el asiento cae en el mes de esta fecha y todo debe caer en el mes del
    # proceso (un contador, 30-ago-2026). La fecha del documento se conserva aparte, siempre.
    primero, ultimo = mes
    f_asiento = min(max(f_emision, primero), ultimo) if f_emision else primero
    # Sentido de la partida: compras = gasto D / proveedor H; ventas = ingreso H / cliente D.
    # La nota de crédito invierte el caso que toque.
    normal = ("H", "D") if venta else ("D", "H")
    d_gasto, d_prov = (normal[::-1] if invierte else normal)
    sd = sub_diario(c, contab, venta)

    documento = {"tipo": tipo_concar(c, contab), "tipo_cp": c.tipo_cp, "serie_numero": serie_numero,
                 "fecha_emision": _iso(f_emision), "fecha_vencimiento": _iso(f_venc)}
    referencia: dict[str, str] = {}
    if c.tipo_cp in TIPOS_NOTA and (c.ref_serie or c.ref_numero):
        ref_num = fmt_numero(c.ref_numero, op)
        m_ref = _mapa(c, contab, c.ref_tipo_cp)
        referencia = {"tipo": str(m_ref["concar"]) if m_ref else "", "tipo_cp": c.ref_tipo_cp,
                      "serie_numero": f"{c.ref_serie}-{ref_num}" if c.ref_serie and ref_num else (c.ref_serie or ref_num),
                      "fecha": _iso(c.ref_fecha)}

    def linea(rol: str, importe: Decimal, cuenta_linea: str, sentido: str, glosa_linea: str = glosa,
              **extra) -> LineaDiario:
        campos = dict(cuenta=cuenta_linea, debe_haber=sentido, importe=str(Decimal(importe).quantize(D2)),
                      rol=rol, sub_diario=sd, correlativo=numero_comprobante, fecha=_iso(f_asiento),
                      moneda=moneda, tipo_cambio=tc, glosa=glosa_linea, documento=_limpio(documento),
                      referencia=_limpio(referencia), tasa_igv=tasa)
        campos.update(extra)
        return LineaDiario(**campos)

    # Recibo por honorarios con retención de 4ta: el gasto va por el TOTAL, la retención al Haber en
    # su cuenta de tributos, y a la cuenta por pagar solo el NETO que se le paga al profesional (regla
    # de contabilidad). Sin retención —lo normal con suspensión— el total completo va a la cuenta por pagar.
    retenido = Decimal(c.retencion or 0).quantize(D2) if es_honorarios else Decimal(0)
    if retenido > total:
        retenido = total
    # La CUENTA decide dónde va el centro (el contador, 09-sep-2026): en su línea si la cuenta lo lleva
    # habilitado, y si no, como referencia (anexo auxiliar) cuando el estudio la usa así. Nunca en los
    # dos. El doble anexo del tercero (`cc_en_anexo_auxiliar`) es otra cosa y no depende de esto.
    cc_en_linea = lleva_centro(cuenta, contab)
    principal = linea("principal", base, cuenta, d_gasto,                 # gasto (compras) / ingreso (ventas)
                      centro_costo=cc if cc_en_linea else "",
                      anexo_auxiliar=cc if (not cc_en_linea and contab.get("cc_referencia_en_x")) else "")
    linea_igv = (linea("igv", igv, str(contab["cuentas"]["igv"]), d_gasto, f"IGV - {glosa}")
                 if igv > 0 else None)
    cuenta_ret = str((contab.get("cuentas") or {}).get("retencion_4ta") or DEFAULTS["cuentas"]["retencion_4ta"])
    linea_ret = (linea("retencion_4ta", retenido, cuenta_ret, d_prov, f"RET 4TA - {glosa}")
                 if retenido > 0 else None)
    if venta:
        cuenta_ter = _cuenta_por_moneda(contab["cuentas"].get("clientes"), moneda, DEFAULTS["cuentas"]["clientes"]["PEN"])
    elif es_honorarios:
        cuenta_ter = cuenta_honorarios(contab["cuentas"], moneda)
    else:
        cuenta_ter = resolve_cxp_account(contab["cuentas"], moneda)
    x_ter = cc if (contab.get("cc_en_anexo_auxiliar") and not es_honorarios) else ""
    tercero = linea("tercero", total - retenido, cuenta_ter, d_prov,      # proveedor (compras) / cliente (ventas)
                    contraparte_doc=ruc, anexo_auxiliar=x_ter)

    # La detracción, calcada del Excel real validado en CONCAR (2026): el total COMPLETO queda en el
    # proveedor y se añaden DOS líneas por el monto detraído — el proveedor al Debe (se le pagará menos)
    # y la cuenta de detracciones al Haber, con su propio tipo de documento y el comodín 9999999999
    # (la constancia no existe todavía al provisionar). Lo dispara que la factura TENGA detracción, no
    # el sub-diario. Solo compras; el recibo por honorarios nunca.
    det_tercero = det = None
    if not venta and not es_honorarios and tiene_detraccion(c):
        _, monto_det = monto_detraccion(c, contab)
        if monto_det > 0:
            det_tercero = linea("detraccion_tercero", monto_det, cuenta_ter, d_gasto,
                                contraparte_doc=ruc, anexo_auxiliar=x_ter)
            # De QUÉ documento sale esta detracción: en una factura, del propio comprobante (lo que
            # CONCAR aceptó). En una NOTA que ya referencia la factura que corrige se RESPETA esa
            # referencia: ningún archivo validado dice otra cosa. Pendiente de una NC real.
            ref_det = referencia if referencia.get("tipo") else {
                "tipo": tipo_concar(c, contab), "tipo_cp": c.tipo_cp,
                "serie_numero": serie_numero, "fecha": _iso(f_emision)}
            det = linea("detraccion", monto_det, resolve_cxp_detraccion_account(contab["cuentas"], moneda), d_prov,
                        f"DETRACCION - {glosa}", contraparte_doc=ruc,
                        documento=_limpio({"tipo": str(contab.get("detraccion_tipo_doc") or TIPO_DOC_DETRACCION),
                                           "serie_numero": NUMERO_DETRACCION_PENDIENTE,
                                           "fecha_emision": _iso(f_emision), "fecha_vencimiento": _iso(f_venc)}),
                        referencia=_limpio(ref_det), detraccion=_detraccion(c, contab, total))

    if venta and not invierte:
        # Venta normal: cliente (D) · ingreso (H) · IGV (H) — el orden del manual de asientos.
        orden = [tercero, principal, linea_igv]
    else:
        # Compras (y NC de venta, que invierte): principal · IGV · retención · tercero · detracción.
        orden = [principal, linea_igv, linea_ret, tercero, det_tercero, det]
    return [ln for ln in orden if ln is not None]


def lineas_del_libro(libro: Libro, comprobantes: list[Comprobante], contab: dict,
                     correlativos: dict[str, int], op: Opciones = OPCIONES) -> tuple[list[LineaDiario], dict[str, dict]]:
    """Todos los comprobantes de un libro → sus líneas, numeradas por sub-diario (`MMNNNN`).

    Devuelve también el rango de correlativos que usó cada sub-diario, que es lo que se recuerda
    para proponer el siguiente. Es la entrada de cualquier driver de asientos."""
    venta = libro.es_venta
    numeros, rangos = numerar(comprobantes, contab, libro.periodo, correlativos, venta)
    mes = mes_del_libro(libro)
    lineas: list[LineaDiario] = []
    for c in comprobantes:
        lineas.extend(asiento_neutral(c, contab, mes, numeros[id(c)], op, venta))
    return lineas, rangos
