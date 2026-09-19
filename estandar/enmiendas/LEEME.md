# Enmiendas de `open-accounting`

Aquí se registra **cómo crece el estándar**. Una enmienda por cambio, con su caso real, su fuente y el test que la
sostiene.

Existe porque `open-accounting` 1.0 promete no romper hasta una 2.0, y una promesa así necesita un mecanismo, no
buena voluntad: sin un sitio donde quede escrito qué entró, por qué y con qué compatibilidad, la única forma de saber
si un cambio rompe es leer el `git log`.

**El texto normativo sigue siendo [`../LEEME.md`](../LEEME.md).** Una enmienda cuenta la decisión y su porqué; lo que
vale es lo que diga el estándar y lo que valide su esquema.

## Los estados

| Estado | Qué significa |
|---|---|
| `borrador` | La idea está escrita. Todavía no hay caso real ni decisión |
| `con caso real` | Hay un archivo de verdad, de un sistema de verdad, que lo pide |
| `aceptada` | Se va a hacer, y se sabe en qué versión |
| `final` | Está en el estándar. **Cita un test que existe** |
| `reservada` | El nombre está tomado: el día que entre, entra así. Mientras tanto, quien tenga el dato lo transporta en `datos_originales`, que el motor pasa sin interpretar |
| `rechazada` | Se decidió no hacerlo, y se dice por qué. No se borra: el porqué vale más que la propuesta |
| `reemplazada` | Otra enmienda la dejó sin sentido, y la nombra |

## La plantilla

Un archivo `NNNN-titulo-en-kebab.md`, con la tabla de cabecera —**Estado**, **Compatibilidad** (aditivo o cambio de
significado), **Nivel**, **Versión**, **Test**— y tres secciones:

- **Motivación** — el caso real. Si no lo hay, se dice qué falta: es lo que separa `borrador` de `con caso real`.
- **Fuente** — la norma, la resolución, la API ajena o el archivo que lo respalda. Ninguna regla sin fuente.
- **Especificación** — qué campo, dónde, de qué tipo, obligatorio u opcional, y qué pasa con quien no lo conozca.

## Cómo se propone una

Un aviso en el repositorio con **el caso real detrás**: un archivo de verdad de un sistema de verdad, anonimizado.
Quién aprueba y en cuánto se responde está en [`../LEEME.md`](../LEEME.md), «Quién gobierna los catálogos».

**Y la regla que protege a quien ya integró: un valor publicado no se quita ni cambia de significado.** Si resulta
equivocado, se marca la enmienda como `reemplazada` y entra otra al lado. Es lo que hacen las listas de códigos de
ISO 20022 y de EN 16931, y la razón de que sus mensajes sobrevivan décadas.

## Las que hay

| | Enmienda | Estado |
|---|---|---|
| [0001](0001-id-en-destino.md) | `linea.id_en_destino` — el id del asiento en el sistema de destino | `reservada` |
| [0002](0002-dimensiones.md) | `dimensiones` — los ejes analíticos más allá del centro de costo | `reservada` |
| [0003](0003-estado-de-la-linea.md) | `linea.estado` — en qué punto del circuito está esa línea | `reservada` |
| [0004](0004-medio-de-pago.md) | `medio_pago` — el código de medio de pago de SUNAT | `reservada` |
| [0005](0005-retencion-de-igv.md) | `retencion_igv` — la retención del 3 % del régimen de retenciones | `reservada` |
| [0006](0006-percepcion.md) | `percepcion` — el régimen de percepciones del IGV | `reservada` |
| [0007](0007-no-domiciliado.md) | `no_domiciliado` — el comprobante de un sujeto del exterior | `reservada` |
