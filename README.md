# ContaPerú · contabilidad peruana de código abierto

[![tests](https://github.com/contaperu/contaperu/actions/workflows/tests.yml/badge.svg)](https://github.com/contaperu/contaperu/actions/workflows/tests.yml)
[![licencia MIT](https://img.shields.io/badge/licencia-MIT-green.svg)](LICENSE)

**Motor abierto para la contabilidad peruana.** Lee los comprobantes electrónicos de SUNAT —factura, boleta, notas de
crédito y débito, recibo por honorarios—, valida el IGV y las detracciones, arma los **asientos contables en partida
doble** y los exporta al formato que pide tu sistema contable: el Excel de **CONCAR** o de **CONTASIS** y el TXT del
**SIRE** (RVIE y RCE). Sin base de datos, sin estado, sin llamadas a la red: entra un JSON, sale un JSON o un archivo.

**La contabilidad automatizada no es un problema de cada empresa: es de arquitectura colectiva.** Un estándar abierto y
un motor abierto, construidos entre todos, para los sistemas que ya existen y para los ERP que vienen.

**Encima de tu sistema contable, no en su lugar, y la base de los que vienen.** Nadie tiene que dejar CONCAR ni cambiar
su forma de trabajar: el motor le quita la digitación. Y quien construya un ERP nuevo no tiene que reimplementar el IGV,
las detracciones ni los sub-diarios: parte del estándar y del motor.

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
- **Salidas para todos:** el SIRE; los sistemas legacy mientras evolucionan, sin que nadie tenga que abandonarlos; y
  los ERP que vienen, que no tendrán que reinventar el IGV porque nacerán sobre un estándar.

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

![Arquitectura colectiva: los comprobantes electrónicos y la propuesta del SIRE entran al estándar abierto open-accounting; de ahí al motor, que la comunidad abierta mejora; y el motor entrega a tres grupos: el SIRE, los sistemas legacy (CONCAR, CONTASIS y, próximamente, STARSOFT) y los ERP que vienen](diagramas/arquitectura-colectiva.svg)

ContaPerú no es una aplicación que se abre: es el motor que va **dentro de un ERP externo**, sea un sistema contable en
la nube, un portal para estudios o el sistema de gestión de una empresa. En el ERP externo el contador carga, revisa y
descarga; el motor hace la contabilidad y no guarda nada. Lo del mes entra de dos formas, y las dos llegan al mismo
documento:

1. **Las facturas en XML.** El motor lee el XML UBL 2.1 de cada comprobante, suelto o en ZIP, y lo lleva al documento
   común [`open-accounting`](estandar/LEEME.md).
2. **La propuesta del SIRE.** El TXT de SUNAT ya empaqueta todos los comprobantes del contribuyente en el periodo: con
   ese solo archivo, el mes entero llega a `open-accounting`.

Desde ese documento, el motor valida cada comprobante, arma el asiento y entrega lo que pida cada grupo de destinos:

- **SIRE:** el TXT de reemplazo del registro de ventas (RVIE) y del de compras (RCE), listo para subir a SUNAT.
- **Legacy:** los sistemas contables instalados que importan un archivo. Hoy, los asientos de CONCAR y el registro de
  CONTASIS; SISCONT y STARSOFT esperan un archivo que ese sistema haya aceptado.
- **ERP:** los sistemas nuevos, en cualquier lenguaje. Reciben el documento `open-accounting` con su asiento **sin
  vocabulario legacy** —sin siglas, sub-diarios ni correlativos, por rol y código SUNAT— (driver `asiento_neutral`), el
  CSV con las líneas de diario, o todo por la puerta HTTP con el contrato OpenConta.

Cualquier entrada puede terminar en cualquiera de los tres grupos. Las cuentas, los sentidos del debe y el haber y la
detracción los decide el motor una sola vez, igual para todos los destinos. Y al costado del motor está la comunidad:
quien lo usa también lo mejora ([Cómo aportar](#cómo-aportar)).

## El motor por dentro

![ContaPerú por dentro: el contador sube al ERP externo los XML o el TXT de la propuesta del SIRE; el ERP le pasa al motor el documento open-accounting, con sus comprobantes y su imputación; el motor entra por sus puertas a la API pública 1.0, el pipeline se apoya en el núcleo peruano y los drivers lo traducen al SIRE, CONCAR, CONTASIS o de vuelta al ERP](diagramas/arquitectura-del-motor.svg)

- **Arriba, tu sistema:** el **ERP externo** recibe lo que sube el contador, los XML o el TXT de la propuesta del SIRE.
  Guarda, revisa y descarga: todo lo que necesita red, disco o credenciales vive ahí, no en el motor.
- **En el medio, el documento común:** lo que el ERP le pasa al motor es un documento
  [`open-accounting`](estandar/LEEME.md), con el libro (RUC, periodo, compras o ventas) y los comprobantes. Tiene su
  [esquema formal](estandar/open-accounting.schema.json). La imputación (la cuenta y el centro de costo de cada
  comprobante) y la configuración contable de la empresa no van dentro: llegan aparte, por el `id_externo` de cada
  comprobante.
- **El motor**, de arriba abajo:
  - cuatro **puertas**: Python, la línea de comandos, MCP para asistentes de IA y HTTP para un ERP en cualquier
    lenguaje, con el contrato OpenConta;
  - todas llaman a la **API pública 1.0**, que no cambia de nombres ni de firmas hasta la 2.0;
  - el **pipeline** lee, prepara, arma y diagnostica cada mes, y se apoya en el **núcleo peruano**, lo único que sabe
    contabilidad: validación, IGV, asiento y PCGE;
  - los **drivers** traducen al formato de cada destino sin decidir ninguna cuenta.

  Un driver de la comunidad se enchufa sin tocar este repositorio.
- **Abajo, los destinos:** el TXT del SIRE, los asientos de CONCAR, el registro de CONTASIS o el resultado de vuelta al
  ERP, en JSON y con su diagnóstico.

### Las puertas y la API pública

![Las puertas y la API pública: un programa en Python, un contador en la consola, un asistente de IA y un ERP entran por sus puertas —Python, CLI, MCP y HTTP— a la API pública 1.0, con sus operaciones, sus errores con clave, la tabla de operaciones y OpenConta; de ahí, todo pedido entra al mismo pipeline](diagramas/puertas-y-api.svg)

Las **puertas** son las formas de llegar al motor, y ninguna sabe contabilidad: traducen el pedido de su protocolo a la
API y devuelven la respuesta. Por eso el mismo mes da el mismo resultado por las cuatro, y un test lo comprueba.

| Puerta | Para quién | Cómo se usa |
|---|---|---|
| **Python** | Un programa en Python | `from contaperu import api` y `api.exportar(documento, driver="concar", ...)`: llama directo a la API |
| **CLI** (`contaperu`) | Quien trabaja en la consola o por lotes | Seis comandos: `generar`, `desde-json`, `diagnosticar`, `configuracion`, `comparar` y `verificar-driver`, que comprueba un driver propio contra el contrato |
| **MCP** (`contaperu-mcp`) | Un asistente de IA | 11 herramientas de solo lectura y 6 recursos, por stdio, HTTP o SSE; el archivo vuelve con hasta 4 MB |
| **HTTP** (`contaperu-http`) | Un ERP en cualquier lenguaje | `POST /v1/exportar`, `POST /v1/diagnosticar`…; responde 421 a un `Host` no declarado, corta la petición en 10 MB y atiende 16 a la vez |

La **API pública** (`contaperu.api`) es la lista de operaciones que comparten las cuatro puertas: leer, revisar,
diagnosticar, generar el asiento, exportar… Es también una promesa: sus nombres y lo que pide cada una no cambian
hasta la 2.0. Cada error lleva una clave estable (`sin_cuenta`, `no_cabe`, `sin_sigla`…), que la puerta HTTP entrega
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
| **SIRE** | El Sistema Integrado de Registros Electrónicos de SUNAT, donde se presentan el registro de ventas (RVIE) y el de compras (RCE) |
| **Legacy** | Un sistema contable instalado que importa un archivo plano: CONCAR, CONTASIS, SISCONT, STARSOFT |
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

**Exporta**, por grupo de destino:

- **SIRE:** el TXT de reemplazo del RVIE y del RCE.
- **Legacy:** a CONCAR (Excel de asientos de 41 columnas) y a CONTASIS (su registro de compras y de ventas en Excel).
- **ERP:** el documento `open-accounting` con su asiento sin vocabulario legacy (driver `asiento_neutral`), y un CSV
  genérico con las líneas de diario, para cualquier destino que todavía no tenga driver.

**Diagnostica** un mes antes de exportarlo: qué comprobantes bloquean y cuáles solo avisan, qué falta para el sistema de
destino (cuenta, centro de costo, tipos sin sigla, monedas, correlativos, un reparto que no suma la base o que el
destino no admite, lo que no cabe en su formato), qué detracciones esperan constancia y qué saldría. Una sola
respuesta, por serie-número, sin corregir ni inventar nada.

## Qué **no** hace

- **No lee PDFs ni fotos.** Lee el XML, que es el comprobante electrónico, y la propuesta del SIRE.
- **No se conecta a SUNAT.** No hay credenciales, no hay Clave SOL, no sale ni un paquete a la red.
- **No guarda nada.** Ni base de datos, ni archivos, ni sesiones.
- **No emite comprobantes.** No genera, no firma y no envía facturas electrónicas.
- **No reemplaza tu sistema contable.** Traduce hacia él.

---

## Estado

| Pieza | Estado |
|---|---|
| **Entradas** | |
| Lectura de XML UBL 2.1 y de la propuesta del SIRE | listo |
| Conciliación de constancias de detracción | **pendiente de un archivo real** del Banco de la Nación |
| **Estándar y comunidad** | |
| El estándar `open-accounting` 1.0, su esquema, sus catálogos y su batería de conformidad | listo |
| Contrato de driver y drivers de terceros por *entry points* | listo |
| Paquete en PyPI | **próximo**: hoy se instala desde el código |
| **Motor** | |
| Validación del comprobante y de la partida doble | listo |
| Asiento: compras, ventas, honorarios, notas y detracción | listo |
| `diagnosticar`: qué falta, para qué destino y a quién pedírselo | listo |
| API pública estable, `contaperu.api`, con las rutas de la 0.10 funcionando con aviso durante la 1.x | listo |
| Servidor MCP y CLI | listo |
| Reglas del **PCGE 2026** | **pendiente de la norma** — ver abajo |
| **SIRE** | |
| Driver SIRE (TXT de reemplazo del RVIE y del RCE) | listo |
| **Legacy** | |
| Driver CONCAR (Excel de asientos) | listo |
| Driver CONTASIS (registro de compras y de ventas en Excel) | **listo**: CONTASIS importó los archivos que genera (13-sep-2026) |
| Drivers de SISCONT y STARSOFT | el contrato ya cubre lo que necesitan; esperan un archivo real aceptado — ver [Cómo aportar](#cómo-aportar) |
| **ERP** | |
| Driver `asiento_neutral`: el asiento en el estándar, sin siglas, sub-diarios ni correlativos | listo |
| Driver CSV | listo |
| Puerta HTTP con el contrato OpenConta | listo |

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
4. **Comparte el formato de tu sistema.** Si usas **SISCONT, STARSOFT** u otro sistema que todavía no tiene driver, lo
   que hace falta es su plantilla de importación y un archivo que ese sistema haya aceptado. Con eso se construye el
   driver.
5. **Revisa los textos.** Las glosas, los mensajes de lo que falta y este README tienen que decirse como los diría un
   contador.

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

La 1.0 todavía no está publicada en PyPI: hoy se instala desde el código.

```bash
git clone https://github.com/contaperu/contaperu.git
cd contaperu
pip install -e .                 # el núcleo
pip install -e ".[excel]"        # + exportar a CONCAR y CONTASIS (.xlsx)
pip install -e ".[mcp]"          # + el servidor MCP
pip install -e ".[http]"         # + la puerta HTTP para un ERP en cualquier lenguaje
pip install -e ".[todo]"         # todo
```

### De un XML de SUNAT a un asiento, en diez líneas

```python
from pathlib import Path

from contaperu import api

libro = {"ruc": "20601234567", "razon_social": "MI EMPRESA SAC", "periodo": "202608", "tipo": "compra"}
documento = api.leer_xml(Path("F001-123.xml").read_text(encoding="utf-8"), libro)
# La cuenta de gasto por defecto viene vacía: va aquí o en la imputación de cada comprobante, por su `id_externo`.
configuracion = {"cuentas": {"gasto": "603201"}}

diagnostico = api.diagnosticar(documento, driver="concar", configuracion=configuracion)
print(diagnostico["listo_para_exportar"], diagnostico["por_que_no"])
archivo = api.exportar_archivo(documento, driver="concar", configuracion=configuracion)
Path(archivo.archivo).write_bytes(archivo.contenido)            # el Excel que importa CONCAR
```

`contaperu.api` es la API pública de la 1.0: el documento primero, todo lo demás por su nombre, y el mismo nombre y la
misma firma hasta la 2.0. Cómo integrarlo en un ERP —desde Python, por lotes, por MCP o por HTTP desde cualquier
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

Once herramientas: `diagnosticar` (qué bloquea, qué falta y qué saldría, **antes** de exportar),
`configuracion_por_defecto`, `validar_comprobantes`, `validar_partida_doble`, `generar_asiento`,
`exportar`, `leer_xml_ubl`, `leer_propuesta_sire`, `normalizar_detracciones`, `buscar_cuenta_pcge` y
`adaptar_pcge2026`, todas anunciadas de solo lectura. Y seis recursos: el esquema del estándar, los catálogos de
SUNAT, el catálogo del PCGE 2026, los drivers disponibles, lo que se configura de cada uno y el esquema de la respuesta
de `diagnosticar`.

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
| [REFERENCIAS.md](REFERENCIAS.md) | Lo que se tomó (y lo que no) de QuickBooks, Xero y las APIs unificadas de EE. UU. |
| [INTEROPERABILIDAD.md](INTEROPERABILIDAD.md) | La investigación: el ciclo contable de EE. UU. y del Perú, los proyectos abiertos y cómo entrarían el banco y las facturas de proveedores |
| [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md) | En qué orden crece el motor y qué dato destraba cada paso, con los frentes en el orden del flujo: entradas, estándar y comunidad, motor, y las salidas SIRE, Legacy y ERP |
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
SUNAT (Peru's tax authority), builds the double-entry journal and exports it to the format each
local accounting system expects — CONCAR, CONTASIS, the SIRE tax filing, or plain CSV. No database, no state,
no network calls: JSON in, JSON or a file out.

Its premise: automated accounting is not a problem each company should solve alone, but a matter of **collective
architecture** — one open standard and one open engine, built together, serving the SIRE, legacy systems while they
evolve, and the ERPs still to come.

It also defines **`open-accounting`**, an open interchange format for Peruvian accounting documents
(`estandar/`), with a formal JSON Schema. The rules aren't designed on paper: they come from real
files that production accounting systems and SUNAT actually accepted.

A stable Python API (`contaperu.api`), an MCP server for AI agents and a stateless HTTP port described by the
**OpenConta** contract (an OpenAPI 3.1 document) let any ERP use it, in any language. For now it installs from
source (`pip install -e ".[todo]"`); the PyPI package will follow the 1.0 release. The docs are in Spanish, because
that's the language of the domain and of the people who use it — but issues and pull requests in English are welcome.

*Keywords: Peruvian accounting, Peru tax, SUNAT e-invoicing, electronic invoices, double-entry bookkeeping, accounting
engine, journal entries, VAT (IGV), open source.*
