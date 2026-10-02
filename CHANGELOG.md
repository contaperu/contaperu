# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El versionado del **paquete** es [SemVer](https://semver.org/lang/es/); el del **estándar
`open-accounting`** (antes `pe-ledger`) va por su cuenta y se documenta en `estandar/LEEME.md`.

## [Sin publicar]

**Contrastado contra un Libro Diario 5.1 y su 5.3 de mayo de 2026, presentados y aceptados por SUNAT** con sus
constancias. Lo que coincide es casi todo: los **dos nombres de archivo son idénticos byte a byte** y los 21 campos
del 5.1 coinciden en forma uno por uno. Dos filas confirman decisiones recientes con el archivo delante: el **campo 5
va vacío en las 10 579 filas** —la corrección de la 4.2.2 era la buena y la deducción era mala— y el **campo 14
escribe `01/01/0001` en 8 436 de ellas**, que es exactamente el arreglo de la 4.2.1.

Y tres inconsistencias, que es lo que trae esta versión.

### Cambios de comportamiento

- **El PLE conserva la Ñ y las tildes.** El 5.3 aceptado escribe «ALQUILER DE BAÑOS QUIMICOS» con el byte `0xD1`
  —cp1252— y el motor escribía «BANOS»; cuatro de las 725 cuentas de ese mes llevaban Ñ. Cambiarle a SUNAT el nombre
  que el contribuyente le da a su cuenta es elegir por él, que es lo que este repositorio se niega a hacer con el
  número de un comprobante y con la sigla de un tipo, y lo que el 5.3 evita al **exigir** la denominación en vez de
  usar la del PCGE. Un mes con tildes produce desde ahora bytes distintos de los que producía, y el `CONTENT_TYPE`
  pasa a decir `charset=windows-1252`. **Sobre datos ASCII es un no-op exacto**: los golden del 5.1 y del 5.3 dan el
  mismo sha256 que antes.

### Añadido

- **`exportar` usa el bloque `asiento` que el documento traiga, en vez de rederivarlo.** El esquema del estándar lo
  admite de entrada desde la 1.0 y el motor solo sabía escribirlo, así que **no podía releer su propio documento**: lo
  que devuelve `generar_asiento` no entraba por `exportar`. El enlace no se inventa —es `linea.documento.id_externo`,
  que el estándar puso en la línea para esto (enmienda 0009)— y **no se renumera**: el sub-diario y el correlativo
  salen de las propias líneas, así que un ERP con su numeración la conserva.
  - **No es «un asiento desnudo vale»**: los `comprobantes` siguen haciendo falta, porque el 5.1 saca cuatro de sus
    veintiún campos de la cabecera y el del vencimiento no es recuperable de las líneas. Son los dos bloques, que es
    lo que el driver `asiento_contable` ya escribe.
  - Entrar por aquí **no relaja ninguna regla**: el destino exige lo que exige, lo que su formato no lleva sigue
    parando, y el asiento tiene que cuadrar. Dos guardas nuevas fallan en voz alta: una línea sin `id_externo` o con
    uno huérfano, y las líneas de un mismo comprobante no contiguas.
  - Lo medido, sobre los **seis** drivers de asientos y no solo el PLE: mismo archivo byte a byte, misma huella y
    mismo resumen por las dos puertas, incluidos el Excel de CONCAR y el ZIP de STARSOFT.
- **`asiento.indice_de_lineas_dadas`, `asiento.rangos_de_lineas_dadas` y `asiento.LineaSinComprobante`** en la
  superficie pública: la vuelta de `lineas_e_indice_del_libro`, que reconoce las líneas en vez de generarlas.
- **`opciones.codificacion` gobierna las dos ramas de `armar_archivo`**, y `sanear` pliega a ella en vez de a ASCII a
  palo seco. Era el único campo de `Opciones` sin comentario y estaba **muerto justo donde hacía falta**: en la rama
  sin sanear el `cp1252` iba escrito a mano. El plegado va carácter a carácter, porque descomponer la cadena entera
  rompe la Ñ en N más una tilde suelta y cp1252 no tiene esa tilde. El defecto sigue en `ascii` y **el SIRE no se
  toca**: su ASCII tiene un test y un caso real detrás, mientras el del PLE era el defecto del dataclass heredado sin
  que nadie lo decidiera.

### Arreglado

- **El `motivo` del campo 20 del 5.1 decía que faltaba que el motor numerara el CUO del registro**, lo que da a
  entender que es trabajo pendiente del motor. No lo es: dos de sus cuatro partes son el campo 2 y el campo 3 de un
  registro que el motor no produce, y deducirlas del CUO del diario sería afirmar algo que no ha visto. Ahora dice de
  dónde puede venir el dato, y que es **opcional** con su número: en el libro contrastado lo traen 4 187 de 12 094
  líneas y el resto van vacías.
- **La anotación de `ple.fila()`** declaraba un `ComprobanteDelAsiento` y recibe un `Cabecera`; y su docstring decía
  «dos campos salen de la cabecera» cuando son cuatro, con el vencimiento.

## [5.1.0] — 2026-10-02

Dos deudas que la 5.0.0 dejó anotadas, las dos pequeñas y las dos de algo que ya había mordido.

### Arreglado

- **`asiento.lineas_del_comprobante` dejaba escapar un `KeyError` pelado.** Dos de las cuentas que necesita vienen de
  la configuración y no de la imputación —la del IGV y la de la retención de 4ta—, y se leían de dos formas distintas
  en líneas consecutivas: la segunda caía a su valor de fábrica y la primera se indexaba sin red. Con una `cuentas`
  incompleta eso daba `KeyError: 'igv'`, que **no es un `ErrorContaperu`**, así que quien atrapa los errores del motor
  no lo cazaba. Por la fachada no era alcanzable —el pipeline funde `CONFIG_POR_DEFECTO` antes de llamar—, pero la
  función está en la superficie pública y no promete esa fusión. Lo delató su espejo en el diagnóstico,
  `resolucion.cuentas_del_asiento`, que ya era simétrico.
- **El release falla si el tag del estándar no sirve el estándar de esa versión.** Los ficheros del estándar se
  publican por la URL de su tag, `open-accounting-X.Y`, que se mueve a mano y que nada vigilaba. La 5.0.0 se etiquetó
  con ese tag en el commit de la 4.3.0, y como cuatro de los `api/esquemas/*.json` referencian el estándar por esa URL
  —entre ellos `asiento.schema.json`, que declara la salida de `generar_asiento`—, la Release apuntaba por contrato a
  un esquema que **rechazaba lo que el motor devuelve**. La batería no puede verlo: esos `$ref` son URLs y el núcleo no
  sale a la red, así que la comprobación vive en el workflow, que es donde hay tags. Compara los **ficheros** y no los
  commits, que es lo que la hace útil, y cubre los cuatro que viajan en la rueda, incluidos los casos de conformidad.
  `CLAUDE.md` dice ahora el orden: el tag del estándar se mueve **antes** que el de la versión.

## [5.0.0] — 2026-10-01

**El tributo sale del nombre del rol y pasa a su bloque.** Un rol dice QUÉ HACE la línea; cuál es el tributo, cuando
lo hay, lo dice un bloque al lado. Es lo que `detraccion` hacía bien desde la 1.0 y lo que tres valores del catálogo
no hacían: `igv` y `retencion_4ta` metían el tributo —y la categoría— en el nombre, y `detraccion_tercero` nombraba
por su causa lo que es un papel.

| Rol de la 1.0 | Rol de la 5.0 |
|---|---|
| `igv` | **`impuesto`**, con `linea.impuesto = {codigo}` del Catálogo 05 |
| `retencion_4ta` | **`retencion`**, con `linea.retencion = {codigo, categoria}` |
| `detraccion_tercero` | **`recorte`** |

Los otros tres —`principal`, `tercero`, `detraccion`— no se tocan. Con esto el modelo de siete papeles queda
completo: `principal`, `tercero`, `recorte`, `contrapartida`, `tesoreria`, `impuesto` y `retencion`. **No hay ningún
renombrado más previsto.**

**Dos relojes, y solo uno se mueve.** El **paquete** sube a 5.0.0 porque cambia lo que el motor escribe. **El
estándar se queda en `1.0`**: añadir valores a un catálogo y bloques opcionales a la línea es aditivo por su propia
regla de versionado, ningún valor se quita ni cambia de significado, y el esquema gana 35 líneas sin borrar una. Su
tag avanza.

### Cambios de comportamiento

- **Las huellas guardadas dejan de coincidir**, y esto es lo único de esta versión que pide una decisión a quien las
  persista. Se mueven **dos veces, por dos motivos opuestos**, y las dos van en el mismo anuncio:
  1. **El `rol` SALE de la huella**, y esto es lo que de verdad importa. Mientras estuviera dentro, cada corrección
     futura del catálogo de roles invalidaría todas las huellas **en silencio**: no falla, deja de proteger, y
     justo cuando hace falta —el Excel de CONCAR se SUMA al importarlo dos veces—. Sale por el motivo del
     `correlativo` y no por el de la `clase`: no es redundante, es que no es contenido. El mismo asiento con otra
     etiqueta es el mismo asiento. **Desde aquí, ningún renombrado ni valor nuevo del catálogo vuelve a tocarlas.**
  2. **Los dos bloques nuevos SÍ entran.** Una línea de IGV y una de ISC con la misma cuenta y el mismo importe son
     hechos distintos, así que dejarlos fuera podría darles la misma huella.
- **El valor del campo `rol`** cambia en los dos únicos destinos que lo llevan como columna: el **CSV** y el JSON de
  **`asiento_contable`**. Comprobado que la cabecera del CSV no gana ni pierde ninguna columna: normalizando el valor
  del rol, el archivo es idéntico.
- **Código que compare `rol == "igv"`** deja de coincidir. La equivalencia no hay que escribirla a mano: viaja en
  `catalogos_del_estandar()["roles"]["obsoletos"]`.
- **`_obsoleto.RETIRO` pasa de `"5.0"` a `"6.0"`**, sin retirar nada: esta mayor llegó sin ninguna ruta ni alias
  avisando. Es la regla que la 3.10 escribió —una promesa de retiro no sostiene nada si el número que da ya quedó
  atrás— y que se cumple con cada mayor.

### Añadido

- **El Catálogo 05 entra como catálogo de datos, con su fuente.** Era lo único de `catalogos.py` que afirmaba códigos
  de SUNAT sin citar la norma: nueve constantes sueltas, fuera de `FUENTES`, fuera de la fachada y **sin un solo
  test**. Y el agujero no era teórico — la superficie pública congela los NOMBRES y no los VALORES, así que cambiar
  `TRIBUTO_IGV` pasaba verde mientras el lector de XML repartía los importes del comprobante en los campos
  equivocados. La fuente se cerró **leyendo el anexo**: Anexo N.° 8 de la RS 097-2012, con el texto del Anexo II de la
  RS 244-2019. Leerlo trajo dos filas que la deducción no tenía, y una de ellas hacía falta: el **`3000`, Impuesto a
  la Renta**, que es el tributo de una retención de 4ta. Sale por `catalogos_sunat()` con su fuente, y suma
  `TRIBUTO_RENTA` y `CATEGORIA_RENTA_4TA` a la superficie pública.
- **`obsoletos`, el mecanismo con que un catálogo del estándar corrige un valor sin quitarlo.** La regla estaba
  escrita desde la 1.0 y no existía como dato, así que quien integraba no tenía forma de enterarse — y hay
  precedente: el `hacia_donde_va` de los roles anunciaba estos tres renombrados desde la 1.1 y **nunca llegó a la
  api**, porque `catalogos()` no lo propagaba. Ahora cualquier tabla puede llevar `{viejo: {usar, desde, por_que}}`, y
  viaja por la api, por HTTP y por el MCP. Dos diferencias con `_obsoleto.py`, las dos con test: un valor marcado
  **sigue siendo válido al leerlo**, y **no tiene versión de retiro** — no desaparece nunca, porque los documentos ya
  guardados lo llevan dentro.
- **Los dos bloques de la línea.** `impuesto = {codigo}` y `retencion = {codigo, categoria}`, opcionales, con
  `additionalProperties: false`. **Ninguno lleva `tasa`, y es una decisión**: en el repositorio conviven dos
  convenciones sin documentar —`detraccion.porcentaje` es porcentaje y `TASA_IGV` es fracción—, el ICBPER no tiene
  tasa porque es un importe por bolsa, y en la retención el motor no la conoce. Si hace falta, entra con su caso real.
- **Dos tests que STARSOFT no tenía**, que comprueban que sus dos tablas de roles —la que excluye filas y la que las
  ordena— siguen siendo del catálogo vigente.

### Arreglado

- **`estandar/LEEME.md` y `test_huella.py` decían que la huella excluye tres campos**, y eran cuatro desde que la
  enmienda 0021 bajó `medio_pago` a la línea. Ahora son cinco, y LEEME remite a `SIN` en vez de repetir la lista.
- **La enmienda 0021 decía «tres constantes sueltas del lector de XML»** hablando del Catálogo 05. Eran **nueve**, y
  vivían en `catalogos.py`; el lector solo las consume.
- **El borrador de `API-DE-REGISTRO.md` dibujaba el bloque con `"codigo": "igv"`** —el nombre del rol— donde va el
  código del catálogo. Era la confusión que esta versión cierra, escrita en el documento que la propone.

### Cómo migrar

1. **Si fijas una versión** (lo recomendado), no te llega nada hasta que decides subir. Prueba primero la
   pre-release `v5.0.0rc1`, también con `-W error::contaperu._obsoleto.RutaObsoleta`.
2. **Si guardas huellas**, las de antes no van a coincidir. No hay forma de recalcularlas sin el asiento original: lo
   que sí hay es que **esta es la última vez que se mueven por un cambio de rol**.
3. **Si comparas el rol con una cadena**, lee la equivalencia de `catalogos_del_estandar()["roles"]["obsoletos"]` en
   vez de escribirla a mano. Y si lees documentos de terceros, acepta los seis valores: los tres viejos siguen
   publicados y siguen siendo válidos.
4. **Si no tocas el rol** —CONCAR, CONTASIS, SIRE, PLE 5.1, PLE 5.3— no tienes nada que hacer. Comprobado generando
   los archivos con el motor de la 4.3.0 y con el de la 5.0.0: el SIRE, los dos del PLE y STARSOFT salen **idénticos
   byte a byte**, y los Excel de CONCAR y de CONTASIS **idénticos celda a celda**.

## [4.3.0] — 2026-10-01

**El motor escribe el otro libro del par: el detalle del plan contable utilizado.** El grupo 05 del PLE son dos
pares, y hasta ahora el motor solo sabía escribir medio: el Libro Diario 5.1 con sus asientos. Entra el **5.3**, que
son las cuentas que esos asientos usaron, con su denominación.

Y con él entra el dato que el motor no tenía y que **no se puede deducir de nada**: cómo llama la empresa a cada una
de sus cuentas.

### Añadido

- **El driver `ple_plan`**, que escribe el TXT del formato 5.3: 8 campos con palote final, CRLF, una fila por cuenta
  distinta y ordenadas, el periodo en `AAAAMMDD` —con día, a diferencia del `AAAAMM00` del 5.1— y el plan `01` de la
  tabla 17 de SUNAT. Contrastado punto por punto contra el 5.3 que SUNAT aceptó junto al 5.1 del mismo mes.
- **`denominacion_cuentas` en la configuración general**: un mapa `cuenta → nombre`, vacío de fábrica. Es de la
  empresa y no de su formato, así que la misma cuenta se llama igual exporte a donde exporte.
- **La falta `sin_denominacion`**, que se dice **por cuenta y no por comprobante** —como la sigla o el código de
  moneda—, con su lista y su `pedir_a: contador`: es la lista con la que un portal filtra la tabla donde se
  completan. Y el requisito `denominacion` en el contrato de drivers, que solo declara quien lo necesita.
- **`asiento.cuentas_sin_denominacion`** y el caso de conformidad del estándar que la fija.

### Por qué no se inventa el nombre

El motor conoce el nombre de la divisionaria del PCGE —`101` es «Caja»— y **no sirve**: el catálogo llega hasta cinco
dígitos y la empresa desagrega hasta donde quiera, así que de `101101` solo sabría decir «Caja» donde la empresa
escribe «CAJA CHICA M.N.». Escribirlo sería declararle a SUNAT una denominación que el contribuyente no usa, que es la
misma clase de invento que una sigla puesta a dedo. Así que **una cuenta sin nombre para la exportación**, con su
lista, en vez de salir con un nombre que nadie eligió.

### Cambiado

- **Lo que SUNAT impone igual a los dos libros del PLE vive en un sitio** (`drivers/ple/comun.py`): las opciones de
  texto, la oportunidad, las banderas del nombre y el estado. Es la misma convergencia que ya se hizo con la
  nomenclatura `LE…` cuando el SIRE dejó de ser el único libro electrónico.
- **El test que exporta el golden con todos los drivers le da a cada uno lo que exige** en vez de saltárselo, así que
  el driver nuevo se ejerce de verdad.

### Cómo migrar

**No hay que hacer nada.** El driver del 5.1 escribe el mismo archivo, ninguna huella se mueve y el Excel de CONCAR no
cambia una celda. Dos avisos para quien lea la respuesta del motor:

1. **`faltantes` trae una clave más**, `sin_denominacion`, y su lista es de **cuentas**, no de serie-números. Solo
   aparece para un destino que la exija, que hoy es únicamente el del plan contable.
2. **La configuración general trae una clave más**, `denominacion_cuentas`, vacía. Si pintas la pantalla de
   configuración con `describir_configuracion`, aparece sola.

## [4.2.2] — 2026-10-01

**El mapa del PLE deja de ser una deducción y pasa a salir de la norma.** John aportó el **libro oficial de
estructuras del PLE** que publica SUNAT, y leerlo campo a campo corrigió dos cosas que la 4.2.0 había deducido de un
archivo presentado — que es justo lo que la regla «ninguna regla contable sin fuente» existe para evitar.

Nada de esto cambia un byte de lo que el motor escribe: el driver del 5.1 produce el mismo archivo que en la 4.2.1.

### Corregido

- **El campo 5 del 5.1 no es la denominación de la cuenta.** Es el **código de la Unidad de Operación**. Iba vacío en
  las 12 094 líneas del archivo contrastado y de ahí se dedujo —mal— que era la denominación y que el artículo 6 la
  hacía opcional. La denominación **no está en el 5.1 en absoluto**.
- **El formato 5.3 no es el Libro Diario Simplificado.** Es **«Libro Diario - detalle del plan contable utilizado»**,
  y es donde vive la denominación: una fila por cuenta, 725 en el archivo contrastado, en vez de repetirla en cada una
  de las 12 094 líneas. El simplificado es el **5.2**, con su propio detalle de plan en el **5.4**. El grupo 05 son
  **dos pares**, no cuatro formatos sueltos. La 4.2.0 decía lo contrario en su CHANGELOG y en `LIBROS-Y-CUENTAS.md`.
- **`contaperu/drivers/ple/txt.py` usaba `Any` sin importarlo.** No rompía nada en ejecución —`from __future__ import
  annotations` deja la anotación sin evaluar— pero `typing.get_type_hints` sobre ese módulo lanzaba `NameError`.

### Añadido

- **El mapa del formato 5.3** en `datos/sunat/ple_campos.json`, al lado del 5.1, con sus 8 campos y la periodicidad
  que manda SUNAT: «obligatorio en el periodo de enero cada año o cuando se genera el libro electrónico por primera
  vez; en los demás meses se puede optar por generar un libro vacío salvo que el Plan Contable sufra modificaciones».
- **La obligatoriedad de cada campo**, que antes no estaba, y los **códigos de libro completos** del grupo 05
  (`050100`, `050200`, `050300`, `050400`) más el `080200` del registro de compras de no domiciliados.
- **Ya no queda nada `[por confirmar]`** en el mapa, y un test lo vigila: lo que no salga de la estructura oficial no
  se escribe.

## [4.2.1] — 2026-10-01

**El Libro Diario no se inventa un vencimiento.** Primer arreglo del driver `ple`, encontrado al contrastar su salida
contra el archivo real justo después de publicar la 4.2.0.

### Arreglado

- **El campo 14 del 5.1 sale de la cabecera del comprobante y no de la línea.** Cuando un comprobante **no trae fecha
  de vencimiento**, el núcleo la rellena con la de emisión —a CONCAR le vale, porque su columna no puede ir vacía— y
  el driver la escribía tal cual. En un libro que se presenta a SUNAT eso es **escribir un dato tributario que el
  documento nunca tuvo**. Ahora se lee de `Cabecera.fecha_vencimiento`, que conserva la verdad, y donde no hay
  vencimiento va la fecha nula del formato (`01/01/0001`) — como hace el archivo contrastado en 4088 de sus 6446
  filas con comprobante. El núcleo **no cambia**: sigue rellenando, porque el Excel de CONCAR depende de ello, y
  ninguna huella se mueve.

Nada más cambia. Quien no use el driver `ple` no nota esta versión.

## [4.2.0] — 2026-10-01

**Un Libro Diario presentado a SUNAT entró como caso real, y de él salen las dos cosas de esta versión:** el formato
del 5.1 publicado columna a columna, y los dos papeles que al catálogo de roles le faltaban.

El archivo: un Libro Diario del formato 5.1 de un mes, **presentado y aceptado por SUNAT con sus constancias de
recepción**. 12 094 líneas, 1 441 asientos y ninguno descuadrado. Vive solo en `privado/`, que `.gitignore` bloquea;
de él salen conteos agregados y nada más.

**No se movió ni una huella**, el Excel de CONCAR no cambió una celda y el motor emite exactamente las mismas líneas
que antes. Todo lo de esta versión es aditivo.

### Añadido

- **El formato del Libro Diario 5.1, columna a columna** (`datos/sunat/ple_campos.json`), como ya estaba el del SIRE:
  de cada uno de sus 21 campos, de dónde lo saca un driver al escribirlo —o por qué va vacío— y qué hizo con esa
  columna el libro contrastado. Con **los códigos de libro verificados**: `050100` el Diario, `050300` el Simplificado,
  `080100` Compras y `140100` Ventas. Ojo, **no son los del SIRE**, que usa `140400` y `080400`. Se sirve por
  `api.campos_del_ple()`, por `GET /v1/catalogos/ple-campos` y por el recurso MCP `contaperu://catalogos/ple-campos`.
- **Dos roles nuevos, `contrapartida` y `tesoreria`** ([enmienda 0021](estandar/enmiendas/0021-contrapartida-y-tesoreria.md)),
  que nombran dos hechos que el catálogo no sabía nombrar: la otra cara de un hecho que no se le debe a nadie —la
  depreciación acumulada frente a su gasto, la cuenta de destino frente a la `79`— y el dinero moviéndose. De los 1 441
  asientos del archivo, **595 no referencian ningún registro** y ninguno de los dos papeles tenía rol. El catálogo de
  roles pasa a su `1.1`; **la versión del estándar no se mueve**, avanza su tag.
- **`medio_pago` en la línea**, opcional, con el mismo catálogo de SUNAT que ya usaba en el comprobante. Completa el
  bloque que abrió la enmienda 0004, que dejó publicada la tabla y la línea sin ella: el comprobante dice con qué se
  paga la operación y la línea de rol `tesoreria` dice con qué se movió el dinero.
- **`asiento.ROLES_DEL_MOTOR`**, los seis que el motor escribe, al lado de `asiento.ROLES`, que son los ocho del
  catálogo. Es la distinción que entra con esta versión: un driver tiene que **entender** los ocho porque puede
  recibirlos; el motor **emite** seis, porque genera compras y ventas.
- **El driver `ple`**, que escribe el TXT del Libro Diario 5.1: 21 campos por fila con palote final, CRLF, el CUO
  compuesto del sub-diario y el correlativo que el motor ya numera, y el secuencial `M000N` dentro de cada asiento.
  Canal `tributario`, como el `sire`. **Lo que emite es el Libro Diario de los comprobantes del mes, no el libro
  completo**: en el archivo contrastado, 595 de 1441 asientos no vienen de ningún registro —el asiento de destino,
  los pagos, la planilla, la depreciación— y el motor no los origina. Es el mismo límite que tiene el `sire`.

### Cambiado · el contrato de drivers

- **Un driver tributario puede recibir las líneas** (`desde_lineas`), y no solo escribir una fila por comprobante
  (`linea`). Lo pidió el 5.1, cuya fila **es una línea del asiento**: una compra con detracción son cinco filas. Lo
  que la regla protege sigue en pie — un tributario escribe texto para SUNAT, no un Excel ni un JSON.
- **Y recibe correlativos**, que antes decidía la familia: la del `ple` es `registro`, pero su CUO se compone del
  sub-diario y del correlativo. Para los drivers de antes **la condición es la misma**, porque todos los
  `desde_lineas` que había eran ya de familia asiento: no se movió ni un correlativo de los que ya se escribían.
- **Unir las líneas y codificarlas sale al kit** (`kit.armar_archivo`), y la nomenclatura `LE…` de un libro
  electrónico también (`kit.nombre_de_libro_electronico`). Las dos vivían dentro del driver del SIRE, que hasta ahora
  era el único libro electrónico. Una regla que SUNAT impone no puede estar escrita en dos drivers.

### Cambiado

- **`medio_pago` queda fuera de la huella** (`asiento.huella.SIN`, que pasa de tres exclusiones a cuatro). Es la
  promesa que la enmienda 0004 escribió al entrar —«el medio de pago no cambia ningún asiento ni ningún importe»— y
  que hasta ahora se cumplía sola porque el campo vivía en la `Cabecera`, que no se hashea. Al bajar a la línea hay
  que declararlo, o se habría roto sin que nadie lo notara.
- **Dos correcciones de lo que el repositorio creía del formato**, las dos del archivo real: el Libro Diario de
  Formato Simplificado es el **5.3** y no el 5.2, y **la denominación de la cuenta no se llena** —el formato en papel
  la pide, pero el artículo 6 de la RS 234-2006 la hace opcional a quien usa más de cuatro dígitos de subcuenta, y en
  las 12 094 líneas va vacía—.

### Cómo migrar

**No hay que hacer nada.** Ningún valor se quitó, ninguno cambió de significado, ningún campo pasó a ser obligatorio y
las huellas guardadas siguen valiendo. Dos avisos para quien lea el catálogo de roles:

1. **Trae ocho valores y no seis.** Si tu código los recorría esperando seis, ahora hay dos más — y la regla de
   degradación sigue siendo la de siempre: un rol que no conoces se contabiliza con `clase`, `debe_haber` e `importe`.
2. **`igv` y `retencion_4ta` NO están marcados como reemplazados**, aunque el catálogo diga hacia dónde va. Son lo que
   el motor escribe en cada asiento, y lo seguirán siendo hasta una versión mayor. El `hacia_donde_va` del catálogo lo
   explica: el modelo al que va son siete papeles con el tributo en su bloque, y los renombrados entrarán todos juntos
   porque cada uno invalidaría las huellas guardadas.

## [4.1.0] — 2026-10-01

**La propuesta del SIRE dice QUE hay detracción; quien integra dice CUÁL.** Un mes importado de la propuesta —el caso
normal de un estudio contable, porque los XML los tiene el cliente— se exportaba **sin ninguna detracción y en
silencio**. El asiento salía mal: sin la línea de la detracción, la cuenta por pagar al proveedor queda inflada, y
nada decía cuáles eran. El aviso `SIRE_SIN_DETALLE` salía en **todos** los comprobantes por igual, así que no
distinguía al que le falta la detracción del que nunca la tuvo.

Y era peor de lo necesario, porque SUNAT sí lo dice: el **campo 38 del Anexo 8 de la RS 040-2022** trae una `D` en las
filas sujetas al SPOT. El motor lo ignoraba, y `datos/sunat/sire_campos.json` lo tenía anotado como «candidato a
entrar: **espera su caso real**». El caso real llegó: un RCE de verdad, 3018 filas, **221 marcadas**.

Lo que falta para armar la detracción es **una sola cosa, el código del Catálogo 54**: de él salen la tasa (la tabla
del motor) y el monto (`total × tasa`, soles enteros). Y no se inventa —inventarlo escribiría una tasa falsa en el
asiento y un código interno falso en CONCAR—, así que lo pone quien integra, por el canal con el que ya pone la cuenta
contable.

### Añadido

- **El lector del RCE lee la marca** y la guarda como anotación: `detraccion: {"_marca_sire": "D"}`, **sin código**. Es
  la primera que usa la puerta que abrió la 4.0 (las anotaciones `^_` dentro de `detraccion`, enmienda 0019). Solo
  compras: el RVIE no tiene esa columna en ninguno de sus 40 campos.
- **`imputacion` acepta `detraccion_codigo`** (enmienda 0020), junto a `cuenta_contable`, `centro_costo`,
  `cuenta_tercero` y `reparto`. Puesto el código, la detracción nace completa en los seis destinos, con su código
  interno y su sigla, igual que si el comprobante hubiera entrado por su XML. Aditivo: la versión del estándar no se
  mueve, avanza su tag.
- **La falta `sin_codigo_detraccion`**, con su lista de comprobantes y `pedir_a: "contador"`. Es la lista con la que un
  portal filtra la tabla donde el contador los completa.
- **El requisito `detraccion` del contrato de drivers**, que declaran los cinco destinos que escriben un asiento. El
  driver `sire` **no**: el registro tributario no lleva detracción, así que un mes marcado se sigue declarando.

### Cambiado

- **`detracciones.normalizar` conserva las anotaciones `_` al blanquear** una detracción sin código reconocible. Hasta
  la 4.0 se llevaba el bloque entero, y con él la marca: la única prueba de que a ese comprobante le faltaba algo.
  `_tasa_tabla` no sobrevive, y con motivo: es la tasa de un código, y sin código no hay nada que anotar.
- **La CLI tiene tope.** `diagnosticar` imprimía una línea por observación y por comprobante, y unía cada lista en UNA
  línea: sobre el RCE real de 3018 filas eran **3018 líneas del mismo aviso y 36 KB de salida**. Ahora enseña las
  primeras doce y dice cuántas quedan y de qué códigos son. La lista completa sigue entera en la respuesta de
  `diagnosticar`, que es de donde la lee un portal.

