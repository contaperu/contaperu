# 0007 · `no_domiciliado`: el comprobante que emite un sujeto sin domicilio en el Perú

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 4.1 (un bloque opcional: sube la menor, porque el tag de la 4.0 ya está publicado) |
| **Test** | `tests/test_no_domiciliado.py`, `tests/test_catalogos_no_domiciliados.py` |

## Motivación

Un proveedor del exterior no emite un comprobante de la Tabla 10: emite su propia factura. El comprobante la lleva
como un 91 —sus notas, el 97 y el 98—, y el registro de compras de no domiciliados del SIRE, el **080500**, pide de
ella bastante más que su número: el país de residencia, la renta, la tasa y el impuesto retenido, el convenio para
evitar la doble imposición, el tipo de renta, la modalidad del servicio y el documento que sustenta el crédito
fiscal del IGV.

**La reserva decía otra cosa**, y se cambia antes de publicar: preveía «el número del comprobante del exterior» como
un texto. Ese número ya tiene sitio —`serie` y `numero`, igual que cualquier comprobante—, y lo que de verdad faltaba
es todo lo otro. Un nombre reservado no es un valor publicado, así que puede cambiar de forma; lo que no podría es
cambiar después de entrar.

**El caso real llegó en dos tiempos.** El 01-nov-2026 el motor empezó a leer el 080500 de un mes presentado (15.3.0):
diez compras del exterior de un contribuyente real, con su país, su renta y su convenio crudos en la fila de SUNAT
porque no había dónde ponerlos. Y el 03-nov-2026 John pidió registrarlas subiendo la factura y escribir el 080500 desde
la aplicación: eso necesita que esas columnas sean campos, no una fila cruda.

## Fuente

El Anexo 9 de la RS 040-2022, §8.5 («Información de operaciones con sujetos no domiciliados»), campo a campo; las
Tablas 16 a 21 de su Anexo 01 para los códigos; y el registro real que SUNAT aceptó en setiembre de 2026, que es de
donde salió que los importes van en soles.

## Especificación

Bloque `no_domiciliado` en el comprobante, objeto o nulo, cerrado. Ninguna clave es obligatoria en el estándar —el
driver del 080500 exige las que el registro marca—; una omitida es «el documento no lo dice».

| Clave | Qué es | Campo del Anexo 9 |
|---|---|---|
| `pais`, `domicilio` | País de residencia (Tabla 16) y domicilio en el extranjero | 17, 19 |
| `beneficiario_doc`, `beneficiario_nombre`, `beneficiario_pais` | El beneficiario efectivo, si no es el proveedor | 21–23 |
| `vinculo` | Vinculación económica (Tabla 17) | 24 |
| `renta_bruta`, `deduccion`, `renta_neta`, `porcentaje`, `impuesto_retenido` | La renta y su retención | 25–29 |
| `igv_utilizacion` | El IGV de la utilización del servicio («Monto Ret.») | 14 |
| `convenio`, `exoneracion`, `tipo_renta`, `modalidad`, `art_76` | Tablas 18, 21, 19 y 20; el art. 76 de la LIR | 30–34 |
| `sustento_tipo_cp`, `sustento_serie`, `sustento_anio_dua`, `sustento_numero` | El documento que sustenta el crédito fiscal | 10–13 |

**Los importes del bloque van EN SOLES**, como los declara el registro, aunque el comprobante sea en otra moneda. Se
midió sobre el registro real: los campos de valor y total vuelven exactos al convertirlos de soles a dólares y de
vuelta, y el impuesto retenido no, porque se calculó en soles. Es la única excepción del estándar a «los importes van
en la moneda del comprobante», y es del bloque.

**No entra en ningún asiento.** El 91 se asienta como una compra común; el IGV de utilización y la renta retenida son
otro paso, con un caso real. Sí llega a la cabecera que ve un driver, por la regla de `tests/test_cabecera.py`.
