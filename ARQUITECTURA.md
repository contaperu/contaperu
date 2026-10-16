# Arquitectura de ContaPerú

Este documento explica **cómo está construido** el proyecto y **por qué así**: qué es el núcleo, qué
es una puerta, por dónde entra un driver nuevo y qué es lo que no se puede tocar. Es la referencia
para quien vaya a contribuir, y la lista de decisiones que no hay que volver a discutir.

## Tres niveles

```
┌─────────────────────────────────────────────────────────────┐
│  3 · AGENTES                                                │
│      servidor MCP · `diagnosticar` · un agente que pregunta │
│      «¿qué falta?», «¿qué saldría?», «¿qué bloquea?»        │
├─────────────────────────────────────────────────────────────┤
│  2 · DRIVERS                                                │
│      sire (TXT) · concar y contasis (Excel) · csv · terceros│
│      cada uno traduce vocabulario; ninguno decide contabilidad│
├─────────────────────────────────────────────────────────────┤
│  1 · NÚCLEO                                                 │
│      modelo · lectores · validación · asiento · detracciones│
│      IGV · partida doble · PCGE · el estándar `open-accounting`   │
└─────────────────────────────────────────────────────────────┘
```

**El núcleo** sabe contabilidad peruana y no sabe nada más: ni de archivos, ni de red, ni de qué
ERP hay al otro lado. **Los drivers** conocen el formato de un sistema concreto y nada de
contabilidad: reciben el asiento resuelto y lo escriben. **Los agentes** hablan con el núcleo a
través de la fachada y de las puertas, y lo usan como riel determinista: la IA lee el PDF; el
núcleo decide el asiento.

La secuencia de construcción es esa, de abajo arriba, y no es casual: primero el núcleo de reglas,
después los drivers que lo conectan con lo que ya existe, y solo entonces los agentes. Es el orden en
que se puede confiar en cada capa porque la de abajo ya está probada con archivos reales.

## El flujo de un comprobante

```
XML UBL / TXT del SIRE / JSON open-accounting
          │
          ▼
   comprobantes/  ──►  Comprobante (Decimal, positivo, fechas date)
   (xml_ubl, sire_txt, archivos)
          │
          ▼
   validar.py  ──►  observaciones: error (bloquea) | aviso (se exporta igual)
          │
          ▼
   asiento/comprobante.py ─►  LineaDiario × 2..5   ◄── ESTA ES LA FUENTE
          │                (cuenta, D/H, importe, rol, sub-diario, correlativo,
          │                 documento.tipo_cp, glosa entera, tasa exacta)
          │
          ├──► drivers/concar/proyeccion.py ──► 41 columnas ──► .xlsx
          ├──► drivers/csv                  ──► una fila por línea
          ├──► un driver de terceros (`desde_lineas`) ──► el formato de su ERP
          └──► operaciones.generar_asiento  ──► el bloque `asiento` del estándar
```

Aparte va la familia **registro**: una fila por comprobante, sin asiento, así que sus drivers no pasan por el
motor. El SIRE es un registro para SUNAT y se escribe desde el comprobante (`linea(c, libro, idx, opciones)`). Un
sistema contable que importa su registro de compras o de ventas y arma el asiento él mismo (CONTASIS)
recibe los comprobantes con la configuración (`desde_comprobantes`) y lleva cuentas, pero no las
decide: las lee de `asiento.partes_de` y `asiento.cuenta_tercero`, la misma resolución que usa el motor para el
asiento de CONCAR.

### Un mes, paso a paso

![El recorrido de un mes dentro del motor: leer el XML o la propuesta del SIRE hasta open-accounting; preparar, revisar, seleccionar y exigir lo del destino; armar un asiento, un registro contable o un registro a SUNAT; y responder con el archivo y cada comprobante](diagramas/recorrido-de-un-mes.svg)

Lo mismo, visto desde `pipeline/`. Si llegan archivos de SUNAT, el motor primero los **lee** (`pipeline/lectura`) y
los lleva al documento `open-accounting`: el XML de cada factura, suelto o en ZIP y sin los CDR, o el TXT de la
propuesta del SIRE. Desde ahí, cada mes recorre seis pasos:

1. **Preparar** (`preparacion`). Separa el libro de los comprobantes, aplica la configuración general y la sección
   del destino, y le pone a cada comprobante su imputación por el `id_externo`. Una imputación que no es de ningún
   comprobante se rechaza. **Un libro de tesorería tiene su propio paso**, `preparar_tesoreria`, porque sus pasos no
   se parecen: lee los `movimientos`, descarta las relecturas por su clave, casa la imputación de cada uno y lee el
   maestro de cuentas bancarias de la configuración. Quién elige entre los dos lo dice `libro.rasgos.origen`, y la
   elección ocurre **una sola vez** en cada puerta (`armado.generar_asiento` y `salida.exportar_archivo`): ni un
   `if es_tesoreria` más adentro.
2. **Revisar** (`validar.revisar`, en el núcleo). Valida el RUC, el IGV, el total, la fecha y los duplicados, también
   contra lo ya anotado en otros periodos. Un error detiene la exportación; un aviso deja pasar el comprobante.
3. **Seleccionar** (`seleccion`). Quedan fuera los excluidos, los duplicados y los tipos que el destino no lleva
   (`EXCLUYE_TIPOS`), como los recibos por honorarios en el SIRE y en CONTASIS.
4. **Exigir lo del destino** (`exigir_requisitos` y `contrato.no_caben`). Si el destino lleva cuentas, el núcleo
   comprueba, antes de armar nada, que cada comprobante tenga su cuenta, su centro de costo y su sigla, y que quepa
   en el formato.
5. **Armar, según la forma del driver** (`armado`).
   - **Asiento** (`desde_lineas`: CONCAR, CSV): el núcleo arma las líneas del asiento, las numera por sub-diario, exige
     que cuadren al céntimo y les calcula la huella; el driver solo traduce cada línea.
   - **Registro contable** (`desde_comprobantes`: CONTASIS): el driver recibe los comprobantes y lee las cuentas de
     la misma resolución que usa el asiento.
   - **Registro para SUNAT** (`linea`: el SIRE): una línea por comprobante, sin cuentas, en un TXT con su ZIP.
     El PLE es el mismo canal con la otra forma: su fila es una línea del asiento (`desde_lineas`).
6. **Responder** (`salida`). El archivo, el resumen y `_exportacion`: por cada comprobante, su identidad, su tramo de
   líneas y su huella, con la versión del motor que lo produjo.

No todas las operaciones hacen el recorrido completo:
- `revisar` llega hasta el paso 2.
- `diagnosticar` recorre hasta el 4 sin detenerse y cuenta lo que bloquea, lo que falta y a quién pedírselo.
- `generar_asiento` se queda en el asiento, sin escribir el archivo.
- `exportar` lo recorre entero.

### La decisión que lo ordena todo: la línea del comprobante es la fuente

Hasta la 0.6 el asiento nacía en las columnas del Excel de CONCAR (`'A'..'AO'`) y la línea del comprobante
se sacaba después releyéndolas. Funcionaba, pero esa línea heredaba el vocabulario de un
ERP —la sigla `FT` en vez del código SUNAT `01`, la glosa cortada a 30 caracteres, la tasa del IGV
redondeada a entero— y un segundo driver de asientos habría tenido que reinterpretar columnas de
CONCAR para escribir las suyas.

**De aquí salió la palabra «neutral»**, que esta línea llevó hasta la 3.10: era la que no arrastraba las columnas de
CONCAR. Se cambió por «línea del comprobante» (John, 29-sep-2026) porque el nombre decía de qué se libró en vez de qué
es, y porque la premisa se invirtió en esta misma versión: ya no es la versión limpia de algo, es la fuente. El
adjetivo sigue vivo donde sí describe —`VOCABULARIO = "neutral"` en el contrato de driver, las palabras del estándar
frente a las de un sistema legacy—.

