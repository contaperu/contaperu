"""El asiento contable: de un comprobante a las líneas de la partida doble.

Aquí vive la contabilidad de verdad. Las reglas, con su fuente al lado:

**Compras** — 3 líneas normalmente:
  1. GASTO (Debe)        total − IGV · la cuenta de la fila o la del contribuyente · centro de costo
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

Nota de arquitectura, sin adornos: hoy las filas nacen ya en las columnas del Excel de CONCAR
(claves 'A'..'AO'), porque este código nació generando ese archivo. `lineas.py` las proyecta al
vocabulario neutral de `pe-ledger`, que es lo que consumen el driver CSV y el servidor MCP.
Cuando exista un segundo driver nativo, la dirección se invierte: la línea neutral pasa a ser
la fuente y CONCAR, una proyección más.
"""
from .datos import (ANCHOS, COLUMNAS, COLUMNAS_FECHA, COLUMNAS_IMPORTE, COLUMNAS_TEXTO,
                    CONTENT_TYPE, D2, DEFAULTS, ETIQUETAS_SUB_DIARIO, EXCEL_HEADERS,
                    FLAG_CONVERSION, FORMATOS, NOMBRE, NUMERO_DETRACCION_PENDIENTE, OPCIONES,
                    TIPO_BOLETA, TIPO_CONVERSION, TIPO_DOC_DETRACCION, TIPO_HONORARIOS,
                    TIPOS_INVIERTEN, TIPOS_NOTA)
from .construir import (CorrelativoFaltante, MonedaSinCodigo, SinCuenta, TipoSinMapa,
                        asiento, config_de, cuenta_de_fila, cuenta_gasto, cuenta_honorarios,
                        cuenta_venta, etiquetas_sub_diario, filas_sin_centro, filas_sin_cuenta,
                        lleva_centro, merge_config, mes_del_libro, monedas_sin_codigo, nombre, numerar,
                        resolve_cxp_account, sub_diario, sub_diarios_presentes,
                        tasa_igv, tiene_detraccion, tipo_concar, tipos_sin_mapa)
from .lineas import LineaDiario, a_lineas, desde_fila

__all__ = [
    "ANCHOS", "COLUMNAS", "COLUMNAS_FECHA", "COLUMNAS_IMPORTE", "COLUMNAS_TEXTO",
    "CONTENT_TYPE", "D2", "DEFAULTS", "ETIQUETAS_SUB_DIARIO", "EXCEL_HEADERS",
    "FLAG_CONVERSION", "FORMATOS", "NOMBRE", "NUMERO_DETRACCION_PENDIENTE", "OPCIONES",
    "TIPO_BOLETA", "TIPO_CONVERSION", "TIPO_DOC_DETRACCION", "TIPO_HONORARIOS",
    "TIPOS_INVIERTEN", "TIPOS_NOTA",
    "CorrelativoFaltante", "MonedaSinCodigo", "SinCuenta", "TipoSinMapa",
    "asiento", "config_de", "cuenta_de_fila", "cuenta_gasto", "cuenta_honorarios",
    "cuenta_venta", "etiquetas_sub_diario", "filas_sin_centro", "filas_sin_cuenta",
    "lleva_centro", "merge_config", "mes_del_libro", "monedas_sin_codigo", "nombre", "numerar",
    "resolve_cxp_account", "sub_diario", "sub_diarios_presentes",
    "tasa_igv", "tiene_detraccion", "tipo_concar", "tipos_sin_mapa",
    "LineaDiario", "a_lineas", "desde_fila",
]
