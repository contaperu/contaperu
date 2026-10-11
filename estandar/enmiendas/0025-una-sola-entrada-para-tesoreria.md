# 0025 · Una sola entrada para tesorería: el movimiento absorbe la constancia

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **rompe**: `constancias[]` sale de la raíz y el `$def` `referencia_de_constancia` se renombra. Un documento 2.0 con ese bloque no valida |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.0 |
| **Test** | `tests/test_estandar.py` (la paridad esquema↔modelo de `movimiento` y `referencia_de_pago`), `tests/test_tesoreria.py` (la forma fundida, los dos números, el `origen` cerrado y la moneda contra su cuenta) y `estandar/conformidad/esquema.json` (once casos, cada regla con su negativo) |

## Motivación

Es de John, el 11-oct-2026, con estas palabras: *«el ERP como producto final puede recibir una constancia de pago o
un estado de cuenta completo del mes, pero al motor solo llegaría como item de operación, o se podría decir
movimientos bancarios… es algo parecido a los comprobantes que provienen de compra o venta: **solo debe haber una
entrada para tesorería**»*.

Tenía razón, y **el motor ya lo afirmaba en dos sitios** que la 9.1 no miró:

1. **`modelo.RASGOS.origen` es singular: una entrada por libro.** `venta`→`comprobantes`,
   `compra`→`comprobantes`, `tesoreria`→`movimientos`. Así que `constancias[]` era un bloque **huérfano**: no era
   el origen de ningún libro. La tabla que la 9.0 construyó para que el libro lo dijera un dato y no un booleano ya
   decía que hay una sola entrada, y nadie la leyó al añadir la segunda.
2. **La procedencia de un comprobante ya es un campo, no otro bloque.**
   `Comprobante.ORIGENES = ("xml", "pdf_texto", "vision", "manual", "sire")`: una factura leída de un XML y una
   leída de una foto son la misma forma con otro `origen`. El estándar tenía la respuesta y la aplicó a los
   comprobantes.

### Los tres argumentos de la 0024, revisados

La [enmienda 0024](0024-movimientos-y-constancias.md) justificó dos bloques con tres razones. **Dos eran
equivocadas y la tercera no era del estándar:**

| Lo que dijo | Qué pasa al mirarlo |
|---|---|
| «Son hechos de testigos distintos» | El testigo es el campo `origen`. Era el patrón del comprobante y no se aplicó aquí |
| «Las cardinalidades no cuadran: un cargo paga un lote de detracciones» | Confunde un uno-a-muchos **dentro** de un item con necesitar dos bloques. Lo resuelve `referencias`, dentro del movimiento, igual que el `reparto` de una compra |
| «Los ciclos de vida difieren: una constancia existe semanas antes del extracto» | Eso es de quien integra. Al motor llega lo que haya, y **un movimiento sin `saldo` y sin `referencia` del banco ES** un pago cuyo extracto no ha llegado |

## Fuente

Los mismos nueve extractos reales de agosto de 2026 de la 0024 —BBVA, Scotiabank y BanBif— y la constancia de
depósito de detracción del Banco de la Nación. Lo que esta enmienda añade no es un dato nuevo: es la observación de
que **los dos documentos describen el mismo hecho desde dos sitios**, y que lo que el estándar necesitaba no era un
segundo bloque sino cuatro campos más en el que ya tenía.

Y una fuente de método: `Comprobante.origen`, que resuelve esto mismo desde la 1.0 para un documento que puede
llegar como XML, como fila de la propuesta del SIRE o como una foto.

## Especificación

**La raíz pierde `constancias`.** El `$def` `constancia` desaparece y `referencia_de_constancia` pasa a llamarse
**`referencia_de_pago`**, porque es lo que cancela un pago venga de donde venga.

**`movimiento` gana ocho propiedades, todas opcionales**, y sus cuatro obligatorias no cambian (`cuenta`, `fecha`,
`importe`, `sentido`):

| Campo | Qué es |
|---|---|
| `constancia` | el número del **papel** que prueba el pago: el vóucher del Banco de la Nación, el comprobante de una transferencia. **Aparte de `referencia`, que es el número del BANCO, porque los dos existen y son distintos**: una detracción pagada desde BBVA tiene su `N° OPER` y su vóucher. `referencia` sigue siendo la llave de deduplicación; `constancia` es el que se escribe en el `detraccion.nro_constancia` del comprobante |
| `contraparte_tipo_doc` · `contraparte_doc` · `contraparte_nombre` | a quién se le pagó o de quién se cobró, **cuando el papel lo dice** —un extracto no lo trae: su descripción es texto libre y leerla es conjetura—. Con **los mismos tres nombres que un comprobante** a propósito: un destino que llena su anexo auxiliar lo busca por `contraparte_doc`, así que el mismo nombre ahorra una traducción y un segundo vocabulario |
| `medio_pago` | Tabla 1 del Anexo 3 de la RS 169-2015, el mismo catálogo que el comprobante y la línea del asiento ([enmienda 0004](0004-medio-de-pago.md)). Patrón `^$\|^[0-9]{3}$` |
| `referencias[]` | qué cancela, cuando el papel lo dice. Las cuatro clases no cambian: `comprobante`, `tributo`, `cuenta_propia`, `libre` |
| `origen` | **enum de cinco: `manual`, `archivo`, `api`, `pdf_texto`, `vision`** |
| `confianza` | lo que el modelo reporta, entre 0 y 1. **No relaja ninguna comprobación** |