Desde la 0.7 la dirección está invertida. `asiento/comprobante.py` arma las líneas en el vocabulario de
`open-accounting` y CONCAR es una proyección más. Lo que hace posible el cambio sin riesgo es
`tests/test_snapshot_concar.py`: 42 casos con las 41 columnas congeladas celda a celda **antes** del
refactor (hoy son 52). Ese Excel lleva un año importándose en CONCARs de producción; el snapshot es la garantía de
que no cambió ni una celda, y la regla para el futuro: **regenerarlo es una decisión contable con
fuente, nunca un trámite.**

### Lo que lleva cada línea

`LineaDiario` (`asiento/lineas.py`) es el bloque `asiento` del estándar. Además de cuenta, sentido e
importe lleva lo que un driver necesita para traducir **sin adivinar**:

| Campo | Para qué |
|---|---|
| `rol` | `principal`, `impuesto`, `retencion`, `tercero`, `recorte`, `detraccion`. Un ERP que pida el IGV en su columna encuentra la línea por su rol, no por su cuenta (que la elige cada empresa). |
| `documento.tipo_cp`, `referencia.tipo_cp` | El código SUNAT (Tabla 10), **y solo ese**: la sigla con la que un sistema legacy llama al tipo la escribe su driver, con `asiento.sigla_de_tipo`. |
| `glosa` | La misma en todas las líneas y entera, sin prefijos. El corte lo decide cada ERP. |
| `tasa_igv` | La del comprobante, como texto exacto (`"10.5"`). Redondear es cosa del que solo admite enteros. |
| `detraccion.codigo` | El código SUNAT del bien o servicio (Catálogo 54), **y solo ese**: el código interno de la tabla de cada sistema lo pone su driver (CONCAR, el de su T.G. 28), no el asiento. |
| `detraccion.nro_constancia`, `.fecha_constancia` | El vóucher del depósito, que llega días después (2.6.0). Sin él, el número sale con el comodín `999999999` y la fecha, vacía. |

### Dónde vive el asiento estándar

Tres cosas distintas llevan la palabra «asiento», y conviene no confundirlas al leer el árbol:

| Capa | Dónde | Qué es |
|---|---|---|
| **La forma** | `estandar/open-accounting.schema.json`, `$defs.linea` (con `enmiendas/` y `conformidad/`) | **La fuente.** El contrato que lee un ERP de terceros, en cualquier lenguaje |
| **La pieza en Python** | `asiento/lineas.py` (`LineaDiario`), `asiento/indice.py` (`Cabecera`) | Su materialización. No es una copia: `tests/test_estandar.py` exige que digan lo mismo, ni un campo de más ni uno de menos |
| **La entrega** | `drivers/asiento_contable/` | Un destino más, y de los cortos, que lo escribe sin traducirlo a vocabulario legacy |

Lo que **no** es el asiento estándar, aunque comparta carpeta, es `asiento/comprobante.py` y `asiento/resolucion/`: son
**la contabilidad peruana** —IGV, detracciones, sub-diarios, catálogos SUNAT—. El reparto no es una opinión, está
medido: `tests/fixtures/capas/acoplamiento_pe.json` registra que `asiento.lineas` toca un solo módulo peruano
(`pcge`, del que sale la `clase`), que `asiento.motor` toca cuatro, que de las cinco partes de `resolucion` la que
más toca son tres (`clasificacion`) y `numeracion` **no aparece**, y que `drivers.asiento_contable` tampoco, es
decir, acoplamiento cero.

Un ERP de otro país usaría las dos primeras capas y tiraría `motor.py` a la basura. Por eso están separadas, y por eso
el driver no se llama `asiento` a secas: `asiento` es la clave raíz del documento del estándar, y un driver no puede
llamarse igual que el bloque que escribe.

Se llamó **`asiento_neutral`** de la 1.1 a la 3.10, y el argumento de entonces era ese acoplamiento cero: «neutral» era
el que no sabe de Perú. El nombre describía una ausencia, y un ERP que elige un destino no busca un asiento neutral:
busca el asiento contable. Desde la 3.10 se llama **`asiento_contable`**, el nombre viejo resolvió toda la 3.x
con aviso (`drivers.ALIAS`) y **la 4.0 lo retiró**, que es lo que el aviso prometía. Lo que no cambia es el eje que el
contrato mide, que sigue llamándose `VOCABULARIO = "neutral"` porque eso sí es lo que describe: las palabras del
estándar frente a las de un sistema legacy.

### Cómo se conectan los tres libros (12.3 y 12.4)

Tres libros —`compra`, `venta`, `tesoreria`— y cuatro aristas entre ellos. Hasta la 12.2 **existían a medias y
ninguna se recorría**:

```
compras/ventas ──ref_tipo_cp, ref_serie, ref_numero──► compras/ventas     la NC nombra su factura
tesorería ─────── referencias[] ────────────────────► compras/ventas     el pago nombra lo que cancela
compras/ventas ── documento{} ──────────────────────► asiento            la línea nombra su documento
asiento ───────── id_en_destino ────────────────────► el destino         enmienda 0001, RESERVADA
```

La primera estaba en el dato y nadie la seguía: `anulada_por_nota` es una marca **a mano**, porque solo la nota
apunta hacia atrás. La segunda está cerrada desde el estándar 3.0 y nadie la puebla, porque no hay lector de banco
(D2) ni conciliación (D3). Con eso no se puede contestar «¿esta factura está pagada?».

**Lo que faltaba era un sustantivo, no un verbo**: `aplicaciones[]` (enmienda 0031), un registro aparte que dice
**cuánto de una cosa cancela otra**. N a N, con su importe, y con el `origen` que separa un hecho (`declarado`,
`manual`) de una conjetura (`propuesto`, que no cuenta para ningún saldo). Conviven con `referencias` por lo mismo
que conviven `movimiento` y su imputación: una dice lo que **afirma el papel** y la otra lo que alguien **decidió
aplicar**.

**Y el saldo no se guarda: se deriva.** `pendiente = total − Σ aplicaciones confirmadas`, y la palabra —«por
pagar», «pagado»— es una lectura de ese número. No hay enum en el estándar, ni campo en el modelo, ni rasgo en la
tabla del libro. Es el tercer uso del patrón, detrás del `rol` (10.0) y del estado de la detracción (2.0), y la
razón de fondo está **medida fuera**: en Odoo, un marcador junto al número se desincronizó dos veces, y su propia
recomendación es leer el residual y no el marcador. Las ocho plataformas comparadas en
[REFERENCIAS.md](REFERENCIAS.md) lo derivan, sin una excepción.

**Los meses se cruzan por argumento.** El libro es mensual y una factura de enero pagada en marzo vive en dos
documentos; `partidas_previas` lo resuelve con el molde que ya existía en `claves_previas` — un argumento que el
motor recibe y no guarda. Funciona porque la identidad de un comprobante no lleva el periodo.

Y una consecuencia de capa que conviene no perder: **`aplicaciones` es núcleo** y el saldo por contraparte es
**api**. Lo primero porque lo que decide si una factura está pagada no puede mirar un destino, y la capa es lo que
lo garantiza. Lo segundo porque un saldo de proveedor es un **informe** y no una fuente: en cero no significa que
todas sus facturas estén pagadas —una sobrepagada y una impaga se netean—, que es la vieja diferencia entre un
estado de cuenta por partida abierta y uno de saldo arrastrado.

### El eje del libro: una tabla, no un booleano (9.0)