### Cómo migrar

1. **Un mes importado de la propuesta del SIRE con detracciones marcadas deja de exportar** hasta que se ponga el
   código de cada una. Es el cambio de comportamiento de esta versión, y es a propósito: antes esos meses salían con el
   asiento incompleto y sin avisar. Lo que hay que hacer son dos cosas: leer
   `diagnosticar(...)["faltantes"]["sin_codigo_detraccion"]` para saber cuáles son, y mandar `detraccion_codigo` en la
   imputación de cada uno. **No afecta a un mes que entró por XML**: ahí el código viene en el archivo.
2. **El TXT del SIRE no se ve afectado**: ese driver no exige la detracción, así que un mes marcado se declara igual.
3. **Si leías `faltantes` esperando un juego fijo de claves**, ahora trae una más. Y `exige` de los cinco drivers de
   asiento trae `detraccion`.
4. **Si imprimías la salida de `contaperu diagnosticar`** y contabas con una línea por comprobante, ahora hay tope.

## [4.0.0] — 2026-10-01

**La base que leen todos es la detracción de SUNAT, y de ahí pasa por cada driver** (decisión de John, 30-sep-2026).
La línea del comprobante llevaba vocabulario de un sistema contable concreto, y el núcleo lo escribía para todos los
destinos: la sigla `DR` —la Tabla General 06 de CONCAR—, el código interno de cinco dígitos —su Tabla General 28— y la
sigla de cada tipo de comprobante. Nada de eso es contabilidad peruana: es cómo numera **un** sistema sus tablas.

Lo que costaba, y no era teórico:

- **STARSOFT nacía con catorce mapeos de CONCAR que nunca leyó.** Escribe el código de SUNAT a propósito —su propio
  comentario lo dice: «el código de SUNAT (`027`), no el interno que CONCAR mapea en su tabla (`02702`)»— y los dos
  campos salían igual en su pantalla de configuración sin hacer nada.
- **El CSV de intercambio escribía códigos de CONCAR.** `02702` en su columna de detracción y `DR` en la del tipo de
  documento: quien lo leyera desde otro sistema tenía que conocer CONCAR para entenderlo.
- **El núcleo inventaba.** Un código de detracción que la empresa no hubiera mapeado salía como el de SUNAT más `01`,
  «el patrón más común» de una tabla ajena. Una conjetura, hecha en el núcleo, contra la regla de que nada se adivina.
- **La línea solo podía llevar la sigla de un destino.** Con dos sistemas sobre el mismo mes, la que escribía era la
  del que se estuviera exportando.

Ahora la línea lleva **códigos de SUNAT** —el Catálogo 54 en la detracción, la Tabla 10 en el documento— y cada driver
traduce al vocabulario de su sistema, en la columna que le toque. Las tres Tablas Generales de la detracción quedan
juntas en `drivers/concar/`: la 06 (la sigla, columna R), la 28 (el interno, columna AI) y la 26 (el área, columna V,
que ya vivía ahí). La traducción de la sigla de un tipo la hace `asiento.sigla_de_tipo`, un nombre nuevo de la
superficie pública, porque un driver legacy de terceros lo necesita.

**El Excel de CONCAR no cambia ni una celda.** Sus 52 casos de snapshot pasan sin regenerarse, con el driver
calculando lo que antes recibía. Es la comprobación que manda en todo el cambio, y por eso el primer commit movió solo
la escritura y dejó el resto en quitar.

**Y la 4.0 cobra la deuda que tres versiones dejaron anotada para ella.** Dos promesas del contrato de drivers decían
«se retira en la 2.0» con el paquete en la 3.10 —el mismo vicio que la 3.10 corrigió en `_obsoleto.RETIRO`: «una
promesa de retiro no puede sostener nada si el número que da ya quedó atrás»—, y había quedado sin barrer en tres
sitios más:

- **La forma `construir` se retira.** Recibía los comprobantes y el driver se armaba el archivo entero, o sea hacía la
  contabilidad: era la del Excel de CONCAR hasta la 0.10 y contradice lo que el contrato promete dos párrafos antes.
- **`CANAL` pasa a obligatorio.** Sin él se adivinaba `legacy`, y de ese canal salen las reglas que el contrato hace
  cumplir. Ningún driver de serie se entera: los siete lo declaran.
- **Se retira el nombre `asiento_neutral`**, con su módulo talón y sus trece nombres congelados. Avisó durante toda la
  3.x, que es lo que `CLAUDE.md` promete. El mecanismo se queda vacío para el próximo renombrado, con su test.
- **`starsoft.proyeccion.voucher` pasa a `correlativo_de_starsoft`**: su columna se renombró el 21-sep-2026 y la
  función no podía seguirla hasta una mayor.
- **`_obsoleto.RETIRO` pasa a la 5.0**, que es la regla que la 3.10 escribió: se mueve con cada mayor que cumple.

**Y el comprobante deja de tragarse lo que no entiende.** `INTEGRAR.md` promete desde hace versiones que «una clave
que el estándar no conoce se rechaza en vez de ignorarse: un dato que se cuela sin error es un dato que se pierde sin
aviso», y la librería hacía lo contrario: la filtraba en silencio. Se encontró probando esta misma versión de punta a
punta, escribiendo `retencion_4ta` donde el campo se llama `retencion`: **el mes se exportó entero sin la línea de
retención de 4ta**, y solo se vio leyendo las celdas del Excel. Además dejaba al motor más laxo que su propio esquema
publicado, que ya rechaza por su `additionalProperties: false`. Ahora el rechazo nombra todas las claves sobrantes y
dice adónde va lo que el motor no entiende: `datos_originales`. La forma estaba ya en el repositorio —`LineaDiario`
rechaza así desde la 1.0— y la promesa hermana, la de la imputación, también se cumplía: faltaba solo el comprobante.

**El estándar gana una pieza, y es aditiva** (enmienda 0019): `$defs/detraccion` admite claves `^_` como ya hacía la
raíz, así que la anotación de la tasa de la tabla pasa a `_tasa_tabla` y **viaja dentro del documento** en vez de
filtrarse al salir. Con el filtro, un documento que volvía a entrar al motor había perdido la tasa con la que se
calculó el monto, y su validación ya no podía avisar de la discrepancia que el motor sí vio la primera vez.
`open-accounting` sigue en **1.0**: lo aditivo avanza el tag, no la versión.

### Cómo migrar

1. **La columna `detraccion_codigo` del CSV lleva ahora `027` y no `02702`, con la misma cabecera.** Es el cambio más
   silencioso de esta versión: no falla, cambia de significado. Si lo lees por nombre de columna, míralo primero.
2. **`detraccion.codigo_interno` desaparece de la línea.** El código de SUNAT está en `detraccion.codigo`; el interno
   de tu tabla lo escribe tu driver (enmienda 0017).
3. **`documento.tipo` y `referencia.tipo` desaparecen de la línea.** El código de SUNAT está en `tipo_cp`, que siempre
   estuvo al lado; la sigla la pone cada driver con `asiento.sigla_de_tipo` (enmienda 0018). La columna `doc_tipo` del
   CSV va vacía.
4. **La huella cambia en TODOS los comprobantes**, porque la sigla entraba en ella —de la línea solo quedan fuera el
   correlativo, la clase y el `id_externo`—. Quien la persista para saber qué ya exportó **deja de reconocer, una vez,
   todo lo anterior**. La de los comprobantes con detracción cambia además por el código interno.
5. **`contaperu.asiento.TIPO_DOC_DETRACCION` ya no existe**: la sigla `DR` es de CONCAR y vive en
   `contaperu.drivers.concar`.
6. **`driver="asiento_neutral"` deja de resolver**, y su sección de configuración también —el error dice adónde se
   movió—. Ojo: **los archivos ya exportados llevan ese nombre dentro**, en `_exportacion.driver`, y eso no lo arregla
   ninguna versión: el alias cubría la entrada, no los datos en disco. Un consumidor que ramifique sobre ese valor
   acepta los dos nombres para siempre.
7. **Si guardaste `detraccion_tipo_doc` o `detraccion_codigos` en la sección `csv` o `starsoft`**, muévelos a `concar`:
   ahí es donde se declaran.
8. **Un driver de terceros** con la forma `construir` o sin `CANAL` deja de cargar, con el error diciendo qué hacer.
9. **`starsoft.proyeccion.voucher` pasa a `correlativo_de_starsoft`.**
10. **Una clave que el estándar no declara, en un comprobante, ya no se ignora: se rechaza.** Si mandabas una de más
    —el nombre equivocado de un campo, o un dato tuyo—, el documento entero se rechaza con `DocumentoInvalido`
    nombrándola. Lo tuyo va en `datos_originales`, que se transporta sin interpretar. Las anotaciones `_` siguen
    valiendo en la raíz del documento, no dentro de un comprobante.
11. Lo que **no** cambia: el Excel de CONCAR, el de CONTASIS, el TXT del SIRE y el TXT de STARSOFT salen idénticos, y
    `open-accounting` sigue en 1.0.

## [3.10.0] — 2026-09-29

**El driver del asiento se llama `asiento_contable`, y las palabras dicen por fin lo que son.** Se llamaba
`asiento_neutral`, y ese nombre describía de qué se libraba en lugar de qué es. «Neutral» se eligió en la 0.7 con un
motivo bueno —distinguir estas líneas de las columnas del Excel de CONCAR, de donde entonces se releían— y con la
misma versión ese motivo caducó: desde que la línea es la fuente y CONCAR una proyección, el adjetivo nombra una
ausencia. Un ERP que elige un destino no busca un asiento neutral: busca **el asiento contable**. Es la salida que
pasa a ser la principal para quien no tiene un sistema contable legacy, así que tenía que decirse sola.

**Nadie se rompe, y eso costó más que el renombrado.** A diferencia de la 1.1.0, cuando este mismo driver pasó de
`open_accounting` a `asiento_neutral` y fue gratis porque nada publicado llevaba el nombre viejo, hoy el paquete está
en PyPI y una aplicación en producción fija su versión. Así que **el nombre viejo sigue resolviendo toda la 3.x y
avisa**:

- `driver="asiento_neutral"` funciona y avisa con `RutaObsoleta` diciendo cuál usar. El alias vive en
  `drivers.ALIAS`, y **a propósito fuera de `DE_SERIE`**: dentro aparecería como un destino más en
  `drivers_disponibles()`, en el recurso `contaperu://drivers` y en la docena de sitios que comprueban la lista de
  destinos. Un alias no es un destino: es la misma salida por su nombre anterior.
- **Las cuatro formas de importar el módulo viejo siguen valiendo**, porque `contaperu/drivers/asiento_neutral/` sigue
  existiendo como talón que reexporta. Un `__getattr__` de paquete habría cubierto solo dos: `import
  contaperu.drivers.asiento_neutral` y `from …asiento_neutral import NOMBRE` necesitan que el módulo exista.
- **La superficie pública no pierde nada**: el talón declara los trece nombres que congeló la 1.0, así que el test de
  superficie pasa sumando el módulo nuevo y sin quitar el viejo. Por eso esto es una menor y no una 4.0.
- Una configuración guardada con la sección `asiento_neutral` recibe el mensaje que dice a qué se movió, en vez de
  «clave desconocida».

Todo se retira en la **4.0** (`_obsoleto.RETIRO`), que es lo que promete `CLAUDE.md`: lo que se retira avisa durante
toda la mayor anterior. De paso, ese `RETIRO` decía «3.0» con el paquete en la 3.9 —un aviso que citaba una versión ya
pasada— y el texto de `avisar` estaba cableado a «es una ruta de la 0.x», que es falso para el nombre de un driver.
`INTEGRAR.md` prometía «la 1.x» en su primera línea y «la 2.x» en su última sección: las dos promesas iban dos mayores
por detrás.

**Y «línea neutral» pasa a ser «línea del comprobante»** (decisión de John, 29-sep-2026), en 56 sitios de prosa. El
sustantivo no cambia porque ya era el correcto —es `linea` en el estándar y `JournalLine` en QuickBooks, Xero y
Merge—; lo que sobraba era el adjetivo. Donde se habla del conjunto de un libro son «las líneas del asiento», que es
lo que son. **No se renombra** `LineaDiario`, ni el valor `VOCABULARIO = "neutral"`: ese sí describe lo que es —las
palabras del estándar frente a las de un sistema legacy—, es un enum publicado, y cambiarlo rompería en silencio a
cualquier driver de terceros que lo declare. El párrafo de `ARQUITECTURA.md` que cuenta de dónde salió la palabra se
conserva, porque es la única fuente escrita de por qué se dijo así.

El glosario del README gana las cuatro palabras sobre las que gira el estándar y que no definía: **asiento**, **línea
del comprobante**, **registro** —con su desambiguación, porque en el contrato es la otra familia de salida: una fila
por comprobante y sin cuentas, no una línea del asiento— y **vocabulario legacy**.

### Cómo migrar

- **Cambia `driver="asiento_neutral"` por `driver="asiento_contable"`** cuando puedas. Mientras no lo hagas funciona
  igual; corre tu batería con `-W error::contaperu._obsoleto.RutaObsoleta` y te sale cada sitio.
- **El formato pasa a `asiento_contable_json`** y el archivo a `ASIENTO_CONTABLE_<libro>_<periodo>_<ruc>.json`. Si
  tienes un script que lo busca por su nombre, es lo primero que mirar. Los archivos ya exportados conservan el
  suyo y su `_exportacion.driver: "asiento_neutral"`: **el alias cubre la entrada, no los datos que ya están en
  disco**, así que un consumidor que ramifique sobre ese valor tiene que aceptar los dos nombres.
- **Ninguna huella se mueve**: va solo sobre las líneas, y ni el nombre del driver ni el del archivo entran en ella.
  Lo que ya importaste sigue reconociéndose.

## [3.9.0] — 2026-09-29

**El documento del estándar se basta, y por eso puede volver a entrar al motor.** El driver `asiento_neutral` escribía
el libro y el asiento, y eso deja preguntas que un asiento no puede contestar. Una compra de 100 gravado más 50
exonerado produce **una sola línea de gasto de 150** —la contabilidad es correcta— y quien recibía el archivo no tenía
forma de separar el desglose ni de comprobar que el IGV de 18 iba sobre 100 y no sobre 150. El nombre del proveedor
viajaba **por accidente**, dentro de la glosa y solo mientras el concepto viniera vacío: con un concepto propio
desaparecía del archivo y el ERP se quedaba con el RUC a secas. Y una nota de crédito revertía bien los importes sin
decir por qué se emitió.

Ahora escribe **los tres bloques que el estándar ya definía** —`libro`, `comprobantes` y `asiento`—, y el bloque nuevo
no inventa nada: sale de la cabecera del índice, que el driver tenía en la mano y descartaba. Cero enmiendas al
estándar y ninguna versión nueva de él, porque un bloque opcional es aditivo. Lo que esto consigue es lo de fondo: el
documento **vuelve a entrar al motor y da el mismo asiento, con la misma huella** —comprobado sobre el mes de los
casos: 39 líneas idénticas, mismos tramos, misma huella—, así que un ERP no necesita haber guardado nada más.

Va siempre y no bajo una opción: un documento que solo a veces se basta obliga a quien lo lee a manejar dos formas y
deja condicional la única garantía que hace útil el formato. **No** lleva `imputaciones`, y también a propósito: el
esquema exige entonces `id_externo` en todos los comprobantes, así que un mes cuyo productor no los puso daría un
documento que falla su propio esquema — quien quiera el asiento idéntico al volver a entrar pasa la misma imputación.
Y no lleva `emisor`: el estándar dice «quién generó este documento», y quien lo genera es la aplicación que llama.

**Para que fuera posible, la cabecera del comprobante tuvo que llevar ya todos sus hechos.** Le faltaban ocho —el
concepto, el vencimiento, el tipo de cambio, los cuatro del comprobante que modifica una nota y la detracción—, con el
argumento de que repetirlos sería tener el mismo hecho en dos sitios porque ya viajaban dentro de la línea. El
argumento se cae en cuanto hay que escribir un comprobante: desde la línea esos ocho **no se pueden recomponer**
—`referencia.serie_numero` va unido por un guion y no hay vuelta fiable, y la cuenta del Banco de la Nación de la
detracción no está en ninguna línea— y sin ellos la validación se detenía en `VENCIMIENTO_FALTA`, `TC_FALTA` y
`NOTA_SIN_REFERENCIA`. La línea responde «qué se asienta» y la cabecera «qué decía el comprobante»: son dos preguntas.

Con ellos dentro, **`Cabecera.como_comprobante()`** produce un `comprobante` que valida contra el esquema publicado.
Dos cosas lo impedían: la `glosa`, que pasa a ser una **propiedad derivada** del concepto —no es un hecho, el estándar
no la declara, y siendo derivada ya no puede discrepar de su fuente—, y la detracción, que ahora se **filtra a las
siete claves del estándar** porque el motor anota además `tasa_tabla` y `$defs/detraccion` la rechaza por su
`additionalProperties: false`. `a_dict()` no cambia para nadie: sigue llevando lo vacío y la glosa.

**Y el comodín de la detracción deja de salir del Perú.** El `999999999` es un apaño de los sistemas peruanos para
llenar una columna obligatoria cuando el depósito todavía no se ha hecho, y se colaba en el vocabulario del estándar:
el flag solo suprimía el código interno y la constancia se resolvía igual para los dos. Un ERP de fuera recibía en
`detraccion.nro_constancia` un vóucher que no existe, sin nada que se lo advirtiera y contra lo que prometía el propio
docstring del driver — y el test que vigilaba ese perfil no lo veía, porque solo mira el documento comodín. Ahora
`asiento.constancia_de` acepta `comodin=False` y entonces no inventa el pendiente ni repite el que venga en el
documento (un comodín guardado de una exportación anterior tampoco es un depósito): **sin depósito, la clave no
viaja**. La constancia de verdad sale igual que antes. Al legacy no se le quita nada: su columna es obligatoria.
De paso, la lista de los dos comodines deja de estar escrita dentro de `estado_de` y pasa a `detracciones.es_comodin`.

**Y la salida que va a ser la principal tiene por fin su snapshot.** CONCAR tiene sus 52 casos vigilados celda a celda
desde la 0.6; esta no tenía ninguno, y lo que parecía serlo engañaba: `lineas_neutrales.json` se genera sin
`vocabulario="neutral"`, así que su contenido es **legacy** —sub-diario, correlativo y la sigla `FT`— y nunca fueron
las líneas del estándar. Pasa a llamarse `lineas_legacy.json`, sin tocar un byte. El nuevo,
`documento_del_estandar.json`, congela el documento entero en ocho casos, cada uno elegido por algo que el asiento por
sí solo no puede contar.

### Cómo migrar

- **La huella del vocabulario del estándar cambia** en los comprobantes con detracción sin constancia, porque la línea
  ya no lleva el comodín. Un ERP que las persista para saber qué importó **deja de reconocer esos comprobantes** y los
  verá como nuevos. La de CONCAR y los demás destinos legacy no se mueve: su snapshot de 52 casos está intacto.
- **El archivo pesa un 48 % más** y eso acerca el tope de 4 MB de las puertas MCP y HTTP: medido con facturas simples,
  de **~2.042 a ~1.381 comprobantes** por llamada. Un mes entre esas dos cifras que hoy pasa, pasará a pedir lotes.
- **Dos claves se llaman `comprobantes`** en el mismo archivo y no son lo mismo: la de la raíz son los hechos de cada
  comprobante —el bloque del estándar— y la de `_exportacion` es su identidad, su tramo de líneas y su huella. La
  segunda se llama así desde la 3.1 y no se renombra.
- **`Cabecera(glosa=…)` deja de aceptarse**, porque `glosa` ya no es un campo. El único constructor del motor es
  `asiento.cabecera_de`; solo afecta a quien construya una cabecera a mano.
- Nada más cambia: los cinco destinos legacy, el TXT del SIRE y la api producen lo mismo, bit a bit.

## [3.8.0] — 2026-09-29

**El formato del SIRE deja de estar repartido en tres sitios que nada obligaba a concordar.** El conocimiento de qué
columna del RVIE y del RCE es cada cosa vivía a la vez en el lector (`POS_VENTA`, `POS_COMPRA`), en los nombres que
`comparar_sire` usa para su informe y en el escritor del driver `sire`. Tres listas paralelas, copiadas a mano del
anexo, que podían separarse sin que nada se rompiera — y el aviso ya había llegado: **tres de las cuatro versiones
anteriores fueron columnas del SIRE mal leídas o ignoradas**. La 3.5.0 es el caso que lo explica solo: `tipo_nota` y
`estado_sunat` estaban en la lista de «referenciales que se ignoran» y resultó que importaban, con cinco filas reales
que SUNAT había dado de baja y que el motor leía como si les faltara el importe.

Ahora hay **una sola fuente, publicada**: `datos/sunat/sire_campos.json` describe las 40 columnas del RVIE y las 41
del RCE, y de cada una dice su número de campo del anexo, el nombre que le da SUNAT, el campo del documento donde cae
—o **el motivo por el que no cae**— y si el TXT de reemplazo la devuelve con dato, presente y vacía, o no la manda.
Se consulta con `api.campos_del_sire()` (recurso `contaperu://catalogos/sire-campos`, `GET
/v1/catalogos/sire-campos`), y es el hermano de `catalogos_api_sire`: aquel describe el CANAL —a qué ruta se sube un
registro— y este el FORMATO. Los dos describen sin ejecutar.

Lo que esto responde, y antes había que leer el código para saberlo: **de las 81 columnas, 63 son campos del
documento y 18 no**, y ninguna de las 18 se pierde —la fila entera del TXT viaja en `datos_originales["sire"]`—. De
esas, ocho son la cabecera del libro o el CAR de SUNAT, y las diez restantes llevan su motivo escrito. Dos van
señaladas como **candidatas a entrar el día que haya un caso real** detrás, que es la única forma en que una regla
entra aquí: la **marca de detracción del RCE** (campo 38), porque el motor ya avisa `SIRE_SIN_DETALLE` y una marca de
sujeción al SPOT sí sería un hecho tributario, y el **valor de operaciones gratuitas del RVIE** (campo 37), porque
una entrega gratuita tiene tratamiento contable propio.

El mapa no puede separarse del código: `tests/test_sire_campos.py` lo confronta con las dos puntas —lo que el lector
lee y lo que el driver escribe, columna por columna— y se comprobó con cinco mutaciones que las cinco lo ponen en
rojo. `comparar_sire` **deriva** de él los nombres de su informe en vez de llevar su propia copia, así que ya no
pueden decir cosas distintas. De paso se corrige un comentario del lector que nombraba tres cosas para cuatro huecos
(los índices 34-36 son el % de participación, el IMB y el CAR original; el 37 es la marca de detracción).

**Y quien integra tiene por fin en un solo sitio quién aporta cada variable.** `INTEGRAR.md` gana la sección que
responde la pregunta que llega siempre —«¿dónde meto lo mío?»— con los cuatro sitios y, lo que faltaba, cuáles
aceptan variables que el motor no conoce: el documento no, porque una clave desconocida se rechaza en vez de perderse
sin aviso; la imputación tampoco, y con su porqué, que es que el motor resuelve la cuenta una sola vez para todos los
drivers; la sección del driver sí, libre y por contribuyente; y `datos_originales` sí, pero solo transporta. Con los
dos caminos para un dato que todavía no existe: al estándar si es un hecho del comprobante, y a `dimensiones` —el
nombre ya reservado, en la imputación y no en el documento— si es una dimensión analítica del entorno.

Nada cambia de comportamiento: el Excel de CONCAR, el TXT del SIRE y los asientos salen idénticos.

## [3.7.0] — 2026-09-27

**Qué le cobraron de IGV a un comprobante deja de deducirse por descarte.** La pantalla del portal miraba cuatro
importes y, si ninguno tenía valor, contestaba «Inafecto» — con un `0.00` al lado. Así es como 460 compras de un mes
real, que informan su importe en la columna de adquisiciones no gravadas del RCE, salían etiquetadas con la palabra
equivocada y un importe que no era el suyo.

### Añadido

- **`igv.clase_de_igv(c, es_venta)`**: qué le cobraron, deducido de los importes. **No se elige, sale de los
  importes**, que es la regla de esta casa desde el 10-sep-2026.

  **No es `destino_igv`, y la confusión cuesta cara**: aquella dice PARA QUÉ se usa una compra —`DG`, `DGNG`, `DNG`—
  y solo tiene sentido si te cobraron IGV. El modelo pone `DG` por defecto a **todo** comprobante, también a una
  compra que no tiene IGV que destinar, así que leer el destino para responder a esta pregunta contesta «gravada» a
  media contabilidad. El aviso llevaba escrito desde la 2.x dentro de un driver
  (`drivers/starsoft/proyeccion.destino_de`, que tuvo que resolverlo por su cuenta); ahora vive en el núcleo, que es
  donde puede mirarlo también quien pinta la pantalla.

  **Los dos libros no dan las mismas clases, porque no informan lo mismo.** En compras: `gravada`, `no_gravada`,
  `importacion` —que se reconoce por la DUA, no por un importe— y `mixto`. En ventas siguen siendo `afecto`,
  `exonerado`, `inafecto`, `exportacion` y `mixto`, porque el RVIE sí separa exonerado de inafecto en dos columnas.
  Llamar «Inafecto» a una compra afirmaría algo que su archivo no distingue.

  Y **devuelve cadena vacía cuando no hay ningún importe**: así declara SUNAT lo que se da de baja, y un comprobante
  en cero no es gravado ni no gravado. Decir cualquiera de las dos cosas sería inventar.

- **`catalogos.CLASES_IGV_COMPRA` y `CLASES_IGV_VENTA`**, con el nombre en castellano de cada clase, y las dos salen
  por `catalogos_sunat()`: el vocabulario de la pantalla no se escribe dos veces. La cadena vacía no está en ninguna
  de las dos, a propósito.

- **`igv.aplicar_no_gravado(c, importe, campo)`**, hermana de `aplicar_igv` y `aplicar_total`: la persona escribe UN
  importe y el motor recoloca la base, sin tocar el total ni el IGV. Existe porque **una compra mixta no se podía
  corregir**: el formulario ofrecía `exonerado` e `inafecto`, que en el RCE no existen, y escondía
  `valor_no_gravado`, que es el único que sí. Poner cero **suelta** el campo declarado (`None`), por lo mismo que lo
  hace `aplicar_igv`: un cero declarado ganaría sobre el desglose.

### Ojo al integrar

«Mixto» significa dos cosas a dos centímetros y conviene no cruzarlas: en la clase de IGV es «lleva importes con y
sin IGV», y en `destino_igv` el `DGNG` es «la compra se usa para ventas con y sin IGV». Qué te cobraron, y para qué
lo usas.

## [3.6.0] — 2026-09-27

**Un descuento dentro de «otros conceptos» deja de sumarse como si fuera un cargo.** En el mismo registro de compras
real de la 3.5.1, seis facturas de grifo y de peaje seguían sin cuadrar: traían el campo «Otros conceptos, tributos y
cargos» **en negativo**, que es como SUNAT informa un descuento global que no forma base. El motor guardaba el valor
absoluto —el signo no es parte del dato— así que sumaba donde había que restar. Y no era solo un aviso feo: el TXT que
este motor genera escribía **+13.40 donde SUNAT tiene −13.40**, una diferencia real en un archivo que se declara.

### Añadido

- **`dscto_otros`** en el comprobante (enmienda 0016): la parte de `otros` que el registro informa en negativo. Va en
  **positivo, como todo importe** —no se rompe la regla de la primera línea del esquema, que es lo que permite que el
  signo de una nota de crédito lo ponga el driver de salida— y **resta del total**. Ahí se separa de `dscto_base` y
  `dscto_igv`, que con el mismo prefijo no mueven el total.

- **`Comprobante.otros_neto`**, que es `otros − dscto_otros`: la columna tal como la lleva el registro, que solo tiene
  una. La usan el TXT del SIRE, el registro de CONTASIS y el cálculo de la base a partir del total; sin ella, cada
  sitio habría rehecho la resta a su manera, que es exactamente lo que causó el fallo de la 3.5.1.

### Cómo se decide que un negativo es un descuento

Por **signo contrario al del total**, no por ser negativo a secas: en una nota de crédito *todos* los campos vienen
negativos porque lo es la operación entera, y ese signo ya lo pone el driver al escribir. Tomarlo por descuento
invertiría la nota. La regla se comprobó sobre las 1116 filas del registro real: sus dos notas de crédito traen esa
columna en `0.00` y las seis facturas con descuento la traen contraria al total.

**Resultado medido sobre ese mes:** `TOTAL_NO_CUADRA` pasa de **460 a 0**, y el TXT regenerado contra el archivo de
SUNAT da **1116 comprobantes en los dos, ninguno de más ni de menos, y ni una diferencia en el campo 24** — ni en
ningún otro campo de importe.

## [3.5.1] — 2026-09-27

**Una compra cuyo importe va en la columna de adquisiciones no gravadas deja de avisar «no cuadra».** En el registro
de compras real de un contribuyente, **460 de 1116 filas de un solo mes** —el 41 %— salían observadas con
`TOTAL_NO_CUADRA` y un esperado de `0.00` teniendo total. El aviso se delataba solo: enumeraba «no gravado» entre los
sumandos y era justo el que no sumaba.

### Corregido

