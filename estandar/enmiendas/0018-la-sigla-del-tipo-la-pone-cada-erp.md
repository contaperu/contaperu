# 0018 · `documento.tipo` y `referencia.tipo`: la sigla la pone cada ERP, no el estándar

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | el motor deja de emitirlos; los campos siguen siendo válidos |
| **Nivel** | motor |
| **Versión** | `open-accounting` 1.0 (el esquema no cambia; lo que cambia es lo que el motor escribe) |
| **Test** | `tests/test_linea_del_comprobante.py::test_el_motor_dice_el_rol_y_el_codigo_sunat_de_cada_linea` |

## Motivación

Es la misma decisión que la enmienda 0017, aplicada al otro par de campos que la arrastraba. La línea del comprobante
llevaba dos formas de decir qué tipo de documento es: `documento.tipo_cp`, el **código de la Tabla 10 de SUNAT**
(`01`), y `documento.tipo`, **la sigla con la que un sistema contable lo llama** (`FT` en la Tabla General 06 de
CONCAR; `FT` también en STARSOFT, pero `CC` donde CONCAR pone `NC`). Lo mismo en `referencia`.

El propio motor lo tenía anotado como deuda, y con fecha: «la sigla del documento (`documento.tipo`) **se conserva por
compatibilidad —la leían los consumidores de la 0.6—**, pero al lado viaja `tipo_cp`, el código SUNAT, que es el que
manda». Esos consumidores ya no existen, y la 4.0 es la primera ventana para retirarla.

Mantenerla costaba dos cosas:

- **El estándar decía una cosa y el motor hacía otra.** Su regla 4 ya manda que el tipo es el código de SUNAT y
  «nunca la sigla del ERP de destino», porque la traducción es del driver. La sigla viajaba igual, en un campo que el
  esquema describe como «Tipo de documento en el vocabulario del ERP destino»: vocabulario de un sistema dentro del
  documento común.
- **Obligaba a elegir un sistema.** La sigla la calculaba el núcleo con el mapa `tipos` de la configuración, así que
  la línea llevaba la del destino que se estuviera exportando. Con un solo mapa por empresa eso funciona; con dos
  destinos distintos sobre el mismo mes, la línea solo puede llevar una.

## Fuente

- **Tabla 10 de SUNAT**, «Tipo de comprobante de pago o documento»: la única numeración oficial, y la que el estándar
  declara en `tipo_cp`.
- **Tabla General 06 de CONCAR** y el maestro de documentos de STARSOFT: cada sistema numera la suya, y el manual de
  STARSOFT lo dice explícitamente —el tipo es «el que tiene registrado TU sistema»—. Dos ejemplos de que no hay una
  sigla universal: la nota de crédito es `NC` en CONCAR y `CC` en STARSOFT.

## Especificación

El motor escribe en la línea **solo `tipo_cp`**, el código de la Tabla 10, en `documento` y en `referencia`. La sigla
la escribe el driver del destino, en la columna que le toque, con **`asiento.sigla_de_tipo(tipo_cp, config)`**:

- Vive en el núcleo, y no copiada en cada driver, porque el mapa (`tipos`) es configuración del asiento y la regla es
  una: **un tipo sin sigla no se inventa**; detiene la exportación antes de llegar al formato (`tipos_sin_sigla`).
- `drivers/concar/`: sus columnas R y Z. `drivers/starsoft/`: sus columnas de tipo de documento, de documento de
  referencia y la glosa, que repite el tipo y el número.
- Al leer un archivo de CONCAR, la columna R **sí vuelve** a `documento.tipo`: ahí la sigla es un dato del archivo que
  se está leyendo, no una traducción que el motor inventa.

## Qué NO hace

- **No toca el esquema.** `tipo` sigue declarado y opcional en `documento` y en `referencia`, así que un documento que
  lo traiga —guardado antes de la 4.0, o producido por otro sistema— **sigue validando**, y la versión del estándar no
  se mueve.
- **No cambia el vocabulario neutral.** Ahí la sigla ya no viajaba: salía vacía desde la 1.1. Lo que hace esta
  enmienda es que el vocabulario legacy deje de ser una excepción.
- **No toca `sub_diario` ni `correlativo`.** Siguen siendo vocabulario legacy en la línea, y con motivo: son
  contabilidad peruana —en qué registro va el apunte y con qué número—, no el nombre que un sistema le da a un tipo.

## Qué rompe

**La huella de todos los asientos**, no solo de algunos: `huella.SIN` excluye el correlativo, la clase y el
`documento.id_externo`, así que la sigla entraba en el hash. Quien persista huellas para saber qué ya exportó deja de
reconocer, una vez, todo lo anterior. Y la columna `doc_tipo` del CSV de intercambio, que decía `FT`, va vacía: el CSV
es un canal neutral y la sigla era de CONCAR.
