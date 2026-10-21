# 0005 · `retencion_igv`: la retención del 3 % del régimen de retenciones

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | open-accounting 4.0 |
| **Test** | `tests/test_retenciones.py` |

## Motivación

Un agente de retención designado por SUNAT retiene el 3 % del IGV al pagar, y el XML lo trae. Sin el
campo, ese dato se pierde o viaja en `datos_originales`.

**El caso real llegó el 20-oct-2026**, y fue el que esta enmienda se temía: una aplicación que integra el motor
volcó el 3 % del IGV de dos facturas en el campo de la renta de 4ta, **porque no había dónde ponerlo**. El motor
lo cazó con `RETENCION_NO_APLICA` —«la retención de 4ta solo se registra en recibos por honorarios»— y las dos
facturas acabaron observadas: el aviso era correcto y lo que faltaba era el campo. Y el dato ya se leía del XML
desde antes: llegaba hasta el constructor y **se cambiaba por un cero**.

Lo que se decidió entonces sigue en pie: **no entra en ninguna línea de asiento** de compras ni de ventas,
tampoco en el neutral, porque no es un hecho del comprobante sino del pago. El campo transporta el dato a quien
lleve el asiento de tesorería. **Sí llega a la cabecera que ve un driver**, y la diferencia importa: lo primero
es contabilidad y lo segundo es no perder un dato por el camino —la regla de `tests/test_cabecera.py`, que nació
porque a STARSOFT se le cayó por el camino un dato que el estándar ya declaraba—.

## Fuente

Régimen de Retenciones del IGV (SUNAT); el XML de la factura electrónica lo trae en `PaymentTerms`
`Retencion`.

## Especificación

Campo `retencion_igv` en el comprobante: `{porcentaje, monto}`, opcional. **Ausente o `null` significa que
nadie lo dijo**, que no es lo mismo que un monto en cero: por eso no tiene un cero de fábrica.

`validar` avisa (`RETENCION_IGV_TASA`, nivel aviso) si el porcentaje declarado se aleja más de 0,5 pp del 3 %,
**sin mirar la fecha** —la misma decisión que la tasa del IGV: un porcentaje que no es el de hoy se le enseña al
contador y decide él—. Nunca es error: no entra en ningún asiento, así que no puede frenarle el mes a nadie.

**No es `retencion_4ta`**, que es la retención de renta de 4ta categoría que muestra un recibo por honorarios y
que **sí** entra al asiento. Confundirlas es un error contable, y por eso los dos nombres se separan —el campo de
la 4ta se llamaba `retencion` a secas hasta la 4.0, y eso es lo que arregla la enmienda
[0034](0034-un-nombre-por-retencion.md)—.

## Nota de la 2.0 del estándar (10-oct-2026)

«Entra al asiento con su rol» hay que leerlo con lo que la 2.0 hizo: el papel de una línea ya no viaja en ella, se
deriva. La separación que esta enmienda defiende —la retención de renta y la del IGV son dos cosas y no se
confunden— se sostiene igual, y mejor: lo que las distingue es el **bloque** `retencion` con su código del Catálogo
05, no un nombre de rol.
