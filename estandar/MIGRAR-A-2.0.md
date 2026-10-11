# Migrar de `open-accounting` 1.0 a 2.0

**Lo único que la 2.0 hace es quitar.** Cuatro claves que ninguna hacía falta, y la versión. Si produces documentos
con el motor, no tienes que hacer nada: los arma él, y la clave de versión la estampa él. Si los escribes tú, esto
es todo — y es un borrado, no una traducción: no hay ningún campo nuevo que rellenar.

**El motor no acepta documentos que se declaren `1.0`**: se rechazan al leer el libro, con un mensaje que nombra lo
que cambia. Es la misma decisión que la 1.0 tomó con la 0.3 —leer las dos cuesta dos caminos en el lector y una
regla de cuál gana—, con una diferencia que conviene decir: cuando salió la 1.0 nadie de fuera producía documentos,
y **la 1.0 lleva semanas publicada en PyPI**. De ahí que esta guía exista y que la versión saliera con una
pre-release para que quien integra la probara antes.

## 1 · La clave de versión

```diff
- "open_accounting": "1.0"
+ "open_accounting": "2.0"
```

Y si citas el esquema o los catálogos por su URL, el tag cambia:

```
https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-2.0/estandar/open-accounting.schema.json
https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-2.0/estandar/catalogos.json
```

## 2 · El `rol` sale de la línea del asiento

```diff
  {
    "cuenta": "6343001", "debe_haber": "D", "importe": "10000.00", "clase": "gasto",
-   "rol": "principal",
    "glosa": "SERVICIO DE PRUEBA"
  }
```

**Y no se sustituye por nada: se deriva.** El papel de una línea sale de lo que la línea ya trae, y esa es la parte
que importa si tu sistema lo usaba:

| Lo que trae la línea | Su papel |
|---|---|
| un bloque `impuesto`, `retencion` o `detraccion` | ese mismo rol |
| su `debe_haber` es el lado del tercero de ese libro (el Haber en una compra, el Debe en una venta) | `tercero` |
| si no, y trae `contraparte_doc` | `recorte` |
| si no | `principal` |

Con un término que no se puede olvidar: **en una nota de crédito los dos lados se cambian**, así que el lado del
tercero se invierte con ellos. Una nota de crédito de compra lleva su tercero al Debe.

Si integras el motor, no lo escribas: `contaperu.drivers.kit.rol.rol_de(linea, libro)` es esa tabla, con sus tests
y con el caso de la boleta —cuyo cliente no lleva RUC y aun así es el tercero— ya cubierto. El vocabulario de los
papeles sigue publicado en el catálogo `roles`, que ya no describe una clave del documento sino lo que esa regla
devuelve.

**Por qué salió**, que es lo que hace esto digerible: el `rol` lo inventamos nosotros. Ningún estándar abierto del
asiento lo tiene —XBRL GL usa cuenta, tipo de documento y D/H; SAF-T distingue la línea por los datos que trae
(`CustomerID`/`SupplierID`, `TaxInformation`); Beancount y hledger llevan cuenta e importe con signo— y el único
precedente es Odoo, que además parte el vocabulario en dos según si el asiento viene de una factura o de un pago.
Existía para que un sistema de destino encontrara la línea que su columna pide sin conocer la cuenta, que la elige
cada empresa; y eso se puede derivar, así que no era un dato del asiento.

**Y tres obsoletos del catálogo `roles` se van con él**: `igv`, `retencion_4ta` y `detraccion_tercero`, los nombres
que la 5.0 renombró. Es la única excepción que este estándar ha hecho a «un valor obsoleto no desaparece nunca», y
la razón vale más que el caso: **un valor obsoleto sobrevive mientras exista la clave donde se guardaba.**

## 3 · La sigla de tu ERP sale de la línea

```diff
  "documento": {
-   "tipo": "FT",
    "tipo_cp": "01", "serie_numero": "F001-123", "fecha_emision": "2026-08-11"
  },
  "referencia": {
-   "tipo": "NC",
    "tipo_cp": "07", "serie_numero": "F001-9"
  }
```

El que manda es `tipo_cp`, el código de la **Tabla 10 de SUNAT**, y es el único que viaja. La sigla con que tu
sistema llame a ese documento la pone su driver desde ese código. Esto cierra lo que la 4.0 ya decidió —el motor
dejó de escribir esas dos claves entonces (enmienda 0018)— y que se quedó a medias: el campo siguió declarado tres
mayores sin que nadie lo escribiera.

Si tienes una sigla que **no** está en la Tabla 10, la respuesta es la misma que para cualquier otra traducción de
tu sistema: va en el mapa `tipos` de tu configuración, que es de donde el driver la saca.

## 4 · `detraccion.estado` sale del bloque

```diff
  "detraccion": {
    "codigo": "027", "porcentaje": 4, "monto": "198.00", "cuenta": "00-123-456789",
-   "estado": "PROVISIONADO",
    "nro_constancia": "", "fecha_constancia": ""
  }
```

**Los dos huecos que quedan SON el estado**, y son los únicos datos que no se pueden inventar: una detracción está
pagada cuando tiene un `nro_constancia` que no es el número comodín **y** una `fecha_constancia`. Con el número y
sin la fecha sigue pendiente, que es lo que hace que alguien vuelva a poner el día.

El campo era informativo y su propia descripción decía que quien lee el documento no se fía de él. Lo que lo cerró
fue medirlo: el motor no lo escribía nunca, y las cadenas `PROVISIONADO` y `PAGADO` no salen de él — lo que la api
publica son los dos cubos del diagnóstico, `detracciones_pendientes` y `detracciones_pagadas`. Un enum publicado
para un campo que nadie escribe es una trampa.

## Lo que NO cambia

- **Los cuatro campos obligatorios de una línea** siguen siendo `cuenta`, `debe_haber`, `importe` y `clase`. De
  hecho la 2.0 es esa regla llevada hasta el final: si con ellos se contabiliza una línea, lo demás no es parte de
  la línea.
- **Ninguna salida.** El Excel de CONCAR y el de CONTASIS quedan celda a celda idénticos, y los tres meses que la
  batería caracteriza no mueven ni un importe. Lo que cambia del CSV son dos columnas que salían siempre vacías
  (`doc_tipo` y `ref_tipo`); su columna `rol` se queda, ahora derivada.
- **Ninguna huella.** `rol`, `documento.tipo` y `detraccion.estado` ya estaban fuera del hash o no se escribían, así
  que quien persista huellas para saber qué exportó sigue reconociendo todo lo anterior.
- **El resto del documento**, entero: el libro, los comprobantes, las imputaciones, los movimientos, las
  constancias, los bloques tipados y las anotaciones `_` del motor.

## Si guardas documentos de la 1.0

El motor no los lee. Para volver a armar su asiento hay dos caminos y los dos son cortos:

1. **Quitar las cuatro claves y cambiar la versión.** Es un borrado mecánico: `rol` en cada línea del asiento,
   `tipo` en `documento` y en `referencia`, y `estado` en la detracción.
2. **Volver a generar desde los comprobantes**, que es lo que hace quien guarda el documento del driver
   `asiento_contable`: ese archivo se basta —lleva `libro` y `comprobantes`—, así que entra al motor y sale con el
   mismo asiento y la misma huella.

Y si lo que tienes es un **archivo ya exportado** —un Excel de CONCAR, un TXT del SIRE—, no hay nada que migrar: eso
no es un documento del estándar.
