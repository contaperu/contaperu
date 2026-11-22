"""El catálogo de las observaciones de la validación: qué significa cada código que `validar` puede dejar en un
comprobante, su nivel y a quién se le pide (15.16.0).

Hasta la 15.15 eso estaba repartido y era interno: el código y su nivel, dentro de cada llamada de `validar.py`; a
quién pedírselo, en `pipeline.diagnostico.PEDIR_A`; y lo que significa, en ninguna parte — el texto de cada
observación lleva los datos de su comprobante, así que una pantalla que quería una leyenda tenía que escribirla.
Ahora vive aquí, se publica entero en `api.catalogo_de_observaciones` y **`PEDIR_A` sale de esta tabla** en vez de
repetirla.

**Las reglas no están aquí y no se mueven**: siguen en `validar.py`, que es quien decide. Esto dice cómo se llaman y
qué significan, y lo vigila `tests/test_catalogo_de_observaciones.py` leyendo las llamadas de `validar.py`: un código
que se emite sin estar aquí, uno que está y nadie emite, o un nivel que no es el de su llamada, lo ponen en rojo.

**La forma de cada entrada no es de ningún país** (`comprobantes.CodigoDeObservacion`): es lo que la hoja de ruta
adelanta del hito J2. Lo que J2 sigue esperando, con su cliente fuera del Perú, es partir ESTA tabla en reglas
universales y peruanas y escribir la fuente de cada una; el código de SUNAT de cada observación, si lo tiene, es C2.

El texto es el significado, para quien lee la leyenda; el que ve el contador en una fila sigue siendo el de la
observación, con sus datos. A quién: **contador** se decide mirando el documento o el plan de cuentas; **sistema**,
la configuración del destino o un dato público que no está en el papel (el T.C. lo publica SUNAT). **`proveedor`
sigue reservado** (`asiento.faltas`).
"""
from __future__ import annotations

from ..asiento.faltas import CONTADOR, SISTEMA
from ..comprobantes.comprobante import CodigoDeObservacion
from .validar import PLAZO_ANOTACION_MESES

ERROR, AVISO = "error", "aviso"


def _error(texto: str, pedir_a: str = CONTADOR, **nivel_por_origen: str) -> CodigoDeObservacion:
    return CodigoDeObservacion(ERROR, pedir_a, texto, dict(nivel_por_origen))


def _aviso(texto: str, pedir_a: str = CONTADOR) -> CodigoDeObservacion:
    return CodigoDeObservacion(AVISO, pedir_a, texto)


