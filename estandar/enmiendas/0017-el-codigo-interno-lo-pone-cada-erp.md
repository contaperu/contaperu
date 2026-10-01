# 0017 · `detraccion.codigo_interno`: el código interno lo pone cada ERP, no el estándar

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | el motor deja de emitirlo; el campo sigue siendo válido |
| **Nivel** | motor |
| **Versión** | `open-accounting` 1.0 (el esquema no cambia; lo que cambia es lo que el motor escribe) |
| **Test** | `tests/test_linea_del_comprobante.py::test_la_linea_lleva_el_codigo_de_sunat_y_el_interno_lo_pone_cada_erp` |

## Motivación

La línea del comprobante llevaba dos códigos para la misma cosa: `detraccion.codigo`, el del **Catálogo 54 de
SUNAT** (`027`), y `detraccion.codigo_interno`, el de la **Tabla General 28 de CONCAR** (`02702`, cinco dígitos: el
de SUNAT más dos propios del contribuyente). El segundo lo calculaba el núcleo, leyendo un mapa que vivía en la
configuración del asiento y no en la de ningún sistema.

Eso tenía tres consecuencias, y ninguna era teórica:

- **El motor inventaba.** Un código que la empresa no hubiera mapeado salía como el de SUNAT más `01`, «el patrón más
  común» de esa tabla. Es una conjetura sobre la numeración interna de un sistema ajeno, hecha en el núcleo, y
  contradice la regla de que nada se adivina.
- **Se lo llevaban destinos que no lo quieren.** STARSOFT escribe el código de SUNAT a propósito —su propio
  comentario lo dice: «el código de SUNAT (`027`), no el interno que CONCAR mapea en su tabla (`02702`)»— y nacía con
  catorce mapeos de CONCAR que nunca leyó. El CSV, que es un canal de **intercambio**, escribía `02702` en su columna
  `detraccion_codigo`: quien lo leyera desde otro sistema recibía un código de CONCAR y tenía que conocer CONCAR para
  entenderlo.
- **El estándar no lo declara como propio de nadie.** `codigo_interno` es un `string` libre, sin dueño: ni el
  Catálogo 54 ni ninguna tabla de SUNAT dicen qué va ahí.

## Fuente

- **Catálogo 54 de SUNAT** (Anexo N.° 8), los códigos de bienes y servicios sujetos al SPOT: es la única
  numeración oficial y la que el estándar declara.
- **Tabla General 28 de CONCAR**, que cada contribuyente numera a su gusto: el Excel validado en producción
  (set-2026) trae `02702` para el `027`, y los siete códigos que ya usaba un contribuyente real conservan su interno
  exacto. Es una tabla de un sistema, no de la Administración.

## Especificación

El motor escribe en la línea **solo `detraccion.codigo`**, el del Catálogo 54, en los dos vocabularios (legacy y
neutral). La traducción al código interno de un sistema la hace **el driver de ese sistema**, en su proyección y con
su mapa declarado en su propia sección de la configuración:

- `drivers/concar/`: `detraccion_codigos` (el mapa de su T.G. 28) y `SUFIJO_T28` (el patrón `01` para lo que la
  empresa no mapeó) viven en el driver, y `proyeccion.codigo_interno_detraccion` escribe su columna AI.
- Al leer un archivo de CONCAR, la columna AI **vuelve al código de SUNAT**: por el mapa invertido del contribuyente
  y, si no está, por sus tres primeros dígitos, que es como se numera esa tabla.
- `drivers/csv/`: su columna `detraccion_codigo` lleva el del Catálogo 54. **La cabecera no cambia de nombre**, así
  que quien la busque por nombre no se enterará de que su contenido sí cambió: va en «Cómo migrar» del `CHANGELOG`.

## Qué NO hace

- **No toca el esquema.** `$defs/detraccion` sigue declarando `codigo_interno` como opcional, así que un documento
  que lo traiga —uno guardado antes de la 4.0, o el que produzca otro sistema— **sigue validando**. Por eso esto no
  sube la versión del estándar: lo que cambia es lo que el motor escribe, no lo que el formato admite.
- **No lo deja declarable como columna.** Sale de `drivers/kit/columnas.BLOQUES`: ninguna línea lo lleva ya, así que
  una columna que lo declarara saldría vacía en silencio, que es lo que esa tabla existe para impedir.
- **No cambia qué códigos se reconocen.** Eso lo decide la tabla del motor (`datos/sunat/detracciones.json`) y lo
  que el ERP le sume con `detraccion_tasas`; el mapa de un driver solo dice cómo los llama su sistema. Un test ata
  las claves de ese mapa a la tabla del motor, para que no puedan separarse en silencio.
