"""Driver `sire`: el archivo de "Reemplazar propuesta" del SIRE según los
anexos oficiales — Anexo 3 de la RS 112-2021 (RVIE, ventas) y Anexo 11 de la
RS 040-2022 (RCE, compras). Referencia: los archivos de estructura que publica SUNAT (plantillas XLSX de
SUNAT) y el manual del SIRE, p. 33.

Lo que lo distingue: empieza por RUC y un ID libre del generador, periodo
AAAAMM, campo CAR vacío, fechas DD/MM/AAAA y CRLF.

**Contrastado contra un archivo REAL aceptado por SUNAT** (RVIE de julio de
un contribuyente real, 25-ago-2026): cada línea lleva **33 campos y termina en palote**. Los
campos 34-40, que "completa la Administración", NO se mandan — mandarlos vacíos
daba 40 campos por fila, que es exactamente el error 453 "la fila no cumple con
la estructura". En compras (Anexo 11) la nota de SUNAT es distinta: los campos
38-41 "deberán mostrarse vacíos", así que ahí sí van presentes (37 + 4), y así salió
idéntico al RCE real presentado del mismo mes (contrastado el 27-ago-2026).

Nombre (Tabla 13 / Tabla 6): LE + RUC + AAAAMM + 00 + libro (140400 / 080400)
+ 02 (reemplaza la propuesta) + 1 (operativa) + 1 (con información) + 1 (soles)
+ 2 (generado por el SIRE) + .TXT — y se sube dentro de un ZIP.
"""
from __future__ import annotations

from ... import catalogos as cat
from ...asiento.faltas import NoExportable
from ...igv import por_destino
from ...modelo import Comprobante, Libro
from ..kit import (
    Opciones, armar_linea, formatear_fecha, formatear_monto, formatear_numero, formatear_cambio, negativo, sanear,
)

NOMBRE = "sire"
# Un registro que se presenta a SUNAT (`drivers.contrato.CANALES`).
CANAL = "tributario"
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


class CampoCambiaDeSigno(NoExportable):
    """Una nota de crédito cuyo descuento es mayor que su base (`DSCTO_MAYOR_QUE_BASE`): el campo 15 o el 17 del RVIE
    saldría en positivo, y SUNAT lo leería como una venta. No se escribe; `comprobantes` trae la nota."""

    clave = "campo_cambia_de_signo"

    def __init__(self, c: Comprobante):
        super().__init__(f"{c.serie}-{c.numero}: DSCTO_MAYOR_QUE_BASE (el campo 15 o el 17 del RVIE cambiaría de signo)",
                         [c])


def _exigir_campos(campos: list[str], esperados: int, registro: str) -> None:
    """Cada línea lleva exactamente los campos de su anexo. Si no, es un error del driver, no del comprobante."""
    if len(campos) != esperados:
        raise RuntimeError(f"La línea del {registro} salió con {len(campos)} campos y lleva {esperados}")


def columnas_igv_compras(c: Comprobante, opciones: Opciones) -> list[str]:
    """Las 6 columnas de base/IGV de compras según el destino de la adquisición:
    DG (gravadas), DGNG (gravadas y no gravadas), DNG (no gravadas). La división es de `igv.por_destino`;
    aquí solo se escribe, con el signo de la nota de crédito."""
    neg = negativo(c, opciones)
    return [formatear_monto(v, opciones, neg) for pareja in por_destino(c) for v in pareja]


def nombre(libro: Libro, opciones: Opciones = OPCIONES) -> str:
    """El nombre oficial del TXT. **Es el ÚNICO driver que no usa `kit.nombre_de_archivo`**, y no es un olvido.

    Dos razones independientes, cualquiera de las dos basta:

    1. **Lo impone SUNAT** (Tablas 6 y 13, arriba). Con otro nombre el SIRE rechaza el archivo, y el error parece
       de SUNAT y no nuestro.
    2. **El propio motor lo lee**: `comparar_sire.registro_de()` deduce si un archivo es de ventas o de compras
       buscando `1404`/`0804` EN EL NOMBRE, «más fiable que contar campos». Renombrarlo lo dejaría ciego.

    Si algún día alguien unifica esto «por coherencia», que lo deshaga después de leer estas dos líneas.
    """
    codigo = LIBRO_VENTAS if libro.es_venta else LIBRO_COMPRAS
    return f"LE{libro.ruc}{libro.periodo}00{codigo}{OPORTUNIDAD_REEMPLAZO}1112{opciones.extension}"


