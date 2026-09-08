# ContaPerú

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

1. **[`pe-ledger`](estandar/LEEME.md)** — un estándar JSON para el documento contable peruano: el libro, los
   comprobantes y las líneas de diario. Con su [esquema formal](estandar/pe-ledger.schema.json).
2. **Un motor determinista** que valida ese documento, arma el asiento y lo traduce al formato de cada ERP.

No es un diseño en papel: el motor lleva un año generando el Excel de CONCAR y el TXT del SIRE de empresas
reales, y el estándar se deriva de su modelo, no al revés.

---

## Instalación

```bash
pip install contaperu              # el núcleo
pip install "contaperu[excel]"     # + exportar a CONCAR (.xlsx)
pip install "contaperu[mcp]"       # + el servidor MCP
pip install "contaperu[todo]"      # todo
```

## De un XML de SUNAT a un asiento, en diez líneas

```python
from contaperu import operaciones as op

libro = {"ruc": "20601111111", "razon_social": "MI EMPRESA SAC",
         "periodo": "202608", "tipo": "compra"}

doc = op.leer_xml(open("factura.xml", encoding="utf-8").read(), libro)
doc = op.revisar(doc)                     # observaciones por comprobante
print(doc["_revision"])

asiento = op.generar_asiento(doc)         # líneas de diario, sin formato de ERP
excel = op.exportar(doc, "concar")        # el .xlsx, en base64
```

Y desde la línea de comandos:

```bash
contaperu generar --tipo compra --ruc 20601111111 --razon "MI EMPRESA SAC" \
    --periodo 202608 --driver sire --salida ./salida  comprobantes/*.xml
```

## Para un agente de IA: el servidor MCP

```bash
contaperu-mcp                                        # por stdio (Claude Desktop, IDEs)
contaperu-mcp --transporte http --host 0.0.0.0       # por HTTP
docker run -i --rm contaperu-mcp                     # sin instalar nada
```

Nueve herramientas: `configuracion_por_defecto`, `validar_comprobantes`, `validar_partida_doble`,
`generar_asiento`, `exportar`, `leer_xml_ubl`, `leer_propuesta_sire`, `normalizar_detracciones` y
`adaptar_pcge2026`. Y tres recursos de lectura: el esquema del estándar, los catálogos de SUNAT y los
drivers disponibles.

El servidor **no guarda nada y no sale a la red**. Cada llamada recibe todo lo que necesita y devuelve todo
lo que produce, así que dos llamadas iguales dan el mismo resultado y ninguna deja rastro.

---

## Qué sabe hacer

**Lee** el XML UBL 2.1 de la factura electrónica (sueltos o en ZIP, descartando los CDR) y el TXT de la
propuesta que SUNAT entrega en el SIRE.

**Valida** lo que se puede validar sin salir a ningún sitio: el RUC por su dígito verificador, que el IGV
cuadre con la base, que el total sea la suma de sus partes, que la fecha caiga en el periodo, los duplicados.
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

**Exporta** a CONCAR (Excel de 41 columnas), al SIRE (TXT de reemplazo del RVIE y del RCE) y a un CSV
genérico con las líneas de diario, para cualquier destino que todavía no tenga driver.

## Qué **no** hace

- **No lee PDFs ni fotos.** Eso lo hace bien un modelo de lenguaje; aquí entra el dato ya estructurado.
- **No se conecta a SUNAT.** No hay credenciales, no hay Clave SOL, no sale ni un paquete a la red.
- **No guarda nada.** Ni base de datos, ni archivos, ni sesiones.
- **No reemplaza tu sistema contable.** Traduce hacia él.

---

## Estado

| Pieza | Estado |
|---|---|
| El estándar `pe-ledger` 0.1 y su esquema | listo |
| Lectura de XML UBL 2.1 y de la propuesta del SIRE | listo |
| Validación del comprobante y de la partida doble | listo |
| Asiento: compras, ventas, honorarios, notas y detracción | listo |
| Drivers CONCAR, SIRE y CSV | listo |
| Servidor MCP y CLI | listo |
| Reglas del **PCGE 2026** | **pendiente de la norma** — ver abajo |
| Conciliación de constancias de detracción | **pendiente de un archivo real** del Banco de la Nación |
| Drivers de CONTASIS y SISCONT | abierto a la comunidad |

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

146 tests, sin red y sin credenciales.

Lo más valioso que puedes aportar es un **driver de salida** para un ERP que hoy no está — ver
[CONTRIBUTING.md](CONTRIBUTING.md) — o un **caso real** que el motor resuelva mal: un asiento que tu sistema
rechazó, un comprobante raro que se leyó torcido.

Regla del proyecto: **ninguna regla contable entra sin una fuente.** La norma, la resolución o el archivo
real que la justifica va al lado, en el código.
