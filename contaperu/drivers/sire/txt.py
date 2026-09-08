"""Plantilla `sire`: el archivo de "Reemplazar propuesta" del SIRE según los
anexos oficiales — Anexo 3 de la RS 112-2021 (RVIE, ventas) y Anexo 11 de la
RS 040-2022 (RCE, compras). Referencia: los archivos de estructura que publica SUNAT (plantillas XLSX de
SUNAT) y el manual del SIRE, p. 33.

Diferencias con `ple`: empieza por RUC y un ID libre del generador, periodo
AAAAMM, campo CAR vacío, fechas DD/MM/AAAA y CRLF.

**Contrastado contra un archivo REAL aceptado por SUNAT** (RVIE de julio de
un contribuyente real, 25-ago-2026): cada línea lleva **33 campos y termina en palote**. Los
campos 34-40, que "completa la Administración", NO se mandan — mandarlos vacíos
daba 40 campos por fila, que es exactamente el error 453 "la fila no cumple con
la estructura". En compras (Anexo 11) la nota de SUNAT es distinta: los campos
38-41 "deberán mostrarse vacíos", así que ahí sí van presentes (37 + 4).

Nombre (Tabla 13 / Tabla 6): LE + RUC + AAAAMM + 00 + libro (140400 / 080400)
+ 02 (reemplaza la propuesta) + 1 (operativa) + 1 (con información) + 1 (soles)
+ 2 (generado por el SIRE) + .TXT — y se sube dentro de un ZIP.
"""
from __future__ import annotations

from ... import catalogos as cat
from ...modelo import Comprobante, Libro
from ...formato import (
    Opciones, armar_linea, columnas_igv_compras, fmt_fecha, fmt_monto, fmt_numero, fmt_tc,
    negativo, sanear,
)

NOMBRE = "sire"
# Lo que no se anota en el registro que se declara a SUNAT (hoy: el recibo por
# honorarios). El Excel de CONCAR no declara esto, así que sí los lleva.
EXCLUYE_TIPOS = cat.FUERA_DEL_REGISTRO_SUNAT

# `palote_final=True` y `rvie_vacios=0` salen del archivo REAL que SUNAT aceptó (RVIE de julio
# de un contribuyente real, contrastado el 25-ago-2026): cada línea lleva 33 campos y termina en '|'. Antes
# se mandaban los campos 34-40 vacíos — 40 campos por fila, que es el error 453.
OPCIONES = Opciones(fecha="DD/MM/AAAA", nueva_linea="\r\n", tc_pen="", extension=".TXT")
FORMATOS = {"venta": "sire_rvie", "compra": "sire_rce"}
LIBRO_VENTAS = "140400"
LIBRO_COMPRAS = "080400"
OPORTUNIDAD_REEMPLAZO = "02"


def nombre(libro: Libro, op: Opciones = OPCIONES) -> str:
    codigo = LIBRO_VENTAS if libro.es_venta else LIBRO_COMPRAS
    return f"LE{libro.ruc}{libro.periodo}00{codigo}{OPORTUNIDAD_REEMPLAZO}1112{op.extension}"


def linea(c: Comprobante, libro: Libro, idx: int, op: Opciones = OPCIONES) -> str:
    return linea_rvie(c, libro, idx, op) if libro.es_venta else linea_rce(c, libro, idx, op)


def _cabecera(c: Comprobante, libro: Libro, op: Opciones, vencimiento: bool = True) -> list[str]:
    return [
        libro.ruc,                           # 1 RUC del generador
        sanear(libro.razon_social, op),      # 2 ID (libre, hasta 1500: se usa la razón social)
        libro.periodo,                       # 3 periodo AAAAMM
        "",                                  # 4 CAR SUNAT (vacío en el reemplazo)
        fmt_fecha(c.fecha_emision, op),      # 5 fecha de emisión
        fmt_fecha(c.fecha_vencimiento, op) if vencimiento else "",   # 6 vencimiento / pago
        c.tipo_cp,                           # 7 tipo de comprobante
        sanear(c.serie, op),                 # 8 serie
    ]