def linea(c: Comprobante, libro: Libro, idx: int, opciones: Opciones = OPCIONES) -> str:
    return linea_rvie(c, libro, idx, opciones) if libro.es_venta else linea_rce(c, libro, idx, opciones)


def _cabecera(c: Comprobante, libro: Libro, opciones: Opciones, vencimiento: bool = True) -> list[str]:
    return [
        libro.ruc,                           # 1 RUC del generador
        sanear(libro.razon_social, opciones),      # 2 ID (libre, hasta 1500: se usa la razón social)
        libro.periodo,                       # 3 periodo AAAAMM
        "",                                  # 4 CAR SUNAT (vacío en el reemplazo)
        formatear_fecha(c.fecha_emision, opciones),      # 5 fecha de emisión
        formatear_fecha(c.fecha_vencimiento, opciones) if vencimiento else "",   # 6 vencimiento / pago
        c.tipo_cp,                           # 7 tipo de comprobante
        sanear(c.serie, opciones),                 # 8 serie
    ]


def _firmado(v, opciones: Opciones) -> str:
    return formatear_monto(abs(v), opciones, v < 0)


def linea_rvie(c: Comprobante, libro: Libro, idx: int, opciones: Opciones = OPCIONES) -> str:
    """Anexo 3 — 33 campos informados; del 34 al 40 se encarga la Administración.

    El campo 6 (vencimiento) va VACÍO salvo en los tipos que lo exigen: es opcional y así
    lo manda el archivo que SUNAT aceptó, y una fecha de más es una validación de más.
    """
    neg = negativo(c, opciones)
    m = lambda d, n=neg: formatear_monto(d, opciones, n)  # noqa: E731
    # Base e IGV son netos y los descuentos, la parte que el registro informa aparte (estandar/LEEME.md). El
    # total es la suma con signo de los campos —así viene en la exportación real de SUNAT—, de modo que el 15
    # lleva la base más lo que se informa en el 16 (s·base + descuento, con s el signo de la operación): una NC
    # de descuento entera escribe 15 = 0 y 16 = −base, como la registra SUNAT, y no la cuenta dos veces.
    s = -1 if neg else 1
    base15, igv17 = s * c.base_gravada + c.dscto_base, s * c.igv + c.dscto_igv
    if neg:
        if base15 > 0 or igv17 > 0:
            raise CampoCambiaDeSigno(c)
    campos = _cabecera(c, libro, opciones, vencimiento=c.tipo_cp in cat.EXIGEN_VENCIMIENTO) + [
        formatear_numero(c.numero, opciones),            # 9 número (o inicial del rango)
        formatear_numero(c.numero_final, opciones),      # 10 número final del rango
        c.contraparte_tipo_doc,              # 11 tipo de documento del cliente
        sanear(c.contraparte_doc, opciones),       # 12 número de documento
        sanear(c.contraparte_nombre, opciones),    # 13 razón social / nombres
        m(c.exportacion),                    # 14 valor facturado de exportación
        _firmado(base15, opciones),                # 15 base imponible gravada (s·base + descuento)
        formatear_monto(c.dscto_base, opciones, True),   # 16 descuento de la base (negativo)
        _firmado(igv17, opciones),                 # 17 IGV / IPM (s·igv + descuento)
        formatear_monto(c.dscto_igv, opciones, True),    # 18 descuento del IGV (negativo)
        m(c.exonerado),                      # 19 exonerado
        m(c.inafecto),                       # 20 inafecto
        m(c.isc),                            # 21 ISC
        m(c.base_ivap),                      # 22 base del IVAP
        m(c.ivap),                           # 23 IVAP
        m(c.icbper),                         # 24 ICBPER
        m(c.otros),                          # 25 otros tributos y cargos
        m(c.total),                          # 26 importe total
        c.moneda,                            # 27 moneda
        formatear_cambio(c, opciones),                       # 28 tipo de cambio
        formatear_fecha(c.ref_fecha, opciones),          # 29 fecha del comprobante modificado
        c.ref_tipo_cp,                       # 30 tipo del comprobante modificado
        sanear(c.ref_serie, opciones),             # 31 serie del comprobante modificado
        formatear_numero(c.ref_numero, opciones),        # 32 número del comprobante modificado
        sanear(c.id_contrato, opciones),           # 33 identificador del proyecto / contrato
    ] + [""] * opciones.rvie_vacios                # 34-40 los completa la Administración
    _exigir_campos(campos, 33 + opciones.rvie_vacios, "RVIE")
    return armar_linea(campos, opciones)


