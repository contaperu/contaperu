"""La LÓGICA del asiento CONCAR: configuración efectiva, clasificación de cada
comprobante (sigla, sub-diario, cuentas), numeración por sub-diario y las 2-4
filas de la partida doble. Las reglas de negocio y su porqué, en el docstring
del paquete (`__init__.py`).
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..modelo import Comprobante, Libro
from ..formato import Opciones, fmt_numero
from .datos import (COLUMNAS, D2, DEFAULTS, FLAG_CONVERSION, NUMERO_DETRACCION_PENDIENTE, OPCIONES, TIPO_DOC_DETRACCION,
                    TIPO_BOLETA, TIPO_CONVERSION, TIPO_HONORARIOS, TIPOS_INVIERTEN, TIPOS_NOTA)


class SinCuenta(Exception):
    """Comprobantes incluidos sin cuenta contable (ni en la fila ni por defecto en el RUC)."""

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) sin cuenta contable")
        self.comprobantes = comprobantes


class TipoSinMapa(Exception):
    """Comprobantes cuyo tipo SUNAT no tiene sigla/sub-diario de CONCAR configurado."""

    def __init__(self, tipos: list[str]):
        super().__init__("Tipos SUNAT sin código CONCAR: " + ", ".join(tipos))
        self.tipos = tipos


class MonedaSinCodigo(Exception):
    """Comprobantes en una moneda que CONCAR no admite (solo MN y US)."""

    def __init__(self, monedas: list[str]):
        super().__init__("Monedas sin código CONCAR: " + ", ".join(monedas))
        self.monedas = monedas


class CorrelativoFaltante(Exception):
    def __init__(self, sub_diarios: list[str]):
        super().__init__("Falta el correlativo de los sub-diarios " + ", ".join(sub_diarios))
        self.sub_diarios = sub_diarios


# ── Configuración por RUC ─────────────────────────────────────────────────────

def merge_config(defaults: dict, overrides: dict) -> dict:
    """Overrides sobre defaults, dict a dict (un sistema anterior lo hacía a 1 nivel: sobreescribir `cxp.USD`
    borraba `cxp.PEN`; aquí se funde en profundidad)."""
    out: dict = {k: (merge_config(v, {}) if isinstance(v, dict) else v) for k, v in (defaults or {}).items()}
    if not isinstance(overrides, dict):
        return out
    for k, v in overrides.items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = merge_config(out[k], v)
        else:
            out[k] = v
    return out


def config_de(config_cliente: dict | None, config_cuenta: dict | None = None) -> dict:
    """Configuración CONCAR efectiva, del general al particular:

        DEFAULTS (código)  →  la CUENTA (el estudio)  →  el RUC (excepciones)

    La cuenta (`contab_config.config`) vale para todos sus RUCs; el RUC
    (`contab_clientes.config`) sobreescribe solo las claves que difieran y
    hereda el resto — `merge_config` funde en profundidad, así que la cuenta
    puede poner `cxp.PEN` y el RUC solo `cxp.USD` sin borrarse entre ellos."""
    base = merge_config(DEFAULTS, ((config_cuenta or {}).get("concar") or {}))
    return merge_config(base, ((config_cliente or {}).get("concar") or {}))


def etiquetas_sub_diario(contab: dict) -> dict[str, str]:
    """{numero: uso} segun la config vigente, para el modal de exportar y el resumen.
    Si el estudio renumera (honorarios → 33), el 33 sale etiquetado. Dos usos con el
    mismo numero se unen con " · " (p. ej. un CONCAR que no separa la detraccion)."""
    tipos = contab.get("tipos") or {}
    usos = [
        (str(contab.get("sub_diario_ventas") or "05"), "Ventas"),
        (str(contab.get("sub_diario_compras") or "11"), "Compras"),
        (str(contab.get("sub_diario_detraccion") or "").strip(), "Compras con detracción"),
        (str((tipos.get(TIPO_BOLETA) or {}).get("sub_diario") or "").strip(), "Boletas de venta"),
        (str((tipos.get(TIPO_HONORARIOS) or {}).get("sub_diario") or "").strip(), "Recibos por honorarios"),
    ]
    out: dict[str, str] = {}
    for num, uso in usos:
        if not num:
            continue
        out[num] = (out[num] + " · " + uso) if num in out else uso
    return out


def _cuenta_por_moneda(valor: Any, moneda: str, fallback: str) -> str:
    if isinstance(valor, dict):
        return str(valor.get((moneda or "").upper()) or valor.get("PEN") or fallback)
    return str(valor) if valor else fallback


def resolve_cxp_account(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("cxp"), moneda, DEFAULTS["cuentas"]["cxp"]["PEN"])


def resolve_cxp_detraccion_account(cuentas: dict, moneda: str) -> str:
    """La cuenta por pagar de la factura afecta a detracción (421203 en las dos monedas por defecto)."""
    return _cuenta_por_moneda(cuentas.get("cxp_detraccion"), moneda, DEFAULTS["cuentas"]["cxp_detraccion"]["PEN"])


def cuenta_honorarios(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("honorarios"), moneda, DEFAULTS["cuentas"]["honorarios"]["PEN"])


# ── Clasificación de cada comprobante ────────────────────────────────────────

def _mapa(c: Comprobante, contab: dict, tipo: str | None = None) -> dict | None:
    # Solo exige la sigla: el sub-diario tiene general (sub_diario_compras) desde el 29-ago-2026.
    m = (contab.get("tipos") or {}).get(tipo if tipo is not None else c.tipo_cp)
    return m if isinstance(m, dict) and m.get("concar") else None


def tipo_concar(c: Comprobante, contab: dict | None = None) -> str:
    m = _mapa(c, contab or DEFAULTS)
    return str(m["concar"]) if m else ""


def _num(v: Any) -> Decimal:
    try:
        return Decimal(str(v if v not in (None, "") else 0))
    except Exception:
        return Decimal(0)


def tiene_detraccion(c: Comprobante) -> bool:
    d = c.detraccion if isinstance(c.detraccion, dict) else {}
    return bool(str(d.get("codigo") or "").strip()) or _num(d.get("porcentaje")) > 0


def sub_diario(c: Comprobante, contab: dict, venta: bool = False) -> str:
    """Por USO: ventas → sub_diario_ventas; compras con detracción → sub_diario_detraccion;
    un tipo con registro propio (boletas 13, honorarios 15) → el suyo; el resto → sub_diario_compras.
    Estas cuatro fuentes son lo que una aplicación deja configurar."""
    m = _mapa(c, contab)
    if not m:
        return ""
    if venta:
        return str(contab.get("sub_diario_ventas") or DEFAULTS["sub_diario_ventas"])
    sd = str(contab.get("sub_diario_detraccion") or "").strip()
    if sd and c.tipo_cp != TIPO_HONORARIOS and tiene_detraccion(c):
        return sd
    return str(m.get("sub_diario") or contab.get("sub_diario_compras") or DEFAULTS["sub_diario_compras"])


def tipos_sin_mapa(comprobantes: list[Comprobante], contab: dict) -> list[str]:
    """Códigos SUNAT presentes que no tienen sigla/sub-diario de CONCAR (en orden de aparición)."""
    vistos: list[str] = []
    for c in comprobantes:
        if not _mapa(c, contab) and c.tipo_cp not in vistos:
            vistos.append(c.tipo_cp)
    return vistos


def monedas_sin_codigo(comprobantes: list[Comprobante], contab: dict) -> list[str]:
    codigos = contab.get("monedas_codigo") or {}
    vistas: list[str] = []
    for c in comprobantes:
        m = (c.moneda or "PEN").upper()
        if not codigos.get(m) and m not in vistas:
            vistas.append(m)
    return vistas


def cuenta_gasto(c: Comprobante, contab: dict) -> str:
    return (c.cuenta_contable or "").strip() or str((contab.get("cuentas") or {}).get("gasto") or "").strip()


def cuenta_venta(c: Comprobante, contab: dict) -> str:
    """Ventas: la cuenta de ingreso de la fila o la del RUC; a diferencia del gasto,
    aquí SÍ hay un default real (el habitual)."""
    return (c.cuenta_contable or "").strip() or str((contab.get("cuentas") or {}).get("ventas") or DEFAULTS["cuentas"]["ventas"]).strip()


def sub_diarios_presentes(comprobantes: list[Comprobante], contab: dict, venta: bool = False) -> dict[str, int]:
    """{sub_diario: cuántos comprobantes} en el orden en que aparecen."""
    out: dict[str, int] = {}
    for c in comprobantes:
        s = sub_diario(c, contab, venta)
        if s:
            out[s] = out.get(s, 0) + 1
    return out


def filas_sin_cuenta(comprobantes: list[Comprobante], contab: dict, venta: bool = False) -> list[Comprobante]:
    if venta:
        return [c for c in comprobantes if not cuenta_venta(c, contab)]
    return [c for c in comprobantes if not cuenta_gasto(c, contab)]


def filas_sin_centro(comprobantes: list[Comprobante], contab: dict) -> list[Comprobante]:
    """Con `usa_centros_costo` encendido, el centro de costo es OBLIGATORIO en el Excel (el contador,
    06-sep-2026): CONCAR lo pide en la columna M de la línea principal, compras y ventas.
    Apagado, ni se exige ni se exporta (M y X van vacías)."""
    if not contab.get("usa_centros_costo", True):
        return []
    return [c for c in comprobantes if not (c.centro_costo or "").strip()]


def nombre(libro: Libro, op: Opciones = OPCIONES) -> str:
    return f"CONCAR_{libro.ruc}_{libro.periodo}_{'VENTAS' if libro.es_venta else 'COMPRAS'}{op.extension}"


# ── Numeración: MM + correlativo de 4 dígitos por sub-diario ──────────────────

def numerar(comprobantes: list[Comprobante], contab: dict, periodo: str,
            correlativos: dict[str, int], venta: bool = False) -> tuple[dict[int, str], dict[str, dict]]:
    """Asigna a cada comprobante (por `id()` del objeto) su número `MMNNNN`, en el orden
    recibido (el natural del registro). Devuelve también el rango usado por sub-diario,
    que es lo que se recuerda para proponer el siguiente."""
    mes_mm = str(periodo)[4:6]
    sin_mapa = tipos_sin_mapa(comprobantes, contab)
    if sin_mapa:
        raise TipoSinMapa(sin_mapa)
    presentes = sub_diarios_presentes(comprobantes, contab, venta)
    faltan = [s for s in presentes if s not in correlativos]
    if faltan:
        raise CorrelativoFaltante(faltan)
    contadores = {s: int(correlativos[s]) for s in presentes}
    if any(n < 1 for n in contadores.values()):
        raise ValueError("Los correlativos empiezan en 1")
    numeros: dict[int, str] = {}
    rangos: dict[str, dict] = {s: {"desde": n, "hasta": n - 1, "n": 0} for s, n in contadores.items()}
    for c in comprobantes:
        s = sub_diario(c, contab, venta)
        n = contadores[s]
        numeros[id(c)] = f"{mes_mm}{n:04d}"
        rangos[s]["hasta"] = n
        rangos[s]["n"] += 1
        contadores[s] = n + 1
    for s, r in rangos.items():
        r["desde_cod"], r["hasta_cod"] = f"{mes_mm}{r['desde']:04d}", f"{mes_mm}{r['hasta']:04d}"
        r["desborda"] = r["hasta"] > 9999
    return numeros, rangos


# ── El asiento ───────────────────────────────────────────────────────────────

def tasa_igv(igv: Decimal, base_gravada: Decimal, respaldo: Any = 18) -> Any:
    """Columna AO: CONCAR admite 0, 10 y 18. Se deriva de IGV/base gravada (10.5 % de
    restaurantes → 10); sin IGV va vacía (así lo lleva un registro real)."""
    if igv <= 0:
        return ""
    if base_gravada <= 0:
        return int(respaldo or 18)
    ratio = igv / base_gravada * 100
    return 10 if abs(ratio - Decimal("10.5")) <= Decimal("1.5") or abs(ratio - 10) <= 1 else \
        (18 if abs(ratio - 18) <= Decimal("1.5") else int(ratio.to_integral_value(rounding=ROUND_HALF_UP)))


def _detraccion_cols(c: Comprobante, contab: dict, total: Decimal, es_usd: bool) -> dict[str, Any]:
    """Columnas AI–AL de la LÍNEA DE DETRACCIÓN (421203, tipo DT) de la factura afecta:
    código interno de la T.G. 28, tasa y el total del documento como base."""
    if not tiene_detraccion(c) or c.tipo_cp == TIPO_HONORARIOS:
        return {}
    d = c.detraccion or {}
    sunat = str(d.get("codigo") or "").strip()
    interno = str((contab.get("detraccion_codigos") or {}).get(sunat) or (f"{sunat}01" if sunat else ""))
    tasa = _num(d.get("porcentaje"))
    if tasa <= 0 and sunat:
        tasa = _num((contab.get("detraccion_tasas") or {}).get(sunat))
    return {"AI": interno, "AJ": float(tasa) if tasa > 0 else "",
            "AK": float(total) if es_usd else "", "AL": float(total) if not es_usd else ""}


def _monto_detraccion(c: Comprobante, contab: dict, total: Decimal, tc, es_usd: bool) -> tuple[Decimal, Decimal]:
    """El monto de la detracción (Excel real validado en CONCAR, 2026): total × tasa en SOLES ENTEROS —
    la detracción se deposita en soles (4 956 × 4 % = 198.24 → 198). En dólares la base se convierte
    con el T.C. del comprobante y el monto vuelve a dólares para la línea, porque el asiento va en US.
    Devuelve (soles, en la moneda del comprobante); (0, 0) si no hay tasa o falta el T.C."""
    d = c.detraccion if isinstance(c.detraccion, dict) else {}
    sunat = str(d.get("codigo") or "").strip()
    tasa = _num(d.get("porcentaje"))
    if tasa <= 0 and sunat:
        tasa = _num((contab.get("detraccion_tasas") or {}).get(sunat))
    if tasa <= 0 or (es_usd and not tc):
        return Decimal(0), Decimal(0)
    tasa = Decimal(str(tasa))
    cambio = Decimal(str(tc)) if es_usd else Decimal(1)
    base_soles = (total * cambio).quantize(D2, rounding=ROUND_HALF_UP)
    soles = (base_soles * tasa / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    en_moneda = (soles / cambio).quantize(D2, rounding=ROUND_HALF_UP) if es_usd else soles
    return soles, en_moneda


def asiento(c: Comprobante, contab: dict, mes: tuple[date, date], numero_comprobante: str,
            op: Opciones = OPCIONES, venta: bool = False) -> list[dict[str, Any]]:
    moneda = (c.moneda or "PEN").upper()
    moneda_code = (contab.get("monedas_codigo") or {}).get(moneda)
    if not moneda_code:
        raise MonedaSinCodigo([moneda])
    cuenta = cuenta_venta(c, contab) if venta else cuenta_gasto(c, contab)
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
    cc = (c.centro_costo or "").strip() if contab.get("usa_centros_costo", True) else ""      # apagado: M y X van vacías
    serie, num = (c.serie or "").strip(), fmt_numero(c.numero, op)
    serie_numero = f"{serie}-{num}" if serie and num else (serie or num)
    glosa = ((c.concepto or "").strip() or (c.contraparte_nombre or "").strip()).upper()
    tasa = tasa_igv(igv, Decimal(c.base_gravada or 0), contab.get("tasa_igv", 18))
    tc = c.tipo_cambio if es_usd and c.tipo_cambio else None
    f_emision = c.fecha_emision
    f_venc = c.fecha_vencimiento or f_emision
    # D y J (compras Y ventas): cada comprobante se
    # asienta con SU fecha de emisión; el extemporáneo (mes anterior) cae al
    # primer día del periodo, y un emitido después del periodo (error
    # FECHA_POSTERIOR, que no bloquea el Excel) al último día — en CONCAR el
    # asiento cae en el mes de esta fecha y todo debe caer en el mes del proceso.
    # T (Fecha de Documento) y U (Vencimiento) siguen siendo las del documento.
    primero, ultimo = mes
    f_asiento = min(max(f_emision, primero), ultimo) if f_emision else primero
    # Sentido de la partida: compras = gasto D / proveedor H; ventas = ingreso H / cliente D.
    # La nota de crédito invierte el caso que toque.
    normal = ("H", "D") if venta else ("D", "H")
    d_gasto, d_prov = (normal[::-1] if invierte else normal)

    def fila_base(importe: Decimal) -> dict[str, Any]:
        f = {col: "" for col in COLUMNAS}
        f.update({
            "B": sub_diario(c, contab, venta), "C": numero_comprobante, "D": f_asiento, "E": moneda_code,
            "F": glosa[:40], "G": float(tc) if tc else "", "H": "C" if tc else TIPO_CONVERSION,
            "I": FLAG_CONVERSION, "J": f_asiento,
            "O": float(importe), "P": float(importe) if es_usd else "", "Q": float(importe) if not es_usd else "",
            "R": tipo_concar(c, contab), "S": serie_numero[:20], "T": f_emision, "U": f_venc, "W": glosa[:30], "AO": tasa,
        })
        if c.tipo_cp in TIPOS_NOTA and (c.ref_serie or c.ref_numero):
            ref_num = fmt_numero(c.ref_numero, op)
            ref = f"{c.ref_serie}-{ref_num}" if c.ref_serie and ref_num else (c.ref_serie or ref_num)
            m_ref = _mapa(c, contab, c.ref_tipo_cp)
            f.update({"Z": str(m_ref["concar"]) if m_ref else "", "AA": ref[:20], "AB": c.ref_fecha or ""})
        return f

    # Recibo por honorarios con retención de 4ta: el gasto va por el TOTAL, la
    # retención al Haber en su cuenta de tributos, y a la cuenta por pagar solo el
    # NETO que se le paga al profesional (regla de contabilidad). Sin retención
    # -lo normal con suspensión-, el total completo va a la cuenta por pagar.
    retenido = Decimal(c.retencion or 0).quantize(D2) if es_honorarios else Decimal(0)
    if retenido > total:
        retenido = total
    filas = []
    principal = fila_base(base)                    # gasto (compras) / ingreso por venta (ventas)
    principal.update({"K": cuenta, "M": cc, "N": d_gasto})
    fila_igv = None
    if igv > 0:
        fila_igv = fila_base(igv)
        fila_igv.update({"K": str(contab["cuentas"]["igv"]), "W": f"IGV - {glosa}"[:30], "N": d_gasto})
    fila_ret = None
    if retenido > 0:
        fila_ret = fila_base(retenido)
        fila_ret.update({"K": str((contab.get("cuentas") or {}).get("retencion_4ta") or DEFAULTS["cuentas"]["retencion_4ta"]),
                         "W": f"RET 4TA - {glosa}"[:30], "N": d_prov})
    tercero = fila_base(total - retenido)          # proveedor (compras) / cliente (ventas)
    if venta:
        cuenta_ter = _cuenta_por_moneda(contab["cuentas"].get("clientes"), moneda, DEFAULTS["cuentas"]["clientes"]["PEN"])
    elif es_honorarios:
        cuenta_ter = cuenta_honorarios(contab["cuentas"], moneda)
    else:
        cuenta_ter = resolve_cxp_account(contab["cuentas"], moneda)
    x_ter = cc if (contab.get("cc_en_anexo_auxiliar") and not es_honorarios) else ""
    tercero.update({"K": cuenta_ter, "L": ruc, "N": d_prov, "X": x_ter})
    # La detracción, calcada del Excel real validado en CONCAR (2026): el total COMPLETO
    # queda en el proveedor (421201/421202) y se añaden DOS líneas por el monto detraído — el proveedor
    # al Debe (se le pagará menos) y la cuenta de detracciones (Configuración → Por pagar →
    # «Detracciones», 421203 en las dos monedas) al Haber, con tipo DT, el comodín 9999999999 (la
    # constancia no se conoce al provisionar), la glosa «DETRACCION - …» y las columnas AI–AL.
    # Lo dispara que la factura TENGA detracción, no el sub-diario: la empresa que lo lleva todo en el
    # 11 hace el mismo asiento. Solo compras; el recibo por honorarios nunca. (Reemplaza la regla del
    # 05-sep, que mandaba el total entero a 421203.)
    fila_det_prov = fila_det = None
    if not venta and not es_honorarios and tiene_detraccion(c):
        _, monto_det = _monto_detraccion(c, contab, total, tc, es_usd)
        if monto_det > 0:
            fila_det_prov = fila_base(monto_det)
            fila_det_prov.update({"K": cuenta_ter, "L": ruc, "N": d_gasto, "X": x_ter})
            fila_det = fila_base(monto_det)
            fila_det.update({"K": resolve_cxp_detraccion_account(contab["cuentas"], moneda), "L": ruc, "N": d_prov,
                             "R": TIPO_DOC_DETRACCION, "S": NUMERO_DETRACCION_PENDIENTE,
                             "W": f"DETRACCION - {glosa}"[:30], "M": "", "X": "",
                             **_detraccion_cols(c, contab, total, es_usd)})
    if venta and not invierte:
        # Venta normal: cliente (D) · ingreso (H) · IGV (H)  — el orden del manual de asientos
        filas.append(tercero)
        filas.append(principal)
        if fila_igv is not None:
            filas.append(fila_igv)
    else:
        # Compras (y NC de venta, que invierte): principal · IGV · retención · tercero
        filas.append(principal)
        if fila_igv is not None:
            filas.append(fila_igv)
        if fila_ret is not None:
            filas.append(fila_ret)
        filas.append(tercero)
        if fila_det_prov is not None:
            filas.append(fila_det_prov)
            filas.append(fila_det)
    return filas


def mes_del_libro(libro: Libro) -> tuple[date, date]:
    """El primer y el ultimo dia del periodo del libro.

    Es el marco dentro del que cae la fecha de cada asiento: un comprobante extemporaneo
    (emitido en un mes anterior) se asienta el dia 1, y uno posterior, el ultimo dia. La
    fecha del documento se conserva aparte, siempre."""
    return (date(libro.anio, libro.mes, 1),
            date(libro.anio, libro.mes, calendar.monthrange(libro.anio, libro.mes)[1]))