- **El total se comprueba contra `adquisiciones_no_gravadas`, no contra `exonerado + inafecto`.** Los dos registros de
  SUNAT no informan lo mismo: el **RVIE** separa lo exonerado (campo 19) de lo inafecto (campo 20) y el **RCE** tiene
  **una sola columna**, «Valor de las adquisiciones no gravadas» (campo 21), que no dice cuál de los dos es — por eso
  el lector la deja en `valor_no_gravado` en vez de inventar el desglose. `validar` era **el último sitio del motor con
  esa cuenta escrita aparte**: el driver del SIRE, el registro de CONTASIS y la cabecera del asiento ya usaban la
  propiedad del modelo. Para cualquier otro origen —ventas, XML, PDF, IA o dictado— es **equivalente exacto** y ningún
  comprobante cambia de veredicto.

  **Lo que salía por la puerta siempre estuvo bien**, y esto es solo el cartel: la línea de gasto del asiento usa
  `total − IGV`, no `base_gravada`, y el TXT del SIRE ya escribía el campo 21 con la propiedad correcta. Comprobado
  contra el archivo de SUNAT de ese mes: 50 comprobantes en los dos, **ninguna diferencia en importes**, y el TXT sale
  byte a byte idéntico antes y después.

- **El campo 21 en cero ya no se declara.** Llega como `"0"` en toda compra gravada, y la cadena `"0"` es verdadera:
  el comprobante quedaba con `valor_no_gravado = 0.00` en vez de `None`. Declararlo en cero significa «lo no gravado
  aquí es cero» y **gana** sobre el desglose, así que se habría llevado por delante lo que alguien escribiera luego.

- **Corregir el IGV o el total de una compra no gravada ya no la descuadra.** `aplicar_igv` mandaba los importes a
  `inafecto` sin mirar el campo declarado —dos verdades a la vez— y `aplicar_total` los hacía caer en `base_gravada`,
  que convertía una compra no gravada en **gravada sin IGV** y contaba el importe dos veces. Ahora los dos llevan lo no
  gravado al campo que usa el libro, y `valor_no_gravado` entra en `PRINCIPALES` para poder absorber el total.

### Documentación

- `estandar/LEEME.md` estrena la fila de `valor_no_gravado` en «Campos que conviene mirar dos veces», con lo que de
  verdad importa: **nulo no es cero**, y el total se comprueba contra la decisión, no contra la suma de los tres.
- `API-DE-REGISTRO.md` decía que el importe no gravado «va en `inafecto`». Es cierto **al dictar**, y era la mitad de
  la historia: ahora explica los dos libros y cuándo aparece `valor_no_gravado`.

## [3.5.0] — 2026-09-26

**Un comprobante que SUNAT da de baja deja de parecer uno al que le falta el importe.** El motor leía la propuesta del
SIRE y descartaba dos de sus columnas —por qué se emitió una nota y qué dice SUNAT del comprobante—, así que no había
forma de distinguir un comprobante dado de baja de uno incompleto. Con un registro de ventas real de 52 filas ya
declarado: cinco venían con **todos** los importes en cero, tres facturas y dos notas de crédito, y eran exactamente
los cinco marcados con «Est. Comp» = `2`, con el tipo de cambio también en cero y sus correlativos en medio de la
serie. El motor les pedía cuenta contable —que a un comprobante dado de baja no se le pone— y, con cuenta puesta, los
escribía al Excel como dos líneas de asiento a `0.00` con su número de vóucher gastado.

### Añadido

- **`tipo_nota`** en el comprobante (enmienda 0014): por qué se emitió una nota de crédito o de débito. **El dato ya
  entraba y se tiraba**: el lector de XML lo leía de `cac:DiscrepancyResponse/cbc:ResponseCode` y lo dejaba en
  `datos_originales`, y la columna del SIRE se descartaba —estaba hasta en el fixture de pruebas del repositorio—.
  Ahora entra como hecho del documento, se puede dictar y llega a la cabecera del asiento.

- **`estado_sunat`** en el comprobante (enmienda 0015): lo que SUNAT dice del comprobante en su propio registro. Es
  campo del **sistema** y no del documento, porque no lo dice el papel —ninguna factura impresa lleva un «Est. Comp»—,
  y el efecto es el que se quiere de una API de registro: **nadie puede dictarle al motor que SUNAT dice algo de un
  comprobante**. **Se transporta verbatim y no condiciona ninguna regla**: la norma lo llama referencial y **no publica
  su tabla de valores**, así que traducirlo sería inventarle el significado. Hay un test cuyo único trabajo es ponerse
  rojo si alguien lo intenta.

- **`motivos_nota_credito` y `motivos_nota_debito`**, los Catálogos 09 y 10 del Anexo N.° 8, con su fuente, en
  `catalogos_sunat` (API y recurso MCP). **Son dos tablas porque los códigos colisionan**: el `01` es «anulación de la
  operación» en el de crédito e «intereses por mora» en el de débito. `motivos_de_nota(tipo_cp)` es el único sitio
  donde se decide cuál le toca a un comprobante, y se apoya en las listas completas: mirar solo `("07", "08")` dejaría
  al 87 y al 88 sin catálogo **en silencio**, que es la forma exacta del fallo que cuenta la cabecera de `resumen.py`.

- **`asentar_sin_efecto_contable`** en la configuración general, apagado de fábrica: lo que no mueve dinero —total, IGV
  y retención en cero, y sin detracción— no pide cuenta ni centro, no gasta número de vóucher y no produce líneas de
  asiento. **Y sigue saliendo en el registro que se declara a SUNAT**, porque el asiento es una cosa y el registro es
  otra: el correlativo necesita su fila, que es justo por lo que SUNAT los declara en cero en vez de quitarlos. Quien
  integre un ERP y quiera esas líneas las recupera con esa clave.

  **Decide por el importe y no por el estado**, y eso es mejor y no solo más prudente: funciona igual si SUNAT cambia
  el código, y atrapa además el comprobante en cero que llegue de un XML, de una foto o dictado por un ERP, que no
  trae estado ninguno.

- **`totales.sin_efecto_contable`** en `diagnosticar`: su propia casilla, no dentro de `fuera_del_destino`, que
  significa otra cosa —«este destino no lleva ese tipo de comprobante»—.

- Tres avisos: **`TIPO_NOTA_DESCONOCIDO`** (el código no está en el catálogo que le toca), **`TIPO_NOTA_NO_APLICA`**
  (un comprobante que no es nota trae motivo) y **`TOTAL_CERO_EN_LA_PROPUESTA`**. Los dos primeros con el criterio de
  `MEDIO_PAGO_DESCONOCIDO`: avisan y **el valor se respeta**. Lo que **no** existe es un `TIPO_NOTA_FALTA`: una nota
  sin motivo no es un defecto, porque el campo no viaja en el archivo y el propio TXT que este motor genera lo manda
  vacío.

### Cambiado

- **`IGV_NO_CUADRA` y `TOTAL_NO_CUADRA` dejan de bloquear cuando el comprobante viene de la propuesta del SIRE.** Es
  lo primero que tiene que leer quien integre. El caso: la propuesta traía una nota de crédito con la base sin declarar
  —base 0, IGV 4 546.31, total 29 803.61— y con ese único comprobante el mes entero no salía por **ningún** destino,
  porque `salida.generar` mira los errores antes de saber a dónde vas. Y el TXT que se negaba a escribir era idéntico
  al que SUNAT ya tenía declarado. El motor no es el auditor de lo que la Administración aceptó: corregir la copia no
  cambia el registro, y el arreglo de verdad es que el emisor emita otra nota. **En un XML, un PDF o un dictado sigue
  siendo error**, porque ahí sí se corrige antes de declarar. Los códigos no cambian de nombre; cambia el nivel, y el
  texto dice por qué no bloquea.

- **`TOTAL_CERO` deja de callarse en las notas.** Llevaba un `and not c.es_nota` desde el commit inicial del núcleo,
  sin test que lo defendiera ni motivo escrito, y por él dos de los cinco comprobantes en cero del mes real salían
  `estado="ok"` sin una sola palabra.

- **El comparador reconoce el tipo de cambio `0.000`.** SUNAT escribe el TC de un comprobante en soles como `1.000` si
  es normal y `0.000` si lo da de baja; el archivo de reemplazo lo manda vacío. Los tres dicen lo mismo y `_norm` solo
  conocía dos, así que un mes con comprobantes dados de baja cantaba una diferencia por cada uno **en un campo que
  rellena la propia Administración**. Con esto, el TXT que el motor genera del mes real sale **sin una sola
  diferencia** contra lo declarado, en las 52 filas: antes había cinco y todas eran esta.

- `catalogos.NOTAS` pasa a **derivarse** de `NOTAS_CREDITO` y `NOTAS_DEBITO`, que son nuevos: dentro de `catalogos` ya
  no se pueden desacordar, y que no se separen de las de `modelo` lo vigila un test, porque los dos módulos son hojas
  y no se importan entre sí.

### Corregido

- El Excel de CONCAR reventaba con un `ValueError` a medio archivo cuando un comprobante no traía correlativo:
  `_numero` hacía `int(correlativo[2:])`. Sin número no hay desborde que calcular, y desde esta versión un comprobante
  sin correlativo es un caso legítimo y no un error.

### El estándar

Sigue en **`open-accounting 1.0`** —dos campos opcionales nuevos no suben la versión— y **el tag
`open-accounting-1.0` avanza**. Seis casos de conformidad nuevos; ninguno de los 27 anteriores cambia de veredicto.

## [3.4.0] — 2026-09-26

**Sumar un libro deja de ser trabajo de cada aplicación.** El motor sabía armar el asiento de un mes y decir qué le
faltaba, y no sabía decir cuánto era: lo único que sumaba dinero era el `resumen` de una exportación —privado, y dentro
de la respuesta de `exportar`—, así que para saber cuánto compró un RUC en agosto había que generarle un archivo, y
`base_gravada` no se agregaba en ningún punto. Quien integraba el motor lo escribía por su cuenta, y ahí se vio por qué
no era suyo: la primera aplicación que lo hizo se quedó con el `07` donde el motor dice `("07", "87")`, así que una nota
de crédito de no domiciliado **le sumaba en vez de restarle** y el total cuadraba con su propia tabla.

### Añadido

- **`resumen(documento, agrupar_por="")`** (`POST /v1/resumen`, herramienta `resumen`): base gravada, IGV y total de un
  libro, **cada moneda por su lado**, y con `agrupar_por="contraparte"` también por proveedor o cliente, de más a menos
  y agrupados por su documento. **No recibe driver ni configuración**, y esa es la diferencia con el
  `resumen_por_contraparte` de `diagnosticar`: aquello es lo que iría a ESE destino —filtra lo que no lleva y cuenta las
  duplicadas—, esto es el libro.

  `recuento` trae cuatro números que **no se solapan y suman `recibidos`**: lo excluido no es del libro y lo duplicado no
  va a ningún archivo, así que ninguno suma, pero son dos cosas distintas. Nace así porque la misma palabra significaba
  dos cifras según quién la leyera: en el resumen de una exportación «comprobantes» son los que salieron, y en la
  pantalla de un SaaS, los que no están excluidos.

- **`por_cuenta(lineas)`** (`POST /v1/por_cuenta`, herramienta `por_cuenta`): el pre-mayor, hermana de `cuadrar` —misma
  entrada— y con el **cuadre por moneda**, que dice algo que el global no puede: dos monedas cuyos descuadres se
  compensan salen cuadradas en el total y descuadradas cada una. Lo suma `partida_doble.cuadra` sobre cada montón, así
  que el pre-mayor y el cuadre no pueden discrepar por construcción.

  `roles` va **en plural**: con una detracción, la cuenta por pagar hace dos papeles en el mismo asiento —`tercero` y
  `detraccion_tercero`—, y quedarse con el primero esconde el segundo. El importe está; lo que faltaba era saber de qué
  era cada mitad.

- **`campos_del_comprobante()`** (`GET /v1/campos/comprobante`, recurso `contaperu://campos/comprobante`) y las tres
  tuplas de `modelo` que lo sostienen: qué campos los pone el **documento**, cuáles el **sistema** que lo produce y
  cuáles la **revisión**. Es lo que una puerta de entrada necesita para saber qué acepta de quien escribe, y su caso es
  concreto: quien la escribió a mano se dejó cinco campos que su propia base ya guardaba —los dos descuentos, el ICBPER,
  el valor no gravado y el destino del IGV—, que se perdían sin error y sin aviso. Los tres tramos cubren el comprobante
  entero y no se solapan, y un campo nuevo que nadie reparta deja el test rojo.

- **`REGLAS`**, en `contaperu.api`: las reglas del dominio **sin nombrar ninguna herramienta**, para que quien monte su
  propia capa de agente encima del motor se las lleve sin decirle a su modelo que llame a un `leer_xml_ubl` que no
  tiene. `INSTRUCCIONES` las sigue incluyendo y **no cambia lo que dice**; ahora vive en `api.instrucciones`, así que un
  integrador ya no tiene que importar una puerta entera para leer un texto —y `from contaperu.puertas.servidor_mcp import
  INSTRUCCIONES` sigue valiendo—.

- **`modelo.NOTAS_CREDITO`, `NOTAS_DEBITO` y `NOTAS`**: la regla que `es_nota_credito` tenía dentro, con nombre. **Son el
  07 y el 87**, y tener un nombre que citar es lo que permite que la próxima aplicación lo pregunte en vez de deducirlo.

### Cambiado

- `diagnosticar` dice en su docstring y en el esquema de su respuesta **qué es y qué no es**
  `resumen_por_contraparte` —lo que iría a ese destino, no el resumen del libro— y a quién preguntarle el otro. **Su
  cifra no cambia.**
- `INTEGRAR.md` parte en dos la fila «Reportes y análisis» de la tabla que decide de quién es cada herramienta:
  **elegir las filas es tuyo; la aritmética de un libro, no.** La pregunta sigue siendo «¿necesita TUS datos?», y para
  un resumen la respuesta es no: necesita los datos que le pasas, como `cuadrar`.
- `INTEROPERABILIDAD.md` aclara su descarte: lo descartado es **convertir** monedas dentro de un resumen, no informar
  cada moneda por su lado.

### Cómo migrar

**Nada que adaptar.** La api pública solo crece, ninguna respuesta existente cambia de forma y ningún archivo se mueve:
los snapshots de los seis destinos salen idénticos. Dos avisos para quien lea la respuesta del MCP: hay **catorce**
herramientas y **nueve** recursos.

## [3.3.0] — 2026-09-25

**Con qué se pagó una operación deja de ser un misterio.** Entra el catálogo de medios de pago de SUNAT y, con él,
el campo que llevaba desde el 12-sep-2026 reservado en el estándar esperando una decisión.

### Añadido

- **El catálogo de medios de pago de SUNAT** (`catalogos.MEDIOS_PAGO`, y en `catalogos_sunat` por la API, la puerta
  HTTP y el recurso `contaperu://catalogos/sunat`). Son los **22 códigos** del Anexo 3 de la RS 169-2015/SUNAT —la
  que aprueba la versión 5.0.0 del PLE—, que son los medios de pago del artículo 5 de la Ley 28194, la de
  bancarización.

  Hasta hoy el motor **escribía un medio de pago que nadie sabía leer**: `contasis.medio_pago` vale `001` de fábrica
  y sale en la columna AN de su registro de ventas, sin que existiera en ninguna parte un mapa que dijera qué es
  `001`. Y el catálogo se gana su sitio con un caso concreto: la primera lista que llegó traía tres filas y decía
  que `005` era «tarjeta de crédito» —en el anexo `005` es **tarjeta de débito** y la de crédito emitida en el país
  es `006`—. Un valor publicado no se cambia de significado después, así que los 22 quedan congelados en
  `tests/test_catalogos.py`, con un test que solo comprueba esas dos tarjetas.
- **`medio_pago` en el comprobante** ([enmienda 0004](estandar/enmiendas/0004-medio-de-pago.md), que pasa de
  `reservada` a `final`). Es un campo **opcional** de tres dígitos, y lo que le faltaba no era un caso sino una
  decisión: si es dato de cada documento o un valor del contribuyente. **Las dos cosas** (John, 25-sep-2026): manda
  el del documento, y el de la configuración del sistema contable es el respaldo para cuando el documento no lo
  dice, que es lo normal hoy. Así queda abierto a cualquier ERP sin romperle nada al que ya exportaba.

  No es `condicion_pago`, que dice **cuándo** se paga; este dice **con qué**. No entra en ninguna línea, ni en
  ninguna cuenta, ni en la huella del asiento, y **sí llega a la cabecera** (`asiento.Cabecera.medio_pago`), que es
  la regla que impide que el próximo driver descubra que el dato se cayó por el camino.
- **Un aviso, `MEDIO_PAGO_DESCONOCIDO`**, para el código que no está en el catálogo. **Aviso y no error, y el valor
  se respeta**: el medio de pago no cambia ningún asiento ni ningún importe, así que un código que este motor
  todavía no conoce —SUNAT puede añadir uno— no puede impedirle a nadie cerrar su mes. La **forma** la cuida el
  esquema (tres dígitos); el **significado**, el catálogo.
- **Tres casos de conformidad** del esquema (27 en total), para que un ERP compruebe el campo sin escribirle a
  nadie: uno válido, uno con un código que el catálogo todavía no tiene —válido a propósito— y uno sin forma de
  código.

### Cambiado

- **El registro de ventas de CONTASIS escribe el medio de pago del DOCUMENTO** cuando lo trae (columna AN), y el
  del contribuyente cuando no. Hasta la 3.2 solo existía el segundo, porque el estándar no tenía dónde poner el
  primero.
- **Un catálogo se nombra por lo que ES, nunca por su número de tabla** (John, 25-sep-2026). Cada anexo de SUNAT
  numera las suyas empezando por 1, así que al entrar los medios de pago pasó a haber **dos «Tabla 1»** en el mismo
  archivo, a seis líneas de distancia: la de documentos de identidad (Anexo 1 de la RS 112-2021) y la de medios de
  pago (Anexo 3 de la RS 169-2015). El número suelto no identifica nada —y además puede cambiar con la siguiente
  resolución, mientras que lo que el catálogo es, no—.

  Así que los comentarios y las descripciones dicen «tipo de documento de identidad» y «tipo de medio de pago», y el
  número se queda **solo dentro de la `fuente`**, que es la cita de la norma y donde hace falta para encontrarla, con
  su asunto siempre al lado. Toca `catalogos.py`, `modelo.py`, `asiento/indice.py`, el esquema del estándar y el de
  la respuesta.

### Cómo migrar

La API pública no cambia y **ningún archivo se mueve** por sí solo: un documento que no traiga `medio_pago` produce
exactamente el mismo Excel, el mismo TXT y la misma huella que en la 3.2. Lo que cambia es de quien empiece a
mandarlo: su registro de CONTASIS llevará el del documento en lugar del configurado.

Dos avisos para quien lea la respuesta del motor: el documento anotado trae ahora `medio_pago` en cada comprobante
—vacío cuando no se sabe, como `condicion_pago`—, y `catalogos_sunat` trae una clave más, `medios_pago`.

### Añadido

- **La Tabla 1 de SUNAT, «Tipo de medio de pago», entra como catálogo** (`catalogos.MEDIOS_PAGO`, y en
  `catalogos_sunat` por la API, la puerta HTTP y el recurso `contaperu://catalogos/sunat`). Son los **22 códigos**
  del Anexo 3 de la RS 169-2015/SUNAT —la que aprueba la versión 5.0.0 del PLE—, que son los medios de pago del
  artículo 5 de la Ley 28194, la de bancarización.

  Hasta hoy el motor **escribía un medio de pago que nadie sabía leer**: `contasis.medio_pago` vale `001` de fábrica
  y sale en la columna AN de su registro de ventas, sin que existiera en ninguna parte un mapa que dijera qué es
  `001`. Y el catálogo se gana su sitio con un caso concreto: la primera lista que llegó traía tres filas y decía
  que `005` era «tarjeta de crédito» —en el anexo `005` es **tarjeta de débito** y la de crédito emitida en el país
  es `006`—. Un valor publicado no se cambia de significado después, así que los 22 quedan congelados en
  `tests/test_catalogos.py`, con un test que solo comprueba esas dos tarjetas.

### Cambiado

- **Un catálogo se nombra por lo que ES, nunca por su número de tabla** (John, 25-sep-2026). Cada anexo de SUNAT
  numera las suyas empezando por 1, así que al entrar los medios de pago pasó a haber **dos «Tabla 1»** en el mismo
  archivo, a seis líneas de distancia: la de documentos de identidad (Anexo 1 de la RS 112-2021) y la de medios de
  pago (Anexo 3 de la RS 169-2015). El número suelto no identifica nada —y además puede cambiar con la siguiente
  resolución, mientras que lo que el catálogo es, no—.

  Así que los comentarios y las descripciones dicen «tipo de documento de identidad» y «tipo de medio de pago», y el
  número se queda **solo dentro de la `fuente`**, que es la cita de la norma y donde hace falta para encontrarla, con
  su asunto siempre al lado. Toca `catalogos.py`, `modelo.py`, `asiento/indice.py` y el esquema de la respuesta.

## [3.2.0] — 2026-09-25

**La detracción tiene dos tiempos y ahora se sabe en cuál está cada una.** La 2.6 hizo que la constancia del depósito
llegara al archivo; lo que faltaba era poder separar lo pagado de lo pendiente sin copiar la regla en cada aplicación
—y que el vóucher llegara **también a CONCAR**, el único de los cuatro destinos que se quedaba con el comodín aunque
alguien lo hubiera pegado—.

### Añadido

- **`detracciones.estado_de(comprobante, config)`: en qué tiempo está esa detracción**, con `esta_pendiente` al lado
  y los dos estados nombrados (`PROVISIONADO`, `PAGADO`) para que nadie escriba la cadena a mano. Un test los ancla
  al `enum` del esquema del estándar: dos listas que dicen lo mismo en dos sitios acaban diciendo cosas distintas.
- **`diagnosticar` dice las DOS caras: `detracciones_pendientes` y `detracciones_pagadas`**, y las dos con la
  **misma forma** —`serie_numero`, `codigo`, `monto`, `nro_constancia`, `fecha_constancia`—, así que quien pinta las
  dos listas no aprende dos formas. Hasta ahora solo salían las pendientes: una aplicación que quisiera enseñar
  «7 pendientes · 12 depositadas» tenía que deducir las pagadas por su cuenta, con la regla copiada. Y en una
  pendiente que ya trae número se ve de un golpe que lo que falta es la fecha.
- **`detracciones.numero_pendiente(config)`: el comodín, en un solo sitio.** Se preguntaba en el asiento
  (`_numero_pendiente`) y hacía falta también fuera de él, porque el estado no arma ningún asiento.
- **`contaperu diagnosticar` lista además las depositadas**, con su número y su fecha, y marca la pendiente que ya
  tiene número con «falta la fecha del depósito».
- **Los nueve importes que forman el total, descritos en el esquema del estándar.** `exonerado` e `inafecto`
  estaban uno al lado del otro sin una línea que los separara, y la diferencia tiene consecuencia tributaria: lo
  **exonerado** está dentro del campo de aplicación del IGV y una norma lo libera (Apéndices I y II); lo
  **inafecto** queda fuera de ese campo (art. 2 de la Ley), así que nunca hubo impuesto que cobrar — y es lo que
  suele llevar la parte no gravada de un recibo de servicios públicos. Un ERP que integre el estándar tenía que
  adivinarlo. Con ellos van `exportacion`, `isc`, `base_ivap`, `ivap`, `icbper`, `otros` y `total`, que estaban
  igual: describir la mitad de un bloque es peor que no describir ninguno.

  Solo son anotaciones, así que **no cambia ninguna validación** ni la versión del estándar. Quedan 15 campos del
  comprobante sin describir, la mayoría evidentes por su nombre.
- **`INTEGRAR.md`: «Tu propio MCP con el del motor debajo».** Faltaba decir dónde va la capa de agente de un ERP
  —configurar, reportes, análisis, cargar una factura— y la respuesta cabe en una pregunta: **¿necesita TUS datos?**
  Lo que no los necesita ya es del motor; lo que sí, es del ERP, y juntarlas obligaría al motor a tener estado.
  Con las dos formas de combinarlas, un ejemplo que la batería ejecuta, y el aviso de traerse `INSTRUCCIONES`
  aunque no se traiga nada más: es lo que evita que un modelo se invente detracciones.

### Corregido

- **El vóucher del depósito no llegaba a CONCAR**, que es el destino en producción. El número de la constancia
  viajaba dentro de la línea de detracción y la proyección de CONCAR no lo mira: la columna donde va es la **S**, el
  número del documento `DR` —ese documento **es** la constancia, y el comodín solo ocupa su sitio mientras no la
  haya—, y ahí se escribía el comodín siempre. STARSOFT (campo 25) y CONTASIS (columna U) sí lo escribían desde la
  2.6, y `docs/concar/LEEME.md` de la aplicación ya prometía lo que el motor no hacía: «comodín **mientras nadie
  haya pegado la constancia** del depósito». La **fecha** del documento `DR` sigue siendo la de la factura: ningún
  Excel validado dice que sea la del depósito, y eso no se decide de memoria.

### Cambiado

- ⚠️ **Cuándo una detracción cuenta como PAGADA** (criterio de John, 25-sep-2026): hacen falta **las dos cosas**, un
  `nro_constancia` que no sea el comodín **y** una `fecha_constancia`. Antes bastaba el número —y contaba el `estado`
  que trajera el documento—, así que un mes con vóuchers pegados sin fecha salía de la lista de pendientes y nadie
  volvía a mirarlo. Ahora sigue pendiente, y por eso vuelve. Se descartan los **dos** comodines, el configurado y el
  de fábrica: un contribuyente que puso el suyo puede tener guardado el otro de una exportación anterior.
- ⚠️ **El `estado` del documento no se lee: se deduce.** Es un campo informativo —está para que se vea en una
  pantalla o en un informe— y quien lo recibe no puede comprobarlo, así que un `estado` que diga `PAGADO` sin
  constancia no convierte en pagada una detracción que no lo está. Queda escrito en el esquema del estándar, en su
  LEEME y en la hoja de ruta, donde el hito D1 pasa a ser lo que de verdad falta: **casar el archivo del Banco de la
  Nación** con cada comprobante, no escribir un estado.
- **`INTEGRAR.md` dice primero que casi nadie necesita un driver.** La guía dedicaba una sección entera a
  escribir uno y una sola línea a pedir el asiento con `asiento_neutral`, así que un sistema moderno que la leyera
  daba por hecho que le tocaba escribir código aquí. Ahora abre con los tres niveles —leer el documento, pedirle
  el asiento al motor, o escribir tu formato— y solo el tercero pide driver. **Un estándar escala cuando la
  mayoría de los que lo adoptan no escriben código en él**, y un driver que no hacía falta es un traductor más
  que mantener. Se dice también que el canal describe el FORMATO y no la edad del software.

### Cómo migrar

La API pública no cambia y **ningún archivo se mueve** mientras nadie haya pegado una constancia: los 52 casos de
CONCAR, los 44 de CONTASIS y la caracterización de los seis destinos salen idénticos, porque un comprobante sin
vóucher sigue llevando el comodín. Lo que cambia es de quien SÍ lo pegó: su Excel de CONCAR lleva ahora el número
de verdad en la columna S, y si le falta la fecha del depósito su mes vuelve a contarlo como pendiente. Quien lea
`detracciones_pendientes` recibe dos claves más por entrada (`nro_constancia`, `fecha_constancia`) y una lista nueva
al lado; el esquema del diagnóstico las declara.

## [3.1.0] — 2026-09-23

### Añadido

- **`contaperu verificar-documento mi-documento.json`** (y `api.verificar_documento`): un documento contra el
  ESTÁNDAR, su esquema y sus catálogos, sin armar ni exportar nada. Es el espejo de `verificar-driver` —aquel
  comprueba lo que alguien escribe contra el contrato del motor; este, lo que alguien produce contra el contrato
  del estándar— y **hasta ahora no existía ninguno**: quien construía sobre `open-accounting` tenía el esquema
  publicado y ninguna forma de correrlo que no fuera clonar el repositorio y lanzar pytest.

  Separa **errores** de **avisos**, y la distinción es la del propio estándar: un error es no cumplir el esquema,
  y ahí no hay nada que interpretar; un aviso es lo que el esquema no puede decir porque vive en los catálogos —un
  `rol` desconocido se degrada y no rompe la línea, un `tipo` de libro desconocido sí rompe—.
- **`INTEGRAR.md` gana la sección «Si NO usas el motor: construir sobre el estándar».** La guía entera suponía que
  llamas a `contaperu` por una de sus cuatro puertas; esta es para quien no lo hace. Dice qué lleva el documento,
  qué garantiza —las cuentas decididas, el asiento cuadrado, el orden estable—, cómo se enlaza con el origen por
  `id_externo` y por la huella de `_exportacion.comprobantes`, y qué no lleva y por qué.


- **Los casos de conformidad viajan en la rueda** (`contaperu/estandar/conformidad/`). El LEEME del estándar los
  ofrecía para «comprobar que lo que tu sistema produce es correcto, sin escribirle a nadie» y **solo estaban en el
  repositorio**: quien instalaba `contaperu` no los tenía y la única forma de correrlos era clonar. Y un guardián
  nuevo comprueba que **todo** JSON de `estandar/` viaje, que era una regla escrita en `_datos.del_estandar` sin
  nadie detrás — así es como estos llevaban desde que existen sin viajar.
- **Un test de la ruta que `esquema.json` declara** (`"esquema": "../open-accounting.schema.json"`), que el runner
  ignoraba: usaba la copia empaquetada. Son el mismo archivo, pero nada lo comprobaba, y un tercero que respetara
  la ruta declarada podía acabar validando contra otro esquema sin que saltara nada.

### Cambiado

- **El comodín del número de la detracción pendiente se configura** (`detraccion_numero_pendiente`), que era una
  deuda anotada en el código: el TIPO de ese documento se configuraba y el NÚMERO no, «una asimetría de cuando el
  comodín era un detalle de CONCAR». Va en la configuración **general** y no en la del asiento, aunque su hermano
  el tipo sí sea del asiento: el tipo solo existe en la línea comodín `DR`, y este número sale además en las
  columnas de constancia de un registro —las U y V de CONTASIS—, que no arma ningún asiento. Declararlo en la
  sección del asiento habría dejado a CONTASIS sin poder leerlo, y lo cazó el espía del contrato al intentarlo.
