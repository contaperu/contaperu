# ContaPerú

**Núcleo contable abierto del Perú.** Lee los comprobantes que emite SUNAT, arma la partida doble y los
exporta al formato que pide cada sistema contable. Sin base de datos, sin estado, sin llamadas a la red:
entra un JSON, sale un JSON o un archivo.

Está pensado para tres tipos de usuario, y a los tres les sirve el mismo código:

- **Un estudio contable o una empresa** que quiere automatizar su registro de compras y ventas sin cambiar
  el sistema que ya usa.
- **Un desarrollador** que integra contabilidad peruana y no quiere reimplementar el IGV, las detracciones,
  las notas de crédito y los sub-diarios por enésima vez.
- **Un agente de IA** que ya sabe leer un PDF o un XML, pero necesita un riel determinista donde depositar
  lo que extrajo — para eso está el servidor MCP.

Licencia MIT. Se dona a la comunidad contable peruana.

---

## El problema

El software contable peruano nació en los noventa y no se habla entre sí. Cada uno importa su propio archivo
plano, con sus columnas y sus siglas. Cuando además aparece una IA capaz de leer cien facturas en un minuto,
el cuello de botella deja de ser la lectura: es que **no hay un formato común y validado donde poner el
resultado**, y una cuenta mal puesta o un asiento descuadrado se detecta meses después.

ContaPerú aporta las dos piezas que faltan:

1. **[`pe-ledger`](estandar/LEEME.md)** — un estándar JSON para el documento contable peruano: el libro, los
   comprobantes y las líneas de diario. Con su [esquema formal](estandar/pe-ledger.schema.json).
2. **Un motor determinista** que valida ese documento, arma el asiento y lo traduce al formato de cada ERP.

---

## Instalación

```bash
pip install contaperu
```

Extras según lo que se necesite:

```bash
pip install "contaperu[excel]"   # exportar a CONCAR (.xlsx)
pip install "contaperu[mcp]"     # servidor MCP para agentes de IA
pip install "contaperu[todo]"    # todo
```

---

## Estado

Este repositorio está en construcción. Lo que hay y lo que falta, sin adornos:

| Pieza | Estado |
|---|---|
| El estándar `pe-ledger` 0.1 y su esquema | **listo** |
| Lectura de XML UBL 2.1 de SUNAT | en curso |
| Lectura de la propuesta del SIRE (TXT) | en curso |
| Validación del comprobante y de la partida doble | en curso |
| Asiento contable (compras, ventas, honorarios, notas, detracción) | en curso |
| Driver CONCAR (Excel de 41 columnas) | en curso |
| Driver SIRE (TXT de reemplazo, RVIE y RCE) | en curso |
| Driver CSV genérico | en curso |
| Servidor MCP | en curso |
| Reglas del **PCGE 2026** | **pendiente de la norma** — ver abajo |
| Conciliación de constancias de detracción | **pendiente de un archivo real** del Banco de la Nación |
| Drivers de CONTASIS y SISCONT | abierto a la comunidad |

### Sobre el PCGE 2026

El módulo `contaperu/pcge/` existe con la tabla **vacía**. Las equivalencias del Plan Contable General
Empresarial 2026 se publicarán **con la cita del artículo de la resolución al lado de cada mapeo**, no de
memoria. Un neteo mal puesto en un repositorio público estropea la contabilidad de quien confíe en él, y eso
es exactamente lo contrario de lo que este proyecto quiere hacer. Si tienes el texto oficial y quieres
ayudar, es la contribución más útil que hay ahora mismo.

---

## Lo que este proyecto **no** hace

- **No lee PDFs ni fotos.** Eso lo hace bien un modelo de lenguaje; aquí entra el resultado ya estructurado.
- **No se conecta a SUNAT.** No hay credenciales, no hay Clave SOL, no sale ni un paquete a la red.
- **No guarda nada.** Ni base de datos, ni archivos, ni sesiones. Cada llamada se explica sola.
- **No reemplaza tu sistema contable.** Traduce hacia él.

---

## Contribuir

El aporte más valioso es un **driver de salida** para un ERP que hoy no está: ver
[CONTRIBUTING.md](CONTRIBUTING.md). El segundo, un **caso real** que el motor resuelva mal — un asiento que
tu sistema rechazó, un comprobante raro que se leyó torcido.

Regla del proyecto: **nada de reglas contables sin una fuente**. Cada regla lleva al lado la norma, la
resolución o el archivo real que la justifica.