def linea_rce(c: Comprobante, libro: Libro, idx: int, opciones: Opciones = OPCIONES) -> str:
    """Anexo 11 — 37 campos informados + los 38-41 vacíos (`rce_vacios`).

    Contrastado contra un RCE REAL presentado (julio de un contribuyente real, 27-ago-2026):
    el archivo generado salió idéntico, 41 campos y palote. Se mandan porque la nota (2)
    del Anexo 11 lo pide de forma explícita ("deberán mostrarse vacíos"), al revés que
    la del Anexo 3 de ventas ("los completa la Administración"), que resultó significar
    que NO se mandan. Sigue siendo una opción: si compras devolviera el 453, `rce_vacios=0`.
    """
    neg = negativo(c, opciones)
    m = lambda d, n=neg: formatear_monto(d, opciones, n)  # noqa: E731
    campos = _cabecera(c, libro, opciones) + [
        sanear(c.anio_dua, opciones),              # 9 año de emisión de la DUA
        formatear_numero(c.numero, opciones),            # 10 número (o inicial del rango)
        formatear_numero(c.numero_final, opciones),      # 11 número final del rango
        c.contraparte_tipo_doc,              # 12 tipo de documento del proveedor
        sanear(c.contraparte_doc, opciones),       # 13 número de documento
        sanear(c.contraparte_nombre, opciones),    # 14 razón social / nombres
        *columnas_igv_compras(c, opciones),        # 15-20 base/IGV DG, DGNG, DNG
        m(c.adquisiciones_no_gravadas),      # 21 valor de adquisiciones no gravadas
        m(c.isc),                            # 22 ISC
        m(c.icbper),                         # 23 ICBPER
        m(c.otros),                          # 24 otros tributos y cargos
        m(c.total),                          # 25 importe total
        c.moneda,                            # 26 moneda
        formatear_cambio(c, opciones),                       # 27 tipo de cambio
        formatear_fecha(c.ref_fecha, opciones),          # 28 fecha del comprobante modificado
        c.ref_tipo_cp,                       # 29 tipo del comprobante modificado
        sanear(c.ref_serie, opciones),             # 30 serie del comprobante modificado
        sanear(c.cod_dep_aduanera, opciones),      # 31 código de la dependencia aduanera
        formatear_numero(c.ref_numero, opciones),        # 32 número del comprobante modificado
        sanear(c.clasif_bienes, opciones),         # 33 clasificación de bienes y servicios
        sanear(c.id_contrato, opciones),           # 34 identificador del proyecto (operadores)
        "",                                  # 35 porcentaje de participación
        "",                                  # 36 IMB (Ley 31053)
        "",                                  # 37 CAR original (solo ajustes posteriores)
    ] + [""] * opciones.rce_vacios                 # 38-41 detracción, tipo de nota, estado, inconsistencias
    _exigir_campos(campos, 37 + opciones.rce_vacios, "RCE")
    return armar_linea(campos, opciones)