- **`contrato.columnas_elegidas(modulo, config, dato)`**: en qué columnas sale un dato, resuelto una sola vez.
  CONTASIS lo reimplementaba contra su propio `por_defecto` y `centro_en_anexo` lo tenía escrito aparte.

### Añadido

- **Un test que corre juntas las cuatro respuestas a «cuál es la tasa del IGV»** sobre el mismo comprobante. Son
  cuatro y las cuatro están bien —el núcleo escribe el cociente, CONCAR lo redondea a entero, CONTASIS declara la
  tasa legal que cuadra y STARSOFT reformatea la de la línea—, pero no había sitio donde se vieran juntas, y el
  snapshot de CONTASIS usa casos donde coinciden: no distinguiría si alguien cambiara una función por otra.
- **Un test de que `CUENTAS_POR_DEFECTO` se lee por su accesor y no en crudo.** Desde la 3.0 guarda dos cosas
  —las contrapartidas, que imputan, y `compras`/`ventas`, que siembran el plan—, y en crudo salen mezcladas.


- **El LEEME del estándar dice de cada juego de conformidad quién puede correrlo.** Los de `esquema.json` los corre
  cualquiera, con un validador y sin el motor. Los de `diagnosticar.json` **no son portables** —nombran drivers del
  motor y esperan la forma de `api.diagnosticar`, que es superficie del paquete y no del estándar— y comprueban que
  ESTE motor decide bien, no el tuyo. Ofrecer los dos como lo mismo prometía de más.

- **El archivo del driver `asiento_neutral` lleva `_exportacion` en su raíz**: la huella del asiento y, por
  comprobante, su identidad y el tramo de líneas que le toca. Hasta ahora eso solo existía en la respuesta del
  API, así que **quien recibiera el JSON a secas se quedaba sin la clave con la que no repetir un comprobante** —
  que es justo lo que `INTEGRAR.md` le pide a un ERP—. El driver tenía el índice en la mano y lo descartaba.

  **No hace falta enmendar el estándar**: su raíz ya admite cualquier clave `_` y `estandar/LEEME.md` dice que un
  productor puede llevar ahí `_exportacion`. Los 24 casos de conformidad siguen pasando sin tocarlos.
- **`asiento.exportacion_de(libro, lineas, indice)`**, que es quien lo arma, y `Cabecera.clave`, para que
  `modelo.identidad_de` sirva igual con un comprobante y con la cabecera de su tramo. `pipeline/armado` pasa a
  delegar en ella: una sola implementación para la respuesta del API y para el archivo, y por eso lo que va
  dentro del documento es idéntico a lo que dice el API, no una versión reducida.

## [3.0.0] — 2026-09-23

### Cambiado — **incompatible: es una 3.0**

- **La cuenta de un comprobante es de su imputación, y nada la suple.** `CONFIGURACION_GENERAL` pierde las dos
  cuentas que la suplían —`cuentas.gasto` (vacía de fábrica) y `cuentas.ventas` (`701101`)— y `asiento.partes_de` se
  queda sin respaldo: lo que nadie imputó se cuenta como `sin_cuenta` y `exigir_requisitos` detiene la exportación.

  Hasta aquí una cuenta por defecto hacía que el motor **dejara de contar** como `sin_cuenta` los comprobantes a los
  que nadie les había puesto una: salían imputados a ella y el mes se daba por listo para exportar. En ventas pasaba
  siempre, porque la de fábrica era real. Es la decisión de John (23-sep-2026) tras verlo en producción: cada
  comprobante tiene su cuenta y un comodín la esconde.

  **Qué hacer al subir:** lo que estaba en `cuentas.gasto` o `cuentas.ventas` pasa a la imputación de cada
  comprobante, por `id_externo` —el argumento `imputacion` o el bloque `imputaciones` del documento—. Una
  configuración que todavía las traiga se rechaza con `ConfiguracionInvalida`, que es lo contrario de perderlas en
  silencio.

- **`CUENTAS_POR_DEFECTO` de un driver tiene dos oficios, y lo dice la clave.** Las de la contrapartida —`cxp`,
  `cxp_detraccion`, `honorarios`, `retencion_4ta`, `igv`, `clientes`— siguen siendo configuración. Las dos nuevas,
  **`compras` y `ventas`** (`contrato.CLAVES_DEL_PLAN`), no: son la cuenta con la que ese sistema registra
  habitualmente una compra y una venta, y **siembran el plan de cuentas** de la empresa que lo abre, para que las
  elija comprobante a comprobante. No imputan solas. Se leen con `contrato.plan_base(driver)`, y
  `contrato.cuentas_por_defecto(driver)` ya no las devuelve.

- **Los tres drivers legacy declaran su bloque entero.** CONCAR era la última excepción —declaraba una sola cuenta
  «porque lo general ya era lo suyo»— y se retiró: un driver se lee de un vistazo y no obliga a ir a buscar qué
  hereda. Sus planes: CONCAR y CONTASIS `631101`/`701101` (PCGE a seis dígitos; la de compras de CONTASIS va marcada
  `# prevista`, porque no consta en ningún manual), STARSOFT `60110100`/`70410001`, las dos de su manual y de una
  instalación real.

### Corregido

- **Un caso de conformidad comprobaba `pedir_a` contra la constante del propio motor**, no contra la respuesta
  del diagnóstico que dice estar verificando (`tests/test_conformidad.py`). Si `diagnosticar` dejara de poner
  `pedir_a`, o lo pusiera mal, los tres casos que lo usan seguirían en verde. Ahora se lee de `que_falta`, y al
  mutar la respuesta caen los tres.

### Añadido

- **Test de las tres cifras del IGV** (`TASA_IGV`, `TASAS_IGV_REDUCIDAS`, `TOLERANCIA_IGV`): no las fijaba
  ninguno. Son de las que depende que el IGV cuadre —`validar` decide con ellas `IGV_NO_CUADRA` e `igv.tasa_legal`
  reconoce con ellas la tasa que un registro declara—, así que cambiarlas movía en silencio lo que el motor acepta.
  Se fija además que la tolerancia sea **la misma** en `validar` y en `igv`: si se separaran, un comprobante
  podría declarar 18 % en el registro y ser `IGV_NO_CUADRA` a la vez.
- **Las cuentas de CONTASIS, comparadas con las que el núcleo decidiría.** `docs/contasis/LEEME.md` promete que
  «el driver no decide ninguna cuenta» y esa frase no la afirmaba ningún test. No sustituye al snapshot, que caza
  que una celda cambie: lo que añade es una fuente independiente —el asiento del núcleo para los mismos
  comprobantes—, que cazaría una divergencia que hubiera estado ahí desde el primer día. Es la pareja que CONCAR
  ya tiene con `test_driver_asiento_neutral`.

## [2.7.0] — 2026-09-22

### Añadido

- **Linter (`ruff check .`), en el CI y antes de un PR.** Acotado a propósito a **código muerto y errores**
  —imports y variables que no usa nadie, redefiniciones, nombres sin definir—, **nunca a estilo**: aquí los
  comentarios se escriben en prosa y 442 líneas pasan de 120 caracteres. Había cuatro `# noqa` en el
  repositorio silenciando a un guardián que no estaba instalado.
- `formatear_fecha` reconoce el **ISO** (`AAAA-MM-DD`), que es lo que el CSV declaraba en sus `Opciones` y lo
  que la línea neutral lleva. Antes ese valor levantaba `ValueError`: no se notaba porque el CSV no pasa por
  ahí, pero su docstring lo ofrece como plantilla para un driver de terceros, que sí lo habría hecho.
- `tests/test_kit_texto.py`: el formateo compartido del kit, probado por sí mismo. No tenía ni un test directo.
- Un guardián de que **todo driver de serie esté en `__all__`**: `starsoft` y `asiento_neutral` llevaban
  tiempo fuera de la lista pública del registro, y no lo cazaba nada porque importarlos seguía funcionando.

- **CONTASIS declara sus `CUENTAS_POR_DEFECTO`** (John, 22-sep-2026), con la misma forma que las de STARSOFT.
  Hoy coinciden una a una con las de fábrica —usa el PCGE a seis dígitos, como CONCAR—, y se declaran igualmente
  para que el día que alguien traiga el plan real de una instalación tenga dónde escribirlo cuenta por cuenta, en
  vez de descubrir que hereda las de otro sistema. Repetir un dato exige un vigilante: `test_cuentas_del_sistema`
  compara el bloque con lo general y se pone rojo si se separan sin que nadie lo decida. **`gasto` no se declara**,
  como en STARSOFT: poner una cuenta real imputaría en silencio toda compra a la que nadie le puso ninguna.
- **Seis reglas nuevas en el examen de los drivers** (`test_contrato_drivers.py`), contra la clase de fallo que
  costó siete versiones al entrar STARSOFT: nadie escribe un importe ni una fecha a mano teniendo el kit, ningún
  corte de texto lleva el número escrito en la proyección —el largo vive junto a su columna—, el nombre del
  archivo sale del kit, y todo driver `legacy` declara con qué cuentas nace. Lo que hoy no las cumple está en
  `TOLERADAS`, con su motivo escrito y un test que avisa cuando una excepción deja de hacer falta.
- **`concar.datos.LARGOS_DE_GLOSA`**: los dos cortes de CONCAR (40 y 30) estaban escritos dentro de la
  proyección, donde no se ven al mirar el formato. Ahora están donde ya los llevan CONTASIS y STARSOFT.
- **`contrato.excluye_tipos(modulo)`**, el accesor que le faltaba a `EXCLUYE_TIPOS`. Era lo único del contrato que
  se leía con un `getattr` crudo desde fuera, mientras `exige`, `no_caben` y `canal` ya tenían el suyo.

### Cambiado

- **`asiento.constancia_de(comprobante)`: la constancia de la detracción, una sola regla.** Estaba escrita dos
  veces, comodín incluido, y el propio docstring de CONTASIS lo admitía: es un driver de REGISTRO, no ve la línea
  de detracción donde el núcleo la deja resuelta, así que la reescribía. Ahora los dos caminos preguntan lo mismo,
  y hay un test que comprueba que responden lo mismo — que es para lo que se extrajo.
- **`kit.forma`**: lo que todo driver `desde_lineas` comprueba y recorre antes de escribir. Las dos guardas
  estaban en CONCAR y en STARSOFT carácter a carácter salvo el nombre del sistema.
- **Los rangos de sub-diario de CONCAR se quedan donde están, y se escribe por qué.** Se miró si sobraban: no
  sobran. Los del núcleo llevan tres cifras y CONCAR añade la etiqueta, los dos códigos `MMNNNN` y el desborde,
  que es lo que un ERP guarda para proponer el correlativo del mes siguiente. Y manda el del driver, porque
  `pipeline/armado.py` funde su resumen al final.


- **Un formateador por cosa, y ningún archivo cambia.** `kit.formatear_monto` acepta ahora lo que trae una línea
  —texto, `Decimal` o nada— y decide el cero por `opciones.cero`, así que el `con_dos_decimales` de STARSOFT pasa
  a ser una llamada a él con las opciones de STARSOFT. `kit.formatear_fecha` acepta el texto ISO además del
  `date`, y con eso desaparece el `formatear_fecha(celdas.fecha(...))` de STARSOFT: dos pasos para decir una
  cosa. `OpcionesArchivo` declara su `cero`, como `Opciones`.
- **Dos conversores de celda salen del driver al kit**: `celdas.importe_exacto` (vivía escondido en CONCAR con
  guion bajo) y `celdas.importe_o_vacia`, que es la regla «un cero deja la celda vacía» que CONTASIS llevaba
  escrita dentro de una expresión. Se documenta que `importe_exacto` **no** es `texto_exacto`: en dinero los
  decimales son parte del dato y `4` no es `4.00`; en un tipo de cambio los ceros de más son ruido.
- **`starsoft.destino_de` NO se unifica con `igv.por_destino`**, y queda escrito por qué: las dos leen
  `destino_igv`, pero aquella reparte base e IGV en tres parejas de importes y esta devuelve un código de la
  tabla de STARSOFT con dos valores que en el estándar no existen.
- `TOLERADAS` del examen de drivers queda **vacía**: nació con dos excepciones y las dos se fueron el mismo día.


- **CONCAR declara `no_caben`, y deja de cortar la serie-número en silencio.** Cortaba a 20 caracteres desde el
  refactor de la 0.7, que es justo lo que la doctrina escrita en CONTASIS prohíbe: un código cortado es otro
  código, y el asiento entraría con un documento que no existe. Los largos que consta que aplica van declarados
  en `datos.LARGOS_DE_CODIGO`; las dos glosas se siguen cortando, porque son texto libre.

  **Con datos peruanos válidos esto no puede dispararse** —serie de 4 más número de hasta 8—, así que no cambia
  ningún archivo. Lo único que se mueve es la respuesta de `diagnosticar/concar`, que **gana la clave `no_cabe`
  vacía**: aparece cuando el driver declara la función, así que ahora los tres legacy responden a la misma
  pregunta. Tres líneas en los fixtures de caracterización, una por documento.

### Corregido

- **Tres variables muertas en `asiento/motor.py`** —`es_usd`, `serie` y `numero`—, del refactor de la 0.7.
  Se calculaban en cada comprobante y se tiraban. No cambian ninguna salida: eran cálculos puros.
- **`COLUMNA_A_CAMPO` de CONCAR**, una tabla de quince líneas que no leía nadie. Lo que documentaba está
  mejor dicho en `datos.CABECERAS`, con los títulos literales de la plantilla oficial y sus notas.
- Veintidós imports muertos, entre ellos el `glosa_de` que CONCAR arrastraba «por compatibilidad con la
  0.10» — compatibilidad que la 2.0 retiró.
- **El bloque `detraccion` de `kit/columnas.py` no declaraba `nro_constancia` ni `fecha_constancia`**, que la
  2.6.0 sí escribe en la línea: un driver de terceros que declarara esa columna lo rechazaba el contrato.
- `starsoft` entra en el guardián de OpenConta (`test_openconta.py`), del que se había quedado fuera: era el
  único driver de serie que no validaba sus respuestas reales contra el contrato HTTP.
- `ARQUITECTURA.md`: la sección de STARSOFT decía que escribía un **Excel** levantado de **dos vídeos**, con el
  número **con ceros** y cinco siglas sin constar. Desde la 2.3-2.5.1 es un TXT en ZIP recalcado de su
  documentación oficial, el número va sin ceros y las siglas sin constar son dos. Y se escribe de una vez
  **dónde vive el asiento estándar**, que se confundía con el driver `asiento_neutral`.

## [2.6.1] — 2026-09-22

### Corregido

- **La glosa larga de STARSOFT se CORTA en vez de detener la exportación.** Era su único `no_caben`, y con
  cuatro comprobantes de más de 60 caracteres el mes entero se quedaba sin archivo. La glosa es **texto libre**:
  cortada sigue diciendo lo que decía. Lo que no se corta es un **código** —una cuenta o una serie cortadas
  serían otra cuenta y otra serie—, y ese criterio ya estaba escrito en CONTASIS; STARSOFT era el único driver
  que no lo seguía, mientras CONCAR cortaba a 40 y 30 y CONTASIS a los largos de sus columnas.

  `no_caben` **se queda declarada y devuelve vacío**: es el sitio donde entrará el día que aparezca un límite de
  verdad, de los que hacen que el sistema rechace la fila.

### Cómo migrar

Nada que tocar. Un mes con glosas largas que antes no se podía exportar, ahora sale, con esas glosas recortadas
al largo de la plantilla.

## [2.6.0] — 2026-09-22

**La detracción tiene dos tiempos y ahora el segundo llega al archivo.** Se provisiona al registrar el comprobante y
se deposita días después —«casi pasando el otro mes»—; hasta hoy esa constancia no volvía a ninguna parte.

### Añadido

- **La línea de detracción transporta `nro_constancia` y `fecha_constancia`** (`asiento.motor._detraccion`), que ya
  estaban declarados en el estándar (`detraccion` del comprobante) y no los usaba nadie. El número cae al
  **comodín** cuando no hay constancia, que es el caso normal al cerrar el mes; la fecha no tiene comodín, porque
  una fecha inventada es peor que ninguna. Se resuelve en el núcleo y no en cada driver: es la contabilidad la que
  dice «esto está pendiente», el driver solo elige en qué columna lo escribe.
- **STARSOFT escribe sus campos 25 y 26**, que estaban declarados y se rellenaban con `""` literal. Van solo en la
  fila del proveedor, como el código y la tasa.
- **CONTASIS escribe sus columnas U y V** —«Constancia de depósito de detracción: número» y «: fecha»—, que
  estaban declaradas con su largo y se escribían vacías. **Revierte la decisión del 12-sep-2026** («no pongas
  nada»), a petición de John del 22: la constancia sale en cualquier destino que tenga el campo.
- El esquema del estándar declara las dos claves nuevas en el bloque `detraccion` de la **línea**, que era
  `additionalProperties: false`.

### Cambiado

- ⚠️ **El comodín pasa de `9999999999` a `999999999`** — de diez nueves a **nueve**, contados por John. **Esto
  mueve el asiento de CONCAR**, no solo el de STARSOFT: es el número del documento comodín de la línea `DR`, y así
  se ha importado ya en un CONCAR real. Los asientos con detracción que se exporten a partir de ahora llevan un
  dígito menos que los que ya están importados.
- La **huella del asiento** de un comprobante con detracción cambia, por lo anterior y porque su línea lleva ahora
  la constancia. Las de soles sin detracción y las de dólares no se mueven.

### Cómo migrar

La API pública no cambia. Lo que cambia es **el archivo** de tres destinos, y el comodín en todos ellos. Quien
guarde `nro_constancia` en el bloque `detraccion` de un comprobante lo verá salir; quien no, verá el comodín donde
antes había un hueco.

## [2.5.1] — 2026-09-22

### Corregido

- **El número del documento de STARSOFT va SIN ceros a la izquierda** (John, 22-sep-2026, viéndolo dentro de su
  sistema): en la columna Documento de su asiento salía `E00100000105` y lo quiere `E001105`. Afecta a las dos
  columnas que dicen el documento —`NRO DOCUMENTO` y la `GLOSA`—, porque no puede escribirse de dos formas en la
  misma fila. **La serie se sigue rellenando a cuatro**, y no es lo mismo: ahí el hueco marca dónde empieza el
  número, como pide el manual («si es de 3, un espacio en blanco y el numero desde la quinta»).

  Hasta ahora se rellenaba a ocho, leído de una captura de la hoja `PLANTILLA`; eso era cómo guarda los números
  **esa** instalación, no lo que el formato exige. Con esto STARSOFT deja de ser la excepción: el SIRE, CONCAR y
  CONTASIS ya escribían el número así, y era la regla de la casa desde antes. Se reutiliza
  `modelo.numero_sin_ceros`, que ya existía.

### Cómo migrar

Nada que tocar. Cambia **el archivo de STARSOFT** en dos columnas, en la dirección que pidió quien lo importa.

## [2.5.0] — 2026-09-22

**Las cuentas dejan de ser unas para todos, y el archivo de STARSOFT se recalca de sus ejemplos oficiales.** Dos
trabajos que empezaron por sitios distintos y acabaron en el mismo: lo que el motor daba por universal era, en
realidad, lo que hace CONCAR.

### Añadido

- **Un driver puede declarar con qué cuentas nace una empresa que lleva su sistema** (`CUENTAS_POR_DEFECTO`). Las
  cuentas se apilan en tres capas: las de fábrica, encima las del sistema al que se exporta y encima las que la
  empresa guardó. Se declaran **solo las que cambian**, así que lo que un driver no diga lo sigue heredando de lo
  general, hoy y el día que lo general mejore. El contrato las valida contra el bloque `cuentas` de lo general.
- `configuracion_por_defecto` acepta un `driver` y devuelve entonces lo general con las cuentas de ese sistema y
  solo su sección, igual que `describir_configuracion`. Es con lo que una aplicación siembra una empresa que ya
  dijo con qué sistema trabaja: sembrar la de todos le daba a un contribuyente de STARSOFT las cuentas de CONCAR.
  El parámetro es opcional y quien llamaba sin él sigue llamando igual.
- **STARSOFT declara las suyas, de ocho dígitos.** Cuatro constan en el manual —facturas por pagar `42120001`,
  IGV `40111000`, clientes `12120001`, ingresos `70410001`— y siete valores se deducen de su patrón (la subcuenta
  del PCGE de cuatro dígitos más un correlativo de cuatro; las de raíz de cinco completan con tres), marcados uno
  a uno como defecto configurable. `gasto` NO se declara: en lo general va vacía a propósito y la del manual
  (`62010001`) es una cuenta de gasto real, que de respaldo imputaría en silencio toda compra sin cuenta.
- **CONCAR declara su cuenta de gasto** (`631101`). Es la única en la que se aparta, porque las demás cuentas de
  lo general ya son las suyas — el PCGE a seis dígitos salió de ahí y hasta hoy no estaba dicho en ninguna parte.

### Corregido

- ⚠️ **Las cuentas 62 llevan centro de costo** (`cuentas_con_centro` pasa de `["63", "65", "70"]` a
  `["62", "63", "65", "70"]`), **para cualquier sistema**. La regla se escribió de una frase que no decía nada del
  62 y nadie lo echó de menos. **Tiene dos caras:** una 62 pasa a escribir su centro y pasa a exigirlo, así que un
  mes con cuentas 62 y sin centro deja de estar «listo para exportar». Quien tenga la lista guardada no lo recibe.
- ⚠️ **En STARSOFT la detracción no es un asiento: son campos de la fila del proveedor.** Su tabla le dedica seis
  —24 afecto, 25 número, 26 fecha, 31 código, 34 tasa, 35 importe— y sus ejemplos llevan tres filas por
  comprobante. Hasta ahora se escribían cinco, porque el driver proyectaba tal cual lo que el núcleo le daba: en
  CONCAR el traslado a la cuenta de detracciones son dos líneas más. **Una compra con detracción sale ahora con
  las mismas tres filas que una sin ella**, y el archivo cuadra igual. El asiento del motor no cambia.
- ⚠️ **La nota de débito de STARSOFT es `CD` y no `ND`**, heredada de CONCAR y marcada «por confirmar». Es el
  mismo error que `NC` en vez de `CC`: el archivo entra igual y el sistema clasifica el comprobante como otra
  cosa. Los mismos ejemplos confirman `TK` y `RC`; de las cinco siglas sin constar quedan dos.
- **El orden de las filas de STARSOFT es el de sus ejemplos**: una compra va IGV, proveedor, gasto; una venta,
  cliente, IGV, ingreso. Se ordena en el driver y no en el núcleo, porque el orden entra en la huella del asiento.
  El caso que lo destapó es la nota de crédito de ventas, que al invertirse los sentidos salía al revés.
- **La columna `GLOSA` de STARSOFT vuelve a llevar el documento** (`FT E001-00000871 /`), con el concepto en
  `GLOSA MOVIMIENTO`: es lo que hacen sus treinta ejemplos, y revierte la decisión del 21-sep-2026.
- **La tasa del IGV sale `18.00`** y no `18`, y los importes que no aplican van `0.00` y no vacíos en compras
  (porcentaje de operaciones mixtas, valor CIF, tasa e importe de detracción). En ventas no: los suyos van en
  blanco.

### Cómo migrar

Quien integre el motor no tiene nada que tocar: la API pública no cambia y el parámetro nuevo es opcional. Lo que
cambia es **el archivo de STARSOFT**, en la dirección correcta, y **qué cuentas exigen centro de costo**, que
afecta a todos los destinos. Si una empresa ya tenía `cuentas_con_centro` guardada, no se mueve. Si prefieres que
el motor siga avisando de las compras sin cuenta hacia CONCAR, deja `cuentas.gasto` en blanco en su configuración:
lo guardado manda sobre lo que traiga el driver.

## [2.4.0] — 2026-09-22

**Las huellas NO cambian.** Esto toca la proyección de STARSOFT a columnas, no el asiento: ni un fixture de
snapshot ni el de líneas neutrales se movió.

**STARSOFT se recalca de su documentación oficial.** Hasta hoy el driver se levantó de dos vídeos y de cuatro
capturas de la hoja `PLANTILLA` de Excel. John consiguió la documentación de STARSOFT —«Sistema de Contabilidad ·
Documentación», compras y ventas, con la tabla de campos y **ejemplos de TXT sacados del propio sistema**— y la
importó de verdad: el archivo entró, y al compararlo con los ejemplos aparecieron dos errores que la hoja de
Excel escondía. Lo que dice el manual está volcado en `STARSOFT-INTEGRACION.md`, campo a campo; los PDF no
entran al repositorio, que es público y son de otra empresa.

### Corregido

- ⚠️ **La línea llevaba campos de más: 38 en compras y 34 en ventas, cuando son 35 y 27.** La regla que la
  plantilla de Excel escondía es que **el número del ítem en el manual no es su posición en la línea**: varias
  columnas dependen de un «concepto general» de cada instalación y, dice literal, «si el concepto está en falso,
  **no incluir la columna**» — así que no ocupan sitio. La hoja las tiene todas; el archivo, no. Quedan
  declaradas en `datos.CONDICIONALES`, con el concepto del que depende cada una, para que conste que existen y
  por qué no se escriben. En compras salían de más `NRO FILE`, `OTROS TRIBUTOS` e `IMP BOLSA`; en ventas esas
  tres y además `NUM DOC FINAL`, `VALOR ISC`, `OTROS TRIB` y `EXONERADO`.
- ⚠️ **Las dos fechas estaban cruzadas, y solo se notaba con un comprobante extemporáneo.** El manual pide que
  la del DOCUMENTO sea la emisión y que la de REGISTRO caiga dentro del periodo; el driver escribía la del
  asiento en la primera y la emisión en la segunda. Con una factura de julio anotada en agosto rompía las dos
  reglas a la vez: la del documento salía **mayor** que la de registro, y la de registro **no era del periodo**.
  Dentro de su propio mes las dos coinciden, y por eso ningún ejemplo lo delataba. En ventas van en posiciones
  cambiadas respecto a compras (5 registro, 10 emisión) y también se corrige.
- El centro de costo de ventas se mueve de la columna `AA` a la `X`, que es su posición real ahora.

### Añadido

- Tres pruebas contra el manual: el número de campos de cada libro, las dos fechas con un comprobante
  extemporáneo, y que **el tipo de conversión (`VTA`) va en TODAS las líneas** y no solo en la del tercero —
  los ejemplos oficiales lo traen en las tres y el manual de compras lo da por obligatorio sin distinguir por
  cuenta. Era una duda razonable; sin prueba, volvería.

### Cómo migrar

Nada que tocar en quien integre el motor: la API pública no cambia. Lo que cambia es **el archivo**, y en la
dirección correcta — si alguien guardaba archivos de STARSOFT generados antes, los nuevos tienen menos campos y
las fechas en su sitio. Los tres fixtures de caracterización se regeneraron: su diff es exactamente `|D|||||` →
`|D||` en compras y el recorte equivalente en ventas.

## [2.3.0] — 2026-09-22

**Las huellas NO cambian.** Esto toca cómo se escriben los bytes, no el asiento, y la batería lo confirma sin
regenerar un solo fixture del SIRE ni de los snapshots.

### Cambiado

- **STARSOFT escribe un TXT de palotes envuelto en un ZIP, y ya no un CSV** (John, 22-sep-2026). Es una de las
  dos vías de carga del sistema —la otra es su plantilla de Excel— y el formato sale de un TXT de STARSOFT de
  verdad: campos separados por `|`, **sin fila de cabecera** y sin palote al final. El CSV era provisional,
  para poder revisarlo columna por columna mientras no se conocía la plantilla; ahora se conoce.

  El archivo pasa a `STARSOFT_COMPRAS_202507_20601234567.txt` dentro de su `.zip`, y el formato, de
  `starsoft_csv` a `starsoft_txt`.

- **Las fechas de STARSOFT salen en `DD/MM/AAAA` y no en ISO.** Es un defecto que llevaba ahí desde el primer
  día y que el CSV también tenía: el driver escribía `2025-07-01` donde su hoja y su TXT dicen `01/07/2025`.
  Son **cinco columnas en compras y cuatro en ventas**, y se traducen **por la clase declarada de la columna**,
  así que la columna de fecha que se añada mañana sale bien sin acordarse de nada.

### Añadido

- **Un driver de archivo puede pedir que su salida viaje comprimida**, con `comprimir=True` en sus
  `OpcionesArchivo`. Hasta ahora el ZIP estaba atado a la FORMA del driver: solo lo hacía la rama de texto, que
  es la del SIRE, y un driver de asientos como STARSOFT no podía usarla sin dejar de recibir el asiento y de
  declarar su configuración. Comprimir es del formato, no de la forma.

  Quien comprime sale además como el SIRE en toda la superficie —`texto` legible, `zip_base64` y `archivo_zip`
  en la respuesta, el TXT y el ZIP en disco desde la CLI, los dos adjuntos en el MCP— **sin que nada de eso
  cambiara**, y conservando lo que la rama de texto no da: el resumen con el cuadre y la huella.

- **`OpcionesArchivo` gana `fecha`**, con los mismos valores que `Opciones`. Vacío —el defecto— deja las fechas
  como vienen, en ISO, que es lo que quiere un formato de intercambio como el CSV o el asiento neutral.

### Documentación

- **Este driver es el de STARSOFT *Desktop*, y ahora lo dice.** Existe además **STARSOFT Web (Gold Edition)**,
  con API pública, que será `starsoft_web` — el hito A5 de la hoja de ruta, **abierto a quien quiera
  escribirlo**. Lo que este driver resolvió le sirve casi entero: las siglas, los sub-diarios, el destino del
  IGV, las cuentas y la proyección son los mismos; lo distinto es a dónde van los datos.

## [2.2.0] — 2026-09-21

