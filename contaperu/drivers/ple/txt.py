"""El TXT del **Libro Diario, formato 5.1** del PLE de SUNAT: 21 campos por fila, separados por `|` y con palote
final.

Es el segundo libro electrónico que escribe el motor, y el primero cuya **fila es una línea del asiento** y no un
comprobante: una compra con detracción son cinco filas. Por eso su forma es `desde_lineas` y no `linea` como la del
SIRE — el canal `tributario` admite las dos desde la 4.2 (`drivers/contrato.py`).

**El formato no se describe aquí**: columna a columna vive en `datos/sunat/ple_campos.json`, con de dónde sale cada
una y qué hizo con ella un libro real que SUNAT aceptó. `tests/test_ple_campos.py` lo confronta con este módulo, así
que el mapa y el escritor no se pueden separar sin que la batería lo diga. Aquí está solo el layout físico.

Fuentes: RS 234-2006/SUNAT, artículo 6 y Formato 5.1; y el contraste con un Libro Diario de un mes **presentado y
aceptado** con sus constancias de recepción (1-oct-2026), del que salen la nomenclatura, la forma del CUO y la fecha
nula. Ese archivo vive solo en `privado/`.

**Lo que este driver emite es el Libro Diario de los COMPROBANTES del mes, no el libro completo.** En el archivo
contrastado, 595 de 1441 asientos no vienen de ningún registro de compras ni de ventas —el asiento de destino, los
pagos, la planilla, la depreciación— y el motor no los origina. Es el mismo límite honesto que tiene el `sire`, y
quien integre tiene que saberlo antes de presentar nada.
"""
from __future__ import annotations

from ...asiento import CONFIGURACION_DEL_ASIENTO, ComprobanteDelAsiento, LineaDiario
from ...modelo import Libro
from ..kit import Opciones, armar_archivo, armar_linea, forma, formatear_fecha, formatear_monto, sanear
from ..kit import nombre_de_libro_electronico as _nombre_de_libro_electronico

NOMBRE = "ple"
# Un registro que se presenta a SUNAT (`drivers.contrato.CANALES`), como el SIRE.
CANAL = "tributario"
# Los dos libros que el motor genera se escriben con el MISMO formato: el 5.1 no distingue compras de ventas, las
# junta en el diario. No es `libro.tipo: diario` —eso sería recibir un diario de un ERP, que es otra cosa—: aquí se
# toma el mes que el motor conoce y se escribe en formato Libro Diario, igual que el `sire` lo escribe como RVIE o
# RCE.
FORMATOS = {"compra": "ple_5_1", "venta": "ple_5_1"}
CONTENT_TYPE = "text/plain; charset=us-ascii"
# `cero="0.00"` porque el 5.1 lleva DOS columnas, Debe y Haber, y la que no toca va con el cero escrito: así sale en
# el archivo contrastado. El `sire` no lo necesita porque sus importes van en una sola columna con signo.
OPCIONES = Opciones(fecha="DD/MM/AAAA", nueva_linea="\r\n", tc_pen="", cero="0.00", extension=".TXT")

# El código del libro (seis dígitos) y lo que lo acompaña en el nombre del fichero. **No son los del SIRE**, que usa
# `140400` y `080400`: confundirlos nombraría el archivo de forma que SUNAT lo rechaza.
LIBRO_DIARIO = "050100"
# Oportunidad y banderas tal como vienen en el archivo contrastado. El `sire` usa `02` porque reemplaza una
# propuesta; un libro diario no reemplaza nada.
OPORTUNIDAD = "00"
BANDERAS = "1111"
# La fecha que el archivo contrastado escribe donde no hay fecha, y que SUNAT aceptó. No es la cadena vacía.
SIN_FECHA = "01/01/0001"
# Lo que el formato escribe donde no hay tercero ni comprobante.
SIN_TERCERO = "0"
SIN_COMPROBANTE = "00"
# La glosa referencial es opcional y el motor no tiene una segunda glosa; el archivo contrastado pone un guion.
GLOSA_REFERENCIAL = "-"
# Estado 1: una operación del periodo. El 8 (de un periodo anterior no anotado) y el 9 (corrige una ya anotada, con
# su CUO original) los decide quien lleva el libro, no el motor.
ESTADO_DEL_PERIODO = "1"
# Prefijo del secuencial dentro del asiento: M de movimiento. La apertura (A) y el cierre (C) no los emite el motor.
PREFIJO_MOVIMIENTO = "M"

CAMPOS = 21

# Lo que se configura, y es **solo lo del asiento**: los sub-diarios y la tabla de tipos que el núcleo lee al armar
# las líneas. El sub-diario no es decorado aquí — es la primera mitad del CUO del campo 2, así que sin él el archivo
# no se puede nombrar por dentro.
#
# Y nada más: este driver no tiene vocabulario propio que configurar. Donde CONCAR declara cómo llama su sistema a
# los soles y a cada Tabla General, el 5.1 escribe los códigos de SUNAT tal cual —la moneda en ISO, el tipo de
# comprobante en su Tabla 10— porque el destino es SUNAT y no un sistema contable con sus siglas.
CONFIGURACION = CONFIGURACION_DEL_ASIENTO


