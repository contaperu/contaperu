# 0013 · La glosa, la misma en todas las líneas y sin prefijos

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | cambio de significado (no toca el esquema) |
| **Nivel** | estándar |
| **Versión** | motor: la próxima (hoy sin publicar) · `open-accounting` **1.0**, sin cambio |
| **Test** | `tests/test_linea_neutral.py::test_la_glosa_de_la_linea_va_entera_y_el_corte_es_del_driver` |

## Motivación

Hasta el motor 2.1, las líneas derivadas de un comprobante anteponían a la glosa lo que las
identificaba. Una compra con detracción salía así:

```
principal            SERVICIO DE MANTENIMIENTO
igv                  IGV - SERVICIO DE MANTENIMIENTO
tercero              SERVICIO DE MANTENIMIENTO
detraccion_tercero   SERVICIO DE MANTENIMIENTO
detraccion           DETRACCION - SERVICIO DE MANTENIMIENTO
```

**Es información repetida, y cara.** Qué es cada línea ya lo dicen dos campos que el estándar exige: su
`rol` —`principal`, `igv`, `retencion_4ta`, `tercero`, `detraccion`, `detraccion_tercero`— y su cuenta. Un
consumidor que necesite encontrar la línea del IGV la busca por `rol`, nunca por el texto de la glosa: es
lo que ya hacen los seis drivers del repositorio, ninguno de los cuales lee la glosa para decidir nada.

**Y el prefijo se comía el espacio del dato.** CONCAR admite 30 caracteres en su columna de detalle (`W`):
`IGV - ` gastaba 6 de esos 30, y `DETRACCION - ` gastaba 13. Con un concepto real —«SERVICIO DE TRANSPORTE
DE MATERIALES DE CONSTRUCCION A LA OBRA»— la línea de la detracción llegaba a CONCAR como
`DETRACCION - SERVICIO DE TRANS`: el prefijo sobrevivía y el concepto se perdía. El contador leía la
etiqueta que ya sabía y no el dato que necesitaba.

**Decidido por John el 21-sep-2026**, revisando el JSON de un asiento con detracción: «no es necesario que
en ningún sistema pongas `DETRACCION - …` o `IGV - …`, debe ser solo la misma glosa normal».

## Fuente

- **El uso**: ningún driver de los seis —CONCAR, CONTASIS, SIRE, CSV, STARSOFT, asiento neutral— lee la
  glosa para identificar una línea. Todos usan `rol`. Comprobado sobre el código: no hay un solo
  `glosa.startswith` ni comparación de glosa en `contaperu/`.
- **El largo de CONCAR**: 30 caracteres en la columna `W`, verificado celda a celda contra
  `plantilla-concar.xlsx` (`drivers/concar/datos.py`).
- **El estándar ya lo pedía a medias**: `rol` es obligatorio desde la 1.0 justamente para que un ERP de
  fuera encuentre cada línea sin conocer el PCGE ni leer textos.

## Especificación

`linea.glosa` es **la misma para todas las líneas del comprobante**, entera y sin prefijos. Cortarla al
largo que admita cada ERP sigue siendo trabajo del driver.

**El esquema no cambia**: `glosa` era y sigue siendo un texto libre opcional, así que
`open-accounting.schema.json` no se toca y la versión del estándar **sigue en 1.0**. Lo que cambia es el
texto normativo (`../LEEME.md`), que describía el prefijo como parte de la forma.

**Quién se entera y quién no:**

- Un consumidor que busque sus líneas por `rol` —lo que el estándar pide— **no nota nada**.
- Un consumidor que buscara la línea del IGV por el texto `"IGV - "` **deja de encontrarla**. Nunca fue una
  forma admitida de leer el asiento, pero era posible, y por eso esto entra como cambio de significado y no
  como un arreglo.
- **Las huellas de los asientos cambian todas.** La glosa entra en la huella (`../LEEME.md`, «Huella»), así
  que cualquier huella guardada antes de la 2.2 deja de coincidir con la que produce el motor hoy. Es lo que
  hay que mirar antes de subir: quien use la huella para reconocer una tanda ya exportada verá las de antes
  como distintas. No afecta a la contabilidad —ni un importe, ni una cuenta, ni un sentido se mueven—, y se
  comprobó celda a celda al regenerar `fixtures/snapshot/`: 57 celdas cambiadas en cada snapshot, **todas
  glosas con prefijo y ninguna otra**.
