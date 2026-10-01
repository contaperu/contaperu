# 0022 · El tributo sale del nombre del rol y pasa a su bloque

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo en el estándar; **el motor cambia lo que escribe** |
| **Nivel** | estándar + motor |
| **Versión** | `open-accounting` **1.0** (no sube: valores de catálogo y bloques opcionales). El catálogo de roles pasa a su `1.2`. El paquete sube a **5.0.0** |
| **Test** | `tests/test_vocabulario.py::test_cada_tabla_puede_marcar_un_valor_como_obsoleto` · `tests/test_linea_del_comprobante.py::test_la_linea_del_impuesto_dice_de_que_tributo_es` |

## Motivación

El catálogo de roles nació con seis valores y tres estaban mal nombrados, de dos maneras distintas.

**Dos metían el tributo en el nombre.** `igv` dice a la vez qué hace la línea y de qué tributo es, así que no hay
forma de decir que una línea es del ISC o del ICBPER: haría falta un rol por tributo, que es un enum con más pasos.
`retencion_4ta` es peor, porque mete además la categoría, y la de 4ta no es la única que existe. Lo llamativo es que
el propio catálogo ya tenía la forma correcta al lado: **`detraccion` lleva su código y su tasa en un bloque** desde
la 1.0, y por eso no necesitó nunca un valor por cada bien del Catálogo 54.

**Uno nombraba por su causa lo que es un papel.** `detraccion_tercero` es «la parte del saldo del proveedor que no se
le paga a él». Eso pasa con una detracción, y pasa igual al aplicar un anticipo o al descontar una retención al pagar.
El papel es recortar un saldo; la detracción es solo el motivo más frecuente.

El modelo al que iba el catálogo quedó escrito en la [enmienda 0021](0021-contrapartida-y-tesoreria.md) y en el
`hacia_donde_va` de la tabla, con los dos motivos de por qué no entraba todavía. Los dos se han resuelto.

## Fuente

**El rol es lo que este estándar aporta y no está en ninguna norma**, así que lo que una enmienda de rol necesita es
un caso real (`estandar/LEEME.md`, «Quién gobierna los catálogos»). Y aquí hay algo más fuerte que un caso: **no son
valores nuevos, son los mismos papeles que el motor ya emite en cada asiento, bien nombrados.** El caso que los
justifica es el que justificó los dos anteriores: el Libro Diario 5.1 de un mes, presentado y aceptado por SUNAT, que
vive solo en `privado/`.

Lo que sí necesitaba norma es el contenido de los bloques, y la tiene:

- **`impuesto.codigo`** — Anexo N.° 8 de la **RS 097-2012/SUNAT**, «No. 05 · Catálogo Código de tipos de tributos y
  otros conceptos», con el texto del Anexo II de la **RS 244-2019/SUNAT**
  (`https://www.sunat.gob.pe/legislacion/superin/2019/anexo-244-2019.pdf`). Entró en
  `contaperu/datos/sunat/catalogos.json` con esta misma versión.
- **`retencion.categoria`** — las categorías de renta del **TUO de la Ley del Impuesto a la Renta (D.S. 179-2004-EF)**,
  artículos 22 y siguientes; la cuarta es el trabajo independiente del artículo 33.

## Especificación

1. **Tres valores nuevos en el catálogo `roles`**, al final de `codigos` porque el orden es el de inserción y los seis
   de la 1.0 tienen que seguir ocupando las seis primeras posiciones: **`impuesto`**, **`retencion`** y **`recorte`**.
2. **Los tres viejos siguen en `codigos`, intactos**, y entran en la tabla `obsoletos` con su reemplazo, su fecha y el
   porqué. **Siguen siendo válidos al leer**: un documento que los traiga se acepta y significa lo mismo.
3. **`obsoletos`, el mecanismo** — clave hermana de `codigos` en cualquier tabla, `{viejo: {usar, desde, por_que}}`,
   propagada por `catalogos_del_estandar` a la api, al HTTP y al MCP. Es por donde un ERP migra sin escribir el mapeo
   a mano. **No tiene versión de retiro**: un valor publicado no desaparece nunca.
4. **`linea.impuesto = {codigo}`** (obligatorio dentro del bloque), el código del Catálogo 05. El motor escribe el
   `1000`.
5. **`linea.retencion = {codigo, categoria}`**, el `3000` y la categoría de la LIR. El motor escribe `{"3000", "4"}`,
   y la categoría la sabe con certeza porque solo emite esa línea desde un recibo por honorarios.
6. **Ninguno de los dos lleva `tasa`.** Conviven dos convenciones en el repositorio —`detraccion.porcentaje` es
   porcentaje y `catalogos.TASA_IGV` es fracción—, así que un `tasa` aquí contradiría a una de las dos en la misma
   línea que ya lleva `tasa_igv`; el ICBPER no tiene tasa porque es un importe por bolsa; y en la retención el motor
   no la conoce, porque el importe le llega dado. Entra el día que haya un caso real y una convención decidida.
