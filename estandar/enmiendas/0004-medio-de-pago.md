# 0004 · `medio_pago`: el código de medio de pago de SUNAT

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 (aditivo: no sube la versión, avanza el tag) |
| **Test** | `tests/test_medio_pago.py::test_el_estandar_admite_un_codigo_del_catalogo_y_el_vacio` |

## Motivación

El registro de CONTASIS pide un medio de pago en cada fila de ventas (su columna AN). El motor lo venía llenando
desde el 12-sep-2026 con un valor de la configuración del contribuyente, `001` de fábrica, **y sin que existiera en
ninguna parte un mapa que dijera qué es `001`**: ni catálogo, ni validación, ni forma de que un ERP dijera el suyo.

Lo que faltaba no era un caso —CONTASIS lo pedía desde el principio—, era **una decisión**: si el medio de pago es
dato de cada documento, y entonces va en el comprobante, o un valor del contribuyente que vale para todos, y
entonces ya cabía en la configuración de su sección.

**Decisión de John, 25-sep-2026: las dos cosas.** Es dato del documento cuando el documento lo dice —una venta se
cobra con tarjeta y la siguiente por transferencia—, y el valor del contribuyente es el **respaldo** para cuando no
lo dice, que es lo normal hoy. Así queda abierto a cualquier ERP: el que tenga el dato por comprobante lo manda en
el documento, y el que no, sigue como estaba.

## Fuente

**Anexo 3 de la RS 169-2015/SUNAT, «Tabla 1: Tipo de medio de pago»** (22 códigos, de `001` depósito en cuenta a
`999` otros medios de pago) — la resolución que aprueba la versión 5.0.0 del PLE y modifica las RS 286-2009,
066-2013 y el Anexo 2 de la RS 234-2006:
<https://www.sunat.gob.pe/legislacion/superin/2015/anexo3-rs169-2015.pdf>

Los códigos son los medios de pago del **artículo 5 de la Ley 28194**, la de bancarización, que el propio texto del
código `007` cita. La tabla entera viaja en el motor (`catalogos.MEDIOS_PAGO`, y en `catalogos_sunat` por la API y
por el recurso `contaperu://catalogos/sunat`), con su fuente.

El consumidor que lo pedía: el registro de ventas de CONTASIS, columna AN (`docs/contasis/LEEME.md` de la
aplicación).

## Especificación

Campo **`medio_pago` en el comprobante**, opcional: texto de **tres dígitos** (`"^$|^[0-9]{3}$"`), un código del
catálogo de medios de pago de SUNAT. Vacío significa **que el documento no lo dice**, no que se pagara en efectivo.

No es `condicion_pago`, que dice **cuándo** se paga (contado o crédito); este dice **con qué**.

**Quien no lo conozca lo ignora**, y ningún asiento cambia por él: no entra en ninguna línea, en ninguna cuenta ni
en ningún importe, así que tampoco entra en la huella del asiento. Sí llega al driver en la cabecera del comprobante
(`asiento.Cabecera.medio_pago`), que es la regla de `tests/test_cabecera.py`: un hecho del comprobante que no llegue
ahí es un hecho que el próximo driver descubre que se cayó por el camino.

**Un código que no esté en el catálogo no invalida el documento**: se avisa (`MEDIO_PAGO_DESCONOCIDO`, nivel aviso)
y **el valor se respeta**. La forma la cuida el esquema; el significado, el catálogo. El motivo es que SUNAT puede
añadir un código y nadie debería quedarse sin exportar su mes por un dato que no cambia ningún importe —el mismo
criterio con el que un `rol` desconocido degrada en vez de romper la línea.

**Precedencia en el archivo:** manda el del documento; si viene vacío, el que tenga configurado el contribuyente en
la sección de su sistema contable (`contasis.medio_pago`). Un destino que no tenga columna para él simplemente no lo
escribe.