El otro eje que ordena el motor es **de qué libro es el comprobante**. De la 1.0 a la 8.x fue un `bool`: `es_venta`,
que viajaba por una veintena de ellas, y `not es_venta` quería decir «es compra». Hoy el eje —la tabla—
viaja por veintiuna funciones: dieciocho de `asiento` —quince de ellas en la superficie congelada— y tres
del IGV. La última en llegar es `lineas_del_movimiento`, que nació con la tabla y nunca tuvo booleano. Con ese booleano el motor
decidía el sentido debe/haber, el crédito frente al débito fiscal, cliente frente a proveedor, el sub-diario y los
requisitos.

Con dos libros era correcto. El problema no era el número de llamadas: era que **un tercer tipo de libro no habría
dado ningún error** —habría salido tratado como una compra, con el debe y el haber invertidos y la contraparte en la
cuenta equivocada—, y el próximo libro ya tiene nombre y número de hito: el **diario** de B13, el que convierte al
motor en la base de un ERP y no solo en la capa sobre un sistema legacy.

Desde la 9.0 cada tipo de libro **declara** lo que el motor necesita saber de él, en `modelo.RASGOS`:

| | Rasgo | `venta` | `compra` | `tesoreria` |
|---|---|---|---|---|
| **qué ES el libro** | `origen` — de qué bloque salen sus líneas | `comprobantes` | `comprobantes` | **`movimientos`** |
| | `roles` — qué roles caben en su asiento | `principal` `impuesto` `tercero` | los tres **+** `retencion` `recorte` `detraccion` | **`tesoreria` `tercero` `principal`** (12.8) |
| | `sentido_principal` — a qué lado va el hecho | `H` | `D` | **`por_operacion`** |
| | `cuenta_contraparte` — con qué cuenta se salda | `clientes` | `cxp` | **vacío** |
| **qué reglas le tocan** | `da_credito_fiscal` | no | sí | no |
| | `lleva_detraccion` · `lleva_honorarios` | no | sí | no |
| **a dónde va** | `sub_diario` | ventas | compras | **vacío** |
| | `etiqueta_de_archivo` — cómo se llama en el nombre de un archivo | VENTAS | COMPRAS | **TESORERIA** (12.10) |

El reparto en tres grupos es de John (10-oct-2026) y no es cosmético: **el sub-diario no es lo que define a un
libro**, es por dónde sale, y tenerlo primero hacía parecer que sí. Lo que define a un libro son su origen, sus
roles y su sentido. Las tres reglas del medio son todas de las compras, y por eso valen `no` en todo lo demás.

**El último rasgo entró con la 12.10 y su historia es la de la 9.0 otra vez**: el nombre de un archivo salía de
`'VENTAS' if libro.es_venta else 'COMPRAS'`, el último sitio donde el booleano que esa versión retiró seguía
decidiendo algo — y habría llamado «COMPRAS» a un archivo de tesorería. Podía arreglarse con un diccionario en
`drivers/kit/nombres.py`, y eso habría sido una tabla paralela a ésta, que es exactamente lo que la 9.0 vino a
quitar. Añadir un libro vuelve a ser añadir una fila.

**`roles` es una declaración y no un mapa, y la distinción costó un intento.** Hubo una versión con
`rol_principal` y `rol_contraparte` que suponía que todo libro tiene un hecho y una contraparte. En tesorería eso
no sobrevive: en un pago que cancela una deuda el hecho es el dinero moviéndose, y en una comisión del banco el
hecho es el gasto y el dinero es la otra cara. Preguntar «cuál es el principal» fuerza una respuesta que a veces es
mentira. **Odoo lo esquiva no preguntándolo** —su pago tiene `liquidity`, `counterpart` y `writeoff`, sin
jerarquía—, y esto hace lo mismo. Quién escribe cada rol en cada línea es de quien genera el asiento, y el camino
del comprobante escribe roles de comprobante porque ES el camino del comprobante.

Los roles de los tres libros están **medidos ejecutando el motor**, no deducidos, y de su unión se **deriva**
`asiento.ROLES_DEL_MOTOR`, que era una lista mantenida a mano. Los de tesorería estuvieron **vacíos a propósito**
entre el 10-oct-2026 y la 12.8 —el motor no emitía ni una línea suya, así que no había forma de medirlos— y ese
vacío era una afirmación verdadera y comprobable, no un hueco por rellenar. **Se llenaron midiendo**, en la 12.8:
son `tesoreria`, `tercero` y `principal`. El que faltaba era el primero, y lo destrabó una fuente y no un archivo:
el **elemento 10 del PCGE 2026**, «Efectivo y equivalentes al efectivo» (p. 17), que es palabra por palabra lo que
el catálogo define como ese rol y lo que permite distinguir la línea del dinero de la de un gasto. Y la pregunta
de si el 42 de un pago es `tercero` o `contrapartida` **no la contestó el archivo del sub-diario**, que es lo que
esta nota esperaba: la contestó el catálogo el 11-oct-2026 —`contrapartida` es «la otra cara de un hecho que no se
le debe a nadie», y un 42 se le debe a alguien—, con tres argumentos más, uno de ellos que es derivable porque esa
línea lleva `contraparte_doc` y la comisión del banco no.

**Y el núcleo no manda por el rol, que desde el 10-oct-2026 es una promesa y no una casualidad.** El rol existe
para que un destino encuentre la línea que su columna pide sin conocer la cuenta —que la elige cada empresa—, así
que los drivers se bifurcaban por él y el núcleo no: la huella lo excluye, el resumen solo lo recolecta para
informarlo, y la api avisa de un rol desconocido con «se lee igual, el rol solo dice qué es. No rompe». Dos tests
lo sostienen (`tests/test_capas.py`): uno reescribe todos los roles y comprueba que la huella, el cuadre y los
importes no se mueven, y otro prohíbe comparar un rol contra un valor. Importa porque **lo que existe para los
sistemas de destino no puede ser de lo que dependa la contabilidad**, y el núcleo se está volviendo la base de un
ERP.

Lo que ningún estándar abierto del asiento tiene, por cierto, es el rol: XBRL GL usa `account` + `documentType` +
`debitCreditCode`, y SAF-T distingue la línea por los datos que trae (`CustomerID`/`SupplierID`,
`TaxInformation`). Beancount y hledger llevan cuenta e importe con signo. El único precedente es Odoo, y **usa dos
vocabularios distintos**: `product`/`tax`/`payment_term` en una factura y `liquidity`/`counterpart`/`writeoff` en
un pago.

### El `rol` se DERIVA, y desde la 9.2 nadie lo lee

Esa comparación es la que cerró la pregunta (John, 10-oct-2026): **si ningún estándar lo tiene, el rol no es un
dato del asiento; es una conveniencia para los destinos.** Y si lo es, el sitio donde se calcula es la capa que lo
usa. Así que vive en `drivers/kit/rol.py`, y el campo del estándar pasa a ser **pura salida**:

| Lo que trae la línea | Su papel |
|---|---|
| un bloque `impuesto`, `retencion` o `detraccion` | ese mismo rol — es el `TaxInformation` de SAF-T |
| su `debe_haber` es el lado del tercero de este libro | `tercero` |
| si no, y trae `contraparte_doc` | `recorte` |
| si no | `principal` |

El «lado del tercero» es `sentido_contraparte`, **cambiado cuando `documento.tipo_cp` está en `TIPOS_INVIERTEN`**
—en una nota de crédito los dos lados se invierten, y una nota de crédito de compra puede llevar detracción, así
que el caso no es teórico—. Los tres bloques van primero porque dos de ellos, la retención y la detracción, caen
en el lado de la contraparte y el tramo siguiente los llamaría `tercero`.

**El orden de los dos últimos tramos se midió, y la primera versión estaba mal.** Preguntaba por `contraparte_doc`
antes que por el lado, y falló en una línea de las 324 que produce la batería: el cliente de una **boleta**, que no
lleva RUC porque es un consumidor final, salía `principal` en vez de `tercero`. El sentido no tiene ese agujero.

