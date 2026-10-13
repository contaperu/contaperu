# 0030 · Las cuotas de una factura al crédito, con su importe

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **aditivo**: dos campos opcionales en el comprobante. Un documento 3.1 sigue valiendo tal cual |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.2 |
| **Test** | `tests/test_cuotas.py` (la lectura del XML entera, el colapso que se conserva, y qué pasa sin cuotas) y `estandar/conformidad/esquema.json` (una factura al crédito con sus tres cuotas, y sus negativos) |

## Motivación

**La norma obliga a declararlas, el lector las ve y las pierde.** Una factura al crédito trae, por obligación, el
monto neto pendiente de pago y **la fecha y el monto de cada cuota**; `contaperu/lectores/xml_ubl.py` lee **solo
las fechas**, las colapsa a su máximo para `fecha_vencimiento` y **descarta todos los importes**. Las fechas
acaban en `datos_originales.cuotas`, que es transporte sin interpretar: el motor no las entiende, las lleva.

El efecto se ve en un caso: una factura a tres cuotas y una a una sola, con el mismo vencimiento final, son hoy
indistinguibles para cualquiera que lea el documento del motor.

**Y la prueba de que el motor ya sabía que estos tres datos existen está dentro del propio repositorio**: el
Catálogo 09 de motivos de nota de crédito, cargado en `contaperu/datos/sunat/catalogos.json`, trae el motivo
**13**: *«Corrección del monto neto pendiente de pago y/o
la(s) fechas(s) de vencimiento del pago único o de las cuotas y/o los montos correspondientes a cada cuota, de
ser el caso»*. El estándar transporta el código de un motivo que corrige tres datos que el estándar no guardaba.

Para qué sirve guardarlas, que es lo que lo convierte en un hueco y no en un capricho:

| Para qué | Por qué hace falta el importe, y no solo la fecha |
|---|---|
| **La antigüedad** | se calcula por cuota vencida, no por la última fecha del documento |
| **El pago esperado** | es lo que la conciliación automática necesita, y es lo único que distingue un cargo por el importe exacto de la cuota 2 en su fecha de una coincidencia de cifras |
| **Lo que de verdad se va a cobrar** | el monto neto pendiente **no es el total**: la norma lo define sin las retenciones ni las detracciones |

La tercera fila es la que más vale para un ERP: el total de la factura y lo que el cliente va a transferir son dos
números distintos, y hasta ahora el motor solo tenía el primero.

**Y está medido, no deducido** (12-oct-2026, sobre tres facturas reales al crédito, en local y de solo lectura):
en las tres, `total − monto_pendiente` es **exactamente** el monto de la detracción, al céntimo. Es la definición
de la norma comprobada contra documentos de verdad, y es lo que convierte el campo en el dato que le falta a
cualquier cuenta por cobrar: lo que se le reclama al cliente no es el total del comprobante.

## Fuente

**RS 000193-2020/SUNAT** (vigente desde el 01-09-2021) y su **Anexo 1**, el de los campos de la factura
electrónica: obliga a consignar si la forma de pago es al contado o al crédito, y al crédito, el monto neto
pendiente de pago y las fechas de vencimiento del pago único o de cada cuota junto con el monto de cada una.

- Resolución: https://www.sunat.gob.pe/legislacion/superin/2020/193-2020.pdf
- Anexo 1: https://www.sunat.gob.pe/legislacion/superin/2020/anexo1-193-2020.pdf

En el XML (UBL 2.1) son varios `cac:PaymentTerms` con `cbc:ID` = `FormaPago`: uno con
`cbc:PaymentMeansID` = `Credito` y su `cbc:Amount` —el monto neto pendiente—, y uno por cuota con
`cbc:PaymentMeansID` = `Cuota001`, su `cbc:Amount` y su `cbc:PaymentDueDate`. El lector ya recorre ese bucle
desde que existe `condicion_pago`: lo que cambia es que deje de tirar lo que encuentra.

Y la fuente interna que lo corrobora: el motivo 13 del Catálogo 09, ya cargado en
`contaperu/datos/sunat/catalogos.json` — cuya propia `fuente` **ya cita esta resolución**, por su Anexo III. La
norma no es nueva en el repositorio: lo nuevo es usarla para lo que declara y no solo para nombrar su corrección.

## Especificación

Dos campos nuevos en el comprobante, **los dos opcionales**:

| Campo | Tipo | Qué es |
|---|---|---|
| `cuotas` | array de `{numero, fecha, importe}` | una entrada por cuota, en el orden del documento. `fecha` e `importe` son obligatorios dentro de cada cuota; `numero` es opcional |
| `monto_pendiente` | importe o `null` | el **monto neto pendiente de pago** que declara el documento. `null` = no lo dice, que **no es cero** |

- **`numero`** son los dígitos del identificador de la cuota (`Cuota001` → `"001"`), y vacío si el documento no
  los da. El prefijo es la etiqueta, no el dato.
- **`fecha_vencimiento` no cambia**: sigue siendo la mayor de las fechas de las cuotas, o el `cbc:DueDate` si no
  hay cuotas. Nada de lo que ya sale se mueve.
- **`condicion_pago` tampoco**: una factura con cuotas sigue siendo `credito` aunque no lo diga en letras.
- Quien no conozca los dos campos los ignora y sigue valiendo su lectura del documento.

## Qué NO hace

- **No comprueba que las cuotas sumen el monto pendiente.** Sería una regla aritmética sobre el documento y
  **no se ha leído la norma que la exija**; ninguna regla entra sin su fuente. El día que se lea, entra como
  observación y de nivel aviso —nunca como error—, porque lo que el documento declara se registra.
- **No deduce el monto pendiente** restándole al total la detracción y la retención. Lo declara el emisor, y una
  resta no es un hecho del papel.
- **No retira `datos_originales.cuotas`**, que queda redundante y con menos información que el campo. Se mantiene
  durante toda la 12.x para no romper a quien lo esté leyendo, y su retiro se decide en la 13.0.
- **No cambia ningún asiento.** Un vencimiento no mueve una cuenta: los cuatro snapshots de celdas quedan
  intactos.
- **No añade el medio de pago de cada cuota.** El `medio_pago` es del comprobante y ninguna factura vista lo
  reparte por cuota; si aparece una, será otra enmienda.
