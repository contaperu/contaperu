# 0019 · El bloque `detraccion` admite anotaciones `_`, como la raíz

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 (aditivo: no sube la versión, avanza el tag) |
| **Test** | `tests/test_cabecera.py::test_la_cabecera_es_un_comprobante_del_estandar` |

## Motivación

El estándar dice desde su 1.0, en dos sitios, que **las claves que empiezan con `_` son anotaciones: se transportan,
se ignoran y nunca llevan datos con significado contable**. El esquema lo implementaba en la raíz del documento —con
`patternProperties: {"^_": …}` al lado de su `additionalProperties: false`— y **no en los bloques de dentro**. Así que
la promesa valía para el documento y no para sus partes.

Donde se notó fue en la detracción. El motor anota, al normalizar, la tasa del Catálogo 54 con la que calculó el monto:
la necesita `validar` para avisar de la confusión más cara que comete una IA leyendo facturas —«la IA lee un 10 % y el
código es del 12 %» (John, 10-sep-2026)— y la necesita sin configuración, porque `validar(c, libro)` no la recibe y se
llama también al leer un archivo. Esa anotación se llamaba `tasa_tabla`, sin guion bajo, y `$defs/detraccion` la
rechazaba por ser un bloque cerrado. Consecuencia: al escribir un `comprobante` del estándar había que **filtrar el
bloque a sus siete claves declaradas**, o el documento que produce un driver fallaba su propio esquema.

El filtro funcionaba, pero cobraba un precio escondido: **un documento que volvía a entrar al motor había perdido la
tasa**, así que su validación ya no podía avisar de la discrepancia que el motor sí había visto la primera vez. La
anotación existe justamente para sobrevivir a ese viaje.

## Fuente

- El propio estándar, [`../LEEME.md`](../LEEME.md): «Las claves que empiezan con `_` son anotaciones de quien produce
  el archivo. Se transportan y se ignoran» (reglas del documento) y la sección «Anotaciones que produce el motor».
- El esquema, que ya traía el precedente exacto en su raíz: `additionalProperties: false` junto a
  `patternProperties: {"^_": {...}}`.

## Especificación

`$defs/detraccion` gana `patternProperties: {"^_": {…}}`. El bloque **sigue siendo cerrado** para todo lo demás: una
clave inventada sin guion bajo se rechaza igual que antes.

La anotación del motor pasa a llamarse **`_tasa_tabla`** (la tasa del Catálogo 54 con la que se calculó el monto, como
texto exacto). Viaja dentro del documento, y por tanto:

- `asiento.cabecera_de(...).como_comprobante()` ya no filtra el bloque: solo quita las claves vacías, que es la regla
  general del estándar —«no lo sé» se dice omitiendo la clave—.
- Un documento que vuelve a entrar conserva la tasa, así que `validar` puede volver a comparar sin configuración.

## Qué NO hace

- **No invalida ningún documento.** Es aditivo: lo que validaba antes valida ahora. Lo único que deja de valer es la
  clave vieja `tasa_tabla` sin guion bajo, que el esquema **ya rechazaba**: no era válida antes y no lo es ahora.
- **No abre los demás bloques.** Esta enmienda es la de la detracción, que es donde hubo un caso. El día que otro
  bloque necesite anotar lo suyo, entra igual y con su enmienda.
- **No hace de `_tasa_tabla` un dato contable.** Es una anotación: quien lea el documento puede ignorarla, y ningún
  importe depende de ella. El motor la usa para avisar, nunca para calcular — el monto lo calcula
  `detracciones.monto_detraccion`, una sola vez.
- **No mueve la huella.** Se serializa con `sort_keys=True` sobre las líneas del asiento, y esta anotación va en el
  comprobante, no en la línea.