Lo sostiene `tests/test_rol_derivado.py`, que exige la igualdad en **cada** línea de los tres meses que la batería
caracteriza, por los cuatro drivers que producen líneas, más los dos casos que ese barrido no trae y que son justo
los que ejercitan la inversión: la nota de crédito de una venta y la de una compra con detracción. Cuatro
mutaciones de la regla —quitar la inversión, cambiar el lado, reordenar los tramos, quitar el bloque de la
detracción— ponen el test rojo.

Lo que queda, y es lo irreducible: `tercero` y `recorte` son la misma cuenta y la misma contraparte sin ningún
bloque tipado, y SAF-T las emitiría indistinguibles. **Lo único que las separa es el sentido**, y por eso la
derivación funciona: recortar un saldo es moverlo en dirección contraria a como nació.

Los dos drivers que lo leían dejaron de hacerlo, y cada uno por su camino. **CONCAR no necesitaba la derivación**:
su único uso era encontrar la línea de la detracción, y esa es la que lleva el bloque `detraccion` —la misma
función ya escribía cuatro columnas así—. De paso arregla la vuelta: una línea leída de un Excel de CONCAR no trae
rol, así que volvía al archivo con el área (columna V) vacía. **STARSOFT sí la usa**, en los cinco sitios donde
mira si una fila es la del total o cómo se ordenan las filas de un comprobante; sus dos tablas siguen escritas con
nombres de rol, porque son de ese driver, y lo que cambió es de dónde sale el rol con el que se comparan.

**El otro `rol` se queda, y son dos cosas distintas con el mismo nombre.** `configuracion.Columna.rol` es
configuración de un driver —dice qué línea del asiento llena una columna de su archivo—, no el rol de una línea.
Una invariante los ata (`tests/test_contrato_drivers.py`): todo papel que una columna declara tiene que ser uno que
la derivación sepa producir, o esa columna no se llenaría nunca y nada lo diría.

**El tercer libro entró el 10-oct-2026 y los TRES vacíos de su columna son la mitad de lo que vale la tabla.**
`cuenta_contraparte` está vacía porque un libro de tesorería no se salda con una sola cuenta: un lado es la cuenta
de efectivo que el contribuyente declaró —su 104— y el otro lo pone la imputación. `roles` estuvo vacío por la misma
razón vista desde el otro campo: qué papeles hace cada pata **depende de lo que el pago cancela** —`tercero` si es
a un proveedor, `principal` si es una comisión del banco, y la otra cara de un traspaso entre cuentas propias es
otra vez efectivo—; declararlos antes de emitir una línea era adivinar, y el intento salió incompleto a la primera.
**Se llenó cuando se pudo medir** (12.8), que es la disciplina de la casa. Y `sub_diario` sigue
vacío porque
**su clave de configuración todavía no existe**: se intentó declararla y el contrato de drivers la paró con la razón
exacta, «una clave que nadie lee se configura para nada». Entra con el hito D6c, que pide un archivo del sub-diario
de bancos que CONCAR haya aceptado.

**Y ese último vacío enseñó que dos invariantes eran una sola afirmación disfrazada.** Hasta la 12.8 se decía «un
libro sin sub-diario es uno que el motor no puede armar» y «un libro declara roles si y solo si el motor lo
origina», y las dos juntas afirmaban más de lo que es cierto: tesorería se arma y **no se numera**, que son dos
cosas distintas. Lo que quedó, partido y comprobable: un libro declara roles **si y solo si la regla los deriva**
—comprobado ejecutando el motor y derivando con `rol_de`, no contra una lista—; y un libro sin `sub_diario`
**no se numera**, lo que con vocabulario legacy levanta `LibroQueTodaviaNoSeNumera` en vez del `KeyError` pelado
que levantaba antes. De hecho `ROLES_DEL_MOTOR` se **deriva** de los roles que declaran los tres libros, así que
las dos cosas se mueven juntas o el test cae.

**Y `sentido_principal` deja de ser una constante.** En una venta el ingreso siempre va al haber y en una compra el
gasto siempre al debe; en tesorería **un abono lleva el efectivo al debe y un cargo al haber**, así que el lado lo
dice cada operación. El valor se llama `por_operacion`, y `sentido_contraparte` **se niega a derivar** cuando lo es:
hasta entonces era `"D" if sentido_principal == "H" else "H"`, que con un tercer valor habría contestado «haber»
callado y mal — el mismo fallo que la 9.0 vino a cerrar, una capa más abajo. Un `else` que acierta por casualidad
mientras los valores son dos deja de acertar en cuanto son tres.

**El efecto sobre el efectivo tiene tres valores y los nombra la NIC 7** (`efectos_de_tesoreria`, en el catálogo
del estándar): «Flujos de efectivo son las **entradas y salidas** de efectivo y equivalentes al efectivo». El
tercero, `transferencia`, existe porque el **§9** excluye de los flujos los traspasos entre partidas de efectivo
—son gestión de tesorería—, así que hay que poder nombrarlo para dejarlo fuera y no contarlo dos veces. Es el mismo
reparto que hacen Odoo (`payment_type`: `inbound`/`outbound`/`transfer`) y ERPNext (`Receive`/`Pay`/`Internal
Transfer`); iDempiere lo resuelve con un booleano `IsReceipt`, que es exactamente lo que aquí se acabó de quitar.

| efecto | la cuenta de efectivo | la contrapartida |
|---|---|---|
| `entrada` | **D** | la pone la imputación |
| `salida` | **H** | la pone la imputación |
| `transferencia` | **H** en la de origen, **D** en la de destino | **ninguna**: las dos patas son cuentas declaradas |

**Y hay un límite que no se puede saltar:** `Movimiento.efecto` deriva `entrada` o `salida` del indicador del banco
y **nunca devuelve `transferencia`**. Una línea sola no puede saber que es la mitad de un traspaso —es una
afirmación sobre un par, y el extracto no la hace—. Se declara, cuando una constancia lo afirma con una referencia
`cuenta_propia`, o se propone, cuando `conciliar` empareja las dos patas y nunca confirma. De ahí que los tres
valores vivan en la **operación** y solo dos en la **línea**, que es el mismo nivel en que los ponen Odoo y
ERPNext: el `payment_type` está en el pago, no en el extracto.

**La contraparte no se declara: se deriva**, porque es la partida doble —`sentido_contraparte` es el otro lado de
`sentido_principal`, y escribirlo dos veces sería un sitio donde pueden discrepar—.

Lo que esto compra, y lo que no:

- **Añadir un libro pasa de auditar medio centenar de `if` a rellenar una fila**, y lo que el motor todavía no sabe
  hacer **se nota**, porque hay que rellenar el campo y no hay con qué. Esa mitad es la que más vale: la tabla es
  también un inventario de lo que falta.
- **Un booleano ya no se interpreta: para.** Es deliberado — un `True` que se colara elegiría la rama equivocada en
  silencio, que es justo lo que la mayor viene a cerrar. Y **omitir el libro tampoco vale**, que era el defecto de la
  firma y era el error.
- **No acercó el asiento de un movimiento bancario, y la predicción se cumplió.** Decía aquí que las de
  entonces parten de un `Comprobante` y preguntan cosas que un extracto no tiene —sigla, IGV, detracción,
  cliente o proveedor—, así que un pago necesitaría **su propio camino de generación y no un tercer valor
  en este eje**. Es exactamente lo que pasó: desde la 12.7 ese camino es `asiento/movimiento.py`, hermano
  de `motor.py` y no una rama suya, porque no comparten ni una regla. Lo dice `ROLES_DEL_MOTOR` desde la
  1.1: «de un comprobante no sale una depreciación ni un pago».

