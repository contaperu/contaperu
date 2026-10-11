# 0024 · `movimientos` y `constancias`: el dinero moviéndose, y lo que prueba cada movimiento

| | |
|---|---|
| **Estado** | reemplazada |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0. Dos bloques opcionales nuevos **no suben la versión**, y `estandar/LEEME.md` §Versionado ya nombraba `movimientos[]` del banco como su ejemplo |
| **Test** | `tests/test_estandar.py` (los dos bloques validan y la raíz los admite sin `comprobantes`) y `tests/test_tesoreria.py` (la forma, el cuadre y la deduplicación) |

## Motivación

El estándar sabe describir un mes de compras o de ventas y no sabe describir **de dónde salió o a dónde fue el
dinero**. Un ERP que lo use para su contabilidad peruana tiene el registro resuelto y la tesorería no, así que
vuelve a inventarse un formato propio —que es exactamente lo que este estándar existe para evitar.

El caso real llegó el 10-oct-2026: **nueve estados de cuenta de producción**, de agosto de 2026, de cinco bancos
peruanos. Lo que enseñaron está volcado en `contaperu/tesoreria/`, y lo que importa aquí son dos cosas.

**La primera es que son dos hechos, no uno.** Lo dijo John al verlos: «la constancia de transferencia es por
operación y un estado de cuenta es todo completo». Y aguanta las tres pruebas que separan dos objetos de uno:

- **Testigos distintos.** El banco sabe el saldo de mi cuenta y no sabe qué cancela cada cargo. La constancia sabe
  qué cancela y no sabe el saldo.
- **Cardinalidades que no cuadran.** Un solo cargo paga un lote de detracciones —los extractos lo escriben así,
  «Pago Detracciones Masivo SUNAT»— y una constancia puede partirse en dos movimientos.
- **Ciclos de vida distintos.** La constancia existe semanas antes de que llegue el extracto. Es justo lo que el
  motor ya hace hoy sin ningún archivo de banco delante: `detracciones.estado_de` deduce `PROVISIONADO` o `PAGADO`
  del número y la fecha de la constancia.

**La segunda es que una constancia tiene que valer para cualquier pago.** Un pago de tributos, un reintegro de
caja chica y un depósito de detracción son el mismo hecho con otra contrapartida. Lo que lo consigue sin que el
estándar enumere propósitos de pago —la trampa en la que cae un modelo de tesorería— es que lo cancelado viaje
como **referencias de cuatro clases**, y que la última sea texto libre.

## Fuente

Nueve extractos reales de producción de agosto de 2026 (BBVA, Scotiabank, BanBif y dos más que no se pudieron
abrir), de una empresa peruana, leídos el 10-oct-2026. **No entran al repositorio**: viven en `privado/`, que
`.gitignore` bloquea, porque esto es público. Lo que entra son los datos, aquí y en el código, que es lo que el
propio `.gitignore` promete.

El invariante que sostiene la forma, verificado en los tres que abren: la cuenta con su **CCI** —20 dígitos,
3+3+12+2, impreso con espacios en BBVA y con guiones en Scotiabank—, una moneda por extracto, un periodo en la
cabecera, y por línea la fecha de operación, la fecha valor, una descripción, el importe y el saldo corrido.

Para los campos que ya existen en el estándar no hace falta fuente nueva, y por eso se reusan: `medio_pago` es la
Tabla 1 del Anexo 3 de la RS 169-2015 (enmienda 0004), el código de tributo es el Catálogo 05 de SUNAT, y la
referencia a un comprobante es la misma 4-tupla que ya identifica uno.

## Especificación

Dos bloques opcionales en la raíz del documento. **Quien no los entienda los ignora**, que es lo que los hace
aditivos. Entraron al esquema el 10-oct-2026, con el tipo de libro `tesoreria`: hasta entonces un documento de puro banco habría tenido que mentir declarándose compra o venta, y era eso lo que mantenía esta enmienda `reservada`.

**`movimientos[]`** — una línea de un estado de cuenta: `cuenta` (el `id` en el maestro declarado), `fecha`,
`fecha_valor`, `descripcion`, `importe`, `sentido` (`cargo` | `abono`), `moneda`, `saldo`, `referencia`, `itf`,
`id_externo` y `datos_originales`.

Tres decisiones que el archivo real impuso y que conviene que estén escritas antes de que nadie escriba un lector:

1. **El importe va siempre positivo y el sentido aparte.** BBVA trae una columna con el importe negativo cuando es
   cargo; Scotiabank y BanBif traen dos columnas. Es la misma regla que ya rige en `linea.debe_haber`.
2. **El ITF es un campo, no un cálculo.** Lo da el banco: BBVA en una columna de la línea, Scotiabank como un
   movimiento propio («IMPUESTO A LOS DÉBITOS»). Las dos formas caben. **Y se descuenta del saldo aunque no esté
   en la columna del importe** — con la cadena inventada de `tests/test_tesoreria.py`, 1 500,00 − 200,00 da
   1 300,00 y la línea trae 1 299,80; los veinte céntimos son el ITF. Las cifras del extracto que lo enseñó no se
   escriben, por la regla 6. Un lector que no lo reste cuadra mal en la segunda fila del mes.
