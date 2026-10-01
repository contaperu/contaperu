# 0020 · La marca de detracción del SIRE, y el código que pone quien integra

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar y motor |
| **Versión** | `open-accounting` 1.0 (aditivo: no sube la versión, avanza el tag) |
| **Test** | `tests/test_detracciones.py::test_la_marca_del_sire_sobrevive_al_blanqueo` |

## Motivación

Un mes que entra por la **propuesta del SIRE** —el caso normal de un estudio contable, porque los XML los tiene el
cliente— se exportaba **sin ninguna detracción, y en silencio**. El asiento salía mal: sin la línea de la detracción,
la cuenta por pagar al proveedor queda inflada, y nada avisaba de cuáles eran. El motor avisaba `SIRE_SIN_DETALLE` en
**todos** los comprobantes por igual, así que el aviso no distinguía al que le falta la detracción del que nunca la
tuvo.

Y era peor de lo necesario, porque **SUNAT sí dice cuáles son**. Su propuesta de compras trae una columna propia con
una marca en las filas sujetas al SPOT. Lo que no dice es **cuál** detracción: ni el código del Catálogo 54, ni la
tasa, ni el monto, ni la cuenta del Banco de la Nación, ni la constancia. Eso es del comprobante, no del registro.

De las dos cosas, la que falta es **solo el código**: de él salen la tasa (la tabla del motor) y el monto
(`total × tasa`, soles enteros). Así que el circuito es corto: SUNAT dice QUE hay detracción, quien integra dice CUÁL,
y el motor hace el resto igual que con un XML.

**El dato no es opcional, y ese es el punto.** La marca no es una inferencia del motor: la afirma SUNAT en su propio
registro. Quien acepta esa propuesta está aceptando que esos comprobantes tienen detracción, así que exportarlos sin
ella contradice el archivo que acaba de aceptar. Por eso la exportación **se detiene** en vez de avisar.

## Fuente

- **Campo 38 del Anexo 8 de la RS 040-2022** (§8.4), «Detracción», del Registro de Compras Electrónico: una `D` en las
  filas sujetas al SPOT. El RVIE **no tiene esta columna** en ninguno de sus 40 campos, así que esto es solo compras.
- **El caso real**, que es lo que esta enmienda esperaba: un RCE real de un mes, 3018 filas, con la marca en **221**
  (30-sep-2026). `datos/sunat/sire_campos.json` tenía el campo anotado como «candidato a entrar: espera su caso real».
- **Catálogo 54 de SUNAT** para el código, y la tabla del motor (`datos/sunat/detracciones.json`) para su tasa.

## Especificación

1. **La marca viaja como anotación.** El lector del RCE escribe `detraccion: {"_marca_sire": "D"}`, **sin código**:
   inventarlo escribiría una tasa falsa en el asiento y un código interno falso en el sistema de destino. El prefijo
   `_` es el que el estándar reserva para lo que se transporta y se ignora, y la enmienda 0019 lo legalizó dentro de
   este bloque: esta enmienda es la primera que lo usa.
2. **`normalizar` conserva las anotaciones al blanquear.** Blanquear una detracción sin código reconocible se llevaba
   el bloque entero, y con él la marca. Ahora se queda. `_tasa_tabla` **no** sobrevive: es la tasa de un código, y sin
   código no hay nada que anotar.
3. **`imputacion` gana `detraccion_codigo`**, el código del Catálogo 54 de ese documento. Está en la imputación, y no
   en el comprobante, por la misma razón que la cuenta contable: **llega aparte**. Lo que traiga el comprobante manda
   sobre lo que diga la imputación —el archivo gana a la persona—, y un código que el contribuyente no reconoce se
   blanquea igual: la imputación no es una puerta trasera a la tabla.
4. **Un comprobante marcado y sin código detiene la exportación**, con la falta `sin_codigo_detraccion` y su lista de
   comprobantes, que se pide **al contador**. Es el requisito `detraccion` del contrato de drivers, y lo declaran los
   cinco destinos que escriben un asiento. **El driver `sire` no**: el registro tributario no lleva detracción, así
   que un mes marcado se sigue declarando.

## Qué NO hace

- **No toca el esquema del comprobante.** `detraccion` ya admitía anotaciones `^_` desde la 0019 y no tiene campos
  obligatorios, así que un bloque con solo la marca valida sin cambiar nada. Lo único que gana el esquema es el
  `detraccion_codigo` de `imputacion`, que es aditivo: la versión del estándar **no se mueve**, avanza su tag.
- **No lee la otra columna que SUNAT escribe y el motor ignora**, el campo 41 («inconsistencias», con valor en 19 de
  las 3018 filas del caso real). Es otra regla, con otra fuente, y espera su propia decisión — anotado aquí porque el
  criterio chirría: el campo 40 sí se transporta con la misma justificación, «opinión de la Administración».
- **No infiere el código de nada.** Ni del proveedor, ni del concepto, ni de un valor por defecto. Si algún día un
  mapeo por proveedor entra, será con su caso real.
- **No cambia la salida de ningún driver** mientras falte el código: sin código no hay tasa, sin tasa el monto es 0 y
  la línea no nacía ya antes. Lo que cambia es que ahora no se llega a escribir el archivo.

## Qué rompe

**Un mes importado de la propuesta del SIRE con detracciones marcadas deja de exportar** hasta que se ponga el código
de cada una. Es el cambio de comportamiento de esta versión y es a propósito: antes esos meses salían con el asiento
incompleto y sin avisar. Quien integra el motor tiene dos cosas que hacer: leer la falta `sin_codigo_detraccion` de
`faltantes` —su lista es la que filtra la tabla donde el contador los completa— y mandar `detraccion_codigo` en la
imputación de cada uno.