**Lo que la tabla no absorbió, y por qué.** De los rasgos solo se preguntan tres veces `es_venta`, y son los
honestos: los sitios donde el **procedimiento** difiere y no solo un dato —el orden de las líneas de una venta
(`asiento/comprobante.py`), la clasificación (`asiento/resolucion/clasificacion.py`) y la rama de venta de `clase_de_igv`
(`tributos/igv.py`)—. Un rasgo más para disimularlos sería peor: diría que son datos cuando son procedimientos.

Y **sigue habiendo `libro.es_venta` por el núcleo**, que es otra cosa y conviene no confundirla: son módulos que
tienen el `Libro` en la mano y nunca recibieron el booleano por parámetro. Se reparten en dos grupos, y solo uno
preocupa:

- **Un formato con exactamente dos variantes**: el TXT del SIRE es el RVIE o el RCE (`comprobantes/sire_txt.py`,
  `catalogos/sire.py`, `drivers/sire/txt.py`), en un XML la contraparte es el adquirente o el emisor
  (`comprobantes/xml_ubl.py`), el nombre del archivo lleva VENTAS o COMPRAS (`drivers/kit/nombres.py`,
  `drivers/starsoft/salida.py`), CONTASIS tiene dos juegos de columnas. Un tercer libro no tiene archivo del SIRE que
  leer: ahí la pregunta es del formato, no de la contabilidad.
- **Reglas que solo tiene una venta** (`tributos/validar.py`): están en forma positiva —`if libro.es_venta and …`—,
  así que un libro nuevo se salta la regla de venta en vez de heredar la de compra, que es la dirección segura. La
  única excepción es una palabra de un mensaje, «cliente» o «proveedor», y ahí el peor caso es una frase torcida.

La 9.0 encontró **un** `not es_venta` fuera de eso y lo arregló: `modelo.identidad_de`, que mete el documento de la
contraparte en la identidad de una compra. Importa porque vive en `modelo`, **por debajo** de la puerta que cierra
este apartado, así que era el único sitio donde un libro nuevo heredaba algo sin que nada lo parase. Hoy pregunta
`es_compra`.

Y la guarda sigue puesta donde el eje se calcula: un libro que el motor no origina **detiene** la exportación
(`asiento.faltas.LibroQueElMotorNoOrigina`). La tabla no la sustituye — tiene las filas que tiene, y un tipo del
catálogo sin fila hay que pararlo ahí, no dejar que falle dentro.

## Capas, api y puertas

Desde la 1.0 el motor se ordena en capas, y cada una solo importa de las de abajo. No es una convención:
`tests/test_capas.py` lo comprueba módulo a módulo, y la lista de excepciones está vacía.

```
 ENTRADA                                                         SALIDA (drivers, por canal)
 ERP en otro lenguaje ─HTTP/OpenConta─► puertas/servidor_http ─┐        ┌─ legacy: concar · contasis · starsoft
 Agente de IA ────────MCP────────────► puertas/servidor_mcp ──┼─► api ─► pipeline ─► núcleo ─┼─ sunat:  sire · ple · ple_plan
 Contador ────────────CLI────────────► puertas/cli ───────────┘        └─ erp:    csv · asiento_contable
```

| Capa | Módulos | Qué sabe |
|---|---|---|
| base | `_version`, `_obsoleto`, `_datos`, `errores` | la versión, el aviso de las rutas viejas, los datos empaquetados, la base de los errores |
| núcleo | `modelo/` (el libro, las coerciones, el accesor objeto-o-dict), `comprobantes/` (el comprobante y su identidad, su imputación, sus lectores —`xml_ubl`, `sire_txt`, `archivos`— y cuánto suma un mes), `tesoreria/` (su espejo del otro lado: la cuenta bancaria, el movimiento, su imputación y el cuadre de saldos), `catalogos/` (los comprobantes, los tributos, el SIRE, el PLE, el contribuyente), `tributos/` (`igv`, `detracciones`, `validar`, `comparar_sire`), `contable/` (`partida_doble`, `resumen.por_cuenta`), `asiento/` (`comprobante` y `movimiento`, los dos motores, con `comun/` debajo y `resolucion/` dentro: lo configurado, lo imputado, la clasificación, los requisitos y la numeración), `pcge/`, `lectores/` (la ruta de siempre de los tres lectores), `sunat/` (la API del SIRE como funciones puras: se sabe la URL, no se llama), `aplicaciones` (cuánto de un pago cancela un documento: el puente entre los tres libros), `configuracion` | contabilidad peruana, sin disco, sin red y sin reloj |
| drivers | `drivers/` (`contrato/` —su taxonomía, sus protocolos, sus accesores y su examen—, `kit`, cada driver) | el formato de un destino, nada de contabilidad |
| pipeline | `pipeline/` (`preparacion/` —el documento, la configuración, las entradas y los pasos de un mes—, `lectura`, `seleccion`, `armado`, `salida`, `diagnostico`) | cómo se prepara y se orquesta un mes, escrito una vez |
| api | `api/` (`operaciones`, `tabla`, `documento`, `errores`, `openconta`, `esquemas/`) | lo que una aplicación usa; cada nombre con su firma, congelados |
| puertas | `puertas/` (`cli`, `servidor_mcp`, `servidor_http`, `comun`) | un protocolo; solo hablan con la api |

- **El pipeline** es el único dueño de la preparación: del documento al libro y los comprobantes, la configuración
  aplicada hacia un destino con la imputación dentro, las claves previas, la selección de lo que sale, lo que exige el
  destino y lo que no cabe en su formato, la numeración, las líneas con su índice, el cuadre y la huella. `revisar`,
  `diagnosticar`, `generar_asiento` y `exportar` recorren los mismos pasos, cada una hasta donde le toca;
  `generar_asiento` es `exportar` sin escribir el archivo.
- **La api** (`contaperu.api`) habla en documentos `open-accounting`: el documento primero, lo demás por su nombre,
  `driver` sin valor por defecto. Su superficie queda congelada con su firma (`tests/test_superficie_publica.py`), y
  debajo queda el nivel de extensión —`modelo`, `asiento`, `drivers.contrato`, `drivers.kit`…— para quien escribe un
  driver. Cada error hereda de `ErrorContaperu` y lleva una `clave` estable; `api.problema` lo dice como RFC 9457.
- **La tabla de operaciones** (`api.OPERACIONES`) declara de cada operación su entrada (JSON Schema 2020-12, sacada de
  su firma), su salida, su ruta HTTP y su nombre en el MCP. De ella salen las herramientas y recursos del MCP, las
  rutas de la puerta HTTP y **OpenConta**, el contrato en formato OpenAPI 3.1 que se versiona en
  `api/openconta.json`.
- **Las puertas** traducen un protocolo y delegan. Comparten en `puertas/comun.py` los topes y la defensa del `Host`,
  y `tests/test_frontera.py` impide que el núcleo importe una puerta, el SDK del MCP, la red o el reloj. Las tres dan
  el mismo documento y el mismo diagnóstico.
- **Las rutas de la 0.10** (`operaciones`, `generar`, `cli`, `servidor_mcp`, `formato`, `drivers.concar.construir`)
  las retiró la 2.0, sin tocar la superficie pública de la 1.0: ninguna versión publicada llegó a ofrecerlas, porque
  la 0.x nunca estuvo en PyPI. La **4.0** retiró lo que avisaba desde la 3.10 —el nombre `asiento_neutral` del driver—
  y dos promesas que llevaban dos mayores sin cumplirse: la forma `construir` de un driver y el `CANAL` opcional. La
  **7.0** retiró los seis atajos que la 6.4.0 dejó en la raíz al agrupar el núcleo en `tributos/` y `contable/`, con
  63 nombres de la superficie congelada: es la primera vez que una retirada se cobra en la mayor siguiente a la que
  la anunció, que es como debería ir siempre. El mecanismo con que se deprecia algo sigue en `_obsoleto.py`, sin
  usuarios y a propósito, para la próxima vez; `RETIRO` dice ahora `"13.0"`.