> ⚠️ **Todas las huellas de asiento cambian.** Es lo primero que hay que mirar al subir: la fórmula es la
> misma, pero el contenido que resume no. Quien guarde huellas para reconocer una tanda ya exportada verá las
> de antes como distintas. **Ni un importe, ni una cuenta, ni un sentido se mueven**, y no es una impresión:
> al regenerar los snapshots congelados se comparó celda a celda contra los anteriores.
>
> Cambian por dos motivos, los dos comprobados:
>
> - **la glosa pierde sus prefijos** — 57 celdas por snapshot, todas glosas y ninguna otra;
> - **el asiento de una venta reordena sus líneas** — 7 de los 52 casos, todos de venta, y en los 7 la lista
>   de *(cuenta, sentido, importe)* es la misma permutada.
>
> Las huellas de los asientos de COMPRA solo cambian por lo primero; su orden no se toca.

### Añadido

- **El canal del SIRE, descrito como datos**: `catalogos_api_sire()`, `GET /v1/catalogos/sire-api` y el recurso
  `contaperu://catalogos/sire-api`, leídos de `datos/sunat/sire_api.json`. Trae los dos caminos de OAuth de SUNAT,
  las rutas **por libro**, los parámetros obligatorios de cada operación, la metadata de TUS, los estados del
  ticket y los códigos de retorno, cada bloque con su fuente y su `actualizado_al`.

  **Esto NO es un cliente y no lo será.** El motor sigue sin salir a la red: `tests/test_frontera.py` prohíbe
  importar `httpx` o `socket` y `conftest.py` mata cualquier conexión. Es la descripción de una API ajena, el
  mismo papel que ya cumplen los formatos de CONCAR, CONTASIS y STARSOFT —describir un sistema ajeno sin hablar
  con él— y lo que el criterio del hito D7 llama separar la normalización del transporte. El transporte, las
  credenciales y el estado se quedan fuera.

  Existe porque el conocimiento del FORMATO ya estaba resuelto una vez para todos y el del CANAL no: cada casa de
  software lo vuelve a reunir a mano desde dos manuales de SUNAT que **se contradicen entre sí** (`codTipoArchivo`
  es `1=csv` en compras y `1=excel` en ventas, y está así en los dos PDF). Incluye lo que más caro cuesta
  descubrir a base de rechazos: que RVIE y RCE no comparten rutas y cruzarlas devuelve **500 de nginx** y no 404;
  que desde la v24 `archivoreporte` exige cuatro parámetros más o responde 500; que el código útil del 422 vive
  dentro de `errors[]` y no en el `cod` de arriba; que el error **1024** significa «ya entró» y no «falló»; y que
  **«Generar el registro» no existe por API** (RS 000040-2022 art. 8.3), así que el techo de cualquier
  integración es dejar el mes en preliminar.

- **`INTEGRAR.md` explica el SIRE de punta a punta**: de dónde salen los bytes y el nombre, que el nombre lo
  impone SUNAT y renombrarlo hace que lo rechace, que ese nombre ES la política de idempotencia, que el ZIP es
  reproducible, que el SIRE no lleva huella, y dónde acaba el motor y empieza tu conector.

### Cambiado

- **La glosa es la misma en todas las líneas del comprobante, sin prefijos.** Las líneas derivadas
  anteponían lo que las identificaba —`IGV - `, `RET 4TA - `, `DETRACCION - `— y era información repetida:
  qué es cada línea lo dicen su `rol` y su cuenta, que es como la buscan los seis drivers. Ninguno leía la
  glosa para decidir nada.

  El prefijo además se comía el dato. CONCAR admite 30 caracteres en su columna de detalle: con un concepto
  real, la línea de la detracción llegaba como `DETRACCION - SERVICIO DE TRANS` —sobrevivía la etiqueta y se
  perdía el concepto—. Ahora llega `SERVICIO DE TRANSPORTE DE MATE`.

  Vale para **todos los drivers y para el asiento neutral**, porque se quita en el motor y no en la salida.
  Enmienda [0013](estandar/enmiendas/0013-glosa-sin-prefijos.md); el esquema no se toca y `open-accounting`
  sigue en **1.0**. Quien busque sus líneas por `rol` no nota nada; quien buscara la del IGV por el texto
  `"IGV - "` deja de encontrarla.

- **El asiento de una VENTA sale `cliente · IGV · ingreso`**, y no `cliente · ingreso · IGV`. Lo piden dos
  archivos reales de STARSOFT —una hoja de su plantilla y un TXT de otro generador— y era la única asimetría
  entre los dos libros: en compras el motor ya ponía el IGV justo detrás del principal. Las cuentas, los
  sentidos y los importes son los mismos, y la partida cuadra igual; **cambian las huellas de los asientos de
  venta**, porque el orden entra en la huella. Las de compras no se mueven.

  Se comprobó caso por caso al regenerar los snapshots: de los 52 congelados cambian 7, **todos de venta y en
  todos solo el orden** —misma cuenta, mismo sentido, mismo importe—.

- **STARSOFT: las dos columnas de glosa dicen lo mismo, el concepto del comprobante** (John, 21-sep-2026). La
  principal llevaba el documento (`FT F001-00000202 /`), que es lo que muestra una de las hojas, pero el tipo y
  el número ya viajan en sus propias columnas: repetirlos gastaba la glosa en decir dos veces lo mismo.

- **El tipo de cambio viaja en la línea del asiento aunque la moneda sea soles.** Es un hecho del comprobante,
  y hasta ahora el núcleo lo descartaba en PEN — lo que dejaba sin él a un destino que lo pide en todas sus
  filas: STARSOFT (John, 21-sep-2026, confirmado por la hoja real, que lo muestra en comprobantes en soles).
  Cuándo se escribe pasa a ser decisión de formato, que es de cada driver: **el Excel de CONCAR no cambia ni una
  celda**, porque sigue llenando su columna `G` y su `H` solo en moneda extranjera, que es como está validado.

  El motor **no inventa un tipo de cambio**: si el comprobante no lo trae, la columna sale vacía. No tiene tabla
  de tipos de cambio ni sale a la red.

- **STARSOFT: la plantilla de COMPRAS se calca del archivo real y pasa de 32 columnas a 38.** Cuatro capturas
  más de la hoja `PLANTILLA` (John, 21-sep-2026). Faltaban las tres columnas de la detracción que van juntas
  —`DETRACCION`, `NRO DOC DETRACCION`, `FECHA DETRACCION`— y `FECHA DOC REF`, así que **desde la `X` todo
  estaba corrido cuatro posiciones**; al final aparecen `OTROS TRIBUTOS` e `IMP BOLSA`. Los nombres pasan a ser
  los de la hoja (`CTA CONTABLE`, `FECHA DOCUMENTO`, `DOCUMENTO ANULADO`, `DEBE / HABER`, `NRO FILE`…).

  La captura **confirma el `04`** del sub-diario de compras, los cuatro dígitos del comprobante, el `03` del
  tipo de anexo y la serie rellenada a cuatro (`020 00044419`). Y cierra una duda: **`IGV POR APLICAR` pasa a
  `0`** —el `1` sería que el IGV está pendiente de aplicación—, porque la hoja la muestra con `0` en todas las
  filas. Estuvo vacía mientras la única fuente fue la narración del vídeo.

- **STARSOFT: la plantilla de VENTAS se calca del archivo real y pasa de 25 columnas a 34.** Cuatro capturas de
  la hoja `PLANTILLA` abierta en Excel con datos dentro (John, 21-sep-2026) corrigieron el mapa entero: faltaban
  `TIPO ANEXO` (`F`) y `CODIGO CLIENTE` (`G`), así que **de la `G` en adelante todo estaba corrido una
  posición**, y aparecen `VALOR ISC`, `OTROS TRIB`, `FECHA DOC REFERENCIA`, `NRO FILE`, `EXONERADO`,
  `OTROS CARGOS` e `IMP BOLSA`. Los nombres pasan a ser los literales de la hoja (`CTA CONTABLE`,
  `DOCUMENTO ANULADO`, `DEBE / HABER`, `CENTRO DE COSTOS`…), que **no son los de compras**: son dos plantillas y
  cada una se calca de su fuente. La de compras sigue levantada del vídeo.

  Con ellas se corrigen tres reglas que el vídeo no dejaba ver: **la serie se rellena a cuatro caracteres** —el
  número ocupa 12 siempre, `F00100000202` y `001 00036207`, así que una boleta salía con 11—; **`RUC CLIENTE` y
  `RAZON SOCIAL` van solo en la fila del cliente**, no repetidos en las tres; y la glosa del documento es
  `BV 001 -00036207 /`.

- **STARSOFT: la columna `D` se llama `COMPROBANTE`** (John, 21-sep-2026), en los dos libros, que es como la
  llama la plantilla real. La función que la calcula sigue llamándose `voucher`, superficie pública congelada.

- **STARSOFT: el tipo de anexo se parte en dos, y los dos traen valor de fábrica.** El maestro de proveedores
  y el de clientes son distintos en STARSOFT, así que `tipo_anexo` —una sola clave, vacía— pasa a
  `tipo_anexo_proveedor` (`03`, compras) y `tipo_anexo_cliente` (`02`, ventas). Antes había que elegir cuál de
  los dos maestros salía bien.

- **STARSOFT: la plantilla de VENTAS gana la columna `TIPO ANEXO` en la `F`**, que este repositorio daba por
  inexistente porque el vídeo no la mostraba. La confirma una captura de la hoja `PLANTILLA` abierta en Excel
  (John, 21-sep-2026), la fuente más fuerte que tiene el driver: no es una narración, es el archivo. Las veinte
  columnas siguientes se corren una letra.

- **El sub-diario de compras de STARSOFT es `04` y no `4`** (John, 21-sep-2026). El vídeo dice «cuatro» y de
  ahí salió un `4` a secas; el formato lleva los dos dígitos, como el `03` de ventas —que sí estaba bien desde el
  principio y venía delatando la inconsistencia—. Es un valor por defecto configurable, así que quien ya lo tenga
  puesto a mano no se entera; quien use el de fábrica verá `04` en la columna y en las claves de
  `resumen["sub_diarios"]`.

- **La columna `ANULADO` de STARSOFT sale `0` y no en blanco**, en compras y en ventas. Un comprobante que está
  entrando al registro no está anulado, y afirmarlo es más claro que callarlo (John, 21-sep-2026). Su hoja admite
  las dos formas —«Blanco o `0` por defecto»— y se elige la que afirma, que además es lo que ya hacían
  `IMPORTACION` y `EXPORTACION` en la misma fila. Con la captura de la hoja real, `IGV POR APLICAR` y
  `DETRACCION` se sumaron al mismo criterio: en una fila de compras las cuatro banderas dicen `0`.

## [2.1.0] — 2026-09-21

**El archivo que produce cada driver cambia de nombre.** Si tienes un script que lo busca por su nombre, es lo
primero que hay que mirar de esta versión.

La regla nueva es **`SISTEMA_LIBRO_PERIODO_RUC`** y vale para los cinco drivers de sistema:

| Antes | Ahora |
|---|---|
| `CONCAR_20601234567_202507_COMPRAS.xlsx` | `CONCAR_COMPRAS_202507_20601234567.xlsx` |
| `CONTASIS_20601234567_202507_COMPRAS.xlsx` | `CONTASIS_COMPRAS_202507_20601234567.xlsx` |
| `STARSOFT_20601234567_202507_COMPRAS.csv` | `STARSOFT_COMPRAS_202507_20601234567.csv` |
| `asiento_20601234567_202507_compra.csv` | `CSV_COMPRAS_202507_20601234567.csv` |
| `asiento_neutral_20601234567_202507_compra.json` | `ASIENTO_NEUTRAL_COMPRAS_202507_20601234567.json` |

El sistema delante y el RUC al final es cómo se busca un archivo cuando se llevan 30-80 contribuyentes: por
sistema y por mes. Hasta aquí convivían tres convenciones —la de los tres ERP, la del CSV en minúscula y con el
libro en singular, y la del SIRE— porque cada driver repetía su propia `f-string`.

**El TXT del SIRE NO cambia** y es la única excepción: su nombre lo impone SUNAT (Tablas 6 y 13), y además
`comparar_sire.registro_de()` lo lee para saber si un archivo es de ventas o de compras. Queda escrito en
`drivers/sire/txt.py`, junto a la función, para que nadie lo unifique «por coherencia».

### Añadido

- **`drivers.kit.nombre_de_archivo(sistema, libro, opciones)`** — la regla, escrita una vez. Un driver de
  terceros la llama y su archivo se llama como los demás sin decidir nada.

### Cambiado

- **El voucher de STARSOFT conserva sus cuatro dígitos: `0001`, no `1`.** El motor numera `070001` (mes +
  correlativo, que es lo que pide CONCAR) y a STARSOFT se le quita el mes; hasta ahora ese recorte pasaba por
  `int()` y se llevaba por delante los ceros, que son el ancho del campo. **CONCAR no cambia**: su columna C
  sigue llevando `070001`, como dice su plantilla. Ojo al revisar el CSV: Excel muestra `0001` como `1` — el
  archivo es correcto, engaña el visor.

### Arreglado

- **STARSOFT devolvía `sub_diarios` como lista** (`["4"]`) en vez del diccionario de rangos que devuelven los
  demás, y como el `resumen` del driver se funde ENCIMA del que calcula el núcleo, borraba `desde`, `hasta`,
  `desde_codigo`, `hasta_codigo` y `desborda`. Eso es justo lo que un ERP guarda para proponer el correlativo del
  mes siguiente: quien lo leyera esperando un diccionario —como hace la aplicación que integra el motor— se
  encontraba una lista. Ahora el driver no pone esa clave y manda la del núcleo.

### Nota para quien integra

Ninguna huella se mueve y la API pública no pierde ni cambia un nombre: el correlativo no entra en la huella y el
voucher se calcula al proyectar, no en la línea neutral. Los archivos ya exportados y guardados conservan el
nombre que tenían — la regla vale para lo que se exporte de aquí en adelante.

## [2.0.0] — 2026-09-21

**Se retira la compatibilidad con la 0.x. Quien integró con la 1.x no tiene que cambiar una línea.**

Esta versión mayor **no cambia la API pública**: `contaperu.api` conserva cada nombre con su firma, y
`tests/test_superficie_publica.py` lo demuestra al seguir pasando contra el mismo
`fixtures/superficie/1.0.json`, sin regenerarlo. Lo que desaparece es la capa que traducía las rutas de la 0.x.

**Por qué ahora, y por qué no rompe a nadie.** El repositorio prometía que lo que una aplicación importaba en la
0.10 seguiría resolviendo hasta la 2.0. Esa promesa **no protegía a un solo usuario**: ninguna versión 0.x llegó a
publicarse en PyPI. La primera publicada es la **1.1.0** (19-sep-2026); las 0.7 a 0.10 y la propia 1.0.0 existen
solo como tags de git, y entre `v0.10.0` y `v1.0.0` pasaron 101 minutos. Nadie pudo instalar nunca una 0.x.

### Retirado

- **Cinco módulos que no contenían nada** —`contaperu.operaciones`, `contaperu.generar`, `contaperu.cli`,
  `contaperu.formato` y `contaperu.servidor_mcp`— y el paquete `_compat/` que los sostenía. Eran tablas de
  redirección: cero `def`, cero `class`. Lo que hacían lo hace `contaperu.api`, y los comandos instalados
  (`contaperu`, `contaperu-mcp`, `contaperu-http`) ya apuntaban a `contaperu.puertas.*` y no cambian. En su lugar,
  `python -m contaperu.puertas.cli`.
- **`drivers.concar.construir`**, la forma de CONCAR hasta la 0.10. El archivo se pide a `api.exportar_archivo`.
- **`comparar_sire.leer(ruta)`**: el núcleo no lee disco. Entra `leer_bytes(datos)`.
- **La tabla del PCGE por ruta de archivo** (`pcge.adaptar(lineas, ruta)`, `pcge.cargar_equivalencias(ruta)`). La
  tabla entra como diccionario; el archivo lo abre quien llama. `adaptar` pierde su segundo parámetro posicional.
- **Los nombres que `asiento.motor` y `drivers.concar.xlsx` reexportaban** de la 0.10 (`Opciones`,
  `formatear_numero`, `numerar`, `huella`…). Viven en `contaperu.drivers.kit` y en su módulo.

### Cambiado

- **`_obsoleto.RETIRO` pasa a `"3.0"`.** El módulo se queda, sin un solo usuario, a propósito: `RutaObsoleta` es
  parte de la API pública —una aplicación la filtra con precisión— y el circuito ya está escrito y probado para la
  próxima vez que algo cambie de sitio. Lo cubre `test_api.py`, sobre un módulo de mentira.
- **La batería baja de 1117 a 1015 tests.** Se van `test_compat_superficie.py` y `test_compat_firmas.py`, que
  congelaban la superficie de la 0.10 y cuyo propio docstring decía que la promesa duraba «hasta la 2.0».
  `test_caracterizacion.py` deja de caracterizar por dos rutas y queda con una: lo que congelan sus JSON **no
  cambió** al retirar la otra.

### Cómo migrar

Desde la 1.x, `pip install -U contaperu` y nada más. Si tu código importa alguno de los nombres retirados —cosa
que solo podría pasar si copiaste código de un tag de git—, la tabla de la 1.0 en este mismo CHANGELOG dice dónde
vive cada uno hoy.

## [1.4.0] — 2026-09-20

**Un driver de asientos ya puede leer los hechos tributarios del comprobante, y hay un driver de STARSOFT.**
Lo segundo destapó lo primero.

### Añadido

- **El driver `starsoft`**, el cuarto de canal `legacy`. STARSOFT importa asientos desde un Excel con una
  plantilla que él publica: cada fila es una cuenta con su debe o haber, y las de un comprobante comparten
  cabecera. Es `desde_lineas`, como CONCAR, y el núcleo sigue poniendo toda la contabilidad.

  Lo que lo separa de CONCAR, con el mismo documento delante: el sub-diario de compras es `4` y el de ventas
  `03`, no `11` y `05`; el voucher va limpio (`1`) y no con el mes delante (`070001`); el número del documento va
  pegado y con ceros (`F13600000431`), al revés que en CONCAR y el SIRE; la nota de crédito se llama **`CC`** y
  no `NC` —`FT` y `BV` sí coinciden, que es lo que hace la trampa peligrosa—; y lleva una columna que CONCAR no
  tiene, **`DESTINO`**, porque su plantilla mezcla el asiento con el registro tributario en la misma fila.

  **Está EN PRUEBAS, y se dice donde se ve.** El formato se levantó de dos vídeos y sus capturas
  (`STARSOFT-INTEGRACION.md`), no de una plantilla oficial: cinco de sus columnas están inferidas de una
  narración y cinco de sus ocho siglas son las de CONCAR como punto de partida, todas marcadas en el código.
  Por eso escribe **un CSV revisable y no el `.xlsx` definitivo**, y su docstring dice «EN PRUEBAS» donde el de
  CONTASIS dice «Aceptado (13-sep-2026)». Nadie ha importado todavía en STARSOFT un archivo que genere.

- **La cabecera del índice lleva ahora todos los hechos del comprobante**: 32 campos donde había 13.

  Un driver de REGISTRO —el SIRE, CONTASIS— recibe el comprobante entero. Uno de ASIENTOS solo ve las líneas y
  la cabecera, y esa cabecera tenía los trece campos que CONCAR necesita. Bastó mientras el único driver de
  asientos escribiera contabilidad pura: de las 41 columnas de CONCAR **ninguna es el destino del IGV**, así que
  el dato podía caerse sin que nadie lo notara. Un comprobante con `destino_igv: "DGNG"` producía exactamente el
  mismo Excel que uno con `DG`.

  Se caían diecinueve campos, y diecisiete son columnas oficiales del registro de compras y ventas de SUNAT.
  Entran todos: `numero_final`, `contraparte_tipo_doc`, los dos descuentos, `exonerado`, `inafecto`,
  `exportacion`, `isc`, `base_ivap`, `ivap`, `icbper`, `otros`, `retencion`, `destino_igv`, `valor_no_gravado`
  —ya resuelto—, `anio_dua`, `cod_dep_aduanera`, `clasif_bienes` e `id_contrato`.

  **Lo que entra de verdad es la regla**, y `tests/test_cabecera.py` la hace cumplir contra el esquema publicado
  y no contra una lista escrita a mano: la cabecera lleva **todo hecho contable o tributario del comprobante y
  ningún dato del proceso que lo produjo**. Un campo nuevo del estándar o entra en la cabecera, o se declara como
  lo que no es un hecho, con su motivo. Fuera quedan siete —`origen`, `confianza`, `archivo_nombre`,
  `datos_originales`, `estado`, `excluida`, `observaciones`—: un driver que mirara `confianza` estaría decidiendo
  contabilidad con la certeza de un modelo de lenguaje.

  **Va a la cabecera y no a la huella, por razones medidas.** La huella del motor responde «¿este asiento ya
  salió?» y va sobre las líneas; si los hechos tributarios entraran, dos exportaciones con el mismo asiento
  darían huellas distintas y el aviso de lote repetido dejaría de dispararse. Hay un test que lo fija. Y cambiar
  la fórmula invalidaría todas las guardadas por quien las persista; añadir a la cabecera no invalida ninguna.

### Cambiado

- **`ARQUITECTURA.md` deja de contradecir a `CONTRIBUTING.md`.** Uno invitaba a escribir un driver «sin esperar a
  nadie» y el otro decía que «hasta entonces no se publica ningún driver ni esqueleto». Un colaborador que
  quisiera hacer el de SISCONT, o mejorar el de CONCAR, leía el segundo y se iba, que es lo contrario de un
  núcleo contable abierto. Lo que esa regla protegía —no prometer que un formato funciona cuando nadie lo ha
  importado— se consigue **declarando el estado, no prohibiendo el código**, que es lo que ya hacía el docstring
  de CONTASIS con su línea de «Aceptado».

  En su lugar queda escrito el criterio: **las mejoras se evalúan y lo que haga falta se cambia**, con el precio
  de cada tipo de cambio en una tabla —añadir es barato, tocar el estándar pide una fuente, cambiar la huella
  invalida las guardadas—. No son prohibiciones: es lo que cuesta, escrito antes de hacerlo.

## [1.3.0] — 2026-09-20

**La puerta MCP deja de decidir por el contribuyente.** Cuatro divergencias con las otras dos puertas, una de
ellas contable. Nada de esto toca la api pública ni el contrato OpenConta: lo que se ha hecho es alinear con
ellos la única puerta que se había desviado.

### Cambiado

- **`driver` se declara siempre en `diagnosticar`, `generar_asiento` y `exportar`.** Traían `"concar"` de
  fábrica y eran las únicas de las tres puertas que lo hacían: la api lo exige, el contrato ya lo declaraba
  obligatorio y la línea de comandos lo enseña en su `--help`. Un agente que olvidara el parámetro le daba un
  **Excel de CONCAR a un contribuyente de CONTASIS**, y eso no se nota hasta que el archivo ya está importado.
  **Es un cambio de comportamiento**: una llamada que hoy omita `driver` pasa a negarse. Era justo la llamada
  que salía mal.
- **Las doce herramientas contestan un `CallToolResult`**, como ya hacía `exportar`: el resultado en JSON, o el
  rechazo como «problem details» del RFC 9457 con su `clave` estable y `isError`. Antes el SDK envolvía
  cualquier excepción en un `ToolError` con el texto pegado, así que un cliente no podía ramificar por nada —y,
  peor, un error que **no** es del motor salía con su texto entero, que puede llevar una ruta interna. Por HTTP
  eso se enmascara desde siempre; esta es la puerta publicada sin autenticación.
- **`claves_previas` acepta el número como número.** La api y el esquema de la puerta HTTP admiten texto,
  entero o nulo; el MCP solo texto. El peligro no era el rechazo sino lo que hace un agente al encontrárselo:
  quitar las claves para que pase deja entrar un comprobante ya anotado en otro periodo, y eso SUNAT lo rechaza.
- **`fecha` es una fecha que puede no venir** (`format: date`), y no una cadena con `""` de fábrica.

### Añadido

- **`drivers_disponibles` también como herramienta**, sin dejar de ser el recurso `contaperu://drivers`. Es la
  única que sale por las dos vías, y es la pareja del cambio de arriba: en MCP los recursos los gobierna la
  aplicación cliente, que puede ofrecérselos al modelo o dejarlos como adjuntos que elige la persona, así que
  preguntar qué destinos hay no podía seguir dependiendo de esa decisión.
- **`validar_comprobantes` recibe `imputacion`**, que `api.revisar` y `POST /v1/revisar` ya aceptaban: una
  llave huérfana sale ahora al revisar y no al exportar.
- **El test que impide que esto vuelva.** `test_la_puerta_mcp_recibe_lo_mismo_que_la_http` compara las doce
  contra `api.OPERACIONES`, con los dos únicos renombres deliberados declarados a la vista. La causa de la
  divergencia contable era que el MCP escribía sus parámetros a mano mientras la puerta HTTP los deriva de
  `api/tabla.py`: dos fuentes para un contrato divergen solas. Con él llegan los primeros tests de `main()`.
- **El README ya no dice de memoria cuántas herramientas hay.** `test_documentacion.py` cuenta las que publica
  el servidor y las compara con lo que dicen `README.md` e `INTEGRAR.md`; decían 11 y 6 cuando eran 12 y 7.

### Retirado

- **`--transporte sse`.** Quedaba fuera del bloque que pone `stateless_http` y la defensa del `Host`, así que
  ignoraba `--dominio` en silencio y acumulaba sesiones. Nunca se documentó ni se probó, y el transporte está
  obsoleto en la especificación desde 2025-03-26. El que sirve en red es `http`, que es *streamable HTTP*.

### Documentación

- El paquete **está publicado en PyPI** desde el 19-sep-2026 y el repositorio es público. `README.md`,
  `INTEGRAR.md` y `CLAUDE.md` seguían diciendo lo contrario y recomendando instalar desde un commit de git.

## [1.2.1] — 2026-09-20

**Las dos puertas dan lo mismo.** Dos defectos que encontró el primer consumidor real al cruzar de
`contaperu.generar` a `contaperu.api`, y los dos venían de lo mismo: `preparar` se adelantaba al driver, decidiendo
cosas que son del **destino** y no del documento.

- **El resumen volvía a contar lo que se dejó fuera.** `preparar` descartaba los comprobantes excluidos antes de que
  `generar` los contara, así que `exportar_archivo` devolvía **`resumen.excluidos` siempre en 0** mientras la ruta de
  la 0.x lo contaba bien. Ese número se persiste: quien lo guardara vería cero excluidos para siempre, sin un error
  que lo delatara. Ahora `preparar` devuelve **todos** los comprobantes y quien llama selecciona —que es lo que ya
  hacían los dos, `salida.generar` y `armado.generar_asiento`—.
- **Un error en un comprobante que ese destino no lleva ya no impide el archivo.** El recibo por honorarios no va en
  el TXT del SIRE (`EXCLUYE_TIPOS`), así que su retención mal puesta no puede impedir declarar a SUNAT. La API
  pública comprobaba los errores **antes** de aplicar la regla del driver y se plantaba; la ruta de la 0.x, que
  filtra primero, dejaba salir el archivo. Lo que bloquea se mira ahora sobre lo que ese destino lleva de verdad, y
  un error en lo que **sí** va sigue deteniéndolo todo — hay un test para cada mitad.

Los dos casos entran en la batería como **la misma propiedad**: la ruta de la 0.x y la API pública tienen que
responder igual sobre el mismo documento. Es el tipo de fallo que solo aparece cuando alguien cruza la frontera de
verdad, y por eso vale más que el arreglo.

## [1.2.0] — 2026-09-19

**`api.config_aplicada`: la configuración tal como la preparan las operaciones.** La pide el primer consumidor real
del estándar, y el hueco que tapa es este: la API pública entregaba las piezas que **consumen** la configuración
aplicada y no la que la **construye**.

`asiento.faltantes_para`, `asiento.sub_diario`, `asiento.cuenta_tercero` y `asiento.lleva_centro` están en la
superficie congelada, y las cuatro reciben la configuración **ya aplicada** —plana, con la sección de su sistema
fundida en la raíz—. La forma en que se guarda es otra, anidada por sistema, y es la única que daba
`configuracion_por_defecto`. Pasarles la guardada **no falla**: devuelve vacío. Un `sub_diario` en blanco y una sigla
en blanco, que es peor que un error, porque el pre-vuelo le dice al contador que le falta algo que sí tiene.

**Exportar no la necesita y no cambia**: ahí se sigue entregando la configuración como se guarda y el motor la aplica
por dentro. Esto es para quien hace su propio pre-vuelo —decir qué falta ANTES de generar el archivo, o pintar una
pantalla con lo que está configurado—, que es lo que hace cualquier ERP con una pantalla de revisión delante.

La imputación llega como en cualquier operación, en el bloque `imputaciones` del documento o por el argumento, nunca
las dos, y con las mismas comprobaciones. **Una imputación exige el documento**: sin los comprobantes no hay contra
qué casar las llaves, y aceptarla a ciegas devolvería el agujero que esas comprobaciones existen para tapar.

**No sale por HTTP ni por MCP, y es una decisión, no un olvido** (`api/tabla.py`): solo le sirve a quien puede llamar
a las funciones que la consumen, y esas son de la librería. Por esas dos puertas la misma pregunta ya tiene una
respuesta mejor —`diagnosticar`, que dice qué falta y a quién pedírselo— sin que nadie tenga que interpretar una
configuración.

Sube a **1.2.0** y no a 1.1.1 porque un nombre público nuevo es una funcionalidad, no un arreglo. Nada más cambia: la
superficie congelada gana una línea y ninguna firma se toca.

## [1.1.0] — 2026-09-19

**El estándar de datos llega a `open-accounting` 1.0**, su primera versión estable, y con ella un compromiso: nada de
lo que existe se quita ni cambia de significado hasta una 2.0. Lo que hace sostenible esa promesa entra en esta misma
versión — los catálogos, que crecen sin tocar el esquema, y las enmiendas, donde cada cambio queda con su
compatibilidad y su test.

