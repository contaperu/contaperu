"""Driver `sire_no_domiciliados`: el TXT del registro de compras de NO DOMICILIADOS del SIRE, el **080500**.

Anexo 9 de la RS 040-2022, §8.5, «Registro de Compras – Información de operaciones con sujetos no domiciliados»: 35
campos por comprobante del exterior. Es el hermano del driver `sire`, que escribe el 080400 y el 140400: el mismo canal,
otro registro, y por eso otro driver —un export produce un archivo, y `FORMATOS` va llaveado por libro—.

**La forma sale del registro real que SUNAT aceptó** (setiembre de 2026, 10 filas, medido el 03-nov-2026 sin mirar un
solo valor): **35 campos, el 36 vacío y palote** —37 partes al partir por `|`—, CRLF, el CAR del campo 2 vacío, las
fechas en DD/MM/AAAA, los importes y la tasa con dos decimales y el tipo de cambio con tres. El nombre es el de un libro
electrónico (`LE` + RUC + periodo + `00` + `080500` + oportunidad `00` + banderas `1112`). Lo que **no** se ha medido
todavía es que SUNAT acepte un archivo escrito por este driver: eso es cargarlo (5.5), y es otro paso.

**Los importes van en SOLES**, la moneda de la contabilidad (regla 5 del campo 16 del anexo): los de valor y total, que
el comprobante lleva en su moneda, se multiplican por su tipo de cambio —lo inverso de lo que hace el lector, medido
exacto en las diez filas reales—, y los del bloque `no_domiciliado` ya están en soles y se copian tal cual. Una
contabilidad en dólares no se escribe: el lector tampoco la sabe leer y no hay un caso real.

**Qué entra.** Solo el 91, el 97 y el 98 (`catalogos.DEL_REGISTRO_DE_NO_DOMICILIADOS`): el driver `sire` deja fuera
esos tres y este, todo lo demás del catálogo, así que entre los dos parten el mes sin solaparse. Un comprobante sin
país, que el registro no admite, o en dólares sin su tipo de cambio, no se escribe: `no_caben` lo dice antes.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ... import catalogos as cat
from ...asiento.faltas import NoExportable
from ...modelo import CENTIMO, Comprobante, Libro
from ..kit import Opciones, armar_linea, formatear_fecha, formatear_monto, formatear_numero, formatear_cambio, sanear
from ..kit import negativo as _negativo
from ..kit import nombre_de_libro_electronico as _nombre_de_libro_electronico

NOMBRE = "sire_no_domiciliados"
# Se presenta a SUNAT, por el SIRE, como el 080400 (`drivers.contrato.CANALES`).
CANAL = "sunat"
FORMATOS = {"compra": "sire_rce_no_domiciliados"}
# Todo lo del catálogo menos lo del exterior: el complemento exacto del `EXCLUYE_TIPOS` del driver `sire`.
EXCLUYE_TIPOS = frozenset(cat.TIPOS_CP) - cat.DEL_REGISTRO_DE_NO_DOMICILIADOS
# Las mismas del driver `sire`: DD/MM/AAAA, CRLF, palote al final y el tipo de cambio vacío en soles.
OPCIONES = Opciones(fecha="DD/MM/AAAA", nueva_linea="\r\n", tc_pen="", extension=".TXT")
LIBRO_NO_DOMICILIADOS = "080500"
# La oportunidad y las banderas del nombre del archivo real: 00, y 1 operativa, 1 con información, 1 soles, 2 generado
# por el SIRE.
OPORTUNIDAD = "00"
BANDERAS = "1112"
# Los 35 campos del anexo y el 36, que el archivo real manda vacío.
CAMPOS = 36

# Los motivos de `no_caben`, en el texto que ve quien exporta.
MOTIVOS = {
    "tipo": "no es un comprobante del registro de no domiciliados (91, 97 o 98)",
    "pais": "le falta el país de residencia del no domiciliado (campo 17 del 080500)",
    "cambio": "está en otra moneda y le falta el tipo de cambio para llevar sus importes a soles",
}


class SinPaisDelNoDomiciliado(NoExportable):
    """Un comprobante del exterior sin su país de residencia: el campo 17 del registro no puede ir vacío. `no_caben`
    lo dice antes de escribir; esto es lo que se lanza si alguien llama a `linea` directamente."""

    clave = "sin_pais_del_no_domiciliado"

    def __init__(self, c: Comprobante):
        super().__init__(f"{c.serie}-{c.numero}: {MOTIVOS['pais']}", [c])


def _exigir_campos(campos: list[str]) -> None:
    if len(campos) != CAMPOS:
        raise RuntimeError(f"La línea del 080500 salió con {len(campos)} campos y lleva {CAMPOS}")


def nombre(libro: Libro, opciones: Opciones = OPCIONES) -> str:
    """El nombre que SUNAT impone a un libro electrónico (`kit.nombre_de_libro_electronico`), con el código del 080500."""
    return _nombre_de_libro_electronico(libro, LIBRO_NO_DOMICILIADOS, OPORTUNIDAD, BANDERAS, opciones)


def no_caben(libro: Libro, comprobantes: list[Comprobante], config: dict | None) -> dict[str, list[Comprobante]]:
    """Lo que el 080500 no puede llevar, por motivo: un comprobante sin país y uno en otra moneda sin tipo de cambio.
    `diagnosticar` lo lista antes de exportar y el núcleo se niega con `NoCabe` antes de escribir un byte.

    Un tipo que no es del registro no se cuenta aquí: no es que no quepa, es que no es de este destino, y eso ya lo
    saca `EXCLUYE_TIPOS` —sale en el resumen como «fuera del destino», igual que el recibo por honorarios del SIRE—."""
    fuera: dict[str, list[Comprobante]] = {MOTIVOS["pais"]: [], MOTIVOS["cambio"]: []}
    for c in comprobantes:
        if c.tipo_cp not in cat.DEL_REGISTRO_DE_NO_DOMICILIADOS:
            continue
        if not (c.no_domiciliado or {}).get("pais"):
            fuera[MOTIVOS["pais"]].append(c)
        elif c.moneda != "PEN" and not c.tipo_cambio:
            fuera[MOTIVOS["cambio"]].append(c)
    return fuera


def _en_soles(importe: Decimal, c: Comprobante) -> Decimal:
    """Un importe del comprobante, de su moneda a soles, con su tipo de cambio: lo inverso del lector."""
    if c.moneda == "PEN" or not c.tipo_cambio:
        return importe
    return (importe * c.tipo_cambio).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def linea(c: Comprobante, libro: Libro, idx: int, opciones: Opciones = OPCIONES) -> str:
    """Anexo 9, §8.5 — 35 campos informados y el 36 vacío, con palote."""
    if c.tipo_cp not in cat.DEL_REGISTRO_DE_NO_DOMICILIADOS:
        raise NoExportable(f"{c.serie}-{c.numero}: {MOTIVOS['tipo']}", [c])
    bloque = c.no_domiciliado or {}
    if not bloque.get("pais"):
        raise SinPaisDelNoDomiciliado(c)
    if c.moneda != "PEN" and not c.tipo_cambio:
        # Sin él, los campos 7-9 saldrían en dólares bajo el rótulo de soles.
        raise NoExportable(f"{c.serie}-{c.numero}: {MOTIVOS['cambio']}", [c])
    neg = _negativo(c, opciones)
    m = lambda d, n=neg: formatear_monto(d, opciones, n)  # noqa: E731
    texto = lambda clave: sanear(str(bloque.get(clave) or ""), opciones)  # noqa: E731
    campos = [
        libro.periodo,                                      # 1 periodo
        "",                                                 # 2 CAR SUNAT (vacío: lo asigna SUNAT)
        formatear_fecha(c.fecha_emision, opciones),         # 3 fecha de emisión
        c.tipo_cp,                                          # 4 tipo de comprobante
        sanear(c.serie, opciones),                          # 5 serie
        formatear_numero(c.numero, opciones),               # 6 número
        m(_en_soles(c.adquisiciones_no_gravadas, c)),       # 7 valor de las adquisiciones, en soles
        m(_en_soles(c.otros_neto, c)),                      # 8 otros conceptos, en soles
        m(_en_soles(c.total, c)),                           # 9 importe total, en soles
        texto("sustento_tipo_cp"),                          # 10 tipo del documento que sustenta el crédito fiscal
        texto("sustento_serie"),                            # 11 su serie
        texto("sustento_anio_dua"),                         # 12 el año de su DUA o DSI
        texto("sustento_numero"),                           # 13 su número
        m(bloque.get("igv_utilizacion")),                   # 14 monto retenido: el IGV de utilización, en soles
        c.moneda,                                           # 15 moneda
        formatear_cambio(c, opciones),                      # 16 tipo de cambio
        texto("pais"),                                      # 17 país de residencia
        sanear(c.contraparte_nombre, opciones),             # 18 razón social del no domiciliado
        texto("domicilio"),                                 # 19 domicilio en el extranjero
        sanear(c.contraparte_doc, opciones),                # 20 su identificación tributaria
        texto("beneficiario_doc"),                          # 21 identificación del beneficiario efectivo
        texto("beneficiario_nombre"),                       # 22 su razón social
        texto("beneficiario_pais"),                         # 23 su país
        texto("vinculo"),                                   # 24 vinculación económica
        m(bloque.get("renta_bruta")),                       # 25 renta bruta, en soles
        m(bloque.get("deduccion")),                         # 26 deducción o costo, en soles
        m(bloque.get("renta_neta")),                        # 27 renta neta, en soles
        formatear_monto(bloque.get("porcentaje"), opciones),   # 28 tasa de retención: sin signo, es un porcentaje
        m(bloque.get("impuesto_retenido")),                 # 29 impuesto retenido, en soles
        texto("convenio"),                                  # 30 convenio para evitar la doble imposición
        texto("exoneracion"),                               # 31 exoneración del art. 19 de la LIR
        texto("tipo_renta"),                                # 32 tipo de renta
        texto("modalidad"),                                 # 33 modalidad del servicio
        texto("art_76"),                                    # 34 aplicación del art. 76 de la LIR
        "",                                                 # 35 CAR original (solo en ajustes posteriores)
        "",                                                 # 36 vacío, como en el archivo real
    ]
    _exigir_campos(campos)
    return armar_linea(campos, opciones)
