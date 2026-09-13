"""El asiento contable: de un comprobante a las líneas de la partida doble.

Aquí vive la contabilidad de verdad. Las reglas, con su fuente al lado:

**Compras** — 3 líneas normalmente:
  1. GASTO (Debe)        total − IGV · la de su imputación o la del contribuyente · centro de costo
  2. IGV crédito (Debe)  solo si hay IGV; nunca en boletas ni en recibos por honorarios,
                         que no dan crédito fiscal
  3. PROVEEDOR (Haber)   total − retención · cuenta por pagar según la moneda · anexo = RUC

**Ventas** — el espejo: cliente al Debe, ingreso al Haber, IGV al Haber.

**Nota de crédito (07)** — invierte el asiento entero, con el documento que modifica en la
referencia.

**Recibo por honorarios (02) con retención de 4ta** — 3 líneas más una: el gasto va por el
TOTAL, la retención al Haber en su cuenta de tributos, y a la cuenta por pagar solo el NETO
que se le paga al profesional. La retención es la que MUESTRA el comprobante: no se calcula
el 8 % por cuenta propia, porque con suspensión no la hay.

**Factura con detracción** — 5 líneas. El total COMPLETO queda en la cuenta por pagar normal
del proveedor, y se añaden dos líneas por el monto detraído: el proveedor al Debe (se le pagará
menos) y la cuenta de detracciones al Haber, con su propio tipo de documento y un número
comodín, porque **la constancia del Banco de la Nación no existe todavía cuando se registra la
compra**. El monto se calcula sobre el total en SOLES ENTEROS —la detracción se deposita en
soles— y si la factura está en dólares se convierte con el tipo de cambio del comprobante.
Lo dispara que la factura TENGA detracción, nunca el sub-diario: una empresa que lo lleva todo
en un mismo libro auxiliar hace exactamente el mismo asiento.
(Calcado de un Excel real que un CONCAR de producción aceptó, 06-sep-2026.)

**El código SUNAT manda.** Cada comprobante guarda su tipo de la Tabla 10 y lo que necesite el
ERP de destino —la sigla del documento, el sub-diario— se DERIVA de él con una sola tabla,
`tipos`, sobreescribible por contribuyente. Un tipo sin entrada **no se inventa**: la
exportación se detiene y dice cuál falta.

---

Nota de arquitectura: el asiento nace en líneas neutrales de `open-accounting` (`motor.py`) y cada ERP
es una proyección de ellas. CONCAR fue el primero y el código nació generando su Excel, así que
durante un año las filas nacieron en sus columnas ('A'..'AO') y la línea neutral se sacaba después;
desde el 11-sep-2026 (0.7) la dirección está invertida — la línea es la fuente y el Excel de CONCAR,
una proyección más (`drivers/concar/proyeccion.py`), que no cambió ni una celda al invertirse
(`tests/test_snapshot_concar.py`). Desde la 0.10 las columnas de
CONCAR y sus datos viven en su driver; el núcleo arma `lineas_del_comprobante()` y `lineas_del_libro()`.
"""
from .configuracion import CONFIG_POR_DEFECTO, NUMERO_DETRACCION_PENDIENTE, TIPO_DOC_DETRACCION
from .faltas import (CONTADOR, FALTA, FALTAS, PROVEEDOR, SISTEMA, Falta, SinCodigoDeMoneda, NoExportable,
                     RepartoNoAdmitido, RepartoNoCuadra, SinCentro, SinCuenta, SinCorrelativo,
                     SinSigla)
from .resolucion import (comprobantes_sin_centro, comprobantes_sin_cuenta, con_reparto, config_aplicada,
                         correlativos_de_partida, cuenta_honorarios,
                         cuenta_por_pagar, cuenta_por_pagar_detraccion, cuenta_tercero, equivalencia_tipo,
                         etiquetas_sub_diario, exigir_requisitos, faltantes_para, fundir_config, imputacion_de,
                         limites_del_periodo, lleva_centro, monedas_sin_codigo, numerar, partes_de, reparto_no_cuadra,
                         repartos_que_no_cuadran, sigla_documento, sub_diario, sub_diarios_presentes,
                         tiene_detraccion, tipos_sin_sigla)
from .huella import huella
from .imputacion import Imputacion, Parte
from .lineas import LineaDiario
from .motor import CENTRO_EN_ANEXO, ROLES, glosa_de, lineas_del_comprobante, lineas_del_libro

__all__ = [
    "CONFIG_POR_DEFECTO", "NUMERO_DETRACCION_PENDIENTE", "TIPO_DOC_DETRACCION", "CONTADOR", "FALTA", "FALTAS",
    "PROVEEDOR", "SISTEMA", "Falta", "SinCodigoDeMoneda", "NoExportable", "RepartoNoAdmitido", "RepartoNoCuadra",
    "SinCentro", "SinCuenta", "SinCorrelativo", "SinSigla", "comprobantes_sin_centro",
    "comprobantes_sin_cuenta", "con_reparto", "config_aplicada", "correlativos_de_partida", "cuenta_honorarios",
    "cuenta_por_pagar", "cuenta_por_pagar_detraccion", "cuenta_tercero", "equivalencia_tipo",
    "etiquetas_sub_diario", "exigir_requisitos", "faltantes_para", "fundir_config", "imputacion_de",
    "limites_del_periodo", "lleva_centro", "monedas_sin_codigo", "numerar", "partes_de", "reparto_no_cuadra",
    "repartos_que_no_cuadran", "sigla_documento", "sub_diario", "sub_diarios_presentes", "tiene_detraccion",
    "tipos_sin_sigla", "huella", "Imputacion", "Parte", "LineaDiario", "CENTRO_EN_ANEXO", "ROLES", "glosa_de",
    "lineas_del_comprobante", "lineas_del_libro",
]