Tres cosas cambian en el documento. **La imputación viaja dentro**, así que un archivo guardado explica su propio
asiento. **Cada línea del asiento lleva su `clase`** —derivada del primer dígito de la cuenta, no del rol—, así que una
línea suelta se entiende sin mirar de qué libro salió. Y **`rol` y `libro.tipo` salen del esquema a catálogos
publicados**, así que el día que entre un hecho nuevo sus valores no cuesten otra versión.

La librería sube a **1.1.0** en la misma tanda, y no por conveniencia: `"1.0"` es prefijo de `"1.0.0"`, y ahí es donde
los dos relojes se confunden. Ahora un test lo prohíbe.

**El motor no acepta documentos de la 0.3**: nadie de fuera los escribía todavía, así que se hizo la limpieza en vez de
cargar con dos caminos en el lector. El Excel de CONCAR validado no cambia ni una celda, y **ninguna huella emitida se
mueve**.


### Añadido
- **La batería de conformidad del estándar** (`estandar/conformidad/`, hito E2), para que un tercero compruebe que lo
  que produce es correcto **sin escribirle a nadie**. Dos juegos: los casos de esquema, con la forma de la *JSON Schema
  Test Suite* (`{description, data, valid}`), que se corren con cualquier validador de draft 2020-12 y **sin el
  motor**; y los casos de `diagnosticar`, con su documento, su destino y lo que se espera. **Los corre la batería de
  aquí**: si el motor no pasa su propia conformidad, no la pasa nadie. Casi todos los casos salen de algo que se
  equivocó de verdad al escribir esta versión.
- **`clase` en cada línea del asiento** —`activo`, `pasivo`, `patrimonio`, `ingreso`, `gasto`—, **obligatoria** desde
  `open-accounting` 1.0. Es lo único que un ERP de fuera entiende sin conocer el PCGE: hasta ahora los roles
  `principal` y `tercero` solo significaban algo mirando `libro.tipo` —en una compra `principal` es el gasto y en una
  venta el ingreso—, y la línea que recibe un sistema de fuera es justo eso, una línea suelta. Son los cinco valores
  idénticos en QuickBooks, Xero, Merge y Rutter.
- **La clase sale del primer dígito de la cuenta**, que es el elemento del PCGE (`contaperu/pcge/clases.py`): 1, 2 y 3
  son `activo`; el 4, `pasivo`; el 5, `patrimonio`; el 6 y el **9** —quien imputa por destino y no por naturaleza—,
  `gasto`; el 7, `ingreso`. **No sale del rol**, y el caso que lo prueba es diario: una compra de mercadería imputada
  a `201101` tiene `rol: principal` y es un **activo**; deducirla del rol daría `gasto` en miles de facturas al mes.
  Consecuencia: el IGV (`401111`, elemento 4) es `pasivo`, y con `debe_haber: D` la línea dice exactamente lo que pasa
  —reduce un tributo por pagar, que es el crédito fiscal—; llamarlo `activo` al debe afirmaría otra cosa.
- **Los elementos 8 y 0 no tienen clase, y no se fuerzan**: son de cierre y de control. Una imputación a una de esas
  cuentas no genera asiento y se dice con su motivo (`sin_clase` en la tabla de faltas, que se le pide al contador
  porque es quien eligió la cuenta). Las cinco clases siguen siendo cinco, que es lo que las hace universales.
  **Se miran TODAS las cuentas del asiento**, no solo la de la base: la del tercero, la del IGV, la de la retención y
  la de la detracción vienen de la imputación y de la configuración, y con solo la base el diagnóstico decía
  `listo_para_exportar: true` mientras el archivo que salía llevaba una línea **sin `clase`** —un documento que el
  propio esquema del estándar rechaza, y sin un aviso—. Lo enumera `resolucion.cuentas_del_asiento`, un test lo ata a
  las líneas que arma el motor de verdad, y la fábrica de líneas se planta si alguna vez se separan.
- **El lector de una línea exige la `clase` y la comprueba contra su cuenta** (`asiento.LineaDiario.de_dict`). Sin eso
  el motor era más laxo que el esquema que publica —que la pide en `required`—, y sobre todo: que la clase pueda quedar
  **fuera de la huella** se sostiene en que no puede contradecir a su cuenta, que sí entra. También en el esquema, la
  `clase` pide `minLength: 1`: `required` sola no atrapaba la clase vacía, porque el texto vacío es un texto. Y una
  equivalencia del PCGE no puede llevar a una cuenta sin clase (`pcge.cargar_equivalencias`), que era el único sitio
  desde donde podía salir una línea con la clase contradiciendo a su cuenta.
- **El CSV gana dos columnas al final**, `clase` y `doc_id_externo`, sin mover las de siempre. **Cambia los bytes de
  esa salida**; el Excel de CONCAR y el registro de CONTASIS no cambian ni una celda.
- **La imputación viaja DENTRO del documento** (decisión de John del 18-sep-2026), en el bloque `imputaciones` de la
  raíz del estándar, llaveado por el `id_externo` de cada comprobante: un archivo guardado explica su propio asiento,
  que antes no podía porque las cuentas llegaban solo como argumento de la llamada. **El argumento `imputacion` sigue
  valiendo** para quien ya integraba así, y **las dos formas a la vez se rechazan**: adivinar cuál manda sería elegir
  en silencio la cuenta de un comprobante. Un test comprueba que las dos vías dan exactamente lo mismo por `revisar`,
  `diagnosticar`, `generar_asiento` y `exportar`, porque una vía que ignorara el bloque contabilizaría con la cuenta
  por defecto sin decir nada.
- **`id_externo` obligatorio cuando el documento trae `imputaciones`**, con un condicional en el esquema: sin la llave
  no hay con qué casar la decisión. Un documento sin imputaciones no lo pide, así que nada de lo que ya valía deja de
  valer. Y el motor añade lo que el esquema no puede expresar: **ningún `id_externo` repetido**. Las dos
  comprobaciones valen solo por la vía del documento; por el argumento se puede seguir imputando 3 de 10 comprobantes
  con los otros 7 sin id, y esa es la única asimetría entre las dos vías.
- **`documento.id_externo` en cada línea del asiento**: el id con el que el sistema que **produjo** el comprobante lo
  conoce, para que la línea enlace con su comprobante y su imputación sin depender de la serie y el número, que son
  la identidad tributaria y no la del sistema. Es el papel que cumplen `SourceID` en Xero y `SourceDocumentID` en
  SAF-T. No confundirlo con `id_en_destino`, reservado para el id que le pone el sistema que **recibe** el asiento
  ([enmienda 0001](estandar/enmiendas/0001-id-en-destino.md)).
- **Las enmiendas del estándar** (`estandar/enmiendas/`, hito E1): una por cambio, con su estado, su compatibilidad,
  su caso real, su fuente y el test que la sostiene. Entran los siete nombres que estaban reservados en el LEEME, y
  el primero ya renombrado — `linea.id_externo` pasa a **`linea.id_en_destino`** antes de existir, para que no se
  confunda con el campo nuevo de la línea. `tests/test_enmiendas.py` hace cumplir el criterio de salida del hito:
  cada reservado tiene su enmienda y una enmienda `final` cita un test que existe.
- **La gobernanza de los catálogos**, en `estandar/LEEME.md`: quién aprueba un valor nuevo, cómo se propone, qué se
  responde, y que un valor publicado no se quita ni cambia de significado. Con lo que **no** se gobierna dicho
  también: los catálogos de SUNAT se copian de la norma.

### Cambiado
- **Cambio de comportamiento: una llave de imputación que nombra a dos comprobantes se rechaza también cuando la
  imputación llega por el argumento.** Hasta ahora eso pasaba en silencio y la misma cuenta se aplicaba a los dos, con
  las dos líneas llevando un `documento.id_externo` que no dice de cuál vienen. Se cierra ahora porque el `id_externo`
  pasa a ser el enlace oficial entre la línea, el comprobante y su imputación. El alcance no es el mismo por las dos
  vías, y es a propósito: en el documento no puede repetirse ningún id —lo pide el condicional del esquema—, y por el
  argumento solo los que la imputación nombra, porque ahí se sigue pudiendo imputar 3 de 10.
- **`rol` y `libro.tipo` salen del esquema a catálogos publicados** (`estandar/catalogos.json`, junto al esquema y
  citable por la URL del tag del estándar), con `clases` al lado. Vivían como enums cerrados **y repetidos** —`ROLES`
  en `asiento/motor.py` y `TIPOS_LIBRO` en `modelo.py`—, sin ningún test que comparara las copias; ahora hay una sola
  fuente (`contaperu/vocabulario.py`) y un test que la ata al código y al esquema. **Los valores no cambian:** los seis
  roles son los de compras y ventas, y abrir el catálogo es para que un hecho nuevo traiga los suyos sin subir la
  versión, no para que estos crezcan. Se sirven en `api.catalogos_del_estandar()`, en `GET /v1/catalogos/estandar` y en
  el recurso MCP `contaperu://catalogos/estandar`, aparte de los de SUNAT, que se copian de la norma y no se gobiernan.
- **Un `libro.tipo` fuera del catálogo lo rechaza el modelo, no el esquema.** El rechazo no desaparece: cambia de
  sitio, porque el esquema ya no enumera. Y es a propósito que `libro.tipo` **no** degrade como el `rol`: quien recibe
  un registro que no conoce no puede adivinar qué hacer con él, así que quien degrada es el destino — el driver que no
  lo declara en sus `FORMATOS` lo rechaza limpio.
- **`_datos.del_estandar(ruta)`**: la doble búsqueda de un archivo del estándar —dentro del paquete instalado o en la
  raíz del repositorio— estaba escrita solo para el esquema. Ahora está una vez, y un archivo nuevo en `estandar/`
  necesita su línea de `force-include` y nada más.
- **`pcge.adaptar` re-deriva la clase al reescribir una cuenta.** Antes solo cambiaba el número, así que un mapeo que
  cruzara de elemento dejaba la línea con una clase que su cuenta contradice — justo lo que el motor promete rechazar,
  y lo que sostiene que la clase quede fuera de la huella.
- **La vuelta desde el Excel de CONCAR también deriva la clase** (`drivers/concar/desde_fila`): CONCAR no lleva una
  columna de clase —no le hace falta, su plan de cuentas vive en su sistema—, así que al volver a línea neutral se
  deriva de la cuenta. Sin eso, un documento reconstruido desde un archivo importado no validaría.
- **El driver neutral se llama `asiento_neutral`** (antes `open_accounting`, que era el nombre del estándar y hacía
  tropezar: uno es el formato que entra y el otro una de las salidas). Cambian el valor de `driver`, el formato
  `asiento_neutral_json` y el nombre del archivo que produce. Nada publicado llevó el nombre viejo. **La clave
  `open_accounting` del documento no cambia.**
- **La huella del asiento deja fuera `clase` y `documento.id_externo`**, además del `correlativo` que ya excluía, y
  `SIN` pasa a admitir rutas con punto para alcanzar un campo de un bloque. **Ninguna huella emitida cambia**: los
  tres campos quedan fuera precisamente porque no cambian el contenido contable, y `tests/test_huella.py` sigue
  fijando los mismos valores literales. El `id_externo` es el caso que la huella existe para atajar — al reexportar
  tras un «deshacer» la aplicación recrea sus filas con ids nuevos, así que con el id dentro el aviso de lote
  repetido se apagaría justo cuando hace falta.
- **La tabla de detracciones vive en el motor** (`contaperu/datos/sunat/detracciones.json`, decisión de John del
  15-sep-2026): el código, el nombre y la tasa de cada detracción, con su fuente, iguales para todos. El ERP que integra
  el motor la sobreescribe en lo general de su configuración: `detraccion_tasas` cambia una tasa o suma un código
  (`null`: se reconoce sin tasa), y `detraccion_nombres` cambia el nombre de uno que ya está. Por eso las dos claves
  **vienen vacías** en `configuracion_por_defecto()`, y una configuración guardada con los 14 códigos de la 1.0 da
  exactamente lo mismo. Lo que ya no se puede es **reconocer menos códigos** que la tabla quitándolos de la
  configuración: sobreescribir cambia o suma, no quita. `detraccion_codigos`, el código interno de cada sistema, sigue
  en la sección de ese sistema.
- **`exportar` y `generar_asiento` dejan en blanco la detracción que la tabla no reconoce**, como ya hacían `revisar` y
  `diagnosticar`: un mismo documento da la misma respuesta por cualquier operación. Una factura con un código que no
  está en la tabla va al sub-diario de compras y no al de detracciones: en el Excel de CONCAR, el caso
  `detraccion_codigo_sin_tasa` (código 031) pasa del 10 al 11 por el camino de exportar. La vista previa de
  `filas_de_comprobante` y su snapshot no cambian.
- **`diagnosticar` escribe el serie-número como la línea del asiento de ese destino** (`asiento.serie_numero_de`): el
  número sin ceros a la izquierda cuando el destino los quita, así un comprobante se nombra igual en el diagnóstico y en
  el archivo. Cierra el punto «a confirmar» del hito 0.8.

### Añadido
- `detracciones.tabla_del_motor()` y `detracciones.tabla_de_detracciones(config)`. `api.catalogos_sunat()` lleva
  `detracciones`, la tabla del motor con su fuente, para que una pantalla nombre cada código aunque el ERP no
  sobreescriba nada (también en `contaperu://catalogos/sunat` y `GET /v1/catalogos/sunat`).
- `asiento.serie_numero_de(comprobante, opciones)`.
- **Los tres grupos de destinos del motor en el código**: `drivers.contrato.GRUPOS` y `grupo(modulo)` presentan cada
  canal como **SIRE** (`tributario`), **Legacy** (`legacy`) o **ERP** (`intercambio`), y `drivers_disponibles` suma
  `grupo` a cada driver (también en `contaperu://drivers` y `GET /v1/drivers`). Los canales no cambian: siguen siendo la
  regla del contrato.
- **`contaperu verificar-driver mi_paquete.mi_driver`** y `api.verificar_driver`: un driver propio contra el contrato
  antes de registrarlo, con su forma, su canal, su grupo, lo que le falta y los avisos con que el registro lo aceptaría
  en la 1.x. Sale con 0 si cumple, 1 si le falta algo y 2 si no se puede importar. Importa código por su nombre, así
  que no está en la tabla de operaciones: nunca se expone por HTTP ni por MCP.
- **El driver `asiento_neutral`, la salida para los ERP que vienen**: el documento del estándar con su asiento **sin
  vocabulario legacy** —sin sub-diario ni correlativo, sin la sigla del documento ni de su referencia, y con la
  detracción sobre el propio comprobante en vez del documento comodín `DR`/`9999999999`—, con el `rol` de cada línea y
  el código SUNAT. La contabilidad es la de CONCAR: las mismas cuentas, sentidos, importes y roles, en el mismo orden
  (`tests/test_driver_asiento_neutral.py`). Un tipo sin sigla no lo detiene y `diagnosticar` no le mira vocabulario
  legacy. Lo hace posible el atributo nuevo del contrato **`VOCABULARIO`** (`legacy` por defecto, o `neutral`), que
  `drivers_disponibles` también dice; un driver neutral es de canal `intercambio`, no declara claves legacy y el
  núcleo solo le exige la cuenta. `asiento.lineas_del_comprobante` y `lineas_e_indice_del_libro` aceptan
  `vocabulario`. CONCAR, CONTASIS, el CSV y sus snapshots no cambian.
- **Drivers declarativos para formatos simples** (`drivers.kit.columnas`): un CSV o un TXT de columnas se describe como
  una tabla de `ColumnaDeLinea` —cabecera, campo de la línea neutral que la llena y su **fuente**, obligatoria— en
  `COLUMNAS_DE_LINEA`, y `escribir_csv` lo escribe, sin código de proyección. El contrato examina la tabla. El driver
  CSV de serie pasa a estar escrito así y sale byte a byte igual; su `COLUMNAS` de pares (ruta, cabecera) se conserva
  para quien lo lea. Declarar el largo de una columna y negarse con `no_caben` queda para cuando un formato real lo
  pida: los largos se miden en la línea, y `no_caben` recibe los comprobantes.
- **Los catálogos de SUNAT viven en datos, con su fuente** (`contaperu/datos/sunat/catalogos.json`, primer paso del
  hito C1): los tipos de comprobante, los documentos de identidad y las monedas dejan de estar escritos a mano en
  `catalogos.py`, que los lee con los mismos nombres, tipos y valores (un test congela los de la 1.0). `catalogos.FUENTES`
  y `api.catalogos_sunat()["fuentes"]` dicen de dónde sale cada uno. Los códigos de retorno y las reglas de validación
  de SUNAT esperan su hoja oficial, y el código SUNAT en cada observación (C2), las enmiendas del estándar (E1).

## [1.0.0] — 2026-09-14

**La 1.0.0**, probada antes como la candidata **1.0.0rc1**. La 1.0 fija una API pública estable (`contaperu.api`) y deja las rutas de la 0.10 funcionando con aviso de obsoleto durante toda la 1.x; ordena el motor en capas que un test hace cumplir, con una sola preparación para diagnosticar, generar el asiento y exportar; separa la salida hacia los sistemas legacy (drivers por canal) de la puerta de entrada para ERPs nuevos (servidor HTTP y contrato OpenConta); y cumple la Fase 0 de la hoja de ruta. El Excel de CONCAR validado no cambia. El detalle de cada cambio entra aquí con su commit.

### Añadido
- **`ErrorContaperu`** (`contaperu.errores`): la base común de todas las excepciones del motor, con una `clave` estable
  por clase («sin_cuenta», «configuracion_invalida», «xml_invalido»). Las excepciones de siempre conservan sus bases:
  atraparlas como en la 0.10 sigue funcionando.
- **`RutaObsoleta`**: el aviso con que las rutas de la 0.10 que cambian de sitio dicen qué usar. Avisa al usar la ruta,
  no al importar el módulo, y se silencia con `warnings.filterwarnings("ignore", category=contaperu.RutaObsoleta)`.
- `Libro.a_dict` y `Libro.de_dict`, `LineaDiario.de_dict` (rechaza claves ajenas y un sentido que no es D ni H),
  `modelo.numero_sin_ceros`, `asiento.numerar_en_orden` (el número de cada comprobante en su posición, sin depender del
  `id()` de los objetos), `comparar_sire.leer_bytes` y `pcge.adaptar(lineas, datos=...)`.
- `modelo.identidad_de`: la identidad estable del comprobante del hito 0.0 (RUC y tipo del libro, tipo, serie y número
  sin ceros; en compras, el proveedor). Todavía no la usa ninguna salida.
- Una red de seguridad de tests antes de mover nada: la superficie pública de la 0.10 congelada, lo que usa
  `contab-core`, la respuesta de la fachada por documento y destino, el Excel de CONCAR por el camino de producción
  caso a caso y la forma de las hojas de Excel.
- `tests/test_capas.py`: cada módulo pertenece a una capa y solo importa de las de abajo; el núcleo y los drivers no
  abren archivos (hito 0.5); el acoplamiento con lo peruano queda congelado y visible (hito J0).

- **`contaperu.api`**, la API pública de la 1.0: `leer_xml`, `leer_propuesta_sire`, `leer_archivos`, `documento_de`,
  `revisar`, `normalizar_detracciones`, `diagnosticar`, `generar_asiento`, `exportar`, `exportar_archivo` (el archivo
  en bytes, como `Exportado`), `cuadrar`, `buscar_cuenta_pcge`, `adaptar_pcge`, la configuración, los drivers y
  catálogos disponibles, el esquema del estándar, `comparar_sire` y todos los errores. **El documento va primero y lo
  demás por su nombre, y `driver` no tiene valor por defecto.** Su superficie queda congelada con su firma
  (`tests/test_superficie_publica.py`), junto con los nombres del nivel de extensión.
- `api.OPERACIONES`: cada operación con la ruta HTTP y el nombre del MCP por los que se expone. Es la fuente de las
  puertas; un test comprueba que el MCP expone exactamente esas herramientas y recursos.
- `api.problema(error)`: un error como «problem details» del RFC 9457, con su `clave`; lo que no es un error del motor no
  enseña su texto.
- `contaperu.pipeline` (interno): la preparación, la lectura, la selección, el armado del asiento, la salida y el
  diagnóstico, cada uno en su módulo y escritos una sola vez.
- `contaperu.puertas`: la CLI y el servidor MCP, que hablan solo con la api, y lo que comparten (topes y nombres de host
  permitidos). `test_capas` lo hace cumplir y la lista de excepciones queda vacía.

- **El canal de cada driver** (`CANAL`): a quién se entrega lo que sale. `legacy`, un sistema contable instalado que
  importa un archivo (CONCAR, CONTASIS); `tributario`, un registro que se presenta a SUNAT (el SIRE); `intercambio`, un
  formato neutral (el CSV). El contrato hace cumplir las reglas de cada uno y rechaza `api_erp`, reservado para escribir
  en la API de un ERP moderno (hito A5). `api.drivers_disponibles` y el recurso `contaperu://drivers` dicen el canal.
- **El índice del asiento** (`asiento.indice`, hito 0.4 en el motor): `asiento.lineas_e_indice_del_libro` devuelve,
  con las líneas, qué tramo es de qué comprobante y una `Cabecera` con sus hechos (identidad, contraparte, glosa,
  importes), fuera de las líneas y de la huella. Un driver `desde_lineas` que acepta `indice` lo recibe.
- `drivers.kit`: lo que comparten los drivers —`Opciones`, `OpcionesArchivo` para un driver de archivo nuevo, el formato
  de texto, las celdas y el libro de Excel—.
- `drivers.contrato.canal`, `declara_canal`, `acepta_indice`, `CANALES` y `CANALES_RESERVADOS`;
  `asiento.MONEDAS_CODIGO`, la única clave de la sección de un sistema que lee el núcleo, con nombre.
- Un driver de prueba de asientos por JSON (`tests/drivers_de_prueba/diario_json.py`), de canal `legacy`, con índice y
  `no_caben`: prueba que el contrato ya cubre lo que pedirá STARSOFT, sin publicar ningún driver.

- **`claves_previas` por las tres puertas** (hito 0.1): `api.revisar`, `diagnosticar`, `generar_asiento`, `exportar` y
  `exportar_archivo`, las herramientas del MCP y `--claves-previas` en `contaperu desde-json` y `diagnosticar`. Lo ya
  anotado en otros periodos del mismo RUC viaja como `[tipo_cp, serie, numero, contraparte_doc]`, se normaliza igual
  que la clave del comprobante («00000123» casa con «123») y lo que coincide sale con `DUPLICADO_PERIODO_ANTERIOR`,
  que se pide al contador. Tope: `api.MAXIMO_CLAVES_PREVIAS`, 50 000; por encima, `DocumentoInvalido`.
- **La identidad de un comprobante, escrita** (hito 0.0, `estandar/LEEME.md`): el RUC y el tipo del libro, más el
  tipo, la serie y el número sin ceros; en compras, el documento del proveedor; en ventas, no el del cliente; nunca el
  periodo.

- **Cada comprobante en la respuesta** (hito 0.4): `_asiento.comprobantes` y `_exportacion.comprobantes` dicen de
  cada uno su identidad, el tramo `[desde, hasta)` de las líneas del asiento que le toca y la huella de ese tramo. Los
  tramos son una partición exacta y cada uno cuadra; la huella de la tanda no cambia. En un registro (el SIRE,
  CONTASIS), solo la identidad. `Exportado.por_comprobante` lo lleva en Python.
- **`motor`** (hito B2): la versión de la librería que produjo la respuesta, en `_asiento` y `_exportacion`, fuera de
  toda huella.

- **Anotaciones MCP** (hito 0.2): las once herramientas se anuncian con `readOnlyHint: true` y `openWorldHint: false`,
  así un cliente puede llamarlas sin pedir confirmación por un efecto que no tienen.

- **OpenConta** (hito B3): el contrato de la puerta HTTP, en formato OpenAPI 3.1, generado desde `api.OPERACIONES` y
  versionado en `contaperu/api/openconta.json` (`api.contrato_openconta()`). Cada operación con su cuerpo, su salida y sus
  rechazos RFC 9457; los esquemas del estándar y de la api, en `components.schemas`; sin `servers`.
  `herramientas/generar_openconta.py` lo reescribe y, con `--comprobar`, falla si no está al día; un test exige que
  regenerarlo no cambie ni un byte, que las respuestas reales validen contra su salida y los documentos de ejemplo
  contra su entrada.
- **La tabla de operaciones declara su entrada y su salida** (hito B1): cada `Operacion` trae `entrada`, el JSON Schema
  2020-12 de sus parámetros sacado de su firma, y `esquema_de_salida`, con `$ref` al esquema del estándar. Los esquemas
  de las salidas viajan en `contaperu/api/esquemas/`.
- **El esquema de la respuesta de `diagnosticar`** (hito B2), también en la forma de una configuración que no se puede
  aplicar: `api.esquema_diagnostico()` y el recurso `contaperu://esquemas/diagnostico`. El SDK del MCP no deja
  declararlo como `outputSchema` de la herramienta sin cambiar lo que responde.

- **La puerta HTTP** (hito B4): `contaperu-http`, con el extra `contaperu[http]` (Starlette y uvicorn). Cada operación
  de `api.OPERACIONES` es una ruta —`POST /v1/exportar`, `GET /v1/drivers`…—, más `/salud` y `/openconta.json`, que
  sirve el contrato. Sin estado; comparte con el MCP la defensa del `Host` (421 a un nombre que no se declaró con
  `--dominio`) y los topes: el cuerpo se lee por trozos y se corta a 10 MiB (413), y el archivo que devuelve
  `exportar`, a 4 MiB. Los rechazos son RFC 9457: 400 cuerpo mal formado, 422 con la `clave` del error, 500 sin
  detalle. `puertas.servidor_http.crear_app` la da como aplicación ASGI. Las tres puertas dan el mismo documento y el
  mismo diagnóstico.

- **`INTEGRAR.md`** (hito B6): cómo integrar el motor en un ERP —qué puerta elegir, la librería, la CLI por lotes, HTTP
  con OpenConta, el MCP, un driver propio en sus dos niveles y lo que promete la 1.x—. Sus ejemplos se ejecutan en la
  batería (`tests/test_integrar.py`).
- CI: la batería también en Windows con Python 3.12; comprobar que OpenConta está al día; un trabajo que construye la
  rueda, la instala en un entorno limpio y arranca los tres comandos con sus datos empaquetados. Publicar una versión
  es empujar su tag: `release.yml` corre la batería en ese commit, comprueba que la etiqueta sea `v` más la versión del
  código y que el CHANGELOG la traiga fechada, pasa `twine check` y crea la Release de GitHub con la rueda, el sdist y
  `SHA256SUMS`. PyPI va aparte y a mano.

### Cambiado
- **Un ZIP ya no se descomprime sin tope.** `archivos.expandir` y la propuesta del SIRE dentro de su ZIP leen cada
  entrada con tres topes (`lectores/_zip.py`):
  - 64 MB por archivo descomprimido;
  - 128 MB por ZIP;
  - una proporción de compresión de 200 a 1.

  Lo que pasa de uno queda como error del lote, con su motivo, y el resto sigue; en la propuesta del SIRE es
  `SireInvalido`. Antes, un ZIP de unos kilobytes podía expandirse hasta agotar la memoria de quien lo abría.
- **La puerta HTTP limita sus conexiones.** Atiende a lo sumo 16 peticiones a la vez (503 si llegan más) y cierra a los
  5 segundos una conexión inactiva (`puertas/comun.py`). El tiempo para leer una petición lenta lo pone el proxy, como
  explica `INTEGRAR.md`.
- **Importar `contaperu` ya no carga todos sus submódulos**: cada uno se importa la primera vez que se pide, así que
  `import contaperu.modelo` no arrastra los drivers ni openpyxl. `from contaperu import asiento` funciona igual.
- El registro de drivers busca los de terceros la primera vez que alguien lo mira, no al importar el paquete.
- **El núcleo no abre archivos** (hito 0.5): el catálogo y la tabla del PCGE se leen como datos empaquetados
  (`contaperu/_datos.py`, con `importlib.resources`), y la CLI lee el disco antes de comparar con el SIRE.
- `igv` deja de importar la validación entera por una constante: la tolerancia vive en `catalogos.TOLERANCIA_IGV`
  (`validar.TOLERANCIA` e `igv.TOLERANCIA` siguen siendo el mismo valor).
- El asiento deja de depender de las opciones de los drivers: `lineas_del_comprobante` y `lineas_del_libro` leen
  `sin_ceros` de las opciones que lleguen, y sin opciones quitan los ceros como siempre.

- **La CLI habla solo con la api.** `contaperu desde-json` revisa siempre el documento, la imputación y cada comprobante
  —`--revisar` ahora solo enseña la tabla—, y un rechazo se imprime con el mensaje de la api. Un documento o una
  imputación que no se pueden usar responden con el código 2 y el motivo en una sola línea; en `contaperu generar`, un
  RUC o un periodo mal escritos también, en vez de un traceback.
- Los comandos `contaperu` y `contaperu-mcp` arrancan desde `contaperu.puertas`. Las herramientas y los recursos del MCP
  conservan sus nombres, sus argumentos y sus respuestas.
- `api.revisar` acepta la `imputacion` y comprueba que cada una hable de un documento que está.

- **CONCAR pasa a la forma `desde_lineas`** y la orquestación del asiento queda en un solo sitio, el pipeline. El
  Excel no cambia ni una celda: la glosa de la columna F y la tasa de la AO salen de la cabecera del comprobante, y la
  AO se sigue redondeando una sola vez desde su IGV y su base (IGV 175.00 sobre 1000.03 da 17, no 18). El resumen
  conserva sus claves y sus valores; el desborde de un sub-diario se detecta igual, antes de escribir.
- **`no_caben` detiene también a un driver `desde_lineas`**, antes de armar el asiento; hasta ahora solo lo hacía con
  la forma `desde_comprobantes`. Ningún driver de serie de asientos lo declara, así que sus salidas no cambian.
- Un driver de terceros sin `CANAL` se registra con un `AvisoDriver` y se trata como `legacy`; uno con la forma
  `construir` sigue exportando, con un `AvisoDriver`.