# En el orden de `validar.py`, sección a sección; `api.catalogo_de_observaciones` lo publica por código.
CATALOGO: dict[str, CodigoDeObservacion] = {
    # identificación
    "TIPO_CP_DESCONOCIDO": _aviso("El tipo de comprobante no está en la Tabla 10 de SUNAT."),
    "NUMERO_FALTA": _error("Falta el número del comprobante."),
    "SERIE_FALTA": _error("Falta la serie de una factura, una boleta o una nota."),
    "SIRE_SIN_DETALLE": _aviso("Viene de la propuesta del SIRE, que trae los importes y las partes pero no el "
                               "detalle del comprobante: faltan el concepto y la cuenta contable."),
    # fechas
    "FECHA_FALTA": _error("Falta la fecha de emisión."),
    "FECHA_POSTERIOR": _error("Está emitido después del periodo del libro."),
    "PERIODO_ANTERIOR": _aviso("Es una venta de un mes anterior: en ventas el IGV nace en la fecha de emisión, no en "
                               "la de anotación (Ley del IGV, art. 4)."),
    "CREDITO_FISCAL_FUERA_DE_PLAZO": _aviso(
        f"Es una compra emitida hace más de {PLAZO_ANOTACION_MESES} meses: está fuera del plazo de anotación en el "
        "Registro de Compras (Ley 29215, art. 2)."),
    # las dos retenciones de una compra, y lo que exige cada tipo
    "RETENCION_NO_APLICA": _aviso("Lleva retención de 4ta y no es un recibo por honorarios, así que no se usa; si es "
                                  "la del régimen de retenciones del IGV, va en `retencion_igv`."),
    "RETENCION_MAYOR": _error("La retención de 4ta es mayor que el total del recibo."),
    "RETENCION_TASA": _aviso("La retención de 4ta no es el 8 % del total: el total tiene que ser el honorario bruto, "
                             "no el neto recibido."),
    "RETENCION_IGV_TASA": _aviso("La retención del IGV no es del 3 % del régimen de retenciones."),
    "VENCIMIENTO_FALTA": _error("Su tipo exige la fecha de vencimiento o de pago, y no la trae."),
    "ANIO_DUA_FALTA": _error("Es un documento aduanero sin el año de su DUA."),
    # la contraparte
    "CONTRAPARTE_FALTA": _error("Falta el documento del proveedor o del cliente."),
    "BOLETA_SIN_DOC": _aviso("Es una boleta de S/ 700 o más sin identificar al cliente, que SUNAT exige."),
    "RUC_INVALIDO": _error("El RUC de la contraparte no es válido."),
    "DNI_INVALIDO": _error("El DNI de la contraparte no tiene 8 dígitos."),
    "COMPRA_BOLETA": _aviso("Es una boleta recibida en compras: no da crédito fiscal y su IGV es costo."),
    "NOMBRE_FALTA": _aviso("Falta la razón social del proveedor o del cliente."),
    # la moneda
    "MONEDA_INVALIDA": _error("La moneda no es un código ISO de tres letras."),
    "TC_FALTA": _error("Está en moneda extranjera y le falta el tipo de cambio, que SUNAT exige.", SISTEMA),
    # los importes: los dos descuadres avisan en vez de bloquear cuando los escribió SUNAT en su propuesta
    "IGV_NO_CUADRA": _error("El IGV no es el 18 % de la base ni cuadra con una tasa vigente o retirada. Si el "
                            "comprobante viene de la propuesta del SIRE es un aviso: así lo tiene SUNAT.", sire=AVISO),
    "IGV_TASA_REDUCIDA": _aviso("El IGV cuadra con una tasa reducida que ya no rige."),
    "ANTICIPO": _aviso("El total descuenta un anticipo: revisa la base que se anota."),
    "TOTAL_NO_CUADRA": _error("El total no cuadra con la base, el IGV, lo no gravado y los otros conceptos. Si el "
                              "comprobante viene de la propuesta del SIRE es un aviso: así lo tiene SUNAT.", sire=AVISO),
    "DSCTO_MAYOR_QUE_BASE": _error("En una nota de crédito, la parte que va como descuento es mayor que su base o "
                                   "que su IGV."),
    "TOTAL_CERO_EN_LA_PROPUESTA": _aviso("SUNAT lo informa en su propuesta con todos los importes en cero, que es como "
                                         "declara lo que se da de baja: el registro lo lleva igual."),
    "TOTAL_CERO": _aviso("El importe total está en cero."),
    # la detracción y el medio de pago
    "DETRACCION_TASA_DISTINTA": _aviso("La tasa de la detracción no es la que la tabla del contribuyente da a su "
                                       "código."),
    "MEDIO_PAGO_DESCONOCIDO": _aviso("El medio de pago no está en la tabla de SUNAT: sale igual."),
    # el no domiciliado (15.6.0): lo decide quien conoce el contrato con el proveedor del exterior
    "NO_DOMICILIADO_EN_VENTAS": _error("Un comprobante de no domiciliado (91, 97 o 98) solo va en el registro de "
                                       "compras."),
    "NO_DOMICILIADO_NO_APLICA": _aviso("Lleva el bloque del no domiciliado y no es un 91, 97 ni 98, así que se "
                                       "ignora."),
    "NO_DOMICILIADO_CON_IGV": _error("Un comprobante del exterior no lleva base gravada ni IGV: lo comprado va en el "
                                     "valor no gravado, y el IGV de la utilización del servicio en el bloque del no "
                                     "domiciliado."),
    "PAIS_DESCONOCIDO": _aviso("El país no está en la Tabla 16 de SUNAT."),
    "VINCULO_DESCONOCIDO": _aviso("La vinculación económica no está en la Tabla 17 de SUNAT."),
    "CONVENIO_DESCONOCIDO": _aviso("El convenio para evitar la doble imposición no está en la Tabla 18 de SUNAT."),
    "TIPO_RENTA_DESCONOCIDO": _aviso("El tipo de renta no está en la Tabla 19 de SUNAT."),
    "MODALIDAD_DESCONOCIDA": _aviso("La modalidad del servicio no está en la Tabla 20 de SUNAT."),
    "EXONERACION_DESCONOCIDA": _aviso("La exoneración no está en la Tabla 21 de SUNAT."),
    "PAIS_PERU_NO_DOMICILIADO": _aviso("El país del no domiciliado es el Perú, y un no domiciliado reside fuera del "
                                       "país (LIR, art. 7)."),
    "RENTA_NETA_NO_CUADRA": _aviso("La renta neta no es la bruta menos la deducción; si es una renta presunta del "
                                   "art. 48 de la LIR, está bien."),
    "IMPUESTO_RETENIDO_NO_CUADRA": _aviso("El impuesto retenido no es su tasa sobre la renta neta (LIR, art. 76)."),
    "EXONERACION_CON_IMPUESTO": _aviso("Lleva una exoneración del art. 19 de la LIR y un impuesto retenido: con la "
                                       "exoneración no se retiene."),
    "CONVENIO_NO_ES_DEL_PAIS": _aviso("El convenio no es el que corresponde al país del no domiciliado."),
    "IGV_UTILIZACION_NO_CUADRA": _aviso("El IGV de la utilización del servicio no es el 18 % de lo comprado en "
                                        "soles."),
    # las notas
    "NOTA_SIN_REFERENCIA": _error("La nota no dice qué comprobante modifica: su tipo, su serie y su número."),
    "NOTA_SIN_FECHA_REF": _error("Falta la fecha del comprobante que la nota modifica."),
    "TIPO_NOTA_DESCONOCIDO": _aviso("El motivo de la nota no está en la tabla de SUNAT para su tipo: sale igual."),
    "TIPO_NOTA_NO_APLICA": _aviso("Lleva el motivo de una nota y no es una nota, así que se ignora."),
    # de dónde salió: el XML lo afirma, la IA lo lee y puede equivocarse
    "XML_DE_OTRO_RUC": _error("Es el XML de una venta que emitió otro RUC: no es una venta de este contribuyente."),
    "XML_PARA_OTRO_RUC": _error("Es el XML de una compra emitida a otro RUC: no es una compra de este "
                                "contribuyente."),
    "GRATUITAS": _aviso("Incluye operaciones gratuitas, que no van al registro."),
    "EMISOR_NO_COINCIDE": _aviso("La IA leyó como emisor otro RUC: puede no ser una venta de este contribuyente."),
    "ADQUIRENTE_NO_COINCIDE": _aviso("La IA leyó que está emitido a otro RUC: puede no ser una compra de este "
                                     "contribuyente."),
    # el lote: los repetidos y las facturas que anula una nota
    "DUPLICADO_PERIODO_ANTERIOR": _error("Ya se anotó en otro periodo del mismo RUC, y SUNAT lo rechazaría (error "
                                         "452)."),
    "DUPLICADO": _error("Está repetido en el mismo lote."),
    "FACTURA_CON_NOTA_DE_CREDITO": _aviso("Una nota de crédito del lote anula su total: si la factura quedó anulada, "
                                          "se marca en su imputación (`anulada_por_nota`) para que no provisione su "
                                          "detracción."),
    "FACTURA_ANULADA_SIN_NOTA": _aviso("Está marcada como anulada y ninguna nota de crédito del lote anula su total: "
                                       "si la nota es de otro periodo, es lo normal."),
}