7. **El `rol` sale de la huella** (`asiento/huella.py`, `SIN`), y esto es lo que hace que esta enmienda no se repita:
   mientras estuviera dentro, cada corrección del catálogo invalidaría todas las huellas guardadas **en silencio**.
8. **El motor adopta los tres**: `ROLES_DEL_MOTOR` pasa a `("principal", "impuesto", "retencion", "tercero",
   "recorte", "detraccion")`, y deja de ser igual a la tupla de la 1.0 — divergen para siempre.
9. **Quien no conozca un rol no se rompe**: lo contabiliza con `clase`, `debe_haber` e `importe`, que es la regla de
   degradación de siempre.

## Qué NO hace

- **No sube la versión del estándar.** Valores nuevos en un catálogo y bloques opcionales en la línea son los dos
  primeros niveles de su regla de versionado. El esquema gana 35 líneas y no borra ninguna. Su tag avanza.
- **No quita ningún valor** ni cambia el significado de ninguno.
- **No toca las ranuras de configuración `cuentas.igv` y `cuentas.retencion_4ta`**, que comparten grafía con dos de
  los roles viejos y **no son roles**: son las cuentas contables que el contribuyente configura. Renombrarlas habría
  roto la configuración de todos los integradores.
- **No hace que el motor arme planilla, depreciación ni pagos.** `recorte` entra como nombre genérico, pero el motor
  sigue produciendo lo mismo: compras y ventas. `contrapartida` y `tesoreria` siguen sin emitirse.
- **No prevé ningún renombrado más.** Los siete papeles están completos.

## Qué rompe, medido

Generando los archivos de los ocho drivers con el motor de la 4.3.0 y con el de la 5.0.0, sobre los mismos dos meses:

| | |
|---|---|
| **SIRE, PLE 5.1, PLE 5.3, STARSOFT** | **Idénticos byte a byte** |
| **CONCAR y CONTASIS** (`.xlsx`) | **Idénticos celda a celda** — los bytes difieren solo por la fecha interna del ZIP |
| **CSV** | Cambia **solo el valor de la columna `rol`**: normalizándolo, el archivo es idéntico, y la cabecera no gana ni pierde ninguna columna |
| **`asiento_contable`** | El valor del `rol`, el bloque `impuesto` nuevo y la huella |
| **El piso contable** (`cuenta`, `debe_haber`, `importe`, `clase`) | **No cambia ni un valor** |
| **Un documento con los tres roles viejos** | Válido contra el esquema y conforme, **sin un solo aviso** |
| **Huellas guardadas** | **Dejan de coincidir.** Se mueven dos veces y por motivos opuestos: una al salir el `rol`, otra al entrar los bloques. Es lo único que pide una decisión a quien las persista |

Y el fixture de líneas del snapshot gana **44 bloques `impuesto` y 3 `retencion`**, que son exactamente las líneas que
ya tenía de cada cosa: ni una de más.

## Lo que se aprendió por el camino

- **Un aviso que no llega no es un aviso.** El `hacia_donde_va` anunciaba estos tres renombrados desde la 1.1 y nunca
  salió del archivo: `vocabulario.catalogos()` propaga cuatro claves y esa no estaba, y el esquema de salida es
  cerrado. Por eso los obsoletos son una clave de verdad y no una nota, y por eso tienen test.
- **Una homonimia puede ser la convención y no un error.** `retencion` es ahora campo del comprobante y rol de la
  línea, y eso asustaba — pero `detraccion` ya era campo, bloque y rol a la vez, y la
  [enmienda 0005](0005-retencion-de-igv.md) ya había reservado `retencion_igv` para el otro tributo justamente para
  que `retencion` signifique siempre la de renta. El rol hereda el nombre correcto.
- **El orden de los commits es parte del diseño.** El `rol` salió de la huella **antes** de los renombrados, en su
  propio commit. Así se movieron una vez en vez de dos, y durante la parte peligrosa la huella fue un invariante:
  cualquier movimiento habría sido un bug y no ruido esperado. Se comprobó, y no se movió ninguna.
- **Un informe de impacto puede equivocarse a favor del miedo.** Se dio por hecho que las dos tablas de rol de
  STARSOFT eran fallos silenciosos sin test. No lo eran: dejándolas atrás a propósito, **dos** de sus tests de
  aceptación fallan con la primera y **siete** con la segunda. El test nuevo no añade seguridad, añade el mensaje
  —allí el síntoma es una compra con cuatro filas donde el manual dice tres, y hay que deducir la causa—.