### El `origen` es una lista propia, y por qué

**No se comparte con el comprobante.** Un `xml` o una propuesta del `sire` no son cosas de un banco, y aceptarlos
sería inventar — lo contrario de «mejor fallar que inventar». Lo que sí se comparte son los dos nombres que
significan exactamente lo mismo, **`pdf_texto` y `vision`, que son los dos que marcan lectura asistida**. Los otros
tres: `manual` (lo escribió una persona), `archivo` (un CSV, un XLSX o un MT940 del banco) y `api` (su API).

**Y lo que NO es `origen`: si esto vino de un extracto o de una constancia.** Eso lo dice el `saldo`, que solo una
línea de extracto trae, y no hace falta una etiqueta para repetirlo. Es la lección del `rol` aplicada aquí: lo que
se deriva no es un campo.

### Lo que el esquema decía mal, y ahora dice

Tres validaciones vivían **solo en Python**, así que un productor que validara con el JSON publicado aceptaba lo
que el motor rechaza:

- **Las claves que admite cada clase de referencia**, ahora con un `if/then` por clase. El daño era medible: el
  caso de conformidad «las cuatro clases de referencia, cada una con lo suyo» **no podía fallar**, porque nadie
  miraba dentro de `datos`. Entra con su gemelo negativo.
- **El enum de `origen`.** Un `origen: "ocr"` validaba y **dejaba de salir en `de_lectura_asistida`**: lo que leyó
  un modelo dejaba de pedir revisión sin que nada lo dijera. Ahora el esquema lo rechaza y el modelo también.
- **La forma de `moneda`**, que era `string` sin patrón: un `"soles"` validaba. Ahora `^$|^[A-Z]{3}$`, la misma del
  comprobante. **Sin enum a propósito**: quien enumera monedas es el maestro de cuentas, no cada línea, y una
  tercera se declara primero como cuenta. Y el motor **la contrasta con la moneda de su cuenta** y avisa: hasta
  aquí una cuenta en dólares aceptaba movimientos en soles y nada fallaba.

## Qué rompe

- **`constancias[]` no valida.** Un documento 2.0 que lo traiga se rechaza por el `additionalProperties: false` de
  la raíz. Cómo se traduce, campo a campo, está en `estandar/MIGRAR-A-3.0.md`.
- **`referencia_de_constancia` ya no existe** como `$def`. Quien lo cite por `$ref` lo cambia por
  `referencia_de_pago`.
- **Un `origen` desconocido deja de pasar**, que es un cambio de comportamiento del modelo y no solo del esquema.
- La respuesta de `revisar_tesoreria` **pierde la clave `constancias`** y sus dos informes nombran el movimiento
  por `cual` —el número del papel si lo tiene, y si no el del banco— en vez de por `numero`.

**Lo que se pudo hacer limpio, y por qué:** `constancias[]` salió el 10-oct-2026 en la 9.1.0, nadie de fuera
produce documentos con él y la aplicación que integra el motor no lo consume. Es la regla de John del 18-sep-2026,
la que permitió que la 1.0 no leyera la 0.3: *«como todavía ningún ERP no lo usa, puedes hacer la limpieza para que
esté bien»*. La alternativa —dejar el bloque declarado y deprecado— es el anti-patrón que la 10.0 acabó de limpiar
en cuatro campos: retirar lo que el motor escribe y dejar la clave en el esquema deja una promesa sin dueño que
nadie vuelve a comprobar.

## Qué NO hace

- **No asienta.** Sigue siendo el hito D6, y sigue esperando la tasa del ITF con su norma y un archivo del
  sub-diario de bancos que CONCAR haya aceptado. `RASGOS["tesoreria"]` mantiene sus cuatro campos vacíos.
- **No añade la imputación de un movimiento**, que entra en su propia enmienda: aquí va lo que el **papel** dice;
  la cuenta con la que se asienta es una decisión y va aparte.
- **No toca `Movimiento.efecto`**, que sigue sin devolver `transferencia` nunca: una línea sola no puede saber que
  es la mitad de un traspaso.
- **No añade ningún valor de catálogo.** Las cuatro clases de referencia y los tres efectos de tesorería son los
  mismos.
