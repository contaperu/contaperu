# 0009 · `documento.id_externo` en la línea, y el `id_externo` obligatorio cuando hay imputaciones

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 |
| **Test** | `tests/test_imputaciones_en_el_documento.py::test_cada_linea_lleva_el_id_externo_de_su_comprobante` |

## Motivación

El bloque `documento` de cada línea del asiento la enlaza con su comprobante, pero lo hacía **por
serie y número**, que es la identidad tributaria y no la del sistema que registró. Con `imputaciones` llaveadas por
`id_externo`, el enlace quedaba a medio camino: el archivo no se podía recorrer entero sin adivinar.

Y al revés: sin `id_externo` en el comprobante no hay con qué casar su imputación, así que el requisito tiene que
existir — pero solo cuando hay imputaciones.

## Fuente

`API-DE-REGISTRO.md`, «El comprobante y el asiento: por qué son dos bloques». Es el papel de `SourceID`
y `SourceType` en Xero y de `SourceDocumentID` en SAF-T, que enlazan el asiento con su documento origen.

## Especificación

Campo `id_externo` dentro de `linea.documento`: el id con el que el sistema que **produjo** el comprobante
lo conoce. Opcional. No confundir con `id_en_destino` ([0001](0001-id-en-destino.md)), que es el del sistema que recibe.

**`comprobante.id_externo` pasa a obligatorio cuando el documento trae `imputaciones`**, con un `if/then` en la raíz
del esquema; sin imputaciones no se pide. El motor añade lo que el esquema no puede expresar: que ningún `id_externo`
esté repetido. **Las dos comprobaciones valen solo por la vía del documento**: por el argumento se puede imputar 3 de
10 comprobantes y que los otros 7 no traigan id, y exigirlo ahí cambiaría en silencio lo que ya funciona.

El campo es **texto único libre**: un uuid es la forma recomendada, pero el esquema no lo impone — quien integra usa
el id de su propia fila.

**Fuera de la huella.** Es un puntero al sistema que produjo el comprobante, no contenido contable, y sobre todo: al
reexportar tras un «deshacer» la aplicación recrea sus filas con ids nuevos, así que con el id dentro la misma tanda
daría otra huella y el aviso de lote repetido se apagaría justo en el caso para el que existe.
