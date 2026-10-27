# ContaPerú · contabilidad peruana de código abierto

[![tests](https://github.com/contaperu/contaperu/actions/workflows/tests.yml/badge.svg)](https://github.com/contaperu/contaperu/actions/workflows/tests.yml)
[![licencia MIT](https://img.shields.io/badge/licencia-MIT-green.svg)](LICENSE)

**Motor abierto para la contabilidad peruana.** Lee los comprobantes electrónicos de SUNAT —factura, boleta, notas de
crédito y débito, recibo por honorarios—, valida el IGV y las detracciones, arma los **asientos contables en partida
doble** y entrega lo que pide cada destino: a un **ERP** el asiento en el propio estándar, sin vocabulario de
ningún sistema; a **SUNAT** el TXT del **SIRE** (RVIE y RCE) y los libros del **PLE**; y a los sistemas instalados el
Excel de **CONCAR** o de **CONTASIS** y el TXT de **STARSOFT**. Sin base de datos, sin estado, sin llamadas a la red: entra
un JSON, sale un JSON o un archivo.

**La contabilidad automatizada no es un problema de cada empresa: es de arquitectura colectiva.** Un estándar abierto y
un motor abierto, construidos entre todos, para los sistemas que ya existen y para los ERP que vienen.

**La base de cualquier ERP, y encima de tu sistema contable sin reemplazarlo.** Quien construya un ERP nuevo no
tiene que reimplementar la contabilidad peruana: el IGV y sus destinos, las detracciones en sus dos tiempos, los
sub-diarios, la validación contra las reglas de SUNAT y la partida doble ya están, con un test por regla y la norma
citada al lado de cada una. Y **la capa hacia los sistemas que ya existen se queda, sin plazo de retiro**: nadie
tiene que dejar CONCAR ni cambiar su forma de trabajar, y el motor le quita la digitación. Las dos cosas a la vez —
primero fue solo la capa, y desde el 10-oct-2026 el eje es la base.

Licencia MIT. Se dona a la comunidad contable peruana.

---

## Por qué abierta: arquitectura colectiva

Hasta hoy, cada empresa ha resuelto la automatización contable por su cuenta: su integración con SUNAT, su plantilla
para CONCAR, su macro para CONTASIS, su script para el ERP de turno. Son miles de soluciones aisladas que hacen lo mismo
—leer un comprobante, validar el IGV, armar el asiento, exportarlo— y que vuelven a equivocarse en los mismos casos: la
detracción, la nota de crédito, el comprobante en dólares.

Eso no se arregla con una mejor organización interna de cada empresa. Se arregla con **una base común y abierta**:

- **Un estándar abierto**, [`open-accounting`](estandar/LEEME.md), para que todos los sistemas hablen el mismo idioma.
- **Un motor abierto** que aplica las reglas contables peruanas una sola vez, cada una con su fuente, y que cualquiera
  puede revisar y mejorar.
- **Salidas para todos:** los ERP que vienen, que no tendrán que reinventar el IGV porque nacerán sobre un
  estándar; el SIRE y el PLE; y los sistemas legacy mientras evolucionan, sin que nadie tenga que abandonarlos.

Nadie queda amarrado a un proveedor, y lo que aprende uno lo aprovechan todos.

### Qué resuelve, en palabras de contador

El software contable peruano nació en los noventa y no se habla entre sí: cada sistema importa su propio archivo plano,
con sus columnas y sus siglas. Cuando además aparece una IA capaz de leer cien facturas en un minuto, el cuello de
botella deja de ser la lectura: **no hay un formato común y validado donde poner el resultado**, y una cuenta mal puesta
o un asiento descuadrado se descubre meses después.

ContaPerú se ocupa de lo que hoy se hace a mano:

- **El registro de compras y el de ventas**, a partir de los XML que emite SUNAT o de la propuesta del SIRE, sin
  digitar comprobante por comprobante.
- **El asiento de cada comprobante**, con los casos que suelen salir mal: IGV, detracción, retención de cuarta
  categoría, notas de crédito, comprobantes en dólares y extemporáneos.
- **Revisar antes de exportar.** Dice qué falta para tu sistema —una cuenta, un centro de costo, una sigla, un
  correlativo— y a quién hay que pedírselo, por serie-número y sin corregir ni inventar nada.
- **El archivo listo para importar**: el Excel de asientos de CONCAR, el registro de CONTASIS o el TXT de reemplazo de
  la propuesta del SIRE.

No es un diseño en papel: el motor lleva un año generando el Excel de CONCAR y el TXT del SIRE de empresas reales, y
cada regla lleva al lado la norma o el archivo real que la justifica.

---

## Cómo funciona

![Arquitectura colectiva: los comprobantes electrónicos y la propuesta del SIRE entran al estándar abierto open-accounting; de ahí al motor, que la comunidad abierta mejora; y el motor entrega a tres canales: un ERP (el asiento en el propio estándar, por JSON, CSV o HTTP), SUNAT (el SIRE y el PLE) y los sistemas legacy (CONCAR, CONTASIS y STARSOFT)](diagramas/arquitectura-colectiva.svg)

ContaPerú no es una aplicación que se abre: es el motor que va **dentro de un ERP externo**, sea un sistema contable en
la nube, un portal para estudios o el sistema de gestión de una empresa. En el ERP externo el contador carga, revisa y
descarga; el motor hace la contabilidad y no guarda nada. Lo del mes entra de dos formas, y las dos llegan al mismo
documento:

1. **Las facturas en XML.** El motor lee el XML UBL 2.1 de cada comprobante, suelto o en ZIP, y lo lleva al documento
   común [`open-accounting`](estandar/LEEME.md).
2. **La propuesta del SIRE.** El TXT de SUNAT ya empaqueta todos los comprobantes del contribuyente en el periodo: con
   ese solo archivo, el mes entero llega a `open-accounting`.

Desde ese documento, el motor valida cada comprobante, arma el asiento y entrega lo que pida cada canal de destino:

- **ERP:** los sistemas nuevos, en cualquier lenguaje. Reciben el documento `open-accounting` con su asiento **sin
  vocabulario legacy** —sin siglas, sub-diarios ni correlativos, por rol y código SUNAT— (driver `asiento_contable`), el
  CSV con las líneas de diario, o todo por la puerta HTTP con el contrato OpenConta. **Es el canal que ordena el
  proyecto desde el 10-oct-2026**: lo que crece primero es lo que un ERP necesita y todavía no tiene.
- **SUNAT:** sus dos regímenes. El **SIRE**, con el TXT de reemplazo del registro de ventas (RVIE) y del de compras
  (RCE), listo para subir; y el **PLE**, con el Libro Diario y el detalle del plan contable.
- **Legacy:** los sistemas contables instalados que importan un archivo. Hoy, los asientos de CONCAR y de STARSOFT
  y el registro de CONTASIS; SISCONT espera un archivo que ese sistema haya aceptado.

Cualquier entrada puede terminar en cualquiera de los tres canales. Las cuentas, los sentidos del debe y el haber y la
detracción los decide el motor una sola vez, igual para todos los destinos. Y al costado del motor está la comunidad:
quien lo usa también lo mejora ([Cómo aportar](#cómo-aportar)).

## El motor por dentro

![ContaPerú por dentro: el contador sube al ERP externo los XML o el TXT de la propuesta del SIRE; el ERP le pasa al motor el documento open-accounting, con sus comprobantes y su imputación; el motor entra por sus puertas a la API pública 1.0, el pipeline se apoya en el núcleo peruano y los drivers lo traducen al SIRE, CONCAR, CONTASIS o de vuelta al ERP](diagramas/arquitectura-del-motor.svg)

- **Arriba, tu sistema:** el **ERP externo** recibe lo que sube el contador, los XML o el TXT de la propuesta del SIRE.
  Guarda, revisa y descarga: todo lo que necesita red, disco o credenciales vive ahí, no en el motor.
- **En el medio, el documento común:** lo que el ERP le pasa al motor es un documento
  [`open-accounting`](estandar/LEEME.md), con el libro (RUC, periodo y cuál de los cuatro: compras, ventas, tesorería o diario) y sus hechos. Tiene su
  [esquema formal](estandar/open-accounting.schema.json). La imputación (la cuenta y el centro de costo de cada
  comprobante) y la configuración contable de la empresa no van dentro: llegan aparte, por el `id_externo` de cada
  comprobante.
- **El motor**, de arriba abajo:
  - cuatro **puertas**: Python, la línea de comandos, MCP para asistentes de IA y HTTP para un ERP en cualquier
    lenguaje, con el contrato OpenConta;
  - todas llaman a la **API pública**, que no cambia de nombres ni de firmas dentro de una versión mayor;
  - el **pipeline** lee, prepara, arma y diagnostica cada mes, y se apoya en el **núcleo peruano**, lo único que sabe
    contabilidad: validación, IGV, asiento y PCGE;
  - los **drivers** traducen al formato de cada destino sin decidir ninguna cuenta.

  Un driver de la comunidad se enchufa sin tocar este repositorio.
- **Abajo, los destinos:** el TXT del SIRE, los asientos de CONCAR, el registro de CONTASIS o el resultado de vuelta al
  ERP, en JSON y con su diagnóstico.

### Cómo está organizado el código

El paquete se entiende con **dos ejes**, y casi todo lo demás se deduce de ellos.

**El primero son las capas**, de abajo arriba. Cada una solo puede usar las de abajo, y eso no es una costumbre:
`tests/test_capas.py` lo comprueba fichero a fichero y se pone rojo si alguien se salta el orden.

| Capa | Carpetas | Qué sabe | Qué NO puede |
|---|---|---|---|
| **base** | `errores`, `_datos`, `_version` | los errores, leer los datos empaquetados | nada de contabilidad |
| **núcleo** | `modelo`, `comprobantes`, `tesoreria`, `asiento`, `contable`, `tributos`, `catalogos`, `pcge`, `sunat`, `aplicaciones`, `configuracion`, `vocabulario` | **toda la contabilidad peruana** | tocar disco, red o reloj; saber a qué ERP va |
| **drivers** | `drivers/` (ocho destinos + `contrato` y `kit`) | el formato de un sistema concreto | decidir una cuenta |
| **pipeline** | `pipeline/` | cómo se orquesta un mes | ser llamado directamente desde fuera |
| **api** | `api/` | la superficie pública y congelada | —— |
| **puertas** | `puertas/` (Python, CLI, MCP, HTTP) | hablar un protocolo | saltarse la api |

**El segundo son los libros**, que hoy son cuatro: `compra`, `venta`, `tesoreria` y `diario`. Un libro **no es un
`if` repartido por el código**: es una fila en la tabla `modelo.RASGOS`, que declara de qué bloque salen sus
líneas, qué papeles caben en su asiento y qué reglas le tocan. Cada capa que necesita distinguirlos lo hace con
un diccionario tecleado por esa fila, nunca preguntando por el nombre del libro — y hay un test que recorre el
paquete entero y lo prohíbe.

Dónde vive cada cosa. **Las carpetas de primer nivel son la estructura canónica**: nada se añade ahí sin que
`tests/test_capas.py` diga a qué capa pertenece y por qué.

```
contaperu/
│
├── modelo/              EL EJE. Qué es un libro y qué lo distingue de otro
│   ├── libro.py           la tabla RASGOS: los cuatro libros, una fila cada uno
│   ├── coerciones.py      a Decimal, a fecha, a número de serie
│   └── accesores.py       leer un campo venga como objeto o como diccionario
│
├── comprobantes/        LIBRO 1 y 2 · una compra o una venta
│   ├── comprobante.py     sus 40 campos y su identidad (qué lo hace duplicado)
│   ├── imputacion.py      lo que el contador decide: cuenta, centro, detracción
│   ├── xml_ubl.py         lee el XML de SUNAT
│   ├── sire_txt.py        lee el TXT de la propuesta del SIRE
│   ├── archivos.py        desarma el ZIP y reparte lo que hay dentro
│   └── resumen.py         cuánto compró o vendió un RUC en el mes
│
├── tesoreria/           LIBRO 3 · el dinero
│   ├── movimientos.py     la única entrada: venga de un extracto o de una constancia
│   ├── imputaciones.py    la contrapartida, que la pone el ERP
│   ├── cuentas.py         las cuentas bancarias del contribuyente, con su 104
│   ├── extractos.py       la cabecera de lo que el banco declaró
│   ├── referencias.py     qué cancela un pago
│   ├── cuadre.py          la cadena de saldos: «¿leí bien el extracto?»
│   └── constancias/       el primer lector: cinco formatos de dos bancos, de texto
│                        (LIBRO 4 · el diario no tiene carpeta: llega ya armado)
│
├── asiento/             LA PARTIDA DOBLE. Un motor por libro, y lo común debajo
│   ├── comprobante.py     el asiento de una compra o una venta
│   ├── movimiento.py      el asiento del dinero
│   ├── comun.py           lo que los dos hacen igual
│   ├── lineas.py          la línea de diario: el bloque `asiento` del estándar
│   ├── resolucion/        qué cuenta, qué sub-diario, qué correlativo, qué falta
│   ├── faltas/            lo que impide exportar, por libro
│   ├── indice/            qué tramo de líneas es de qué comprobante o movimiento
│   └── huella.py          el sha256 que identifica un asiento
│
├── contable/            LO UNIVERSAL. No depende del país ni del régimen
│   ├── partida_doble.py   Debe = Haber, sin tolerancia
│   └── resumen.py         el pre-mayor: cuánto cayó en cada cuenta
│
├── tributos/            LO PERUANO. Las normas, no los libros
│   ├── igv.py             se LEE del comprobante, nunca se supone
│   ├── detracciones.py    el Catálogo 54 y los dos tiempos del depósito
│   ├── validar.py         las reglas deterministas y los duplicados
│   └── comparar_sire.py   lo nuestro contra lo que SUNAT tiene
│
├── catalogos/           LOS CÓDIGOS DE SUNAT, cada uno con su resolución
├── pcge/                EL PLAN DE CUENTAS 2026 y de qué clase es cada cuenta
├── sunat/               LA API DEL SIRE descrita: se sabe la URL y no se llama
├── lectores/            la ruta de siempre de los lectores (viven en comprobantes/)
│
├── drivers/             LOS DESTINOS. Traducen; no deciden ninguna cuenta
│   ├── contrato/          lo que un driver tiene que exponer, y su examen
│   ├── kit/               lo común: columnas, celdas, nombres de archivo, el rol
│   ├── asiento_contable/  canal ERP · el documento del estándar, sin vocabulario ajeno
│   ├── csv/               canal ERP · una fila por línea
│   ├── sire/              canal SUNAT · el TXT del RVIE y del RCE
│   ├── ple/ · ple_plan/   canal SUNAT · el Libro Diario 5.1 y su plan de cuentas 5.3
│   └── concar/ · contasis/ · starsoft/   canal legacy · lo que cada sistema importa
│
├── pipeline/            LA ORQUESTACIÓN de un mes, escrita una sola vez
│   ├── lectura.py         de archivos a documento
│   ├── preparacion/       el documento, la configuración y los pasos de cada libro
│   ├── seleccion.py       qué entra y qué se queda fuera
│   ├── armado.py          → el asiento          ┐
│   ├── salida.py          → el archivo          ├ los tres eligen camino por el
│   └── diagnostico.py     → qué falta           ┘ `origen` del libro, en una tabla
│
├── api/                 LA SUPERFICIE PÚBLICA, congelada dentro de cada mayor
│   ├── operaciones.py     lo que una aplicación llama
│   ├── tabla.py           la tabla de operaciones, de la que sale todo lo demás
│   ├── esquemas/          el JSON Schema de cada entrada y cada respuesta
│   └── openconta.json     el contrato OpenAPI, generado y verificado
│
├── puertas/             LOS PROTOCOLOS. Solo hablan con api/
│   ├── cli.py             la línea de comandos
│   ├── servidor_mcp.py    para un asistente de IA
│   └── servidor_http.py   para un ERP en cualquier lenguaje
│
├── datos/sunat/         los catálogos que viajan en el paquete, con su fuente
├── aplicaciones.py      el puente entre libros: cuánto de un pago cancela un documento
├── configuracion.py     lo que cada empresa declara: sus cuentas, sus centros, sus tasas
├── vocabulario.py       los roles, las clases y los tipos de libro del estándar
└── errores.py           el error del motor, con su clave estable
```

Y **el repositorio alrededor del paquete**, que es la otra mitad de lo que hay que saber para moverse:

```
contaperu/               ← el paquete de arriba: lo que se instala con `pip`
│
├── estandar/            EL ESTÁNDAR `open-accounting`, que se publica aparte del motor
│   ├── open-accounting.schema.json   el esquema del documento
│   ├── catalogos.json                los roles, las clases y los cuatro tipos de libro
│   ├── LEEME.md                      el texto normativo: qué significa cada bloque
│   ├── enmiendas/                    33 enmiendas, cada una con su motivo y su fuente
│   ├── conformidad/                  casos para probar OTRA implementación, sin este motor
│   └── MIGRAR-A-1.0.md · 2.0 · 3.0   qué tocar al subir de versión mayor
│
├── tests/               LA BATERÍA. 74 ficheros, y es donde vive la mitad del porqué
│   ├── test_capas.py                 nadie importa fuera de su capa
│   ├── test_frontera.py              el núcleo no toca disco, red ni reloj
│   ├── test_superficie_publica.py    lo que se promete no cambia sin que se vea
│   ├── test_snapshot_concar.py       el Excel validado, celda a celda (52 casos)
│   ├── fixtures/                     las fotos congeladas y los documentos de ejemplo
│   └── drivers_de_prueba/            drivers de mentira, para probar el contrato
│
├── herramientas/        LO QUE SE CORRE A MANO, nunca en producción
│   ├── regenerar.py                  la puerta única a las fotos congeladas
│   ├── generar_openconta.py          regenera el contrato desde la tabla de operaciones
│   └── comprobar_sire.py · medir.py  capturar respuestas reales · medir rendimiento
│
├── diagramas/           los cinco SVG que ilustran este README
├── .github/workflows/   `tests.yml` en cada push · `release.yml` al empujar un tag
│
├── README.md            esto
├── ARQUITECTURA.md      las capas y sus porqués, y lo que no se negocia
├── INTEGRAR.md          cómo meter el motor en un ERP, con ejemplos que se ejecutan
├── estandar/LEEME.md    el estándar, para quien no use este motor
├── HOJA-DE-RUTA.md      en qué orden crece, y qué dato destraba cada cosa
├── REFERENCIAS.md       lo que se miró de otros sistemas, y lo que se descartó
├── CHANGELOG.md         cada versión con su porqué: la bitácora, y en ningún otro sitio
└── CONTRIBUTING.md      la regla que manda: ninguna regla contable sin su fuente
```

Y una carpeta que **no** está y se nombra a propósito: `privado/`, que `.gitignore` bloquea. Ahí viven los
archivos reales de contribuyentes con los que se contrasta el motor —un mes de compras, un extracto, un Libro
Diario aceptado—. **Nada de eso entra al repositorio**: lo que entra son los datos que dejan, y siempre con el
RUC de ejemplo.

La mitad del código está en dos sitios, y no por casualidad: **`drivers/` es con diferencia lo más grande**
—ocho formatos ajenos, cada uno con sus manías— y **`asiento/` lo segundo**, que es donde vive la contabilidad.
Todo lo demás es más pequeño de lo que suele esperarse.

La mitad del código está en dos sitios, y no por casualidad: **`drivers/` es con diferencia lo más grande**
—ocho formatos ajenos, cada uno con sus manías— y **`asiento/` lo segundo**, que es donde vive la contabilidad.
Todo lo demás es más pequeño de lo que suele esperarse.

Tres cosas más que ayudan a leerlo:

- **Nada de lo que está dentro de `contaperu/` toca el disco, la red ni el reloj**, salvo `_datos`, que lee los
  catálogos que viajan en el paquete. La fecha la pone quien llama. Lo vigila `tests/test_frontera.py`.
- **Los destinos van por canal, no por nombre**: `erp` (el estándar y el CSV), `sunat` (SIRE y PLE) y `legacy`
  (CONCAR, CONTASIS, STARSOFT). Un driver declara qué libros lleva, y el que no lleva uno lo rechaza diciendo
  cuáles sí.
- **La documentación de cada decisión está en el código, al lado de la regla**, y el porqué de cada versión en
  [`CHANGELOG.md`](CHANGELOG.md). Si algo parece arbitrario, el comentario de encima suele decir qué archivo real
  o qué resolución lo obligó.

### Por dónde pasa un comprobante

![Qué carpeta y qué archivo toca un comprobante: entra por comprobantes/ (xml_ubl, sire_txt, archivos, _zip), que es también donde vive su forma (modelo, vocabulario y catalogos leen datos/sunat/ con su fuente), lo revisan las reglas deterministas (tributos/ con validar, igv y detracciones, más configuracion), asiento/ arma la partida doble apoyándose en contable/ y pcge/, y drivers/ lo traduce a sus ocho destinos por canal; por debajo, pipeline/ orquesta, api/ expone la superficie congelada y puertas/ solo habla con api/, y al final lo que este recorrido no toca, porque es el de uno de los cuatro libros: tesoreria/ el dinero, el diario que llega ya armado, aplicaciones y sunat/](diagramas/recorrido-por-los-modulos.svg)

El mismo motor, un nivel más abajo: **los archivos que toca un comprobante**, en el orden en que lo hacen. El
franja del final es lo que este recorrido NO toca, porque es el de **uno de los cuatro libros**: `tesoreria/`
es el dinero; el **diario** llega ya armado y el motor no lo origina —sus líneas las produce quien tiene las
reglas de una planilla o de una depreciación—; `aplicaciones` dice cuánto de un pago cancela un documento; y
`sunat/` es la API del SIRE.

- **`comprobantes`** es el paquete de una compra o una venta: sus **lectores** convierten un archivo que ya existe
  —el XML UBL de SUNAT, el TXT de la propuesta del SIRE— en un `Comprobante`, que es una fila del registro, y
  guardan además lo que el contador decide sobre él y cuánto suma el mes. Su espejo del otro lado es
  **`tesoreria`**, que hace lo mismo con el dinero. (`lectores` sigue sirviendo como la ruta de siempre.)
- **`validar`, `igv` y `detracciones`** aplican las reglas deterministas. El IGV **se lee** de los importes del
  comprobante, nunca se supone; y la detracción se contrasta con la tabla del contribuyente antes de tocarla.
- **`asiento`** es donde vive la contabilidad de verdad: qué cuenta, qué sentido, cuántas líneas y con qué correlativo.
- **`drivers`** traducen esas líneas al formato de cada sistema, sin decidir ni una cuenta.

Tres módulos lo sostienen desde abajo: **`catalogos`** da los códigos de SUNAT a la lectura y la validación,
**`partida_doble`** comprueba que el Debe iguale al Haber antes de escribir un solo byte, y **`contrato`** dice lo que
un driver tiene que exponer para que el registro lo acepte. Y los catálogos no están escritos en el código: se leen de
`datos/sunat/`, **cada uno con la resolución de la que sale**.

Hasta la 1.x convivían ahí cinco archivos más —`operaciones.py`, `generar.py`, `cli.py`, `formato.py` y
`servidor_mcp.py`— que **no contenían nada**: eran las rutas que una aplicación importaba en la 0.x, redirigidas con
un aviso. **La 2.0 las retiró**, y con ellas todo el resto de la compatibilidad con la 0.x. Quien integró con la 1.x
no cambia una línea: la superficie pública de la 1.0 sigue entera.

Y volvió a pasar lo mismo, a propósito: la 6.4.0 agrupó el núcleo en `tributos/` y `contable/` y dejó seis archivos
de redirección en la raíz para no obligar a nadie a cambiar un import de un día para otro; **la 7.0 los retiró**,
como su aviso prometía. Si usas `contaperu.api`, tampoco esta vez cambias nada.

### Las puertas y la API pública

![Las puertas y la API pública: un programa en Python, un contador en la consola, un asistente de IA y un ERP entran por sus puertas —Python, CLI, MCP y HTTP— a la API pública 1.0, con sus operaciones, sus errores con clave, la tabla de operaciones y OpenConta; de ahí, todo pedido entra al mismo pipeline](diagramas/puertas-y-api.svg)

Las **puertas** son las formas de llegar al motor, y ninguna sabe contabilidad: traducen el pedido de su protocolo a la
API y devuelven la respuesta. Por eso el mismo mes da el mismo resultado por las cuatro, y un test lo comprueba.

| Puerta | Para quién | Cómo se usa |
|---|---|---|
| **Python** | Un programa en Python | `from contaperu import api` y `api.exportar(documento, driver="concar", ...)`: llama directo a la API |
| **CLI** (`contaperu`) | Quien trabaja en la consola o por lotes | Seis comandos: `generar`, `desde-json`, `diagnosticar`, `configuracion`, `comparar` y `verificar-driver`, que comprueba un driver propio contra el contrato |
| **MCP** (`contaperu-mcp`) | Un asistente de IA | 17 herramientas de solo lectura y 13 recursos, por stdio o HTTP; el archivo vuelve con hasta 4 MB |
| **HTTP** (`contaperu-http`) | Un ERP en cualquier lenguaje | `POST /v1/exportar`, `POST /v1/diagnosticar`…; responde 421 a un `Host` no declarado, corta la petición en 10 MB y atiende 16 a la vez |

La **API pública** (`contaperu.api`) es la lista de operaciones que comparten las cuatro puertas: leer, revisar,
diagnosticar, generar el asiento, exportar… Es también una promesa: sus nombres y lo que pide cada una no cambian
hasta la 15.0. Cada error lleva una clave estable (`sin_cuenta`, `no_cabe`, `sin_sigla`…), que la puerta HTTP entrega
en formato RFC 9457.

La **tabla de operaciones** (`api/tabla.py`) tiene una fila por operación, con su ruta HTTP y su nombre en el MCP. De
ella salen solas las rutas, las herramientas y **OpenConta**: el manual de la puerta HTTP, en formato OpenAPI 3.1,
que se sirve en `/openconta.json` y con el que cualquier herramienta genera el cliente del ERP en su lenguaje.
OpenConta no es una puerta: describe una.

Pase por la puerta que pase, después de la API todo pedido entra al mismo **pipeline**.

Todo esto, con sus porqués, en [ARQUITECTURA.md](ARQUITECTURA.md), que también cuenta
[el recorrido de un mes dentro del motor, paso a paso](ARQUITECTURA.md#un-mes-paso-a-paso); cómo integrarlo en un ERP,
en [INTEGRAR.md](INTEGRAR.md).

## Glosario: palabras de programador en lenguaje contable

| Palabra | Qué es, en términos contables |
|---|---|
| **Arquitectura colectiva** | Resolver la contabilidad automatizada una vez, en abierto y entre todos, en vez de que cada empresa construya su propia integración |
| **Asiento** | El apunte de partida doble de un comprobante: sus líneas, con la misma suma al Debe y al Haber |
| **Línea del comprobante** | Una línea de ese asiento: una cuenta, un sentido (Debe o Haber) y un importe. Es lo que cualquier sistema contable sabe recibir, y en el documento se llama `linea` |
| **Registro** | El libro de compras o de ventas, con una fila por comprobante y **sin cuentas**. Es la otra familia de salida frente al asiento, y un driver declara en cuál está; no es lo mismo que «registrar» un comprobante en una aplicación. Ojo: no todo lo que va a SUNAT es un registro — el Libro Diario del PLE es un asiento, con una fila por línea |
| **Vocabulario legacy** | Las palabras que pide un sistema contable instalado y que no son contabilidad: la sigla del documento, el sub-diario, el correlativo. Un ERP nuevo no las necesita |
| **Canal** | A quién entrega un driver lo que sale, y lo único que hay que declarar para saberlo: `sunat`, `legacy` o `erp`. Distinto de la **familia**, que dice *qué* entrega (un registro o un asiento) |
| **SUNAT** | Como canal, **sus dos regímenes**: el SIRE, donde se presentan el registro de ventas (RVIE) y el de compras (RCE), y el PLE, por donde van el Libro Diario, los demás libros y el plan de cuentas. Son normas distintas y formatos distintos; lo que comparten es que se entregan a SUNAT, en texto |
| **SIRE** | El Sistema Integrado de Registros Electrónicos de SUNAT, donde se presentan el registro de ventas (RVIE) y el de compras (RCE). **Es uno de los dos regímenes, no todo SUNAT** |
| **PLE** | El Programa de Libros Electrónicos: el otro régimen, por donde se presentan el Libro Diario y el detalle del plan contable (RS 234-2006 y RS 286-2009) |
| **Legacy** | Un sistema contable instalado que importa un archivo plano: CONCAR, CONTASIS, SISCONT, STARSOFT |
| **ERP** | Un sistema nuevo, en cualquier lenguaje, que recibe el documento del estándar con su asiento sin vocabulario legacy — o el CSV de líneas de diario |
| **Driver** | El traductor al formato de un sistema contable: sabe en qué columna va cada dato de CONCAR o de CONTASIS, pero nunca decide una cuenta |
| **`open-accounting`** | El documento común: el libro, sus comprobantes y su asiento, escrito de una forma que cualquier sistema entiende |
| **Núcleo** | La parte que sabe contabilidad peruana: valida el comprobante, calcula el IGV y arma el asiento |
| **Pipeline** | El recorrido de cada mes: leer, preparar, armar el asiento y diagnosticar lo que falta |
| **Puerta** | Cada forma de hablar con el motor: la línea de comandos, el MCP o HTTP |
| **API** | La lista de operaciones que el motor ofrece (leer, diagnosticar, exportar…) y la promesa de que no cambian sin aviso |
| **MCP** | El protocolo con el que un asistente de IA usa el motor como herramienta |
| **OpenConta** | El contrato de la puerta HTTP: describe cada operación para que un ERP en cualquier lenguaje genere su cliente |
| **Entry point** | El enchufe por el que un driver hecho por otra persona se suma sin tocar este repositorio |
| **Test** | Una comprobación automática: un caso con el resultado que debe dar, que se repite en cada cambio |
| **Snapshot** | Un Excel de CONCAR congelado celda por celda: si un cambio mueve una sola celda, el test lo detiene |

---

## Qué sabe hacer

**Lee** el XML UBL 2.1 de la factura electrónica (sueltos o en ZIP, descartando los CDR) y el TXT de la propuesta que
SUNAT entrega en el SIRE.

**Valida** lo que se puede validar sin salir a ningún sitio: el RUC por su dígito verificador, que el IGV cuadre con la
base, que el total sea la suma de sus partes, que la fecha no sea posterior al periodo (y, en compras, que no pasen los
12 meses de anotación de la Ley 29215) y los duplicados, también los de periodos anteriores. Y **la partida doble**, sin
tolerancia: un céntimo de diferencia detiene la exportación.

**Arma el asiento** de compras y de ventas, incluidos los casos que suelen salir mal:

| Caso | Qué hace |
|---|---|
| Factura con IGV | gasto, IGV crédito y proveedor |
| Boleta de venta (compras) | todo al gasto: no da crédito fiscal |
| Recibo por honorarios | cuenta propia, y la retención de 4ta **que muestra el comprobante** |
| Nota de crédito | invierte el asiento, con el documento que modifica en la referencia |
| **Factura con detracción** | cinco líneas: el total al proveedor y la detracción provisionada aparte |
| Comprobante en dólares | el tipo de cambio del comprobante, y la detracción convertida a soles |
| Comprobante extemporáneo | se asienta dentro del periodo, conservando la fecha del documento |

**Exporta**, por canal de destino:

- **ERP:** el documento `open-accounting` con su asiento sin vocabulario legacy (driver `asiento_contable`), y un CSV
  genérico con las líneas de diario, para cualquier destino que todavía no tenga driver. El mismo documento **vuelve a
  entrar al motor y da el mismo asiento con la misma huella**, que es lo que lo hace un formato y no una salida.
- **SUNAT:** el TXT de reemplazo del RVIE y del RCE (el SIRE), y el Libro Diario y el plan de cuentas (el PLE).
- **Legacy:** a CONCAR (Excel de asientos de 41 columnas), a CONTASIS (su registro de compras y de ventas en Excel)
  y a STARSOFT (sus asientos en TXT de palotes).

**Le ahorra a un ERP lo que no tiene por qué escribir**, y es la parte que menos se ve:

- **Recibir un Libro Diario, no solo producirlo.** Un ERP puede mandar sus asientos ya armados —la planilla, la
  depreciación, el asiento de destino, un ajuste— con `libro.tipo: "diario"`, y el motor los lee, los **cuadra**,
  les da su huella y los lleva a su destino. Es el único libro que el motor no origina, y tiene que ser así:
  armar una planilla pide las reglas de la planilla, que este motor no tiene ni debe inventar.
- **Cuánto es un libro.** `resumen` da la base gravada, el IGV y el total, cada moneda por su lado y con agrupación
  por contraparte; `por_cuenta` da el pre-mayor con su cuadre. Existen porque un conector los escribió por su cuenta
  y le salió `07` donde el motor dice `("07","87")`: una nota de crédito de no domiciliado que no restaba.
- **Qué campos pone cada uno.** `campos_del_comprobante` reparte el comprobante en tres tramos —lo que trae el
  documento, lo que pone el sistema y lo que decide la revisión— y `REGLAS` da las reglas del dominio **sin nombrar
  ninguna herramienta de este motor**, para quien monte su propia capa de agente.
- **La API del SIRE, descrita.** Las once operaciones con su ruta, su método y su grada; armar la petición, leer el
  estado de un ticket y clasificar el rechazo de SUNAT. **El motor sabe la URL y no la llama**: enviar necesita red y
  Clave SOL, y eso es de quien lo integra.
- **Una batería de conformidad portable**, que se corre **sin el motor y en cualquier lenguaje**: si escribes tu
  propia implementación del estándar, ahí está contra qué medirla.

**Diagnostica** un mes antes de exportarlo: qué comprobantes bloquean y cuáles solo avisan, qué falta para el sistema de
destino (cuenta, centro de costo, tipos sin sigla, monedas, correlativos, un reparto que no suma la base o que el
destino no admite, lo que no cabe en su formato), qué detracciones esperan constancia y cuáles ya se
depositaron —con número y fecha, que son las dos cosas que hacen falta— y qué saldría. Una sola
respuesta, por serie-número, sin corregir ni inventar nada.

## Qué **no** hace

- **No lee PDFs ni fotos.** Lee el XML, que es el comprobante electrónico, y la propuesta del SIRE.
- **No se conecta a SUNAT.** No hay credenciales, no hay Clave SOL, no sale ni un paquete a la red. **Sí sabe cómo
  es su API**: describe las once operaciones del SIRE y arma la petición exacta, para que quien la envíe no tenga que
  adivinarla. Saber es un dato; llamar es entrada y salida, y eso es del integrador.
- **No guarda nada.** Ni base de datos, ni archivos, ni sesiones.
- **No emite comprobantes.** No genera, no firma y no envía facturas electrónicas.
- **No reemplaza tu sistema contable.** Traduce hacia él — y para quien construye uno nuevo, le pone la base.

---

## Estado

| Pieza | Estado |
|---|---|
| **Entradas** | |
| Lectura de XML UBL 2.1 y de la propuesta del SIRE | listo |
| Conciliación de constancias de detracción | **pendiente de un archivo real** del Banco de la Nación |
| **Estándar y comunidad** | |
| El estándar `open-accounting` 4.0, su esquema, sus catálogos y su batería de conformidad | listo |
| Contrato de driver y drivers de terceros por *entry points* | listo |
| Paquete en PyPI | listo: `pip install contaperu` |
| **Motor** | |
| Validación del comprobante y de la partida doble | listo |
| Asiento: compras, ventas, honorarios, notas y detracción | listo |
| **Asiento de tesorería**: pagos, cobros, cargos del banco, repartos y traspasos, con el ITF como su propio asiento | **listo** para un ERP (12.10): el documento del estándar con sus movimientos, su imputación y su asiento, y el archivo vuelve a entrar dando lo mismo. Hacia un sistema legacy, **pendiente de un archivo real** del sub-diario de bancos |
| `diagnosticar`: qué falta, para qué destino y a quién pedírselo | listo |
| API pública estable, `contaperu.api`: cada nombre con su firma, congelados por un test | listo |
| Servidor MCP y CLI | listo |
| Reglas del **PCGE 2026** | **pendiente de la norma** — ver abajo |
| **ERP** · el eje desde el 10-oct-2026 | |
| Driver `asiento_contable`: el documento del estándar con sus comprobantes y su asiento | listo |
| Driver CSV | listo |
| Puerta HTTP con el contrato OpenConta | listo |
| `resumen` y `por_cuenta`: cuánto es un libro, y el pre-mayor con su cuadre | listo |
| `campos_del_comprobante` y `REGLAS`: qué pone cada uno, y el dominio sin nombrar una herramienta | listo |
| Recibir un diario que no viene de compras ni de ventas (planilla, depreciación, destino) | **listo** desde la 13.2.0 (16-oct-2026), hito B13: el **Libro Diario** es el cuarto tipo de `libro.tipo`, junto a `venta`, `compra` y `tesoreria`. Eran 595 de los 1 441 asientos de un mes real |
| La cuenta según con quién y según qué, y el nivel fino de la cuenta | **pendiente de un caso real** — ver la hoja de ruta |
| **SUNAT** · los dos regímenes | |
| Driver SIRE (TXT de reemplazo del RVIE y del RCE) | listo |
| Driver PLE (el Libro Diario, formato 5.1) y PLE-plan (el detalle del plan contable, 5.3) | listo, contra un libro presentado y aceptado con sus constancias |
| La API del SIRE descrita: las once operaciones, la petición armada, el ticket y el rechazo | listo (8.1) — **sin salir a la red**: enviar es del integrador |
| Los lectores de lo que SUNAT contesta | **pendiente de una respuesta real** por operación, que se captura con `herramientas/comprobar_sire.py` |
| **Legacy** | |
| Driver CONCAR (Excel de asientos) | listo |
| Driver CONTASIS (registro de compras y de ventas en Excel) | **listo**: CONTASIS importó los archivos que genera (13-sep-2026) |
| Driver STARSOFT (asientos en TXT de palotes) | **listo**: STARSOFT importó un mes de compras (7-oct-2026) y uno de ventas (8-oct-2026) |
| Driver SISCONT | el contrato ya cubre lo que necesita; espera un archivo real aceptado — ver [Cómo aportar](#cómo-aportar) |

Lo que no está listo no tiene fecha: tiene un orden y un dato que lo destraba, en [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md).

### Sobre el PCGE 2026

El módulo `contaperu/pcge/` existe con la tabla **vacía**, y mientras lo esté no toca ninguna cuenta: lo dice
en su informe en vez de adivinar. Las equivalencias del Plan Contable General Empresarial 2026 se publicarán
**con la cita del artículo de la resolución al lado de cada mapeo** — el cargador rechaza un mapeo sin
fuente. Un neteo mal puesto en un repositorio público estropea la contabilidad de quien confíe en él, que es
exactamente lo contrario de lo que este proyecto quiere hacer.

Si tienes el texto oficial y quieres ayudar, es la contribución más útil que hay ahora mismo.

---

## Cómo aportar

**La contabilidad abierta se construye entre todos.** El motor mejora con cada regla corregida, cada formato compartido
y cada driver nuevo, y lo que aporta uno lo aprovechan todos.

La regla que manda en todo el proyecto: **ninguna regla contable entra sin una fuente.** La norma, la resolución o el
archivo real que la justifica va al lado, en el código. Por eso quien más puede aportar es quien lleva la contabilidad
todos los días.

### Si eres contador, no necesitas programar

1. **Reporta una regla mal puesta.** Un asiento que no corresponde, una cuenta o un sentido equivocados, una
   detracción mal calculada: abre un aviso con la plantilla
   [«Regla mal puesta»](https://github.com/contaperu/contaperu/issues/new?template=regla-mal-puesta.yml) y cita la
   norma que lo respalda.
2. **Reporta un comprobante que se leyó o se asentó mal**, o un archivo que tu sistema rechazó, con la plantilla
   [«Error»](https://github.com/contaperu/contaperu/issues/new?template=error.yml).
3. **Aporta la norma.** Las equivalencias del PCGE 2026, una resolución de SUNAT, el plazo de un régimen: con la cita
   exacta, porque sin fuente no entra.
4. **Comparte el formato de tu sistema.** Si usas **SISCONT** u otro sistema que todavía no tiene driver, lo
   que hace falta es su plantilla de importación y un archivo que ese sistema haya aceptado. Con eso se construye el
   driver: la plantilla
   [«El formato de mi sistema»](https://github.com/contaperu/contaperu/issues/new?template=formato-de-mi-sistema.yml)
   pide justo eso.
5. **Propón una enmienda al estándar.** Si a `open-accounting` le falta un dato que tu sistema sí tiene, con la
   plantilla [«Enmienda»](https://github.com/contaperu/contaperu/issues/new?template=enmienda.yml). Así crecen las
   reglas, y no hace falta escribir código.
6. **Revisa los textos.** Las glosas, los mensajes de lo que falta y este README tienen que decirse como los diría un
   contador.

**Y si prefieres elegir tú.** Lo que el proyecto necesita ahora mismo, hito por hito y con quién se consigue cada
cosa, está en [«Lo que hay que conseguir»](HOJA-DE-RUTA.md#5--lo-que-hay-que-conseguir).

**Nunca compartas datos reales.** Antes de subir un archivo, cambia los RUC por los de prueba —`20131312955` y
`20601234567`—, las razones sociales por nombres inventados y, si quieres, los importes. Los detalles, en
[CONTRIBUTING.md](CONTRIBUTING.md) («Nunca subas datos reales»).

### Si programas

```bash
git clone https://github.com/contaperu/contaperu.git
cd contaperu
pip install -e ".[dev]"
pytest
```

Más de 800 tests, sin red y sin credenciales. Lo más valioso que puedes aportar es un **driver de salida** para un
sistema que hoy no está —la receta y el contrato, en [CONTRIBUTING.md](CONTRIBUTING.md)— o un **caso real** que el
motor resuelva mal.

---

## Para desarrolladores

### Instalación

Desde PyPI, como cualquier dependencia. La versión va fijada con `==`: una versión publicada no se
reemplaza jamás, así que el número significa «estos bytes exactos».

```bash
pip install contaperu                 # el núcleo
pip install "contaperu[excel]"        # + exportar a CONCAR y CONTASIS (.xlsx)
pip install "contaperu[mcp]"          # + el servidor MCP
pip install "contaperu[http]"         # + la puerta HTTP para un ERP en cualquier lenguaje
pip install "contaperu[todo]"         # todo
```

### De un XML de SUNAT a un asiento, en diez líneas

```python
from pathlib import Path

from contaperu import api

libro = {"ruc": "20601234567", "razon_social": "MI EMPRESA SAC", "periodo": "202608", "tipo": "compra"}
documento = api.leer_xml(Path("F001-123.xml").read_text(encoding="utf-8"), libro)
# La cuenta de cada comprobante va en su imputación, por `id_externo`: no hay ninguna de la empresa que la supla.
configuracion = {}
imputacion = {c.setdefault("id_externo", f"fila-{n}"): {"cuenta_contable": "603201"}
              for n, c in enumerate(documento["comprobantes"], 1)}

diagnostico = api.diagnosticar(documento, driver="concar", configuracion=configuracion, imputacion=imputacion)
print(diagnostico["listo_para_exportar"], diagnostico["por_que_no"])
archivo = api.exportar_archivo(documento, driver="concar", configuracion=configuracion, imputacion=imputacion)
Path(archivo.archivo).write_bytes(archivo.contenido)            # el Excel que importa CONCAR
```

`contaperu.api` es la API pública: el documento primero, todo lo demás por su nombre, y el mismo nombre y la
misma firma hasta la 15.0. Cómo integrarlo en un ERP —desde Python, por lotes, por MCP o por HTTP desde cualquier
lenguaje—, en [INTEGRAR.md](INTEGRAR.md).

### Para un ERP en cualquier lenguaje: la puerta HTTP

```bash
pip install -e ".[http,excel]"
contaperu-http --host 127.0.0.1 --puerto 8080
curl -s http://localhost:8080/openconta.json -o openconta.json
```

Cada operación de la api es una ruta (`POST /v1/exportar`, `POST /v1/diagnosticar`, `GET /v1/drivers`…) y el contrato
que las describe, **OpenConta**, se sirve en `/openconta.json` en formato OpenAPI 3.1: cualquier generador arma el
cliente de tu lenguaje con él. Sin estado, con la misma defensa del `Host` y los mismos topes que el MCP, y rechazos
RFC 9457 con una `clave` estable. La guía, en [INTEGRAR.md](INTEGRAR.md).

### Para un agente de IA: el servidor MCP

Diecisiete herramientas: `diagnosticar` (qué bloquea, qué falta y qué saldría, **antes** de exportar),
`resumen` (cuánto es el libro, cada moneda por su lado), `por_cuenta` (en qué cuentas cayó el asiento)
y `estado_de_cuenta` (qué queda por cobrar o por pagar, derivado de las aplicaciones: **sin ninguna
columna de estado**),
`configuracion_por_defecto`, `drivers_disponibles`, `validar_comprobantes`, `validar_partida_doble`,
`generar_asiento`, `exportar`, `leer_xml_ubl`, `leer_propuesta_sire`, `normalizar_detracciones`,
`buscar_cuenta_pcge`, `adaptar_pcge2026`, `validar_cuentas_bancarias` (el maestro de cuentas del contribuyente,
con la 104 que declara cada una) y `revisar_tesoreria` (los movimientos de las cuentas —una sola entrada,
venga de un extracto o de una constancia—, con el cuadre de los totales y del saldo que declara el banco; **mirar y asentar son dos preguntas, y el asiento lo arma `generar_asiento`**), todas anunciadas de solo lectura. Y trece recursos: el esquema del
estándar, los catálogos de SUNAT, el canal del SIRE, **el formato del SIRE columna a columna** —dónde cae cada
campo del anexo, o por qué no cae—, **el del Libro Diario 5.1 del PLE** —de dónde sale cada uno de sus 21 campos,
con los códigos de libro de SUNAT—, los catálogos del propio estándar, el catálogo del PCGE 2026, los drivers
disponibles, lo que se configura de cada uno, el esquema de la respuesta de `diagnosticar`, **quién escribe
cada campo de un comprobante** (el documento, el sistema o la revisión), **los regímenes tributarios** —qué
libros obliga a llevar cada uno y cómo tributa, con la cita de su artículo— y **los dos cronogramas de
vencimiento**: cuándo vence la declaración del mes y hasta cuándo se puede atrasar el registro electrónico.

Las tres que van hacia un sistema contable —`diagnosticar`, `generar_asiento` y `exportar`— **exigen el
`driver`** y no lo suponen: el sistema de un contribuyente es suyo. `drivers_disponibles` dice cuáles hay.

El Excel y el ZIP del SIRE vuelven **como archivos** —recursos incrustados con su tipo—, así que el cliente
los ofrece para guardar en vez de enseñar una tira de letras.

#### En tu propia máquina (stdio)

```bash
docker build -t contaperu-mcp .
docker run -i --rm --network none contaperu-mcp
```

El `--network none` no es una precaución: es la demostración de que no hace falta red. En Claude Desktop,
en `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "contaperu": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--network", "none", "contaperu-mcp"]
    }
  }
}
```

#### Servido en red, para conectarlo como conector remoto

```bash
docker run -d --name contaperu-mcp --restart unless-stopped -p 8000:8000 contaperu-mcp \
    contaperu-mcp --transporte http --host 0.0.0.0 --dominio contaperu.tudominio.com
```

Habla **Streamable HTTP** en `/mcp`, así que la URL del conector es `https://contaperu.tudominio.com/mcp`.
**Sin token y sin OAuth**, y es una decisión, no un descuido: la especificación dice que la autorización es
[OPCIONAL](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization), y aquí no habría a
quién autenticar — este servidor no tiene usuarios, ni cuentas, ni base de datos, ni sale a la red. Quien
tenga la URL puede gastarte CPU; no puede leer nada de nadie, porque no hay nada guardado. (Si lo que
necesitas es un conector *por usuario*, con su login y sus datos, eso es otra pieza y va por encima de esta.)

**`--dominio` no es opcional al publicarlo.** El SDK del protocolo rechaza con un 421 toda petición cuyo
`Host` no reconozca —es la defensa contra el *DNS rebinding*— y por defecto solo se reconoce como
`localhost`: sin declararlo, el certificado y el proxy están perfectos y aun así no entra ni una petición.

Detrás de un proxy basta con pasarle las peticiones tal cual. Con Caddy:

```caddyfile
contaperu.tudominio.com {
	request_body {
		max_size 4MB
	}
	reverse_proxy contaperu-mcp:8000
}
```

Nada de reescribir rutas ni de inyectar cabeceras. Y como no lleva autenticación, el freno sensato es de
recursos: el tope de cuerpo de arriba, y memoria y CPU acotadas en el contenedor.

#### Una imagen, tres puertas

La misma imagen sirve el MCP, la puerta HTTP y la CLI, según lo que le pases:

```bash
docker run --rm -p 8080:8080 contaperu-mcp contaperu-http --host 0.0.0.0 --dominio contaperu.ejemplo.com

docker run --rm -v "$PWD:/data" contaperu-mcp \
    contaperu desde-json /data/mes.json --salida /data/salida
```

El servidor **no guarda nada y no sale a la red**. Cada llamada recibe todo lo que necesita y devuelve todo
lo que produce, así que dos llamadas iguales dan el mismo resultado y ninguna deja rastro.

---

## Documentos del proyecto

| Documento | Qué responde |
|---|---|
| [ARQUITECTURA.md](ARQUITECTURA.md) | Cómo está construido el motor y por qué, y lo que no se negocia |
| [INTEGRAR.md](INTEGRAR.md) | Cómo integrarlo en un ERP: desde Python, por lotes, por MCP o por HTTP |
| [CONTRIBUTING.md](CONTRIBUTING.md) | La regla que manda, nunca datos reales, cómo añadir un driver |
| [estandar/LEEME.md](estandar/LEEME.md) | El estándar `open-accounting`: sus bloques, sus reglas y su versionado |
| [REFERENCIAS.md](REFERENCIAS.md) | La investigación: lo que se tomó —y lo que no— de QuickBooks, Xero, los ERP grandes de EE. UU., las APIs unificadas, los estándares abiertos de factura (EN 16931, Peppol) y los ERP abiertos. Cuatro escalones: el asiento, el registro del comprobante, la clasificación de la cuenta y la aplicación de un pago |
| [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md) | En qué orden crece el motor y qué dato destraba cada paso. Desde el 10-oct-2026 lo ordena **ser la base de cualquier ERP**: primero lo que le falta a un ERP para mandar lo que hoy no puede, después el banco, después SUNAT, y los drivers legacy en paralelo |
| [CHANGELOG.md](CHANGELOG.md) | Cada versión con su porqué |
| [SECURITY.md](SECURITY.md) | Cómo reportar una vulnerabilidad |

---

## Palabras clave

Contabilidad peruana · software contable Perú · motor contable · código abierto · SUNAT · SIRE · RVIE · RCE · PLE ·
comprobantes de pago electrónicos · factura electrónica · boleta de venta · nota de crédito · recibo por honorarios ·
XML UBL 2.1 · registro de compras · registro de ventas · asientos contables · partida doble · libro diario ·
PCGE 2026 · IGV · detracciones · retención de cuarta categoría · CONCAR · CONTASIS · SISCONT · STARSOFT · estudio
contable · automatización contable · contabilidad abierta · arquitectura colectiva · inteligencia artificial · MCP ·
OpenAPI · ERP

---

## In English

**ContaPerú is the open accounting core for Peru.** It reads the electronic receipts issued through
SUNAT (Peru's tax authority), builds the double-entry journal and delivers it to three kinds of destination:
**SUNAT** (the SIRE tax filing and the PLE books), the **installed systems** that import a file (CONCAR, CONTASIS,
STARSOFT) and an **ERP**, which gets the journal in the standard itself — no legacy vocabulary. No database, no
state, no network calls: JSON in, JSON or a file out.

Its premise: automated accounting is not a problem each company should solve alone, but a matter of **collective
architecture** — one open standard and one open engine, built together. **Since 10 Oct 2026 the engine is organised
around being the foundation any new ERP can be built on**: nobody writing one should have to reimplement Peruvian
VAT, withholdings or sub-ledgers. The layer that translates towards the systems already installed stays, with no
retirement date — nobody has to leave CONCAR.

It also defines **`open-accounting`**, an open interchange format for Peruvian accounting documents
(`estandar/`), with a formal JSON Schema. The rules aren't designed on paper: they come from real
files that production accounting systems and SUNAT actually accepted.

A stable Python API (`contaperu.api`), an MCP server for AI agents and a stateless HTTP port described by the
**OpenConta** contract (an OpenAPI 3.1 document) let any ERP use it, in any language. It installs from PyPI (`pip install "contaperu[todo]"`) or from source. The docs are in Spanish, because
that's the language of the domain and of the people who use it — but issues and pull requests in English are welcome.

*Keywords: Peruvian accounting, Peru tax, SUNAT e-invoicing, electronic invoices, double-entry bookkeeping, accounting
engine, journal entries, VAT (IGV), open source.*