def nombre(libro: Libro, opciones: Opciones = OPCIONES) -> str:
    """El nombre que SUNAT impone: `LE` + RUC + periodo + día + `050100` + oportunidad + banderas + `.TXT`.

    La regla la arma el kit, que la comparte con el SIRE; lo propio de este libro —su código, su oportunidad y sus
    banderas— está arriba."""
    return _nombre_de_libro_electronico(libro, LIBRO_DIARIO, OPORTUNIDAD, BANDERAS, opciones)


def _cuo(ln: LineaDiario) -> str:
    """El código único de la operación: el sub-diario y el correlativo del asiento, unidos por un guion.

    El motor ya numera las dos piezas, y el correlativo ya trae el mes delante (`010001`), así que el CUO sale tal
    cual: `10-010001`. En el archivo contrastado tiene esa misma forma. Sin sub-diario configurado va el correlativo
    solo, que sigue identificando el asiento dentro del periodo."""
    return f"{ln.sub_diario}-{ln.correlativo}" if ln.sub_diario else ln.correlativo


def _fecha(valor: Any, opciones: Opciones) -> str:
    """Una fecha del 5.1, con la fecha nula del formato donde no hay ninguna."""
    return formatear_fecha(valor, opciones) or SIN_FECHA


def fila(ln: LineaDiario, cabecera: ComprobanteDelAsiento, n: int, libro: Libro, opciones: Opciones) -> str:
    """Una línea del asiento → su fila del 5.1, con los 21 campos en el orden del formato.

    `n` es la posición de la línea DENTRO de su asiento, de 1 en adelante: el campo 3 del formato.

    Dos campos salen de la cabecera y no de la línea, y por eso este driver necesita el índice: el **tipo** de
    documento del tercero (la línea lleva el número, no el tipo) y la **serie y el número por separado** (la línea los
    trae unidos en `documento.serie_numero`).
    """
    doc = ln.documento or {}
    tiene_tercero = bool(ln.contraparte_doc)
    m = lambda d: formatear_monto(d, opciones)
    campos = [
        f"{libro.periodo}00",                                            # 1 periodo
        _cuo(ln),                                                        # 2 CUO
        f"{PREFIJO_MOVIMIENTO}{n:04d}",                                  # 3 secuencial del movimiento
        ln.cuenta,                                                       # 4 cuenta contable
        "",                                                              # 5 denominación: opcional (art. 6)
        sanear(ln.centro_costo, opciones),                               # 6 centro de costos
        ln.moneda,                                                       # 7 moneda
        cabecera.contraparte_tipo_doc if tiene_tercero else SIN_TERCERO,  # 8 tipo de doc del tercero
        ln.contraparte_doc or SIN_TERCERO,                               # 9 número de doc del tercero
        doc.get("tipo_cp") or SIN_COMPROBANTE,                           # 10 tipo de comprobante
        sanear(cabecera.serie, opciones),                                # 11 serie
        sanear(cabecera.numero, opciones),                               # 12 número
        _fecha(ln.fecha, opciones),                                      # 13 fecha de la operación
        _fecha(doc.get("fecha_vencimiento"), opciones),                  # 14 fecha de vencimiento
        _fecha(doc.get("fecha_emision"), opciones),                      # 15 fecha de emisión
        sanear(ln.glosa, opciones),                                      # 16 glosa
        GLOSA_REFERENCIAL,                                               # 17 glosa referencial
        m(ln.importe if ln.debe_haber == "D" else 0),                    # 18 debe
        m(ln.importe if ln.debe_haber == "H" else 0),                    # 19 haber
        "",                                                              # 20 dato estructurado: ver el mapa
        ESTADO_DEL_PERIODO,                                              # 21 estado
    ]
    if len(campos) != CAMPOS:
        raise RuntimeError(f"el Libro Diario 5.1 lleva {CAMPOS} campos y se armaron {len(campos)}")
    return armar_linea(campos, opciones)


def desde_lineas(libro: Libro, lineas: list[LineaDiario], config: dict, opciones: Opciones = OPCIONES, *,
                 indice: tuple[ComprobanteDelAsiento, ...] = ()) -> tuple[bytes, dict]:
    """Las líneas del libro, ya numeradas y cuadradas por el núcleo → el TXT del 5.1.

    **El orden de las filas es el del motor**, y eso es una decisión: el formato 5.1 no manda ningún orden dentro de
    un asiento, y del archivo contrastado solo se puede leer el que eligió *ese* software. Imponer aquí el suyo sería
    escribir una regla sin fuente, que es lo que este repositorio no hace. Si algún día un rechazo real demuestra que
    SUNAT mira el orden, entra entonces y con ese rechazo al lado.
    """
    forma.exigir_indice("PLE", libro, lineas, indice, FORMATOS)
    filas: list[str] = []
    for entrada in indice:
        del_asiento = entrada.lineas(lineas)
        filas.extend(fila(ln, entrada.cabecera, n, libro, opciones)
                     for n, ln in enumerate(del_asiento, 1))
    return armar_archivo(filas, opciones), {"filas": len(filas), "asientos": len(indice)}
