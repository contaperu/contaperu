"""Un comprobante → una fila del registro de compras o de ventas de CONTASIS.

Cada dato sale de la misma función del núcleo que usa el asiento de CONCAR: la cuenta de la base y el centro de
`asiento.partes_de`, la cuenta del total de `asiento.cuenta_tercero`, la glosa de `asiento.glosa_de`, la división de
la compra de `igv.por_destino` y el porcentaje del IGV de `igv.tasa_legal`. Aquí solo se escribe con el vocabulario
de CONTASIS; las reglas del formato, con su fuente, están en `datos.py`.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ...asiento.configuracion import NUMERO_DETRACCION_PENDIENTE
from ...asiento.resolucion import cuenta_tercero, lleva_centro, partes_de
from ...asiento.motor import glosa_de
from ...configuracion import por_defecto
from ..kit import Opciones, celdas, formatear_numero, negativo
from ...igv import SIN_CREDITO_FISCAL, por_destino, tasa_legal
from ...modelo import CENTIMO, Comprobante, Libro
from . import datos

# Los valores por defecto de la sección de CONTASIS, con sus columnas: el respaldo si la configuración no trae uno.
_POR_DEFECTO = por_defecto(datos.CONFIGURACION, datos.COLUMNAS_ELEGIBLES)


def _importes(c: Comprobante, es_venta: bool) -> dict[str, Decimal]:
    """Los importes de la fila, columna por columna, en la moneda del documento y en positivo."""
    if es_venta:
        return {"I": c.exportacion, "J": c.base_gravada, "K": c.exonerado, "L": c.inafecto, "M": c.isc,
                "N": c.igv, "O": c.otros, "AQ": c.icbper, "P": c.total}
    cargos = {"Q": c.isc, "R": c.otros, "AW": c.icbper, "S": c.total}
    if c.tipo_cp in SIN_CREDITO_FISCAL:
        # Sin crédito fiscal (la boleta; el recibo por honorarios no llega a este archivo): el importe va entero a no
        # gravadas y sin IGV propio. Así llevan sus boletas el registro validado y el asiento (`igv.igv_del_asiento`).
        return {"P": c.total - c.isc - c.otros - c.icbper, **cargos}
    (base_dg, igv_dg), (base_dgng, igv_dgng), (base_dng, igv_dng) = por_destino(c)
    return {"J": base_dg, "K": igv_dg, "L": base_dgng, "M": igv_dgng, "N": base_dng, "O": igv_dng,
            "P": c.adquisiciones_no_gravadas, **cargos}


def _en_soles(importes: dict[str, Decimal], tipo: str, tc: Decimal) -> dict[str, Decimal]:
    """Cada importe × T.C. y el total, total × T.C. (John, 12-sep-2026). Si el redondeo los separa por un céntimo, lo
    absorbe la base —la columna sin IGV de mayor importe— para que la fila siga sumando su total. Un documento que no
    cuadraba en dólares no se toca: no se esconde un descuadre que no es del redondeo."""
    total, igvs = datos.TOTAL[tipo], datos.COLUMNAS_IGV[tipo]
    soles = {k: (v * tc).quantize(CENTIMO, rounding=ROUND_HALF_UP) for k, v in importes.items()}
    partes = [k for k in soles if k != total]
    if sum((importes[k] for k in partes), Decimal(0)) == importes[total]:
        diferencia = soles[total] - sum((soles[k] for k in partes), Decimal(0))
        candidatas = [k for k in partes if k not in igvs and soles[k]] or [k for k in partes if soles[k]]
        if diferencia and candidatas:
            soles[max(candidatas, key=lambda k: abs(soles[k]))] += diferencia
    return soles


def _constancia(c: Comprobante) -> dict[str, Any]:
    """Las columnas U y V: la constancia del depósito de la detracción (2.6).

    CONTASIS es un driver de REGISTRO —no arma el asiento, así que no ve la línea de detracción donde el núcleo ya
    resuelve el comodín—, y por eso lo resuelve aquí sobre el comprobante. Sin detracción las dos van en blanco: la
    columna existe para las compras que la llevan, no para todas.
    """
    det = c.detraccion or {}
    if not str(det.get("codigo") or "").strip():
        return {"U": "", "V": None}
    return {"U": str(det.get("nro_constancia") or "").strip() or NUMERO_DETRACCION_PENDIENTE,
            "V": _fecha(celdas.fecha(str(det.get("fecha_constancia") or ""), None))}


def valores(c: Comprobante, libro: Libro, config: dict, opciones: Opciones = datos.OPCIONES) -> dict[str, Any]:
    """Lo que va en cada columna antes del formato de celda: textos sin rellenar, importes en `Decimal` (en soles y
    con el signo de la nota de crédito) y fechas como `date`. `no_caben` mira aquí los largos."""
    es_venta = libro.es_venta
    cuenta, centro, _ = partes_de(c, config, es_venta)[0]      # una sola parte: el núcleo ya exigió `cuenta_unica`
    # El centro, donde la cuenta lo lleva: la misma regla que pone el centro en la columna M de CONCAR.
    centro = centro if config.get("usa_centros_costo", True) and lleva_centro(cuenta, config) else ""
    # Y el mismo centro en la segunda columna de centro de costos, si la configuración la elige (John, 13-sep-2026).
    elegidas = (config.get("columnas") or {}).get("centro_costo")
    if elegidas is None:
        elegidas = _POR_DEFECTO["columnas"]["centro_costo"]
    centro_2 = centro if "centro_costo_2" in elegidas else ""
    es_usd = c.moneda == "USD"
    importes = _importes(c, es_venta)
    if es_usd and c.tipo_cambio:
        importes = _en_soles(importes, libro.tipo, Decimal(str(c.tipo_cambio)))
    signo = Decimal(-1) if negativo(c, opciones) else Decimal(1)
    importes = {k: v * signo for k, v in importes.items()}
    cuentas = config.get("cuentas") or {}
    nota = c.es_nota
    comunes = {
        "moneda": datos.MONEDAS.get(c.moneda, ""),
        "dolares": c.total * signo if es_usd else None,
        "cambio": (c.tipo_cambio if es_usd else Decimal(1)),
        "condicion": datos.CONDICIONES.get(c.condicion_pago, datos.CONDICION_SIN_DATO),
        "tercero": cuenta_tercero(c, config, es_venta),
        "glosa": glosa_de(c),
        "ref_fecha": c.ref_fecha if nota else None,
        "ref_tipo": c.ref_tipo_cp if nota else "",
        "ref_serie": c.ref_serie if nota else "",
        "ref_numero": formatear_numero(c.ref_numero, opciones) if nota else "",
    }
    if es_venta:
        return {
            "A": c.fecha_emision, "B": c.fecha_vencimiento, "C": c.tipo_cp, "D": c.serie,
            "E": formatear_numero(c.numero, opciones), "F": c.contraparte_tipo_doc, "G": c.contraparte_doc,
            "H": c.contraparte_nombre, **importes,
            "Q": comunes["cambio"], "R": comunes["ref_fecha"], "S": comunes["ref_tipo"], "T": comunes["ref_serie"],
            "U": comunes["ref_numero"], "V": comunes["moneda"], "W": comunes["dolares"], "X": c.fecha_vencimiento,
            "Y": comunes["condicion"], "Z": centro, "AA": centro_2, "AB": cuenta,
            "AC": (cuentas.get("otros_tributos") or "") if importes["O"] else "", "AD": comunes["tercero"],
            # El régimen especial (detracción, percepción, retención) va vacío (John, 12-sep-2026).
            "AE": None, "AF": None, "AG": None, "AH": "", "AI": "", "AJ": None, "AK": "",
            "AL": tasa_legal(c.igv, c.base_gravada), "AM": comunes["glosa"],
            "AN": str(config.get("medio_pago") or _POR_DEFECTO["medio_pago"]), "AO": "", "AP": None,
            "AR": (cuentas.get("icbper") or "") if importes["AQ"] else "",
        }
    return {
        "A": c.fecha_emision, "B": c.fecha_vencimiento, "C": c.tipo_cp, "D": c.serie or c.cod_dep_aduanera,
        "E": c.anio_dua, "F": formatear_numero(c.numero, opciones), "G": c.contraparte_tipo_doc, "H": c.contraparte_doc,
        "I": c.contraparte_nombre, **importes,
        # El no domiciliado va vacío (John, 12-sep-2026: «no pongas nada»). La CONSTANCIA de la detracción sí se
        # escribe desde la 2.6, y revierte esa decisión a petición suya del 22-sep: si el comprobante tiene
        # detracción, su número —o el comodín mientras no se haya depositado— y la fecha del depósito, que va
        # vacía si no consta. Sin detracción, las dos en blanco: son columnas suyas, no de todas las compras.
        "T": "", **_constancia(c), "W": comunes["cambio"],
        "X": comunes["ref_fecha"], "Y": comunes["ref_tipo"], "Z": comunes["ref_serie"], "AA": comunes["ref_numero"],
        "AB": comunes["moneda"], "AC": comunes["dolares"], "AD": c.fecha_vencimiento, "AE": comunes["condicion"],
        "AF": cuenta, "AG": (cuentas.get("otros_tributos") or "") if importes["R"] else "", "AH": comunes["tercero"],
        "AI": centro, "AJ": centro_2,
        "AK": None, "AL": None, "AM": None, "AN": "", "AO": "", "AP": None, "AQ": "",
        "AR": None if c.tipo_cp in SIN_CREDITO_FISCAL else tasa_legal(c.igv, c.base_gravada),
        "AS": comunes["glosa"], "AT": "", "AU": None, "AV": c.clasif_bienes, "AW": importes["AW"],
        "AX": (cuentas.get("icbper") or "") if importes["AW"] else "",
    }


def _fecha(d: date | None) -> datetime | None:
    return celdas.fecha_hora(d)


def fila(c: Comprobante, libro: Libro, config: dict, opciones: Opciones = datos.OPCIONES) -> dict[str, Any]:
    """La fila tal como va a las celdas, por letra: textos rellenos con espacios hasta su largo, fechas como
    `datetime`, importes, tipo de cambio y porcentajes como `float`. Un cero o un dato que no va, `None`: la celda
    queda vacía."""
    tipo = libro.tipo
    crudos = valores(c, libro, config, opciones)
    salida: dict[str, Any] = {}
    for letra, _, clase, largo in datos.COLUMNAS[tipo]:
        valor = crudos.get(letra)
        if clase == datos.TEXTO:
            texto = " ".join(str(valor or "").split())
            if letra in datos.SE_CORTAN[tipo]:
                texto = texto[:largo]
            if not texto:
                vacia = letra in datos.VACIAS_SIN_ESPACIOS[tipo] or letra in datos.SIN_RELLENO[tipo]
                salida[letra] = None if vacia else " " * largo
            else:
                salida[letra] = texto if letra in datos.SIN_RELLENO[tipo] else texto.ljust(largo)
        elif clase == datos.FECHA:
            salida[letra] = _fecha(valor)
        else:
            salida[letra] = None if valor is None or Decimal(valor) == 0 else float(valor)
    return salida


def no_caben(libro: Libro, comprobantes: list[Comprobante], config: dict) -> dict[str, list[Comprobante]]:
    """Lo que el registro de CONTASIS no puede llevar, por motivo (`datos.MOTIVOS`). Un código no se corta: una
    cuenta o una serie cortadas serían otra cuenta y otra serie. Por eso el largo se mira en toda columna de texto
    salvo las que sí se cortan, el nombre y la glosa (`datos.SE_CORTAN`)."""
    tipo = libro.tipo
    opciones = datos.OPCIONES
    salida: dict[str, list[Comprobante]] = {texto: [] for texto in datos.MOTIVOS.values()}
    for c in comprobantes:
        if c.moneda not in datos.MONEDAS:
            salida[datos.MOTIVOS["moneda"]].append(c)
            continue
        if c.moneda == "USD" and not c.tipo_cambio:
            salida[datos.MOTIVOS["cambio"]].append(c)
            continue
        if c.numero_final and formatear_numero(c.numero_final, opciones) != formatear_numero(c.numero, opciones):
            salida[datos.MOTIVOS["rango"]].append(c)
        if c.base_ivap or c.ivap:
            salida[datos.MOTIVOS["ivap"]].append(c)
        crudos = valores(c, libro, config, opciones)
        if any(len(" ".join(str(crudos.get(letra) or "").split())) > largo
               for letra, _, clase, largo in datos.COLUMNAS[tipo]
               if clase == datos.TEXTO and letra not in datos.SE_CORTAN[tipo]):
            salida[datos.MOTIVOS["largo"]].append(c)
    return salida