- **El portal** (otro repositorio) usa la api y el nivel de extensión; el `resumen` de cada exportación, que guarda tal
  cual, conserva sus claves.
- **Lo peruano, a la vista** (hito J0): qué módulos importan uno peruano queda congelado en
  `tests/fixtures/capas/acoplamiento_pe.json`, y un acoplamiento nuevo no entra sin verse. Separar la jurisdicción
  (J2-J6) espera un cliente real fuera del Perú.

## Cómo se enchufa un driver

Un driver expone `NOMBRE`, `CANAL`, `FORMATOS`, `OPCIONES`, `nombre()` y **una** forma (`drivers/contrato.py`):

| Forma | Recibe | Para qué |
|---|---|---|
| `linea(c, libro, idx, opciones) -> str` | un comprobante | un registro a SUNAT línea a línea (el SIRE) |
| `desde_comprobantes(libro, comprobantes, config, opciones)` | los comprobantes y la configuración, con la imputación | el registro de un sistema contable que arma el asiento él mismo (CONTASIS) |
| `desde_lineas(libro, lineas, config, opciones, *, indice=())` | las **líneas del asiento**, numeradas y cuadradas, y el índice de cada comprobante | **todo driver de asientos**, CONCAR incluido desde la 1.0 |

Con `desde_lineas` el pipeline arma el asiento, lo numera y exige que cuadre **antes** de llamar al driver; el driver
solo traduce. Si su firma acepta `indice`, recibe además qué tramo de líneas es de qué comprobante y una **cabecera**
con sus hechos (`asiento.indice.Cabecera`: identidad, contraparte, glosa, base, IGV y total en texto exacto), fuera de
las líneas y de la huella. Es lo que permite escribir en cada fila lo que la línea no guarda: CONCAR saca de ahí la
glosa de su columna F y la tasa entera de la AO, que se redondea una sola vez desde el IGV y la base del comprobante.

**El canal dice a quién se entrega** (la familia dice qué se entrega), y el contrato hace cumplir sus reglas:

| Canal | Qué es | Reglas | Drivers |
|---|---|---|---|
| `legacy` | un sistema contable instalado que importa un archivo | lleva cuentas; declara `EXIGE` | concar, contasis, starsoft; SISCONT cuando entre |
| `sunat` | un registro o libro que se presenta a SUNAT | forma `linea` (una fila por comprobante) o `desde_lineas` (una fila por línea del asiento) | sire, ple, ple_plan |
| `erp` | un ERP, por el formato neutral del estándar | forma `desde_lineas` | csv, asiento_contable |

**Una palabra por destino, y es el canal** (8.0). Hasta la 7.x había una segunda tabla, `contrato.GRUPOS`, que lo
traducía a «SIRE», «Legacy» y «ERP» para quien integra, y `drivers_disponibles` devolvía las dos. Se retiró porque
eran dos vocabularios para lo mismo y el de fuera mentía: ver abajo.

**Por qué `sunat` y no `sire`.** Son dos regímenes distintos de SUNAT, no uno:

| | Qué manda | Norma |
|---|---|---|
| **SIRE** | compras y ventas: el RVIE y el RCE | RS 112-2021 (anexo 2) y RS 040-2022 (anexo 8) |
| **PLE** | el Libro Diario y los demás libros, y el plan de cuentas | RS 234-2006 (art. 6, formato 5.1) y RS 286-2009 (anexos 2 y 3) |

El canal es el mismo —se entrega a SUNAT, en texto— y el régimen no. Hasta la 7.x los tres drivers se presentaban
como grupo `sire`, así que **el motor llamaba SIRE al Libro Diario del PLE**. «Ése es el universo del SIRE, no el de
SUNAT» (John, 1-oct-2026, al traer un Libro Diario presentado y aceptado). Y lo que el canal fija sigue siendo lo de antes: se escribe **texto para
SUNAT**, no un Excel ni un JSON. Lo que cambió en la 4.2 es de qué es su FILA: el SIRE escribe una por comprobante
(forma `linea`, sin cuentas ni configuración) y el Libro Diario del PLE una por línea del asiento (`desde_lineas`,
con cuentas y con su CUO), porque 595 de los 1441 asientos de un mes real no vienen de ningún registro de compras ni
de ventas.

`api_erp` —escribir el cuerpo de la API de un ERP moderno— queda **reservado**: el contrato lo rechaza, y el
criterio para admitirlo es que haya un formato que `erp` no pueda llevar. Tuvo un hito detrás, A5, que se retiró el
10-oct-2026 con la investigación que lo sostenía; la reserva no dependía de él. Ojo a la pareja: `erp` se admite y
`api_erp` no, a una letra de distancia. **Un driver de terceros sin `CANAL` no se registra** desde la 4.0: es un
incumplimiento del contrato y `drivers.de_terceros` lo deja fuera con su `AvisoDriver`.

**El vocabulario dice con qué palabras llegan las líneas** (`VOCABULARIO`, 1.1). `legacy`, el de siempre: siglas,
sub-diarios, correlativos y el documento comodín de la detracción, lo que importan CONCAR y los de su familia.
`neutral`: las líneas del estándar sin nada de eso, por `rol` y código SUNAT. Es el de `asiento_contable`, la salida para
un ERP nuevo, que parte del estándar en vez de reimplementar el IGV. Un driver neutral es de canal `erp`, no
declara claves legacy en su configuración y el núcleo solo le exige la cuenta. La contabilidad es la misma que la de
CONCAR: `tests/test_driver_asiento_contable.py` compara cuentas, sentidos, importes y roles línea a línea.

Y **declara qué exige** (`EXIGE`): lo que ese ERP no puede importar sin y que el núcleo, si no se lo dicen, deja pasar
—`centro_costo` en las cuentas que lo llevan, `moneda` con código en el destino; en uno de registro, `centro_costo` y
`cuenta_unica`—. La cuenta contable la exige el núcleo a todo driver que lleva cuentas, y la equivalencia del tipo, de
la que sale el sub-diario, a los de asientos. Con eso `diagnosticar` decide si un mes está listo **para ese destino**,
y el pipeline lo hace cumplir antes de armar nada. Lo que su formato no puede llevar —una moneda, un código más largo
que su columna— lo declara en `no_caben`: `diagnosticar` lo dice antes y el pipeline se niega con `NoCabe`, en toda
forma que lleva cuentas.

Y **declara lo que se configura**: las claves de su sección (`CONFIGURACION`) y en qué columnas de su archivo puede ir
un dato (`COLUMNAS_ELEGIBLES`). La configuración se guarda con lo general en la raíz y una sección por sistema, se
valida entera y el núcleo recibe lo general con la sección del destino encima. Un driver solo lee lo que declara, y el
núcleo solo lo general, lo del asiento y `MONEDAS_CODIGO`: lo vigila `tests/test_contrato_drivers.py`. Lo que todos los
drivers comparten para escribir —las opciones, el formato de texto, las celdas y el libro de Excel— está en
`drivers/kit/`.

Eso es también el reparto que ve quien integra: el documento trae los hechos, la imputación la decisión
contable, la sección del driver el vocabulario de su sistema y `datos_originales` lo que nadie interpreta.
Cuál de los cuatro acepta variables nuevas está en `INTEGRAR.md`, §«Quién aporta cada variable».

Se publica de dos maneras:

