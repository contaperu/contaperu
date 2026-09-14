# ContaPerú

[![tests](https://github.com/contaperu/contaperu/actions/workflows/tests.yml/badge.svg)](https://github.com/contaperu/contaperu/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/contaperu.svg)](https://pypi.org/project/contaperu/)
[![Python](https://img.shields.io/pypi/pyversions/contaperu.svg)](https://pypi.org/project/contaperu/)
[![licencia MIT](https://img.shields.io/badge/licencia-MIT-green.svg)](LICENSE)

**Núcleo contable abierto del Perú.** Lee los comprobantes que emite SUNAT, arma la partida doble y los
exporta al formato que pide cada sistema contable. Sin base de datos, sin estado, sin llamadas a la red:
entra un JSON, sale un JSON o un archivo.

Sirve a tres usuarios distintos con el mismo código:

- **Un estudio contable o una empresa** que quiere automatizar su registro de compras y ventas sin cambiar
  el sistema que ya usa.
- **Un desarrollador** que integra contabilidad peruana y no quiere reimplementar el IGV, las detracciones,
  las notas de crédito y los sub-diarios por enésima vez.
- **Un agente de IA** que ya sabe leer un PDF, pero necesita un riel determinista donde depositar lo que
  extrajo. Para eso está el servidor MCP.

Licencia MIT. Se dona a la comunidad contable peruana.

---

## El problema

El software contable peruano nació en los noventa y no se habla entre sí: cada uno importa su propio archivo
plano, con sus columnas y sus siglas. Cuando además aparece una IA capaz de leer cien facturas en un minuto,
el cuello de botella deja de ser la lectura — es que **no hay un formato común y validado donde poner el
resultado**, y una cuenta mal puesta o un asiento descuadrado se descubre meses después.

ContaPerú aporta las dos piezas que faltan:

1. **[`open-accounting`](estandar/LEEME.md)** — un estándar JSON para el documento contable peruano: el libro, los
   comprobantes y las líneas de diario. Con su [esquema formal](estandar/open-accounting.schema.json).
2. **Un motor determinista** que valida ese documento, arma el asiento y lo traduce al formato de cada ERP.

No es un diseño en papel: el motor lleva un año generando el Excel de CONCAR y el TXT del SIRE de empresas
reales, y el estándar se deriva de su modelo, no al revés.

---

## Instalación

```bash
pip install contaperu              # el núcleo
pip install "contaperu[excel]"     # + exportar a CONCAR y CONTASIS (.xlsx)
pip install "contaperu[mcp]"       # + el servidor MCP
pip install "contaperu[todo]"      # todo
```

## De un XML de SUNAT a un asiento, en diez líneas

```python
from contaperu import operaciones as op

libro = {"ruc": "20601111111", "razon_social": "MI EMPRESA SAC",
         "periodo": "202608", "tipo": "compra"}
# La cuenta de gasto por defecto viene vacía: sin ella (aquí o en la imputación de cada comprobante) no hay asiento
# (`SinCuenta`). Una 60 no lleva centro de costo; una 63 o una 65 lo pediría (`cuentas_con_centro`).
configuracion = {"cuentas": {"gasto": "601101"}}

doc = op.leer_xml(open("factura.xml", encoding="utf-8").read(), libro)
doc = op.revisar(doc)                     # observaciones por comprobante
print(doc["_revision"])

asiento = op.generar_asiento(doc, configuracion)     # líneas de diario, sin formato de ERP
salida = op.exportar(doc, "concar", configuracion)   # un dict; el .xlsx va en salida["contenido_base64"]
```

Y desde la línea de comandos:

```bash
contaperu generar --tipo compra --ruc 20601111111 --razon "MI EMPRESA SAC" \
    --periodo 202608 --driver sire --salida ./salida  comprobantes/*.xml
```

Antes de generar el archivo de un sistema contable, parte de su configuración y pregunta qué falta:

```bash
contaperu configuracion --driver concar --por-defecto > mi-empresa.json
contaperu diagnosticar mes.json --driver concar --config mi-empresa.json
contaperu desde-json mes.json --driver concar --config mi-empresa.json --salida ./salida
```

La cuenta, el centro de costo, la cuenta del total y el reparto de cada documento no van en el comprobante: llegan
aparte, en la **imputación**, con el `id_externo` del comprobante como llave. Es el argumento `imputacion` de
`generar_asiento`, `diagnosticar` y `exportar` (en la fachada y en el MCP) y `--imputacion` en `contaperu
diagnosticar` y `desde-json`; lo que no trae sale de la configuración. Su forma, en
[estandar/LEEME.md](estandar/LEEME.md) (*Documento, imputación y configuración*).

## Para un agente de IA: el servidor MCP

Once herramientas: `diagnosticar` (qué bloquea, qué falta y qué saldría, **antes** de exportar),
`configuracion_por_defecto`, `validar_comprobantes`, `validar_partida_doble`, `generar_asiento`,
`exportar`, `leer_xml_ubl`, `leer_propuesta_sire`, `normalizar_detracciones`, `buscar_cuenta_pcge` y
`adaptar_pcge2026`. Y cinco recursos de lectura: el esquema del estándar, los catálogos de SUNAT, el
catálogo del PCGE 2026, los drivers disponibles y lo que se configura de cada uno.

El Excel y el ZIP del SIRE vuelven **como archivos** —recursos incrustados con su tipo—, así que el cliente
los ofrece para guardar en vez de enseñar una tira de letras.

### En tu propia máquina (stdio)

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

### Servido en red, para conectarlo como conector remoto

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

### Una imagen, dos puertas

La misma imagen sirve el MCP y ejecuta la CLI, según lo que le pases:

```bash
docker run --rm -v "$PWD:/data" contaperu-mcp \
    contaperu desde-json /data/mes.json --salida /data/salida
```

El servidor **no guarda nada y no sale a la red**. Cada llamada recibe todo lo que necesita y devuelve todo
lo que produce, así que dos llamadas iguales dan el mismo resultado y ninguna deja rastro.

---

## Qué sabe hacer

**Lee** el XML UBL 2.1 de la factura electrónica (sueltos o en ZIP, descartando los CDR) y el TXT de la
propuesta que SUNAT entrega en el SIRE.

**Valida** lo que se puede validar sin salir a ningún sitio: el RUC por su dígito verificador, que el IGV
cuadre con la base, que el total sea la suma de sus partes, que la fecha no sea posterior al periodo (y, en
compras, que no pasen los 12 meses de anotación de la Ley 29215), los duplicados.
Y **la partida doble**, sin tolerancia: un céntimo de diferencia detiene la exportación.

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

**Exporta** a CONCAR (Excel de asientos de 41 columnas), a CONTASIS (su registro de compras y de ventas en
Excel), al SIRE (TXT de reemplazo del RVIE y del RCE) y a un CSV genérico con las líneas de diario, para cualquier
destino que todavía no tenga driver.

**Diagnostica** un mes antes de exportarlo: qué comprobantes bloquean y cuáles solo avisan, qué falta
para el sistema de destino (cuenta, centro de costo, tipos sin sigla, monedas, correlativos, un reparto que no
suma la base o que el destino no admite, lo que no cabe en su formato),
qué detracciones esperan constancia y qué saldría. Una sola respuesta, por serie-número, sin corregir
ni inventar nada.

## Cómo está construido

Tres niveles, de abajo arriba: un **núcleo** que sabe contabilidad peruana y nada más; **drivers** que
conocen el formato de un sistema concreto y nada de contabilidad; y encima, la capa para **agentes**.
El asiento nace en las líneas neutrales del estándar `open-accounting` y cada ERP es una proyección de ellas
—CONCAR incluido—, así que un driver nuevo solo traduce vocabulario: las cuentas, los sentidos y la
detracción los pone el núcleo una vez para todos. Un driver de la comunidad se enchufa por *entry
points* sin tocar este repositorio. Todo esto, con sus porqués, en [ARQUITECTURA.md](ARQUITECTURA.md).
Lo que se tomó de QuickBooks, Xero y las APIs unificadas de EE. UU. —y lo que no—, en
[REFERENCIAS.md](REFERENCIAS.md).

## Qué **no** hace

- **No lee PDFs ni fotos.** Eso lo hace bien un modelo de lenguaje; aquí entra el dato ya estructurado.
- **No se conecta a SUNAT.** No hay credenciales, no hay Clave SOL, no sale ni un paquete a la red.
- **No guarda nada.** Ni base de datos, ni archivos, ni sesiones.
- **No reemplaza tu sistema contable.** Traduce hacia él.

---

## Estado

| Pieza | Estado |
|---|---|
| El estándar `open-accounting` 0.3 y su esquema | listo |
| Lectura de XML UBL 2.1 y de la propuesta del SIRE | listo |
| Validación del comprobante y de la partida doble | listo |
| Asiento: compras, ventas, honorarios, notas y detracción | listo |
| Drivers CONCAR, SIRE y CSV | listo |
| Servidor MCP y CLI | listo |
| `diagnosticar`: la capa para agentes — qué falta, para qué destino y a quién pedírselo | listo |
| Contrato de driver y drivers de terceros por *entry points* | listo |
| Reglas del **PCGE 2026** | **pendiente de la norma** — ver abajo |
| Conciliación de constancias de detracción | **pendiente de un archivo real** del Banco de la Nación |
| Driver CONTASIS (registro de compras y de ventas en Excel) | **listo**: CONTASIS importó los archivos que genera (13-sep-2026) |
| Drivers de SISCONT y STARSOFT | abierto a la comunidad — ver [CONTRIBUTING.md](CONTRIBUTING.md) |

### Sobre el PCGE 2026

El módulo `contaperu/pcge/` existe con la tabla **vacía**, y mientras lo esté no toca ninguna cuenta: lo dice
en su informe en vez de adivinar. Las equivalencias del Plan Contable General Empresarial 2026 se publicarán
**con la cita del artículo de la resolución al lado de cada mapeo** — el cargador rechaza un mapeo sin
fuente. Un neteo mal puesto en un repositorio público estropea la contabilidad de quien confíe en él, que es
exactamente lo contrario de lo que este proyecto quiere hacer.

Si tienes el texto oficial y quieres ayudar, es la contribución más útil que hay ahora mismo.

---

## Contribuir

```bash
pip install -e ".[dev]"
pytest
```

533 tests, sin red y sin credenciales.

Lo más valioso que puedes aportar es un **driver de salida** para un ERP que hoy no está — ver
[CONTRIBUTING.md](CONTRIBUTING.md) — o un **caso real** que el motor resuelva mal: un asiento que tu sistema
rechazó, un comprobante raro que se leyó torcido.

Regla del proyecto: **ninguna regla contable entra sin una fuente.** La norma, la resolución o el archivo
real que la justifica va al lado, en el código.

---

## In English

**ContaPerú is the open accounting core for Peru.** It reads the electronic receipts issued through
SUNAT (Peru's tax authority), builds the double-entry journal and exports it to the format each
local accounting system expects — CONCAR, CONTASIS, the SIRE tax filing, or plain CSV. No database, no state,
no network calls: JSON in, JSON or a file out.

It also defines **`open-accounting`**, an open interchange format for Peruvian accounting documents
(`estandar/`), with a formal JSON Schema. The rules aren't designed on paper: they come from real
files that production accounting systems and SUNAT actually accepted.

Install with `pip install contaperu`. The docs are in Spanish, because that's the language of the
domain and of the people who use it — but issues and pull requests in English are welcome.
