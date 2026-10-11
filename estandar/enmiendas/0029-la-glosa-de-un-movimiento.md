# 0029 · La glosa de un movimiento: la decide el contador, no el banco

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **aditivo**: dos campos opcionales. Un documento 3.0 sigue valiendo tal cual |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.1 |
| **Test** | `tests/test_tesoreria.py` (la cadena de respaldo entera y un reparto con una glosa por parte) y `estandar/conformidad/esquema.json` (un caso con las dos glosas y su negativo) |

## Motivación

Es de John, el 11-oct-2026, **integrando**: *«en movimiento no existe la variable "glosa", y esto es importante
para los libros»*.

Tiene razón, y lo que importa es **cómo apareció**: no lo encontró la batería ni una revisión, lo encontró alguien
conectando un ERP de verdad. Y falsifica lo que la 11.0.0 escribió de sí misma —*«el contrato del dinero queda
cerrado: un ERP ya puede decir **todo** lo que el motor necesitará para asentarlos»*—. No podía decir esto.

**La piden los cuatro destinos**, y eso es lo que lo convierte en un hueco y no en una mejora:

| Destino | Dónde |
|---|---|
| PLE, Libro Diario 5.1 | campo **16**, la glosa (y el 17, la referencial, que el motor no tiene y rellena con un guion) |
| CONCAR | **dos**: «Glosa Principal» (col F, 40 caracteres) y «Glosa Detalle» (col W, 30) |
| CONTASIS · STARSOFT | la suya, con su largo (`LARGO_GLOSA`) |

Sin sitio donde ponerla, el día que el motor asiente tesorería el Libro Diario saldría con el texto crudo del
banco: «TRANSFERENCIA A CUENTAS DE TERCEROS BCP LOCAL».

## Fuente

**El PLE y las plantillas de los tres sistemas**, que ya están en el repositorio y ya reservan la columna: el
campo 16 del Diario 5.1 en `drivers/ple/txt.py`, los dos largos de CONCAR en `drivers/concar/datos.py`
(`LARGOS_DE_GLOSA = {"F": 40, "W": 30}`) y el de STARSOFT. No hace falta un archivo nuevo: la necesidad está
escrita en el motor desde que existen esos drivers.

Y una fuente de método: **`asiento.glosa_de`**, que resuelve esto mismo para un comprobante desde la 1.0 —el
concepto o, si no trae, el nombre de la contraparte, en mayúsculas y sin cortar—.

## Especificación

**`glosa` entra en dos sitios, los dos opcionales y los dos dentro de la imputación**: en
`imputacion_de_movimiento` y en cada `parte_de_imputacion_de_movimiento`.

**Por qué en la imputación y no en el movimiento**, que es la pregunta que decide esto:

1. **Es una decisión, no un hecho del papel.** Es exactamente lo que ese bloque es: *«lo que el ERP decide,
   porque el motor lo necesita y el papel no lo dice»* ([enmienda 0027](0027-la-imputacion-de-un-movimiento.md)).
2. **`movimiento.descripcion` ya existe y es otra cosa**: el texto que imprimió el banco. Además **entra en la
   clave de deduplicación**, así que no puede ser lo que alguien reescriba al revisar.
3. **Y el argumento dirimente: un cargo que paga tres facturas necesita tres glosas.** Las partes viven en la
   imputación, así que una glosa en el movimiento no podría dar más de una. Es literalmente la distinción que
   CONCAR ya hace entre su «Glosa Principal» y su «Glosa Detalle».

**La cadena de respaldo**, para que ninguna línea salga sin glosa:

```
parte.glosa  →  imputacion.glosa  →  movimiento.descripcion  →  movimiento.contraparte_nombre
```

Lo que el contador decide manda sobre lo que imprimió el banco, siempre. Pero el texto del banco es mejor que una
celda vacía, y un libro no admite una glosa en blanco.

**En mayúsculas y sin cortar**, igual que la del comprobante: el largo lo decide cada destino, porque es suyo.

La compone `tesoreria.glosa_de_movimiento(movimiento, imputacion, parte)`, al lado de `efecto_de`, y por el mismo
motivo: son las dos cosas que solo se saben juntando el movimiento con lo que el ERP declaró.

## Qué NO hace

- **No toca `movimiento.descripcion`.** Sigue siendo el texto del banco tal cual, y su docstring lo dice ahora sin
  ambigüedad — se llamaba a sí misma «la glosa del banco», y eso es lo que despistó.
- **No asienta.** El motor todavía no arma el asiento de tesorería (D6): lo que esta enmienda cierra es que el
  documento **pueda decir** la glosa cuando llegue el momento.
- **No añade la glosa referencial** del campo 17 del PLE. El motor no tiene una segunda glosa y el archivo
  contrastado pone un guion; cuando alguien enseñe un caso real donde haga falta, será otra enmienda.
- **No corta a ningún largo.** Eso es del driver, que ya sabe el suyo.
