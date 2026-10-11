# 0028 · Un cargo del banco es su propio movimiento

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **ninguna**: no añade ni quita campos. Escribe una regla de modelado que ya se cumplía sin estar dicha |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.1 (entra con ella; por sí sola no la habría subido) |
| **Test** | `tests/test_tesoreria.py` (una comisión entra como movimiento y se imputa como cualquier otro) |

## Motivación

Es de John, el 11-oct-2026, integrando: *«todos los ITF o comisión van sobre una propia fila, aunque también se
puede anexar dentro de la fila principal de la salida o entrada; pero a las finales, si pones un pago de 2 000 y
su ITF 0,50, serían 2 asientos contables, uno por el pago y otro por el ITF»*.

Tiene razón en las dos mitades, y la segunda es la que manda: **son dos hechos con cuentas distintas**, así que el
día que el motor asiente tesorería saldrán dos asientos, uno contra la cuenta del tercero y otro contra la cuenta
del impuesto.

Y al mirarlo apareció una **asimetría que nadie había nombrado**: el ITF tiene campo propio (`movimiento.itf`) y
una comisión bancaria **no tiene ninguno**. Si un banco descuenta portes o mantenimiento, no había dónde ponerlos.

## Fuente

**La práctica, vista en los nueve extractos reales** de agosto de 2026 que dieron la forma del movimiento (BBVA,
Scotiabank y BanBif): los cargos del banco **vienen con su propia fila** —Scotiabank escribe «IMPUESTO A LOS
DÉBITOS» como un movimiento más— salvo el ITF de BBVA, que va en una columna al lado. Esa excepción es
precisamente la que dio origen al campo, y el archivo que la enseñó rompía el cuadre en la segunda fila del mes
hasta que se tuvo en cuenta.

Y la consecuencia contable es del **PCGE**, que ya tiene sus dos cuentas con su página: el ITF como gasto en
`6412` (p. 40) y su pasivo en `40181` (p. 32). Son cuentas distintas de la del tercero al que se le pagó, y dos
cuentas distintas no caben en un asiento que pretenda ser uno solo.

## Especificación

**Un cargo del banco es un `movimiento`.** Una comisión, los portes, el mantenimiento de cuenta, un interés
cobrado: todos llegan como un item de operación más, con su fecha, su importe, su `sentido` y **su propia
imputación**, que es lo que les da su cuenta de gasto.

Dicho así, **la asimetría se resuelve sola: no le falta un campo a la comisión, le sobra uno al ITF.** Y lo que se
evita es la trampa en la que cae un modelo que enumera: pedir un campo nuevo cada vez que un banco inventa un
concepto. El estándar no sabe cuántos hay y no tiene por qué — es el mismo argumento con el que la clase `libre`
de una referencia evita enumerar propósitos de pago ([enmienda 0024](0024-movimientos-y-constancias.md)).

## Por qué `itf` se queda, y qué es exactamente

**No es una excepción a la regla: es el caso en que la regla no se puede aplicar.** Hay bancos que descuentan el
ITF **sin darle fila** —BBVA lo pone en una columna al lado del importe—, de modo que **no existe un movimiento
que lo represente** y el saldo corrido lo resta igual. Sintetizar una fila que el extracto no tiene sería
inventar, que es lo contrario de la regla de la casa. Cuando el banco sí le da fila —Scotiabank escribe
«IMPUESTO A LOS DÉBITOS»— llega como un cargo más y el campo va vacío, que es la regla aplicándose.

Su único lector es `tesoreria.cuadra`, la función que comprueba una lectura, así que **su retiro se revisa junto
con `movimiento.saldo`**, que está en la misma situación: cuando llegue el primer lector de banco real y se vea
si alguien los usa (decisión de John, 11-oct-2026).

## Qué NO hace

- **No añade ni quita ningún campo.** Nada que valide hoy deja de valer, y nada nuevo valida.
- **No asienta.** El pago y su ITF serán dos asientos el día de D6, que espera la tasa con la norma que diga quién
  la soporta y un archivo del sub-diario de bancos aceptado. Las cuentas del PCGE ya están, con su página: el
  gasto en `6412` y el pasivo en `40181`.
- **No añade un campo de comisión**, y ése es justo el punto: una comisión es un movimiento.