- CONTASIS y CONCAR escriben su Excel con el kit común. `drivers.csv.CANAL`, `drivers.sire.CANAL` y
  `drivers.sire.txt.columnas_igv_compras`, que vivía en `formato`.

- **En ventas, dos comprobantes con el mismo tipo, serie y número son el mismo aunque el cliente difiera**:
  `validar.revisar` los marca como duplicados, también contra las claves previas. Es la identidad del hito 0.0; en
  compras no cambia nada. `validar.marcar_duplicados` recibe `sin_contraparte` para decidirlo y por defecto hace lo de
  siempre.

- **`generar_asiento` exige lo del destino**: es `exportar` sin escribir el archivo. Deja fuera los excluidos, los
  duplicados y lo que ese destino no lleva, y se niega por lo que su driver exige —en CONCAR, el centro de costo donde
  la cuenta lo lleva y una moneda con código— y por lo que no cabe en su formato. Mirar sin exigir es `diagnosticar`, o
  `generar_asiento` hacia el CSV. El desborde de un sub-diario no se lanza: queda en `_asiento.sub_diarios`.

- **El tipo de cambio y la tasa de la detracción viajan como texto exacto en la línea neutral** (hito 0.6):
  `"3.550"` y `"4"` en vez de `3.55` y `4.0`, y `float` solo al escribir la celda. El Excel de CONCAR no cambia. Cambian,
  y es a propósito, la huella de las tandas en dólares o con detracción —una huella guardada con la 0.10 para esas
  tandas no coincide con la nueva; la de soles, sí— y cómo se escriben esas dos columnas en el CSV. El camino inverso
  (`drivers.concar.a_lineas`) también devuelve texto.

- **`diagnosticar` cuenta igual lo que saldría** (hito 0.8): `totales.saldrian` es el largo de la lista `saldrian`;
  hasta ahora contaba también los comprobantes que bloquean.
- **`diagnosticar` no suma soles con dólares** en `resumen_por_contraparte` (hito 0.8): cada contraparte trae
  `por_moneda`, con un total por moneda, y `total` y `moneda` son los de la primera moneda en que aparece. El
  serie-número sigue escribiéndose como en el documento, con sus ceros: igualarlo al de la línea queda por confirmar.

- **Un PDF o una foto enviados a `leer_xml` cuentan como pendientes de leer** (hito 0.7): `_lectura.pendientes_de_leer`
  sube en uno y no aparece un «XML inválido». El motor reconoce el PDF, el JPEG, el PNG y el WEBP por sus primeros
  bytes, porque lo que llega por un protocolo no trae nombre de archivo.

- **El CSV lleva tres columnas más al final** (B5): `rol`, `doc_tipo_cp` y `ref_tipo_cp`, lo que un driver necesita
  para traducir sin adivinar. Las columnas de siempre no se mueven.

- `estandar/LEEME.md`, «La detracción, que ocurre en dos tiempos» (hito 0.3): ya no dice que el asiento «puede
  regenerarse» con el número de la constancia. En un destino que suma lo importado, regenerarlo duplica; el segundo
  tiempo es una decisión contable que entrará con su fuente y un archivo real.

- **El TXT del SIRE no usa `assert`.** Una nota de crédito cuyo descuento cambiaría de signo el campo 15 o el 17 del
  RVIE se niega con `CampoCambiaDeSigno`, un `NoExportable` que trae la nota, en vez de un `AssertionError` que
  `python -O` se saltaba. Un test impide `assert` en todo el paquete.

- El extra `mcp` pide `mcp>=1.30`, la versión más antigua con la que se probó el servidor (el `>=1.2` de antes no
  tenía las anotaciones ni la defensa del Host que ya usaba). Un trabajo de CI, `minimos`, instala ese mínimo tal cual.

- La imagen de Docker instala también la puerta HTTP y expone el 8080; su `CMD` sigue siendo `contaperu-mcp`.

- **Versión 1.0.0** (antes, la candidata 1.0.0rc1) y `Development Status :: 5 - Production/Stable`. `README.md`, `ARQUITECTURA.md` (las capas, el
  pipeline, el contrato v1 con sus canales, «STARSOFT: qué se sabe y qué falta» y lo que queda preparado),
  `CONTRIBUTING.md`, `CLAUDE.md`, `SECURITY.md` (la política de la 1.x) y la hoja de ruta, con sus hitos cumplidos,
  describen la 1.0.

### Obsoleto
- `comparar_sire.leer(ruta)`, `pcge.cargar_equivalencias(ruta)` y `pcge.adaptar(lineas, ruta)`: siguen funcionando y
  avisan; se pasan los bytes o el diccionario. `asiento.motor.Opciones` y `asiento.motor.formatear_numero` siguen
  resolviendo desde ahí, con aviso.
- **`contaperu.operaciones`** (todo el módulo): sigue funcionando con las firmas y los valores por defecto de la 0.10 y
  avisa con la ruta nueva, `contaperu.api`. `contaperu.generar`: `api.exportar_archivo`, `api.Exportado` y
  `api.ErroresBloqueantes`. `contaperu.cli` y `contaperu.servidor_mcp`: `contaperu.puertas.cli` y
  `contaperu.puertas.servidor_mcp`. Son el mismo objeto por las dos rutas (`generar.Exportado is api.Exportado`).
- **`drivers.concar.construir`** (y `drivers.concar.xlsx.construir`): da las mismas celdas y el mismo resumen y avisa;
  el Excel de CONCAR se pide a `api.exportar_archivo`. **`contaperu.formato`** entero: `contaperu.drivers.kit`.
  La forma `construir` de un driver de terceros se retira en la 2.0.

### Cómo migrar desde la 0.10

Nada deja de funcionar: cada ruta de la 0.10 resuelve al mismo objeto, con su firma, y avisa con `RutaObsoleta` qué usar.
Para silenciar el aviso mientras se migra: `warnings.filterwarnings("ignore", category=contaperu.RutaObsoleta)`.

| En la 0.10 | En la 1.0 |
|---|---|
| `from contaperu import operaciones as op` | `from contaperu import api` |
| `op.exportar(doc, "concar", config, correlativos)` | `api.exportar(doc, driver="concar", configuracion=config, correlativos=correlativos)` |
| `op.generar_asiento(doc, config, None, False, imputacion, "csv")` | `api.generar_asiento(doc, driver="csv", configuracion=config, imputacion=imputacion)` |
| `op.diagnosticar(doc, config, driver="concar")` | `api.diagnosticar(doc, driver="concar", configuracion=config)` |
| `op.revisar(doc, config)` · `op.leer_xml(contenido, libro, True)` | `api.revisar(doc, configuracion=config)` · `api.leer_xml(contenido, libro, es_base64=True)` |
| `op.documento(libro, comprobantes)` | `api.documento_de(libro, comprobantes)` |
| `op.config_aplicada`, `op.con_imputacion`, `op.libro_de`, `op.comprobantes_de` | dentro de cada operación; el paso suelto está en `contaperu.pipeline.preparacion`, que es interno |
| `generar.generar(libro, comprobantes, "concar", config=..., correlativos=...)` | `api.exportar_archivo(documento, driver="concar", configuracion=...)` |
| `generar.Exportado`, `generar.ErroresBloqueantes`, `op.DocumentoInvalido` | `api.Exportado`, `api.ErroresBloqueantes`, `api.DocumentoInvalido` |
| `drivers.concar.construir(...)` | `api.exportar_archivo`; un driver nuevo, `desde_lineas` |
| `from contaperu.formato import Opciones` | `from contaperu.drivers.kit import Opciones` |
| `contaperu.cli`, `contaperu.servidor_mcp` | `contaperu.puertas.cli`, `contaperu.puertas.servidor_mcp`; los comandos no cambian |
| `comparar_sire.leer(ruta)` · `pcge.cargar_equivalencias(ruta)` | `comparar_sire.leer_bytes(datos)` · `pcge.cargar_equivalencias(datos)` |

No cambian de sitio ni avisan: `asiento.*`, `drivers.concar.filas_de_comprobante`, `igv.aplicar_igv`,
`igv.aplicar_total`, `detracciones.normalizar`, `detracciones.monto_detraccion`, `validar.marcar_duplicados`,
`validar.revisar` y `modelo.clave_de`. El `resumen` de cada exportación conserva sus claves.

Lo que sí cambia de comportamiento está arriba en negrita. Lo que no se aplicó y queda por decidir: descartar al
exportar las detracciones que la tabla del contribuyente no reconoce (movería de sub-diario una factura y cambiaría el
Excel de CONCAR validado), e igualar el serie-número de `diagnosticar` al de la línea.

## [0.10.0] — 2026-09-13

**CONTASIS entra como driver de serie**, con lo que hizo falta para que un segundo sistema contable salga del mismo
documento que CONCAR. CONTASIS importa su registro de compras y de ventas —una fila por comprobante, con la cuenta
de la base y la del total— y arma el asiento él mismo: cada columna sale de la misma función del núcleo que usa el
asiento de CONCAR, y ningún driver decide una cuenta.

**El documento lleva los hechos; las cuentas llegan aparte.** Decisión de John (12-sep-2026) al integrar CONTASIS:
el JSON universal `open-accounting` es el riel que recibe cualquier input, y las cuentas contables viven en la
aplicación —en la configuración de cada entorno y en lo que el contador decide en su Revisión—. El motor recibe
tres piezas: el documento, la imputación de cada documento y la configuración. **El Excel de CONCAR no cambia**:
los casos de `tests/test_snapshot_concar.py` salen idénticos celda a celda. El estándar pasa a la `0.3` y se llama
`open-accounting`.

**La configuración se declara, va por secciones y la valida el motor.** Decisión de John (13-sep-2026): el dato se
guarda una vez, la contabilidad general también, y lo propio de cada sistema contable —sus códigos y en qué columnas
de su archivo va cada dato— vive en su sección: `{"cuentas": …, "concar": {"tipos": …, "columnas": …}, "contasis":
{"medio_pago": …}}`. El motor es de cualquier aplicación que se construya encima: cada driver declara lo que se
configura en su sección, el motor lo valida antes de generar y se lo describe a quien pinte la pantalla.

### Añadido
- **El driver `contasis`** (`drivers/contasis/`): el Excel de «FORMATO REGISTRO DE COMPRAS» y «FORMATO REGISTRO DE
  VENTAS» del Sistema Experto Contable 26.00 (NewContaSis), con sus 50 y 44 columnas transcritas de la plantilla
  oficial, sin sus filas de notas y con su pestaña. Las reglas de formato las revisó John contra un registro que
  CONTASIS importó (12-sep-2026):
  - textos rellenos con espacios hasta su largo, la serie tal como la trae el comprobante y el número sin ceros a
    la izquierda;
  - importes en soles: en dólares, cada columna × T.C. y el total en «equivalente en dólares»;
  - la nota de crédito en negativo, el % IGV legal y la glosa cortada a 60;
  - la boleta de compras, entera en no gravadas, y la detracción vacía;
  - el recibo por honorarios queda fuera del archivo (`EXCLUYE_TIPOS`);
  - una cuenta por documento (`cuenta_unica`), el medio de pago del entorno y las cuentas de otros tributos e ICBPER,
    que se configuran como el resto: su sección declara `medio_pago` (`001`), y lo general, `cuentas.otros_tributos` y
    `cuentas.icbper` (vacías);
  - el centro de costo también en su segunda columna de centro de costos, si su sección la elige (`columnas`);
  - anchos de columna para que el archivo se lea al abrirlo: los de la plantilla, los que ensanchó John al revisar
    el primer archivo generado, y ninguna fecha por debajo de lo que la deja ver.

  Lo que no cabe —otra moneda, dólares sin T.C., un rango de boletas, IVAP, un código más largo que su columna— lo
  dice `no_caben`. `tests/test_snapshot_contasis.py` congela las filas celda a celda, y
  `tests/test_plantilla_contasis.py` compara columnas y celdas con la plantilla y el registro validado cuando están
  en `tests/fixtures/privado/contasis/` (fuera de Git).

  Su formato es `contasis_xlsx`, en compras y en ventas (`FORMATOS`). **Aceptado el 13-sep-2026:** CONTASIS importó
  los dos Excel que genera el driver, el registro de compras y el de ventas de un mes real, con los anchos ya
  fijados. Los del 12-sep-2026 eran registros que CONTASIS ya había importado; estos los generó el driver.
- **`condicion_pago`** (`contado` | `credito`) en el comprobante: lo que declara el documento sobre su pago. En la
  factura electrónica es obligatorio (`PaymentTerms FormaPago`), y el lector de XML ya lo leía y lo dejaba en
  `datos_raw.forma_pago`; ahora es campo, y una factura con cuotas es a crédito. Vacío no es contado: es que el
  documento no lo dice. «Crédito» o «CONTADO» se normalizan; otro valor se rechaza.
- **`id_externo`** en el comprobante (era un nombre reservado): el id con el que la aplicación conoce el
  documento, y la llave de su imputación.
- **La imputación** (`asiento.Imputacion`): la cuenta, el centro de costo, la cuenta del total y el **reparto** de
  un documento, que llegan aparte y por `id_externo`: en la fachada, el argumento `imputacion` de `exportar`,
  `diagnosticar` y `generar_asiento`. En la configuración guardada, `imputaciones` es un error; la fachada se la
  entrega al núcleo dentro de la configuración aplicada (`operaciones.con_imputacion`). El
  reparto divide solo la base —el caso: una factura con una parte de sistemas y otra de
  desarrollo; la plantilla de CONTASIS admite varias filas por documento—, y el asiento lleva una línea de gasto o
  ingreso por parte. Un reparto con cuenta o centro al lado, o la imputación de un `id_externo` que no está, se
  rechazan en la puerta.
- **`reparto_que_no_cuadra`** (en `diagnosticar` y `faltantes_para`) y **`asiento.RepartoNoCuadra`**: las partes
  suman la base del asiento, sin tolerancia; si no, el mes no está listo y `lineas_del_comprobante` no arma ese
  asiento.
- **`asiento.partes_de` y `asiento.cuenta_tercero`**: resuelven la cuenta de la base y la del total una sola vez
  para todos los drivers. La del total vivía dentro de `lineas_del_comprobante`; se sacó primero sin cambiar nada.
- **`igv.base_imputable` e `igv.igv_del_asiento`**: la regla de que en compras la boleta y el recibo por
  honorarios no dan crédito fiscal salió de `lineas_del_comprobante`, porque la comprobación del reparto la necesita
  igual.
- `estandar/LEEME.md`: **documento, imputación y configuración**, con la forma de la imputación, y **las dos
  familias de salida** (registro y asiento). Y los nombres reservados que pide CONTASIS: `medio_pago`,
  `retencion_igv`, `percepcion` y `no_domiciliado`.
- **La familia registro en el contrato de drivers: la forma `desde_comprobantes(libro, comprobantes, config,
  opciones)`**, para un sistema contable que importa su registro de compras o de ventas y arma el asiento él mismo
  (CONTASIS). El driver recibe los comprobantes y la configuración, con la imputación dentro,
  y lee cada cuenta de `asiento.partes_de` y `asiento.cuenta_tercero`: no decide ninguna. El núcleo no le arma
  asiento ni le numera nada, y le exige la cuenta antes de llamarlo (`contrato.EXIGE_NUCLEO_REGISTRO`); puede
  exigir además el centro de costo (`EXIGE_POSIBLES_REGISTRO`). La equivalencia del tipo y el código de la
  moneda son de la configuración del asiento y no le aplican. `diagnosticar` le cuenta la cuenta, el reparto y
  el centro, sin sub-diarios.
- **`contrato.familia(modulo)`** (`registro` | `asiento`) y **`contrato.lleva_cuentas(modulo)`**: la configuración
  la pide todo driver que lleva cuentas; los correlativos, solo el que arma asientos (`arma_asientos`). El recurso `contaperu://drivers` del MCP dice la familia de cada driver.
- **`igv.por_destino`**: la base y el IGV de una compra en las tres parejas del destino de la adquisición (DG,
  DGNG, DNG). Vivía dentro de `formato.columnas_igv_compras`, la del SIRE, y la plantilla de importación de
  CONTASIS lleva las mismas seis columnas (J–O): la regla no puede vivir dos veces. El TXT del SIRE no cambia.
- **La imputación entra por las dos puertas**: `--imputacion` en `contaperu desde-json` y en `contaperu
  diagnosticar`, y el argumento `imputacion` en las herramientas `generar_asiento`, `diagnosticar` y `exportar`
  del MCP. `operaciones.con_imputacion` es pública: la CLI escribe bytes y llama al núcleo sin pasar por
  `exportar`.
- **`igv.tasa_legal`**: la tasa legal del IGV que cuadra con la base y el IGV (la general o una reducida del
  catálogo), con la tolerancia de `validar`; si ninguna cuadra, la del cociente a 2 decimales. Es la que pide un
  registro («Porcentaje I.G.V. — Ejemplo: 18.00», plantilla de CONTASIS): el registro que CONTASIS validó escribe
  18 aunque base e IGV, redondeados ítem a ítem, den 17.98. `igv.tasa_calculada` no cambia, ni la tasa entera de CONCAR.
- **`cuenta_unica`**, un requisito que puede declarar un driver de registro: su destino lleva una cuenta por
  documento y no admite un reparto de la base (CONTASIS arma un asiento por fila, John 12-sep-2026).
  `diagnosticar` lo dice como `reparto_no_admitido` —a quién pedirlo: al contador— y el núcleo se niega con
  `asiento.RepartoNoAdmitido`. A quien no lo declara no le aparece.
- **`no_caben(libro, comprobantes, config)`**, opcional en el contrato de drivers: lo que un formato no puede
  llevar aunque la contabilidad esté completa (una moneda que no tiene, un código más largo que su columna).
  `diagnosticar` lo lista en `faltantes.no_cabe`, por motivo, y deja el mes «no listo»; el núcleo se niega con
  `drivers.contrato.NoCabe` antes de llamar a un driver `desde_comprobantes`, y la CLI lo dice sin traceback.
- **`asiento.FALTAS`**, la única tabla de lo que impide exportar (clave, requisito, excepción, texto, a quién pedirla
  y título de la CLI), y **`asiento.NoExportable`**, la base de sus excepciones y de `contrato.NoCabe` y
  `concar.CorrelativoDesborda`: quien exporta atrapa una sola y lee su `clave`, la de su fila de `FALTAS` o la propia
  de un driver (`CorrelativoDesborda` lleva `sub_diario_desborda`: un sub-diario que pasaría de 9999).
  **`asiento.correlativos_de_partida`**, el correlativo de partida de cada sub-diario. Y en `modelo`, **`CENTIMO`**,
  **`a_decimal`**, **`texto_tasa`** y **`serie_y_numero`**: cada uno es la única copia de lo que se repetía.
- **La configuración declarada** (`contaperu/configuracion.py`): `Campo` (clave, tipo, valor por defecto, patrón,
  título, ayuda) y `Columna` (en qué columna de un archivo puede ir un dato, con su letra en compras y ventas, fija o
  marcada), con `validar`, `por_defecto`, `describir` y `ConfiguracionInvalida`, que trae todos los errores con su
  ruta. Se declara en tres sitios: lo general en `CONFIGURACION_GENERAL`, lo que lee el asiento en
  `asiento.CONFIGURACION_DEL_ASIENTO` y lo propio de cada sistema en su driver (`CONFIGURACION` y
  `COLUMNAS_ELEGIBLES`). El contrato gana `configuracion`, `columnas_elegibles`, `seccion_por_defecto`, `describir`,
  `centro_en_anexo` y `DATOS_CON_COLUMNAS`, e `incumplimientos` examina lo declarado.
- **`columnas`: en qué columnas va el centro de costo**, elegidas en la sección de cada sistema. En CONCAR, la M,
  fija; la X de la línea del gasto como referencia, y la X del tercero, marcada de fábrica. En CONTASIS, su columna de
  centro de costos, fija, y la segunda. Una aplicación guarda el centro una vez y elige dónde sale.
- **En la fachada:** `operaciones.errores_de_configuracion`, `configuracion_por_defecto` (la forma guardada, con los
  valores por defecto de cada sección) y `describir_configuracion` (lo que se configura, para pintar una pantalla).
  `diagnosticar` dice `errores_de_configuracion` y el motivo `configuracion_invalida` en vez de lanzar, y
  `generar_asiento` recibe `driver`.
- **En las puertas:** el recurso `contaperu://configuracion` y la clave `configurable` en `contaperu://drivers` del
  MCP, el `driver` de su `generar_asiento`, y `contaperu configuracion [--driver] [--por-defecto]` en la CLI.
- **Los vigilantes de la configuración:** una configuración espía comprueba, por driver, que lo que se lee está
  declarado y lo declarado se lee; dos pruebas leen el código para que ni un driver ni el núcleo pidan por su nombre
  una clave que no les toca; y `test_frontera` comprueba que el motor no nombra ninguna aplicación.

### Cambiado (rompe)
Sin alias ni compatibilidad hacia atrás (John, 12-sep-2026: era el momento de rebajar la deuda de nombres, con la
arquitectura recién cambiada y contab-core sin usuarios activos, que se ajusta a la vez). Los tres snapshots
—el Excel de CONCAR, el registro de CONTASIS y las líneas neutrales— no cambian ni una celda, y julio rehecho desde
los registros que CONTASIS importó sale igual que antes de los renombres. Con la configuración por secciones
(13-sep-2026) solo cambió la entrada de un caso: el área de la detracción de `detraccion_area_y_tipo_doc` era `9001`, y
la sección de CONCAR rechaza un área de más de sus 3 caracteres.

- **La configuración va por secciones y se valida entera**: lo general en la raíz y lo de cada sistema en su sección.
  Una clave de un sistema en la raíz —la forma plana de antes—, una retirada o una desconocida detienen la generación
  con `ConfiguracionInvalida` y un mensaje que dice adónde va (`CLAVES_RETIRADAS`). `generar` también la comprueba,
  para quien lo llama directamente.
- **La tabla de detracciones que se reconocen** son las claves de `detraccion_tasas`, que es general (`null`: se
  reconoce sin tasa); `detraccion_codigos` queda para el código interno de CONCAR.

- **El estándar se llama `open-accounting`** (antes `pe-ledger`) y pasa a la `0.3`: la clave del documento es
  `open_accounting`, el esquema `estandar/open-accounting.schema.json`, la constante `OPEN_ACCOUNTING` y el recurso
  del MCP `contaperu://estandar/open-accounting`. `datos_raw` pasa a `datos_originales`. Rompe a quien lea los
  nombres viejos; contab-core se ajusta a la vez.
- **CONCAR sale del núcleo**, con el mismo reparto que CONTASIS (`drivers/concar/datos.py`, `proyeccion.py` y
  `xlsx.py`): el núcleo ya no importa ningún driver.
- `contrato.incumplimientos` explica de otra manera por qué un driver de la forma `linea` no declara `EXIGE`
  («no lleva cuentas»): ya no es cosa solo de los de asientos, porque uno de registro también lo declara.

Los nombres del núcleo:

| Antes | Después |
|---|---|
| `asiento/datos.py`, `DEFAULTS` | lo general en `contaperu/configuracion.py` (`CONFIG_POR_DEFECTO`, sin lo de ningún sistema), lo del asiento en `asiento/configuracion.py` (`CONFIGURACION_DEL_ASIENTO`) y lo de cada sistema en su driver; los datos del Excel, en `drivers/concar/datos.py` |
| `EXCEL_HEADERS` (`row1`, `row2`, `row3`), `FLAG_CONVERSION` | `drivers.concar.datos.CABECERAS` (`titulos`, `notas`, `formatos`), `MARCA_CONVERSION` |
| `asiento.asiento`, `asiento.tasa_igv`, `asiento.nombre`, `asiento.CorrelativoDesborda` | `drivers.concar.filas_de_comprobante`, `tasa_igv_entera`, `nombre`, `CorrelativoDesborda` |
| `asiento.desde_fila`, `asiento.a_lineas`, `ETIQUETAS_SUB_DIARIO` | `drivers.concar.desde_fila` y `a_lineas`; la tabla sin uso, fuera (queda `etiquetas_sub_diario`) |
| la configuración bajo la clave `concar`; `tipos.NN.concar`, `cc_referencia_en_x`, `cc_en_anexo_auxiliar` | lo general en la raíz y lo de cada sistema en su sección; `concar.tipos.NN.sigla`; el centro en la X, con las columnas `anexo_auxiliar` y `anexo_auxiliar_del_tercero` de `concar.columnas.centro_costo` |
| `tipo_concar`, `_mapa` | `sigla_documento`, `equivalencia_tipo` |
| `asiento/construir.py` | `asiento/resolucion.py` |
| `merge_config`, `resolve_cxp_account`, `resolve_cxp_detraccion_account` | `fundir_config`, `cuenta_por_pagar`, `cuenta_por_pagar_detraccion` |
| `build_xlsx`, `DRIVER_DEFAULT` | `escribir_xlsx`, `DRIVER_POR_DEFECTO` |
| `fmt_fecha`, `fmt_monto`, `fmt_tc`, `fmt_numero` | `formatear_fecha`, `formatear_monto`, `formatear_cambio`, `formatear_numero` |
| `filas_sin_cuenta`, `filas_sin_centro`, `tipos_sin_mapa` | `comprobantes_sin_cuenta`, `comprobantes_sin_centro`, `tipos_sin_sigla` |
| `cuenta_gasto`, `cuenta_venta`, `cuenta_de_fila` | fuera: la cuenta de la base la resuelve `partes_de` |
| `asiento_neutral(c, contab, mes, numero_comprobante, op, venta)`, `mes_del_libro` | `lineas_del_comprobante(c, config, limites, correlativo, opciones, es_venta)`, `limites_del_periodo` |
| `contrato.necesita_config`, `necesita_asiento`, `EXIGE_POSIBLES`, `EXIGE_NUCLEO` | `lleva_cuentas`, `arma_asientos`, `EXIGE_POSIBLES_ASIENTO`, `EXIGE_NUCLEO_ASIENTO` |
| `DriverTexto`, `DriverRegistro`, `DriverArchivo`, `DriverAsientos` | `DriverRegistroTexto`, `DriverRegistroArchivo`, `DriverAsientoComprobantes`, `DriverAsientoLineas` |
| `generar(…, **params)` con `contab`; `generar.lineas` | `generar(…, config=…, correlativos=…)`; `lineas_de_texto` |
| `Exportado.txt`, `.zip`, `.nombre_zip`, `.n_filas` | `.texto`, `.comprimido`, `.nombre_comprimido`, `.comprobantes` |
| `igv.tasa`, `detracciones.monto`, `detracciones.tasa`, `drivers.formato` | `tasa_calculada`, `monto_detraccion`, `tasa_detraccion`, `formato_de` |
| `asiento.config_de(config_cliente, config_cuenta)` con sus tres capas; `operaciones.configuracion`, que aceptaba la forma anidada | `operaciones.config_aplicada(configuracion, driver)`: lo general con sus valores por defecto y encima la sección del destino con los suyos, plana; validada entera |
| los parámetros `contab` y `conf`, `op`, `mod`, `venta` | `config`, `opciones`, `modulo`, `es_venta` |
| `xml_ubl.parsear(data, tipo_libro)` | `parsear(datos, libro)`, como el lector del SIRE |
| `lectores.archivos.Resultado`, `partida_doble.Resultado`, `pcge.cargar`, `pcge.catalogo.cargar` | `ResultadoLectura`, `Cuadre`, `cargar_equivalencias`, `cargar_catalogo` |
| `asiento.REQUISITO_DE`, `operaciones.TEXTO_FALTANTE` | `asiento.FALTAS` (y `asiento.FALTA`, por clave) |
| `TipoSinMapa`, `CorrelativoFaltante`, `MonedaSinCodigo` | `SinSigla`, `SinCorrelativo`, `SinCodigoDeMoneda` |
| `RepartoNoCuadra` y `RepartoNoAdmitido` heredan de `SinCuenta` | todas las excepciones de exportar heredan de `NoExportable` |
| `asiento.D2` | `modelo.CENTIMO` |
| `lineas_del_comprobante` y `lineas_del_libro` leían `centro_como_referencia` y `centro_en_anexo_del_tercero` | el parámetro `centro_en_anexo` (`principal`, `tercero`), que calcula `contrato.centro_en_anexo` desde las columnas elegidas |
| el parámetro `config` de `exportar`, `diagnosticar`, `generar_asiento` y `revisar` | `configuracion`, la forma guardada (`config` queda para la aplicada) |

Las respuestas de la fachada, el MCP y la CLI (las herramientas, sus parámetros y las opciones no cambian):

| Antes | Después |
|---|---|
| `faltantes`: `sin_centro_de_costo`, `tipos_sin_equivalencia`, `monedas_sin_codigo`, `sub_diarios_sin_correlativo`, `reparto_no_cuadra`, `no_caben` | con `sin_*`, como el modal de contab-core: `sin_centro`, `sin_sigla`, `sin_codigo_de_moneda`, `sin_correlativo`, `reparto_que_no_cuadra`, `no_cabe` (también en `que_falta[].motivo`) |
| `exportar.filas` | `exportar.comprobantes` |
| `fuera_del_registro`, en el resumen y en `diagnosticar.totales` | `fuera_del_destino` |
| `con_avisos`, `con_errores` en el resumen | `con_aviso`, `con_error`, como en `diagnosticar` |
| `_revision.total`, `_revision.bloquean_la_exportacion` | `_revision.comprobantes`, `_revision.bloqueantes` |
| el resumen de CONCAR `filas_excel`; por sub-diario `n`, `desde_cod`, `hasta_cod` | `filas`; `comprobantes`, `desde_codigo`, `hasta_codigo` |
| la herramienta `configuracion_por_defecto` devolvía la configuración plana | la forma por secciones, que se puede volver a pasar |

`por_que_no` y la lista de la CLI siguen el orden de `asiento.FALTAS`: sigla, código de moneda, reparto no admitido,
cuenta, reparto que no cuadra y centro.