def linea_rvie(c: Comprobante, libro: Libro, idx: int, op: Opciones = OPCIONES) -> str:
    """Anexo 3 — 33 campos informados; del 34 al 40 se encarga la Administración.

    El campo 6 (vencimiento) va VACÍO salvo en los tipos que lo exigen: es opcional y así
    lo manda el archivo que SUNAT aceptó, y una fecha de más es una validación de más.
    """
    neg = negativo(c, op)
    m = lambda d, n=neg: fmt_monto(d, op, n)  # noqa: E731
    campos = _cabecera(c, libro, op, vencimiento=c.tipo_cp in cat.EXIGEN_VENCIMIENTO) + [
        fmt_numero(c.numero, op),            # 9 número (o inicial del rango)
        fmt_numero(c.numero_final, op),      # 10 número final del rango
        c.contraparte_tipo_doc,              # 11 tipo de documento del cliente
        sanear(c.contraparte_doc, op),       # 12 número de documento
        sanear(c.contraparte_nombre, op),    # 13 razón social / nombres
        m(c.exportacion),                    # 14 valor facturado de exportación
        m(c.base_gravada),                   # 15 base imponible gravada
        fmt_monto(c.dscto_base, op, True),   # 16 descuento de la base (negativo)
        m(c.igv),                            # 17 IGV / IPM
        fmt_monto(c.dscto_igv, op, True),    # 18 descuento del IGV (negativo)
        m(c.exonerado),                      # 19 exonerado
        m(c.inafecto),                       # 20 inafecto
        m(c.isc),                            # 21 ISC
        m(c.base_ivap),                      # 22 base del IVAP
        m(c.ivap),                           # 23 IVAP
        m(c.icbper),                         # 24 ICBPER
        m(c.otros),                          # 25 otros tributos y cargos
        m(c.total),                          # 26 importe total
        c.moneda,                            # 27 moneda
        fmt_tc(c, op),                       # 28 tipo de cambio
        fmt_fecha(c.ref_fecha, op),          # 29 fecha del comprobante modificado
        c.ref_tipo_cp,                       # 30 tipo del comprobante modificado
        sanear(c.ref_serie, op),             # 31 serie del comprobante modificado
        fmt_numero(c.ref_numero, op),        # 32 número del comprobante modificado
        sanear(c.id_contrato, op),           # 33 identificador del proyecto / contrato
    ] + [""] * op.rvie_vacios                # 34-40 los completa la Administración
    assert len(campos) == 33 + op.rvie_vacios, len(campos)
    return armar_linea(campos, op)


def linea_rce(c: Comprobante, libro: Libro, idx: int, op: Opciones = OPCIONES) -> str:
    """Anexo 11 — 37 campos informados + los 38-41 vacíos (`rce_vacios`).

    OJO: esto NO está contrastado contra un RCE aceptado. Se mandan porque la nota (2)
    del Anexo 11 lo pide de forma explícita ("deberán mostrarse vacíos"), al revés que
    la del Anexo 3 de ventas ("los completa la Administración"), que resultó significar
    que NO se mandan. Si compras devuelve el 453, `rce_vacios=0`.
    """
    neg = negativo(c, op)
    m = lambda d, n=neg: fmt_monto(d, op, n)  # noqa: E731
    campos = _cabecera(c, libro, op) + [
        sanear(c.anio_dua, op),              # 9 año de emisión de la DUA
        fmt_numero(c.numero, op),            # 10 número (o inicial del rango)
        fmt_numero(c.numero_final, op),      # 11 número final del rango
        c.contraparte_tipo_doc,              # 12 tipo de documento del proveedor
        sanear(c.contraparte_doc, op),       # 13 número de documento
        sanear(c.contraparte_nombre, op),    # 14 razón social / nombres
        *columnas_igv_compras(c, op),        # 15-20 base/IGV DG, DGNG, DNG
        m(c.adquisiciones_no_gravadas),      # 21 valor de adquisiciones no gravadas
        m(c.isc),                            # 22 ISC
        m(c.icbper),                         # 23 ICBPER
        m(c.otros),                          # 24 otros tributos y cargos
        m(c.total),                          # 25 importe total
        c.moneda,                            # 26 moneda
        fmt_tc(c, op),                       # 27 tipo de cambio
        fmt_fecha(c.ref_fecha, op),          # 28 fecha del comprobante modificado
        c.ref_tipo_cp,                       # 29 tipo del comprobante modificado
        sanear(c.ref_serie, op),             # 30 serie del comprobante modificado
        sanear(c.cod_dep_aduanera, op),      # 31 código de la dependencia aduanera
        fmt_numero(c.ref_numero, op),        # 32 número del comprobante modificado
        sanear(c.clasif_bienes, op),         # 33 clasificación de bienes y servicios
        sanear(c.id_contrato, op),           # 34 identificador del proyecto (operadores)
        "",                                  # 35 porcentaje de participación
        "",                                  # 36 IMB (Ley 31053)
        "",                                  # 37 CAR original (solo ajustes posteriores)
    ] + [""] * op.rce_vacios                 # 38-41 detracción, tipo de nota, estado, inconsistencias
    assert len(campos) == 37 + op.rce_vacios, len(campos)
    return armar_linea(campos, op)
