# 0016 · `dscto_otros`: el descuento que el registro informa dentro de «otros conceptos»

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 (aditivo: no sube la versión, avanza el tag) |
| **Test** | `tests/test_sire_txt.py::test_otros_conceptos_en_negativo_es_un_descuento` |

## Motivación

Un registro de compras real de 1116 filas, ya declarado: **seis facturas no cuadraban**, y las seis por lo mismo.
Traían el campo «Otros conceptos, tributos y cargos» en negativo, que es como SUNAT informa un descuento global que no
forma base imponible. Son facturas de grifo y de peaje —series `FA04`, `FA05`, `FTVI`—, donde el descuento es la
norma y no la excepción.

```
01-FA04-440774   no gravado 96.00 · otros −13.40 · total 82.60
```

El motor guardaba el importe con `monto()`, que **devuelve el valor absoluto porque el signo no es parte del dato**
(la regla de la primera línea del esquema). Así que sumaba 96.00 + 13.40 = 109.40 y avisaba «el total no cuadra» por
un comprobante perfectamente correcto. Y lo peor no era el aviso: el TXT que este motor genera escribía **+13.40 donde
SUNAT tiene −13.40**, o sea una diferencia real con la Administración en un archivo que se declara.

No valía con dejar que `otros` fuera negativo. «Los importes van SIEMPRE en positivo» no es un detalle de estilo: es
lo que hace que una nota de crédito se guarde igual que una factura y que el signo lo ponga **el driver de salida**,
que es quien sabe cómo lo escribe cada destino. Romperla por un caso habría obligado a revisar cada driver.

## Fuente

- **Campo 24 del Anexo 8 de la RS 040-2022/SUNAT, §8.4** (propuesta del RCE, compras): «Otros conceptos, tributos y
  cargos que no forman parte de la base imponible».
- **Campo 25 del Anexo N.° 2 de la RS 112-2021/SUNAT** (propuesta del RVIE, ventas): el equivalente.

Los dos son **una sola columna con signo**: el neto de lo que suma y lo que resta. El archivo no desglosa cuánto era
cargo y cuánto descuento, y esta enmienda tampoco se lo inventa.

## Especificación

`dscto_otros` — importe opcional, **positivo** como todos, por defecto `0`.

- **Resta del total.** Ahí se separa de `dscto_base` y `dscto_igv`, que con el mismo prefijo **no mueven el total**:
  aquellos solo dicen qué parte de la base viaja en la columna de descuento del registro. El total se comprueba como
  `base + IGV + no gravado + cargos − dscto_otros`.
- **Al leer**, un valor negativo en esa columna va aquí y `otros` queda en cero. La condición es que su signo sea
  **contrario al del total**, no que sea negativo a secas: en una nota de crédito *todos* los campos vienen negativos
  porque lo es la operación entera, y ese signo ya lo pone el driver al escribir. Tomarlo por descuento invertiría la
  nota. En el registro real citado, las dos notas de crédito traen esta columna en `0.00` y las seis facturas con
  descuento la traen contraria: la regla se comprobó, no se supuso.
- **Al escribir**, el registro recibe el **neto** `otros − dscto_otros` con su signo, que es la única columna que
  tiene. La ida y vuelta devuelve el archivo idéntico.
- **No se inventa el desglose.** Si una factura tuviera cargo y descuento a la vez, el archivo solo trae el neto y eso
  es lo que se guarda.

## Qué NO hace

- **No cambia el tipo de `otros`.** Sigue siendo un importe positivo y el esquema sigue con `minimum: 0`.
- **No toca las notas de crédito.** Su signo se decide donde se decidía.
- **No llega al asiento como línea propia.** Es parte de «otros conceptos» y comparte su cuenta
  (`cuentas.otros_tributos`); lo que cambia es el neto que llega.
