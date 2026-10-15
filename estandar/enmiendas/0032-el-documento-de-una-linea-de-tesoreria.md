# 0032 · El `documento` de una línea de tesorería: un vóucher no es un comprobante de SUNAT

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **ninguna forma cambia**: no entra ni sale ningún campo. Lo que cambia es lo que el estándar DICE de dos campos que ya existen, y el catálogo de roles pasa a su `2.1`. Un documento 3.3 vale exactamente igual |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.3 (descriptivo: no sube la versión, avanza el tag) |
| **Test** | `tests/test_asiento_de_tesoreria.py` (el documento de cada línea de un pago, sin `tipo_cp` y con el `id_externo` del movimiento) y `tests/test_vocabulario.py::test_la_regla_no_deriva_todos_los_roles_del_catalogo` |

## Motivación

Desde la 12.9 el motor arma el asiento de un libro de tesorería, y esas líneas llenan el bloque `documento` con
algo que el estándar describía solo pensando en un comprobante:

- **`documento.id_externo`** lo definía la [0009](0009-id-externo-en-la-linea.md) como «el `id_externo` del
  comprobante que originó esta línea». En una línea de tesorería es el del **movimiento** que la originó, que es el
  mismo papel —el id con el que lo conoce el sistema que lo produjo, y la llave con la que se casa su imputación—
  pero de otro bloque del documento.
- **`documento.tipo_cp`** ya decía «ausente en la línea de la detracción, cuyo documento no es un comprobante de
  SUNAT», y una línea de tesorería es el segundo caso de lo mismo: un vóucher de pago o una línea de extracto no
  tienen código de la Tabla 10, y **no se les inventa uno**.
- **El catálogo de `roles`** declaraba `tesoreria` como RESERVADO, «que el motor todavía no sabe armar». Desde la
  12.8 se deriva, con la fuente que lo hace posible, así que la nota dejó de ser verdad.

Nada de esto se arregla añadiendo un campo: se arregla **diciendo lo que ya pasa**. Y dejarlo sin decir sería peor
que un hueco, porque quien integre leería que `documento` es siempre el de un comprobante y escribiría un lector
que casa por serie y número.

## Fuente

- El precedente está **dentro del propio estándar**: la línea de la detracción ya viaja sin `tipo_cp` desde la 1.0,
  porque la constancia del Banco de la Nación no es un comprobante de SUNAT. Una línea de tesorería es el mismo
  caso y por la misma razón.
- Para el enlace línea↔origen, lo de la 0009: `SourceID`/`SourceType` en Xero y `SourceDocumentID` en SAF-T
  (`REFERENCIAS.md`, «El documento y su asiento, y el enlace entre los dos»). **Ninguno de los dos presupone que el
  origen sea una factura**: en SAF-T un `Payment` es un documento origen como cualquier otro.
- Para el rol: el elemento **10 del PCGE 2026**, «Efectivo y equivalentes al efectivo» (p. 17), que es la fuente
  publicada con la que la regla distingue la línea del dinero de la de un gasto — y es palabra por palabra lo que
  el catálogo define como ese rol.

## Especificación

Dentro de `linea.documento`, en un libro cuyo asiento sale de `movimientos`:

| Campo | Qué lleva |
|---|---|
| `tipo_cp` | **ausente**. Un vóucher del banco no tiene código de la Tabla 10 |
| `serie_numero` | el número del papel que prueba el movimiento: su `constancia` si la tiene, y si no la `referencia` que le dio el banco. **Ausente si no tiene ninguno** |
| `id_externo` | el `id_externo` del **movimiento** que originó la línea |
| `fecha_emision` | la fecha del movimiento |
| `fecha_vencimiento` | ausente: un pago no vence |

Y el catálogo de `roles` pasa a `2.1`: `tesoreria` deja de estar reservado y se declara **derivado**, con su regla
—en un libro de movimientos, la línea que lleva `contraparte_doc` es `tercero`; la de una cuenta del elemento 10 es
`tesoreria`; lo que no es ninguna de las dos es `principal`—. `contrapartida` sigue reservado y sigue esperando el
diario que un ERP produce (B13): un pago a un proveedor **no** lo usa, porque su 42 se le debe a alguien.

**Quien no conozca esto no se rompe**: los tres campos son opcionales y ya lo eran, y un productor que solo escriba
comprobantes escribe exactamente lo que escribía. Lo que gana quien lea un documento de tesorería es saber que
`documento` no implica «comprobante de SUNAT», que es lo que el estándar no decía.
