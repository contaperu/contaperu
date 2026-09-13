"""Driver CONTASIS: el registro de compras y el de ventas en Excel que importa NewContaSis («Sistema Experto
Contable 26.00»).

CONTASIS no importa asientos: importa su registro, UNA fila por comprobante con la cuenta de la base y la del total,
y arma el asiento él mismo; el sub-diario se elige al importar (John, 12-sep-2026). Es un driver de la familia
registro (`desde_comprobantes`): cada columna sale de la misma función del núcleo que usa el asiento de CONCAR, y
aquí no se decide ninguna cuenta.

Cómo se escribe el archivo (las fuentes de cada regla, en `datos.py`):

- **Archivo:** `.xlsx`, sin las filas 1-13 de la plantilla y con su pestaña (`FORMATO_COMPRAS`, `FORMATO_VENTAS`).
- **Textos:** rellenos con espacios hasta su largo, también los vacíos; serie y número sin ceros a la izquierda.
  El nombre va de corrido; la glosa (`asiento.glosa_de`), cortada a 60.
- **Fechas:** celdas de fecha. **Importes:** números con dos decimales, y un cero es una celda vacía. **Tipo de
  cambio:** `1` en soles.
- **Dólares:** cada importe × T.C. y el total, total × T.C.; si el redondeo los separa, lo absorbe la base. El total
  en dólares va en «equivalente en dólares».
- **Nota de crédito:** sus importes en negativo. **% IGV:** la tasa legal que cuadra (`igv.tasa_legal`).
- **Compras:** base e IGV por destino (`igv.por_destino`); la boleta, sin crédito fiscal, entera en no gravadas.
- **Cuentas:** la de la base y el centro, de `asiento.partes_de` (el centro solo donde la cuenta lo lleva); la del
  total, de `asiento.cuenta_tercero`; las de otros tributos e ICBPER, de la configuración (`cuentas.otros_tributos`,
  `cuentas.icbper`) cuando su columna lleva importe. **Medio de pago** (ventas): `medio_pago`, `001` por defecto
  (`CONFIG_POR_DEFECTO`).
- **Lo que no va:** el recibo por honorarios (`EXCLUYE_TIPOS`), el régimen especial y la constancia de detracción
  (vacíos), y un reparto entre cuentas (`EXIGE = {"cuenta_unica"}`). Lo que no cabe —otra moneda, dólares sin T.C.,
  un rango de boletas, IVAP, un código más largo que su columna— lo dice `no_caben` antes de exportar.

**Pendiente de aceptación:** escrito contra la plantilla oficial y un registro que CONTASIS importó; falta que
CONTASIS importe un archivo generado por este driver.
"""
from . import datos
from .datos import CONTENT_TYPE, EXCLUYE_TIPOS, EXIGE, FORMATOS, NOMBRE, OPCIONES
from .proyeccion import fila, no_caben, valores
from .xlsx import escribir_xlsx, desde_comprobantes, nombre

__all__ = ["CONTENT_TYPE", "EXCLUYE_TIPOS", "EXIGE", "FORMATOS", "NOMBRE", "OPCIONES", "escribir_xlsx", "datos",
           "desde_comprobantes", "fila", "no_caben", "nombre", "valores"]