- **Como paquete propio**, por entry points (`[project.entry-points."contaperu.drivers"]`). El registro lo busca la
  primera vez que se consulta; los de serie ganan ante un nombre repetido y uno que no cumple el contrato se ignora con
  un `AvisoDriver` en vez de tumbar el registro.
- **Dentro del repositorio**, en `drivers/<sistema>/` y en `DE_SERIE`. Para eso hace falta un archivo real que ese ERP
  haya aceptado, salvo en un driver cuyo formato es el propio estándar, como `asiento_contable`: lo valida su esquema.

Esté donde esté, `tests/test_contrato_drivers.py` lo examina: cumple el contrato, declara su canal y exporta el golden
de compras con el asiento cuadrado.

### STARSOFT: qué se sabe y qué falta

- **Qué se sabe.** STARSOFT Desktop importa un **TXT de palotes, suelto** —35 campos en compras, 27 en
  ventas—, no un Excel. Cada fila es una cuenta con su debe o haber y las filas de un comprobante comparten
  cabecera. Desde el 22-sep-2026 el formato está recalcado de **su documentación oficial** —los manuales de importación
  del fabricante, que no entran al repositorio por licencia y están volcados columna por columna en
  `contaperu/drivers/starsoft/datos.py`—, que sustituyó a los dos vídeos con los que nació: sus sub-diarios (`04` compras, `03` ventas), sus siglas, la
  columna `DESTINO` —el destino del IGV de la adquisición, que CONCAR no tiene y que hizo crecer la cabecera del
  índice en la 1.4.0—, sus cuentas de ocho dígitos y la detracción, que en STARSOFT son **campos de la fila del
  proveedor y no dos líneas de asiento**.
- **Qué falta.** Ya no falta el mes: STARSOFT importó uno de compras el **7-oct-2026** y uno de ventas el
  **8-oct-2026**, y los dos destaparon cosas que ningún vídeo decía —el TXT va suelto, sin el ZIP, y el archivo de
  ventas empieza por `V` y no por la `C` de compras—. Lo que falta son valores, no la aceptación. De sus ocho
  siglas, **seis constan** en el manual
  (`FT`, `BV`, `CC`, `CD`, `TK`, `RC`) y **dos siguen marcadas `[por confirmar]`** —`02` (RH) y `05` (BA)—, que no
  aparecen en ningún ejemplo; el manual dice además que el tipo es «el que tiene registrado TU sistema», así que se
  cotejan contra el maestro de cada contribuyente y no se fijan aquí.
- **Su API Web no se hace** (John, 10-oct-2026): fue el hito A5 y se retiró, con el motivo escrito en el §6 de
  [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md). Si alguien la escribe fuera, lo que resolvió el driver de escritorio le sirve
  casi entero, y el envío y los reintentos son de la aplicación y no del motor —la identidad y la huella de cada
  comprobante (`_exportacion.comprobantes`) son la clave de idempotencia—.

### Las mejoras se evalúan, y lo que haga falta se cambia

Nada aquí está cerrado por principio. Si un driver nuevo necesita un campo en la cabecera, un valor en un catálogo o
incluso otra forma en el contrato, **se estudia y entra si mejora el motor**: así creció la cabecera del asiento en la
1.4.0, porque STARSOFT pedía un dato que el estándar ya tenía y que no llegaba a un driver de asientos.

Lo único que se pide es **saber lo que cuesta**, para no romper en silencio a quien ya integra:

| Cambio | Lo que cuesta |
|---|---|
| **Añadir** — un campo en la cabecera, un valor por defecto, un driver nuevo | Nada se rompe. Sale en una versión menor |
| **Cambiar el estándar** | Una fuente —una norma, una resolución, un archivo que un sistema aceptó— y su enmienda, porque otros lo leen |
| **Cambiar la fórmula de la huella** | Invalida todas las guardadas por quien las persista: va anunciada como cambio de comportamiento en el `CHANGELOG` y con su versión |

No son prohibiciones: es el precio de cada cambio, escrito antes de hacerlo. Quien lo paga, lo cambia.

### Lo que queda preparado, sin símbolo público

| Punto | Qué hay en la 1.0 | Hito |
|---|---|---|
| Lectores de terceros | nombre reservado `lectores.contrato` y grupo `contaperu.lectores`: identificar, extraer, deduplicar | B7 |
| El banco | **ya no está reservado**: `contaperu/tesoreria/` existe desde la 8.2 con la cuenta bancaria, el movimiento de un extracto, la constancia de un pago y el cuadre de lo que el banco declara; desde la 12.9 el motor **arma su asiento** para un ERP (`asiento/movimiento.py`, con el dispatch en `pipeline/armado`) y desde la 12.10 **escribe su archivo** por el driver neutral, con el ida y vuelta cerrado. Lo que sigue fuera es leer un banco concreto, conciliar, y llevarlo a un sistema legacy, que espera el sub-diario de bancos; y los conectores nunca entran al paquete | D1-D8 |
| La API del SIRE | **ya no está reservada**: `contaperu/sunat/` arma la petición de cada una de las once operaciones, lee el estado de un ticket y clasifica el rechazo de SUNAT, todo desde su catálogo y sin salir a la red (8.1). Lo que **sigue fuera** es enviar: el socket, los reintentos, el reloj del ticket y las credenciales. Y lo que **todavía no está** son los lectores de la forma de cada respuesta: eso no lo sostiene un catálogo, lo sostendría una respuesta real, y no hay ninguna guardada | C-SIRE |
| Reglas de SUNAT como datos | `_datos.leer_json("datos/sunat/…")`; `catalogos` las cargará sin cambiar sus nombres | C1-C2 |
| El contribuyente como datos | `catalogos.regimenes_tributarios()` y `catalogos.cronogramas_de_vencimiento()`: en qué régimen tributa y cuándo le vence el mes, **cada regla con la cita de su artículo** y un cargador que no arranca sin ella. Son catálogo y no campo del estándar porque «qué libros estoy obligado a llevar» se pregunta sin un documento delante. El cronograma cabe en un núcleo sin reloj porque no es un reloj: dado un periodo y un dígito de RUC devuelve una fecha | C13 |
| CDR y no domiciliados | `lectores/cdr.py` reservado; los roles pueden crecer sin romper un driver | C3, C12 |
| Otra jurisdicción | J0 como test, J1 como efecto de las capas, `jurisdicciones/pe` reservado, `open-accounting` 3.3 para J5 | J0-J6 |
| La API de un ERP moderno | canal `api_erp` reservado y rechazado; su hito se retiró el 10-oct-2026 | — |

## La capa para agentes

`diagnosticar` es la operación pensada para que un agente —o una persona con prisa— pregunte **antes**
de exportar y reciba, en una sola respuesta: si el mes está listo y por qué no, qué bloquea y qué avisa
por serie-número, qué falta para el destino (cuenta, centro de costo, tipos sin sigla, monedas,
correlativos, un reparto que no suma la base o que el destino no admite, y lo que no cabe en su formato: la tabla
es `asiento.FALTAS`), qué detracciones esperan constancia, el resumen por contraparte y desde qué correlativo
arranca cada sub-diario. No corrige ni inventa: describe. Está en la fachada, en el MCP y en la CLI, y
no añade ninguna regla contable —reúne comprobaciones que ya existían y las cuenta en vez de lanzarlas.

Desde la 0.8 responde además **para qué destino** (`exige`) y **a quién pedir** lo que falta
(`que_falta[].pedir_a`: `contador` si se resuelve mirando el documento o el plan de cuentas; `sistema`
si es configuración del destino o un dato público que no está en el papel; `proveedor` reservado). Y
cada exportación deja su **huella** (`_exportacion.huella`, `asiento/huella.py`): la misma
exportación repetida lleva la misma, que es lo que permite avisar de que ese contenido ya salió.