3. **La fecha llega completa.** Las líneas traen día y mes; el año está en la cabecera y lo baja quien lee el
   archivo, porque el núcleo no tiene reloj con el que adivinarlo.

**`constancias[]`** — la prueba de una operación: `numero`, `fecha`, `importe`, `moneda`, `medio_pago`,
`cuenta_origen`, `beneficiario`, `concepto`, `referencias[]`, `origen`, `confianza` y `datos_originales`.

**`referencias[]`** es lo que la hace genérica. Cuatro clases y ninguna más:

| Clase | Lleva | Cubre |
|---|---|---|
| `comprobante` | `tipo_cp`, `serie`, `numero`, `contraparte_doc` | el depósito de detracción, el pago a un proveedor |
| `tributo` | `codigo` (Catálogo 05) y `periodo` | el IGV, la renta, el ITF |
| `cuenta_propia` | `cuenta` | el traspaso entre cuentas propias, que no se cuenta dos veces |
| `libre` | `texto` | el reintegro de caja chica y todo lo demás |

Y dos reglas sobre lo que **no** se afirma:

- **Solo entra lo que el papel dice.** Una constancia de detracción nombra su comprobante: eso es un hecho. Que un
  cargo de 3 500 corresponda a una factura de 3 500 es una conjetura, y las conjeturas son de `conciliar`, que las
  devuelve con su método y su certeza y **nunca confirma**.
- **La suma de las referencias no tiene que igualar el importe.** Un cargo lleva el ITF dentro. Lo que ninguna
  referencia reclama se reporta y no se cierra: qué es ese resto lo decide el contador, por la imputación.

## Qué no hace

**No toca `libro`**, y es la decisión que más se pensó. Un extracto no es un registro de ventas ni de compras, y la
tentación era darle un `libro.tipo` propio —`caja_bancos`, por el grupo 01 del PLE—. Dos cosas lo desmontan:

- El propio motor lo dice en `datos/sunat/ple_campos.json`: **el contribuyente que lleva el Libro Diario 5.1 con
  sus campos de libre utilización se exime del Libro Caja y Bancos electrónico.** El libro que un documento de
  banco nombraría es el **diario**, y eso es el hito B13.
- Los códigos del grupo 01 del PLE no están en el repositorio. Escribirlos de memoria sería una regla sin fuente.

Y no hace falta: la raíz del documento solo exige `open_accounting` y `libro`, y **`comprobantes` no es
obligatorio** —hay un caso de conformidad que lo demuestra, «El mínimo: un libro y nada más»—. Así que un documento
con su cabecera de contribuyente y periodo más `movimientos[]` ya es válido en forma el día que los bloques entren.

## Qué rompe

Nada. Son dos bloques opcionales en la raíz: quien no los entienda los ignora, y la raíz sigue exigiendo solo
`open_accounting` y `libro`. Lo que se añadió son tres `$defs` nuevos —`movimiento`, `constancia` y
`referencia_de_constancia`— y dos claves en `properties`, ninguna en `required`. Y **no sube la versión del
estándar**, que es el segundo de los tres niveles de `LEEME.md` §Versionado.

## Qué falta para pasar a `final`

Que un lector lea de verdad uno de los nueve extractos y devuelva movimientos que cuadren. La forma está publicada
y el cuadre está probado; lo que falta es el parser de un banco.

Y un obstáculo que conviene anotar bien, porque la primera versión de esta enmienda lo contó peor de lo que es:
**dos de los nueve archivos no se abren** —los dos cifrados con contraseña— y otros **dos solo necesitan que se les
quite un prefijo de cinco bytes**, `$BOP$`, un centinela de impresora de *mainframe* delante del `%PDF-`. Los otros
cinco abren directamente. Así que siete de nueve se leen hoy, no cinco. Lo difícil de un extracto peruano sigue sin
ser las columnas, pero es menos difícil de lo que parecía.

## Reemplazada por la 0025 (11-oct-2026)

Esta enmienda metió el dinero en el estándar, y eso se queda: la forma de un movimiento, el ITF como campo, las
cuatro clases de referencia y el cuadre de la cadena de saldos son suyos y no se tocan.

**Lo que no sobrevivió fue partirlo en dos bloques.** La
[enmienda 0025](0025-una-sola-entrada-para-tesoreria.md) funde `constancias[]` dentro de `movimientos[]`, por
decisión de John: *«solo debe haber una entrada para tesorería»*. Y los tres argumentos con que esto se justificó
—los testigos distintos, las cardinalidades, los ciclos de vida— no resisten mirarlos: el testigo era el campo
`origen`, que el comprobante ya usaba; un cargo que paga un lote es un uno-a-muchos **dentro** de un item; y que
una constancia exista antes del extracto es asunto de quien integra, porque un movimiento sin `saldo` y sin
`referencia` del banco **es** exactamente eso.

Lo que había delante y nadie leyó: **`modelo.RASGOS.origen` es singular**, una entrada por libro, así que
`constancias[]` era un bloque que no era el origen de ningún libro.