### Retirado
- `Opciones.correlativo` (el campo 3 del PLE), `formato.fmt_fecha_libre` y `drivers.csv.construir`, que además se
  saltaba los requisitos del destino: no los usaba nadie.
- `asiento.config_aplicada` (queda `operaciones.config_aplicada`, que conoce los drivers) y, en la configuración,
  `centro_como_referencia` y `centro_en_anexo_del_tercero`: los reemplazan las columnas del centro de CONCAR.
- **`cuenta_contable` y `centro_costo` salen del comprobante** (`open-accounting 0.3`): la cuenta y el centro de cada
  documento llegan solo en la imputación, y un documento que todavía los trae se rechaza en vez de perderlos en
  silencio. En esta rama hubo antes un `cuenta_tercero` y unas `imputaciones` dentro del comprobante: nunca se
  publicaron, y salieron al separar la imputación del documento.

## [0.9.0] — 2026-09-12

Una regla que estaba sin fuente, corregida contra la norma: **un comprobante de compras del mes anterior no
es una observación**. John lo vio en pantalla (un recibo de luz del 29/08 pintado de ámbar dentro del mes 09)
y la Ley 29215, art. 2, dice que la compra se anota en el mes de emisión **o en los 12 siguientes**.

### Cambiado
- **En compras, el comprobante emitido en un mes anterior ya no produce observación** mientras esté dentro
  del plazo de anotación (Ley 29215, art. 2, texto del D.Leg. 1116: «el mes de su emisión o del pago del
  Impuesto, según sea el caso, o … los 12 (doce) meses siguientes»). Hasta ahora `PERIODO_ANTERIOR` avisaba
  a cualquier fecha anterior —de un mes o de dos años— sin norma detrás, y como todo aviso convertía la fila
  en «observada». Es un **cambio de comportamiento**: las filas que hoy salen observadas solo por eso pasan a
  «ok» al revalidar. En un documento aduanero la referencia es la fecha de pago del impuesto (campo 6 del
  RCE): el «o del pago del Impuesto» del artículo.
- **En ventas el aviso `PERIODO_ANTERIOR` se queda** —ahí no hay plazo: el IGV nace con la emisión (Ley del
  IGV, art. 4)— y su texto ahora lo dice así. Deja de hablar del Excel de CONCAR: eso ya lo dice el resumen
  de la exportación («extemporáneos al 01/MM»).

### Añadido
- **`CREDITO_FISCAL_FUERA_DE_PLAZO`** (aviso, no bloquea): la compra emitida hace más de 12 meses. Dice el
  hecho —fuera del plazo de anotación— y deja la decisión sobre el crédito fiscal al contador. Está en
  `PEDIR_A` (contador).
- `validar.PLAZO_ANOTACION_MESES = 12`, con la nota de relevo: el **D.Leg. 1669** (28-sep-2024) lo baja a 0
  meses para los electrónicos, 2 para los físicos y 3 con detracción, pero rige recién con la Resolución de
  Superintendencia que SUNAT no ha publicado (verificado el 12-sep-2026), y lo emitido antes de esa vigencia
  conserva los 12. Ese día cambia la constante y entra la distinción por `origen` y `detraccion`, con su cita.

## [0.8.0] — 2026-09-11

Lo que `REFERENCIAS.md` proponía y tenía un caso real detrás (decisión de John, 11-sep-2026): el
destino declara qué exige, cada exportación deja su huella, y `diagnosticar` dice a quién pedir lo que
falta. **El Excel de CONCAR validado no cambia**: los 42 casos de `tests/test_snapshot_concar.py` siguen
idénticos celda a celda.

### Cambiado
- **El driver de CONCAR se detiene sin centro de costo** donde la cuenta lo lleva (`SinCentro`) y cuando
  un sub-diario pasaría de 9999 (`CorrelativoDesborda`). Las dos reglas existían —la del contador del
  06-sep-2026 y la de los cuatro dígitos de CONCAR— pero las aplicaba solo el portal antes de llamar al
  motor; el driver generaba igual. Es un **cambio de comportamiento** para quien use el motor sin el
  portal: un mes que antes salía con la M vacía ahora se niega y dice cuáles. Lo declara `EXIGE`.
- **`diagnosticar` decide «listo» por lo que exige el destino** (`exige` en la respuesta): el CSV no
  bloquea por centro ni por moneda; CONCAR sí. `faltantes` conserva sus cinco claves, informando.
- La CLI remite a `contaperu diagnosticar` también ante `SinCentro` y `CorrelativoDesborda`.

### Añadido
- **`EXIGE` en el contrato de driver** (`drivers/contrato.py`): lo que ese ERP no puede importar sin y
  que el núcleo, si no se lo dicen, deja pasar (`centro_costo`, `moneda`). La cuenta y la equivalencia
  del tipo las exige el núcleo a todo driver de asientos. `contrato.exige(mod)` devuelve la unión;
  `incumplimientos()` rechaza un requisito fuera del catálogo y un `EXIGE` en un driver de texto. El
  recurso MCP `contaperu://drivers` lo publica.
- `asiento.faltantes_para()` y `asiento.exigir_requisitos()`: una sola lista de comprobaciones para el
  driver (que lanza), el núcleo (`generar._desde_lineas`, para los drivers `desde_lineas`) y
  `diagnosticar` (que describe).
- **La huella del asiento** (`asiento/huella.py`): sha256 del contenido de las líneas neutrales, en su
  orden y sin el correlativo. Va en `resumen["huella"]` de todo driver de asientos, en `_asiento.huella`
  de `generar_asiento` y en **`_exportacion`** de `exportar` (`{driver, archivo, huella, fecha}`). La
  misma tanda exportada otra vez —tras un «deshacer»— lleva la misma huella: es lo que permite avisar
  de que ese contenido ya salió, porque el Excel de CONCAR se **suma** al importarlo dos veces. La
  `fecha` la pone quien llama (`exportar(..., fecha="AAAA-MM-DD")`, también en el MCP); el núcleo no
  mira el reloj. La fórmula es contrato y `tests/test_huella.py` la fija con un valor literal.
- **`que_falta` y `pedir_a` en `diagnosticar`**: lo que bloquea para ese destino, agrupado por motivo,
  con a quién pedírselo —`contador` si se resuelve mirando el documento o el plan de cuentas,
  `sistema` si es configuración del destino o un dato público que no está en el papel—. La tabla
  (`operaciones.PEDIR_A`) cubre todos los códigos de `validar.py` y un test lo comprueba recorriendo el
  módulo. `proveedor` queda reservado. La CLI lo imprime.
- **`REFERENCIAS.md`**: cómo modelan el asiento, los impuestos, las dimensiones, la escritura y la
  idempotencia la API de QuickBooks Online, la de Xero y las APIs unificadas de EE. UU. (Merge, Codat,
  Rutter, Apideck), comparado campo a campo con `pe-ledger`; qué no se toma y por qué; y la propuesta
  de campos opcionales de la que sale esta versión. `id_externo`, `dimensiones` y `estado` de la línea
  quedan como **nombres reservados** (`estandar/LEEME.md`) hasta que haya un caso real.

### Corregido
- `README.md` y `estandar/LEEME.md` decían pe-ledger 0.1; es 0.2 desde la 0.6.0. Y el docstring de
  `test_frontera` decía que el portal instala solo `[excel]`: instala también `[mcp]` desde que monta su
  conector.

## [0.7.0] — 2026-09-11

Infraestructura para escalar: el núcleo deja de estar atado al formato de un ERP, un driver nuevo se
enchufa sin tocar el repositorio, y un agente puede preguntar qué falta antes de exportar. **Ninguna
regla contable cambia**: el Excel de CONCAR sale idéntico celda a celda (lo prueba un snapshot de 42
casos congelado antes del refactor).

### Cambiado
- **El asiento nace en líneas neutrales; CONCAR pasa a ser una proyección.** La lógica contable sale
  de `asiento.construir.asiento()` a `asiento/motor.py` (`asiento_neutral`, `lineas_del_libro`), que
  arma las líneas de `pe-ledger` directamente; el Excel se proyecta desde ellas en
  `drivers/concar/proyeccion.py`. Hasta ahora la línea «neutral» se sacaba releyendo las columnas de
  CONCAR y heredaba su vocabulario. `asiento()` conserva su firma y su salida: es API pública.
- **La línea neutral dice más**: `rol` (`principal`, `igv`, `retencion_4ta`, `tercero`,
  `detraccion_tercero`, `detraccion`), `documento.tipo_cp` y `referencia.tipo_cp` (el código SUNAT,
  al lado de la sigla del ERP), `detraccion.codigo`, la glosa **entera** (el corte a 40/30 es de
  CONCAR) y `tasa_igv` como texto exacto (`"10.5"`; redondear es cosa del ERP). Son campos opcionales
  añadidos: el estándar sigue en `pe-ledger` 0.2.
- **El registro de drivers carga los de terceros** por entry points (grupo `contaperu.drivers`). Los de
  serie ganan ante un nombre repetido; uno que no cumple el contrato o revienta al importarse se ignora
  con un `AvisoDriver` en vez de tumbar el registro. `drivers.DRIVERS` se muta en sitio, así que quien
  ya lo importó ve lo mismo; `drivers.recargar()` vuelve a buscar.
- **El driver CSV pasa a la forma `desde_lineas`** y sirve de plantilla; conserva `construir` por
  compatibilidad.
- **La CLI llega a todos los drivers.** `desde-json --driver csv|concar` reventaba con un `TypeError`
  porque nunca pasaba la configuración ni los correlativos (venía así desde antes); ahora entran por
  `--config` y los correlativos arrancan en 1, como en `operaciones.exportar`. Lo que falte se dice y
  remite a `contaperu diagnosticar`. Los JSON de entrada se leen con `utf-8-sig`: el Bloc de notas y
  `Out-File` de PowerShell escriben BOM.

### Añadido
- **`operaciones.diagnosticar`**, herramienta MCP `diagnosticar` y comando `contaperu diagnosticar`:
  en una sola respuesta, si el mes está listo y por qué no, bloqueantes y avisos por serie-número, qué
  falta para el destino (cuenta, centro de costo, tipos sin equivalencia, monedas, sub-diarios sin
  correlativo), detracciones sin constancia, resumen por contraparte y desde qué correlativo arranca
  cada sub-diario. No añade reglas: reúne comprobaciones que ya existían y las describe en vez de
  lanzarlas. Deja fijado que el centro de costo lo **avisa** el diagnóstico pero el driver de CONCAR
  sigue sin pararlo: cambiar eso es una decisión aparte.
- **`drivers/contrato.py`**: las tres formas de driver (`linea`, `construir` y la nueva
  `desde_lineas`, que solo ve líneas neutrales ya numeradas y cuadradas), `incumplimientos()` para
  decir qué le falta a uno, y `tests/test_contrato_drivers.py`, el examen que pasa cualquier driver
  registrado.
- **`tests/test_snapshot_concar.py`**: 42 casos con las 41 columnas del Excel congeladas celda a celda
  (y las líneas neutrales aparte). Regenerarlo es una decisión contable con fuente, no un trámite.
- **`ARQUITECTURA.md`**: los tres niveles, el flujo comprobante → línea neutral → proyección, núcleo /
  fachada / puertas, cómo se enchufa un driver y lo que no se negocia.

### Corregido
- El README decía nueve herramientas y tres recursos en el MCP; eran diez y cuatro (faltaban
  `buscar_cuenta_pcge` y el catálogo del PCGE 2026). Ahora son once y cuatro.

## [0.6.0] — 2026-09-11

### Cambiado
- **La base y el IGV son siempre netos; los descuentos ya no entran en el total** (estándar `pe-ledger` 0.2).
  `dscto_base`/`dscto_igv` pasan a decir qué parte de la base y del IGV informa el SIRE en sus campos 16 y 18.
  Una nota de crédito de descuento global —la FC01-45 del contraste de agosto— llegaba distinta por cada
  puerta, y las dos se bloqueaban con `TOTAL_NO_CUADRA`: del XML, con la base **y** el descuento, y el TXT del
  SIRE la contaba dos veces; de la propuesta de SUNAT, con base e IGV en cero, así que el asiento de CONCAR
  perdía la línea del IGV y el portal la pintaba «Inafecto». Ahora las dos dan base 9985.36, IGV 1797.36 y el
  descuento igual, validan, y el TXT la escribe como SUNAT (15 = 0.00, 16 = −9985.36).
- El TXT del SIRE escribe el campo 15 como `signo · base + descuento` (y el 17 igual): el total es la suma con
  signo de los campos, como en la exportación real de SUNAT. El lector de la propuesta hace lo inverso, y
  rechaza un descuento en positivo.
- El lector XML solo llena el descuento en una NC de ventas cuyo descuento de documento es todo su importe;
  en facturas, notas de débito y compras queda en cero, porque la base del XML ya es neta. Cada descuento de
  documento queda anotado en `datos_raw["descuentos_globales"]`.
- `igv.aplicar_igv` devuelve también los dos descuentos: una nota entera como descuento sigue entera.

### Añadido
- `igv.aplicar_total()`: el total que dice el papel sin tocar el IGV; lo absorbe el importe principal (la
  regla de la celda «Total» del portal, que hasta hoy calculaba el navegador).
- Error `DSCTO_MAYOR_QUE_BASE`.

## [0.5.0] — 2026-09-10

### Cambiado
- **El monto de la detracción tiene una sola cifra: la del motor.** El cálculo que vivía privado en el
  asiento (total × tasa en soles enteros, con el T.C. si es en dólares) es ahora `detracciones.monto()`, y
  lo usan el asiento y `detracciones.normalizar()`, que desde hoy anota en cada detracción su `monto` y la
  tasa de la tabla para ese código (`tasa_tabla`). Hasta ahora el portal enseñaba otra cifra —calculada en
  el navegador con decimales, o la que la IA leyó del PDF— que no siempre era la que iba a CONCAR.
  `normalizar()` no toca la tasa del comprobante: la huella del asiento depende de ella.

### Añadido
- `detracciones.monto()`, `detracciones.tasa()` y `detracciones.tasa_de_tabla()`.
- **Aviso `DETRACCION_TASA_DISTINTA`** cuando la tasa con la que va a salir la detracción no es la de la
  tabla del contribuyente para ese código: el caso de una IA que lee un 10 % en un código del 12 %. Aviso
  y no error, porque la del comprobante puede ser legítima.

## [0.4.0] — 2026-09-10

### Cambiado
- **La tasa del IGV ya no se supone en ninguna parte: sale de cada comprobante** (decisión de John,
  10-sep-2026: puede ser 18, 10.5 o 0). `asiento.tasa_igv()` —la columna AO del Excel de CONCAR— es
  ahora la tasa del comprobante (IGV ÷ base) redondeada a entero, porque CONCAR solo admite enteros.
  Desaparecen el **18 de respaldo** para un IGV sin base (ese comprobante no llega al asiento: la
  validación lo para con `IGV_NO_CUADRA`) y la regla que llevaba el **10.5 al 10**; las dos suponían
  una tasa en vez de leerla. Sale también `tasa_igv` de `asiento.DEFAULTS`. **Cambio de
  comportamiento:** un comprobante al 10.5 % sale ahora con AO = 11, no 10 — y la plantilla describe
  la columna con «valores validos 0,10,18», así que hay que comprobarlo con la primera importación real
  que lo traiga. Hoy no hay ninguno en producción: los 99 comprobantes con IGV están al 18 %.

### Añadido
- **`contaperu.igv`**: `tasa(igv, base)` y `aplicar_igv(comprobante, igv)`, el recálculo de importes
  cuando se escribe el IGV que trae el papel, sin tocar el total. Con IGV el comprobante es afecto y
  la base se deduce; sin IGV cae en inafecto. Lo consume el portal, que hasta ahora hacía esta cuenta
  en el navegador dividiendo entre 1.18.

### Corregido
- **La versión se escribía a mano en dos sitios y se separaron.** Llegaron a convivir **tres**:
  `0.3.0` en `pyproject.toml`, `0.2.0` en `contaperu/__init__.py` y `0.1.0` en la metadata de la
  instalación editable — y la del medio era la que el servidor MCP le decía a su cliente al
  presentarse, y la que imprimía `contaperu --version`. Ahora se escribe **una sola vez**, en
  `contaperu/_version.py`, y `pyproject.toml` la lee de ahí (`[tool.hatch.version]`). No al revés:
  leerla con `importlib.metadata` parece más limpio pero en una instalación editable esa metadata se
  congela el día que se instaló — así apareció el `0.1.0`. `PE_LEDGER` también estaba duplicado
  (`__init__.py` y `operaciones.py`) y ahora sale del mismo módulo.
- **La línea de comandos no pasaba por la fachada.** No importaba `operaciones` ni una vez:
  construía `Libro` y `Comprobante` por su cuenta y serializaba el documento a mano, así que emitía
  un JSON **sin la clave `pe_ledger`** mientras el servidor MCP sí la ponía — el mismo comprobante,
  dos documentos distintos según la puerta, hasta el punto de que un test tenía que añadir la clave
  para poder validar contra el esquema. Ahora las dos puertas leen y escriben por `operaciones`, y
  `desde-json` gana de paso lo que se saltaba: el motivo legible cuando falta el bloque `libro` y el
  tope de 5.000 comprobantes.

### Añadido
- **`tests/test_frontera.py`** — la frontera deja de sostenerse por convención. Comprueba que el
  núcleo no importa ninguna puerta ni el SDK del protocolo, que no sale a la red ni lee variables de
  entorno ni mira el reloj, que cada puerta pasa por la fachada, y que **las dos puertas producen el
  mismo documento para el mismo XML** (normalizando `archivo_nombre`, que es procedencia: el CLI
  recibe una ruta y el MCP bytes).
- **`tests/conftest.py`** — los tests corren **sin red de verdad**. Antes era un comentario en el
  YAML del CI; ahora un candado bloquea toda conexión que no sea a localhost y hay un test que
  comprueba que el candado muerde, con una IP y no con un nombre — con un nombre, la resolución DNS
  falla antes en una máquina sin red y el test pasaría en verde sin ejercitar nada.

### Cambiado
- **La línea de la detracción se calca de un Excel que CONCAR ACEPTÓ** (set-2026), no del borrador de
  la plantilla. El tipo de documento pasa de **`DT` a `DR`**: el `DT` anterior nunca llegó a
  importarse en un CONCAR de verdad. **Es un cambio de comportamiento** — quien ya exporte facturas
  con detracción verá `DR` donde antes veía `DT`—, y por eso la sigla queda además configurable
  (`detraccion_tipo_doc`): la Tabla General 06 la numera cada contribuyente.
- La misma línea estrena la **referencia al documento del que sale la detracción** (columnas Z, AA y
  AB: tipo, serie-número y fecha de emisión del comprobante). Es lo que traía el archivo validado, y
  solo la lleva esa línea: las otras cuatro del asiento siguen sin referencia. **En una nota de
  crédito o débito no se pisa la que ya había** —la del documento que la nota corrige—, porque no
  hay ningún archivo validado que diga que deba ser otra; queda pendiente de comprobar con una nota
  real.

### Añadido
- **`detraccion_area`**: el código de área (Tabla General 26 de CONCAR) de la línea de la detracción,
  columna V. Va **vacío de fábrica** a propósito: es un número propio de cada empresa, no una
  constante contable, y ponerle uno por defecto metería los apuntes de todo el mundo en un área que
  nadie eligió. **No se recorta a los 3 caracteres** que pide la plantilla: cortar `0612` a `061`
  mandaría el apunte a otra área en silencio, mientras que entero CONCAR lo rechaza y se ve. Es la
  diferencia con la glosa, que sí se corta — ahí sobra texto, aquí sobraría significado.
- **`detraccion_tipo_doc`**, la sigla de arriba, con `DR` de serie.
- **El catálogo oficial del PCGE 2026**: `contaperu/pcge/catalogo2026.json`, 1615 cuentas con su
  nombre y la **página impresa** de la norma que lo dice (77 madre · 311 de tres dígitos · 641 de
  cuatro · 586 de cinco). Es el dato que le faltaba al motor: sin él, quien registra una compra
  escribe `631101` y no hay nada contra lo que contrastarlo.
- `contaperu/pcge/catalogo.py` — `existe()`, `nombre_de()`, `buscar()` y **`resolver()`**. La regla
  que gobierna el módulo: **una cuenta que no está en el catálogo NO es un error**. El PCGE llega a
  cinco dígitos y cada empresa abre sus divisionarias debajo, así que `resolver()` devuelve la
  cuenta exacta o **su antecesora más larga** —de `603201` sale `6032 Suministros`—, que es
  información útil y no un rechazo. Medido contra un plan de cuentas real en producción: **137 de
  137 cuentas son de seis dígitos, ninguna existe literalmente en la norma y las 137 resuelven a su
  madre**. Un `existe()` que bloqueara habría bloqueado el plan entero.
- `herramientas/extraer_pcge2026.py`, que genera ese JSON desde el PDF oficial. El PDF **no entra
  al repositorio** (2 MB y no es nuestro); entra el extracto y el script con el que se hizo, para
  poder rehacerlo y auditarlo cuando salga una modificatoria.
- En el servidor MCP, el recurso **`contaperu://catalogos/pcge2026`** y la herramienta
  **`buscar_cuenta_pcge`** (por nombre o por código). Son **diez** herramientas ahora.

### Cambiado
- `adaptar_pcge2026` sigue con la tabla vacía, pero ahora dice **por qué**: este proyecto nace en
  2026 y trabaja con el PCGE 2026 desde el primer asiento, así que no hay plan anterior del que
  traducir. No es una tarea pendiente — es el riel para el día que una modificatoria sustituya
  cuentas, y ese día entrará como datos con su cita, no como código.

### Corregido
- Dentro de `contaperu.pcge` conviven **dos `cargar()`**: el de la tabla de adaptación, que devuelve
  `(mapeos, datos)`, y el del catálogo, que devuelve el diccionario de la norma. El servidor MCP
  llamaba al que no era y servía una lista donde el cliente esperaba un objeto — no reventaba,
  devolvía otra cosa. Ahora el submódulo `catalogo` se exporta con nombre propio y las llamadas se
  escriben `pcge.catalogo.…`; lo vigila el test que lee el recurso por el protocolo.

## [0.2.0] — 2026-09-10

**La primera versión pública.** La 0.1.0 existió pero nunca salió del disco: se instaló como wheel
local en el servidor de Global Procesos y no llegó ni a PyPI ni a un tag. Queda documentada abajo
porque ese wheel sigue corriendo en producción, y porque reutilizar su número para un código que se
comporta distinto es justo lo que SemVer sirve para evitar.

### Añadido
- **`cuentas_con_centro`** y **`cc_referencia_en_x`** en la configuración de CONCAR, y los helpers
  `lleva_centro()` y `cuenta_de_fila()`.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, este `CHANGELOG.md` y las plantillas de issue y de pull
  request.
- El esquema `pe-ledger` estrena **`$id` canónico**, colgado del tag del **estándar**
  (`pe-ledger-0.1`) y no del de la librería: quien lo cite no tiene por qué verlo cambiar cada vez
  que sale una versión del paquete.
- CI endurecido: acciones fijadas por SHA, permisos mínimos, CodeQL, Dependabot y publicación en
  PyPI por OIDC —sin ningún token guardado en el repositorio.
- Los tests de la regla del centro de costo: **152 en total**, sin red y sin credenciales, sobre
  Python 3.11, 3.12 y 3.13.

### Cambiado
- **El centro de costo lo decide la CUENTA, no un interruptor global.** Hasta ahora la columna M se
  rellenaba en toda línea principal con `usa_centros_costo` encendido, fuera cual fuera la cuenta. En
  CONCAR la marca «C. Costo habilitado» vive en cada cuenta del plan. El contador (09-sep-2026): «la
  cuenta 63 y 65 tiene habilitado el centro de costo en la columna M, pero cuando es una cuenta 60 por
  defecto no se debe asignar un centro de costo». Ahora `cuentas_con_centro` lo declara por prefijo,
  de fábrica `["63", "65", "70"]` — el `70` para que las ventas no cambien. Una cuenta fuera de la
  lista deja la M vacía y **deja de bloquear la exportación**: exigir un centro que no se escribe en
  ningún sitio obligaba a inventarlo.
- Y para esas cuentas, `cc_referencia_en_x` (apagado de fábrica) manda el centro a la **X de su propia
  línea** como referencia: «algunas empresas optan en colocar la columna X como referencia el centro de
  costo». Es independiente de `cc_en_anexo_auxiliar`, la X del tercero, que no cambia.
- `filas_sin_centro()` acepta `venta=False` como tercer parámetro opcional, igual que su hermana
  `filas_sin_cuenta()`: sin él, un libro de ventas resolvería la cuenta como si fuera de gasto.
- Los datos de los tests no dejan rastro de terceros: RUC, razones sociales y nombres son ficticios
  con dígito verificador correcto, siguiendo el patrón repetitivo del propio repositorio. Se conserva
  a propósito un RUC **inválido**, porque hay un caso que comprueba que el módulo 11 lo rechaza.

## 0.1.0 — 2026-09-09 (nunca publicada)

La primera versión que sirve para algo: lee un comprobante de SUNAT, arma la partida doble y la
exporta al formato que pide un sistema contable. Sin estado, sin base de datos y sin salir a la red.

### Añadido
- **El estándar `pe-ledger` 0.1**: la especificación escrita (`estandar/LEEME.md`) y su esquema
  formal (`estandar/pe-ledger.schema.json`, JSON Schema 2020-12), validable desde el CLI.
- **El núcleo contable**: modelo canónico del comprobante, validación previa, construcción del
  asiento y **partida doble comprobada antes de escribir un solo byte** — si no cuadra, no se
  exporta.
- **Lectores**: XML UBL de SUNAT (con `defusedxml`), TXT del SIRE y archivos sueltos.
- **Drivers de salida**: CONCAR (`.xlsx`, 41 columnas), SIRE (`.txt`) y CSV genérico.
- **Reglas peruanas que rompen cualquier modelo genérico**: detracción en dos tiempos, recibo por
  honorarios sin crédito fiscal, nota de crédito que invierte el asiento, moneda extranjera con su
  tipo de cambio, y la fecha del asiento del comprobante extemporáneo.
- **Comparador contra SUNAT**: enfrenta nuestro TXT con la exportación del detalle del SIRE.
- **PCGE 2026**: adaptación del plan contable.
- **CLI** (`contaperu`) y **servidor MCP** (`contaperu-mcp`), que devuelve el Excel como archivo, no
  como texto, y admite publicarse tras un proxy declarando el dominio.
- 148 tests, sin red y sin credenciales, sobre Python 3.11, 3.12 y 3.13.

<!-- Los enlaces de comparación. Cada versión va contra la ANTERIOR QUE SE ETIQUETÓ, que no siempre es la de arriba:
     6 de las 44 secciones nunca tuvieron tag —3.8.0, 3.5.1, 0.6.0, 0.5.0, 0.4.0, 0.2.0— y por eso no llevan
     enlace. Las 0.x no llegaron a PyPI y algunas no se etiquetaron; la 3.5.1 y la 3.8.0 se documentaron pero se
     publicaron dentro de la siguiente. Un `compare/vA...vB` con un tag que no existe da 404, así que no se inventan:
     hasta hoy el de la 0.2.0 era justo eso. Si alguna vez se etiquetan, su enlace entra aquí y se recalcula el de
     la versión siguiente. -->
[5.1.0]: https://github.com/contaperu/contaperu/compare/v5.0.0...v5.1.0
[5.0.0]: https://github.com/contaperu/contaperu/compare/v4.3.0...v5.0.0
[4.3.0]: https://github.com/contaperu/contaperu/compare/v4.2.2...v4.3.0
[4.2.2]: https://github.com/contaperu/contaperu/compare/v4.2.1...v4.2.2
[4.2.1]: https://github.com/contaperu/contaperu/compare/v4.2.0...v4.2.1
[4.2.0]: https://github.com/contaperu/contaperu/compare/v4.1.0...v4.2.0
[4.1.0]: https://github.com/contaperu/contaperu/compare/v4.0.0...v4.1.0
[4.0.0]: https://github.com/contaperu/contaperu/compare/v3.10.0...v4.0.0
[3.10.0]: https://github.com/contaperu/contaperu/compare/v3.9.0...v3.10.0
[3.9.0]: https://github.com/contaperu/contaperu/compare/v3.7.0...v3.9.0
[3.7.0]: https://github.com/contaperu/contaperu/compare/v3.6.0...v3.7.0
[3.6.0]: https://github.com/contaperu/contaperu/compare/v3.5.0...v3.6.0
[3.5.0]: https://github.com/contaperu/contaperu/compare/v3.4.0...v3.5.0
[3.4.0]: https://github.com/contaperu/contaperu/compare/v3.3.0...v3.4.0
[3.3.0]: https://github.com/contaperu/contaperu/compare/v3.2.0...v3.3.0
[3.2.0]: https://github.com/contaperu/contaperu/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/contaperu/contaperu/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/contaperu/contaperu/compare/v2.7.0...v3.0.0
[2.7.0]: https://github.com/contaperu/contaperu/compare/v2.6.1...v2.7.0
[2.6.1]: https://github.com/contaperu/contaperu/compare/v2.6.0...v2.6.1
[2.6.0]: https://github.com/contaperu/contaperu/compare/v2.5.1...v2.6.0
[2.5.1]: https://github.com/contaperu/contaperu/compare/v2.5.0...v2.5.1
[2.5.0]: https://github.com/contaperu/contaperu/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/contaperu/contaperu/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/contaperu/contaperu/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/contaperu/contaperu/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/contaperu/contaperu/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/contaperu/contaperu/compare/v1.4.0...v2.0.0
[1.4.0]: https://github.com/contaperu/contaperu/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/contaperu/contaperu/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/contaperu/contaperu/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/contaperu/contaperu/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/contaperu/contaperu/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/contaperu/contaperu/compare/v0.10.0...v1.0.0
[0.10.0]: https://github.com/contaperu/contaperu/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/contaperu/contaperu/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/contaperu/contaperu/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/contaperu/contaperu/releases/tag/v0.7.0