Esa es la forma en que crecerá esta capa: **cada pregunta de un agente se responde con reglas que ya
tienen fuente**, nunca con una regla nueva escrita para el agente.

## Lo que no se negocia

1. **Ninguna regla contable sin fuente.** La norma, la resolución o el archivo real que la justifica va
   al lado, en el código. Un refactor mueve reglas; no las escribe.
2. **El Excel de CONCAR validado no cambia.** `test_snapshot_concar.py` lo vigila celda a celda.
3. **Un tipo sin sigla detiene la exportación.** Nunca se inventa una sigla.
4. **Sin red, sin disco, sin estado, sin reloj en el núcleo.** `test_frontera.py` y `conftest.py`.
5. **`Decimal` de punta a punta**, `float` solo en el borde de escritura del archivo.
6. **Nunca datos reales en el repositorio.** Dos RUC seguros: `20131312955` y `20601234567`.
7. **Código y comentarios en español**, porque es el idioma del dominio.

## Lo que no se hace, y por qué

La otra mitad de lo de arriba: lo que se estudió y se dejó fuera. Cada línea lleva su motivo, porque
un descarte sin motivo se vuelve a proponer cada año — y porque el código los cita: `resumen.py` y
`api/operaciones.py` remiten aquí para explicar por qué el motor no convierte monedas.

Sale de la investigación del ciclo contable de setiembre de 2026, que vivió en
`INTEROPERABILIDAD.md` hasta el 8-oct-2026; al retirarlo, los motivos se escribieron aquí en vez de
seguir remitiendo a sus secciones.

| Qué | Por qué no |
|---|---|
| Emparejar órdenes de compra y recepciones (las tres vías de EE. UU.) | Necesita estado y las guías de remisión, que están fuera por decisión. De ahí solo se toma la tolerancia en dos medidas |
| Un buzón, estados de borrador o la aprobación de facturas | Son de la aplicación; el motor ya dice lo que falta |
| Redes EDI, portales, DBNAlliance o Peppol dentro del motor | El Perú valida antes de emitir, y un canal de entrega es transporte |
| Leer `cbc:AccountingCost` (BT-19/BT-133) | **Espera un XML real que lo traiga**: no hay evidencia de que los peruanos lo lleven |
| Imputar por ítem de la factura | **Hueco declarado.** Hoy lo cubre el reparto de la imputación |
| La factura negociable como canal del motor | **En vigilancia**: la conformidad la registra SUNAT y la anotación en cuenta es de CAVALI |
| Un lenguaje de requisitos declarativos | ERPNext y Odoo lo necesitan porque ellos **son** el destino; este motor escribe hacia un destino que ya guarda esa exigencia en su plan. Tomar el dato es más corto y no inventa reglas |
| Los estados de intercambio de OCA y el `blocking_level` de Odoo | Son estado de la aplicación, y la gradación error/aviso ya existe (`Observacion.nivel` y `FALTAS`) |
| TIN Matching o el padrón en línea, y retenciones calculadas por el motor | Lo primero es red; lo segundo, una regla sin un comprobante que la muestre |
| Llamar CUO a la identidad del comprobante, o hacerla un hash opaco | El CUO es del software que genera el PLE, y una clave legible se puede leer en un error |
| Una huella de la configuración aplicada | Metería las imputaciones en la huella y no tiene caso |
| Log con hash encadenado, secuencia sin huecos, fechas de bloqueo | Son estado: de la aplicación o del ERP de destino, nunca del motor |
| Guardar aparte el tipo de cambio usado, o tres fechas nuevas | Ya van en la línea y en `_exportacion` |
| `Idempotency-Key`, webhooks y sincronización incremental | El motor no habla con otra API con estado |
| Redis como recomendación contable | No hay una fuente contable que la respalde; es nota de ingeniería para la aplicación |
| La cuenta transitoria inmediata (Odoo) | El destino suma; primero se empareja |
| *Embeddings* y aprendizaje estadístico dentro del motor | No son deterministas: son de la aplicación, y el motor recibe lo aprendido como datos |
| Doble aprobación o un registro de cuentas bancarias de proveedores | Son estado |
| Un resumen anual por tercero, o la DAOT | El libro es mensual, y la exclusión de lo anotado en registros electrónicos la vacía |
| Sales tax, nexo o certificados de exención | No hay caso peruano |
| Saber si un mes está en plazo, y los plazos de conservación | **Necesita el hoy**, y el núcleo no tiene reloj (`tests/test_frontera.py`). Si queda tiempo o hay mora lo calcula quien tiene la fecha |
| El calendario de vencimientos como tal | **Acotado el 7-oct-2026**: un calendario no es un reloj —dado un periodo y un dígito de RUC devuelve siempre la misma fecha—, así que entró en la 6.1.0 como datos, con los dos anexos de la RS 000281-2022. Lo descartado sigue siendo la pregunta de arriba |
| Asentar el tipo 91 como costo, a imitación del *use tax* | En el Perú es crédito con requisitos |
| **Convertir** monedas dentro de un resumen | Sería una cifra nueva sin caso. Lo descartado es convertir, **no** informar cada moneda por su lado, que es lo que `resumen` hace desde la 3.4.0: sus totales son un mapa por moneda y ninguna clave suma dos |
| Numscript o cualquier lenguaje de reglas contables (Formance) | Las reglas viven en código, con su fuente al lado (`CONTRIBUTING.md`) |
| Importes en enteros de la unidad mínima (TigerBeetle) | El texto exacto con `Decimal` ya lo resuelve y no pierde la moneda de vista |
| Modelos definidos por el usuario y *field mappings* por conexión | El modelo lo define SUNAT, y dónde va cada dato ya lo resuelven `COLUMNAS_ELEGIBLES` y la configuración por sistema |
| Del MCP: tareas, *sampling*, *roots*, prompts y los interruptores de escritura | Unas herramientas puras de solo lectura no los necesitan |
| La jurisdicción en la configuración | Es del libro |
| Un motor de impuestos genérico, con tasas como datos sin fuente | Ninguna regla contable sin fuente: es la primera regla de la casa |
| Adelantar la puerta a otra jurisdicción (J1-J6) | **Espera un cliente real fuera del Perú** |
| Traducir al inglés el vocabulario del estándar | El español es el idioma del dominio |

## Hoja de ruta

El orden en que crece el motor, y el dato o el código que destraba cada paso, viven en
[HOJA-DE-RUTA.md](HOJA-DE-RUTA.md): una fase para afinar lo que existe y seis frentes —los drivers de SISCONT y
STARSOFT, la puerta para que cualquier ERP integre el motor, leer y validar más con las reglas oficiales de SUNAT, el
banco como punto de partida del proceso contable, un estándar que mejora siempre y la puerta a otra jurisdicción,
condicionada a un cliente real fuera del Perú—, cada uno con sus hitos y su criterio de salida. Aquí no se repiten. La
investigación y el diseño de cada pieza, ordenados por el ciclo contable y con el de EE. UU. como referencia, están en
el §8 de [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md), y lo tomado de las APIs de EE. UU., en
[REFERENCIAS.md](REFERENCIAS.md).

La idea que la ordena **cambió de eje el 10-oct-2026** (John), y conviene decir las dos versiones porque la
primera explica cómo se construyó esto. Durante un año fue: primero la compatibilidad con los sistemas que ya
existen, después un lenguaje común y, encima, las preguntas de un agente. Hoy es al revés: **el lenguaje común es el
centro y el motor es la base de cualquier ERP**, con la capa hacia los legacy intacta y sin plazo de retiro, porque
nadie tiene que cambiar de sistema contable y el cambio no puede ser abrupto.

Lo que no cambia es cómo se construye: con casos reales detrás, cada regla con su fuente, y sin anunciar lo que no
está en producción. El orden en que crece, con esa prioridad nueva, está en [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md).
