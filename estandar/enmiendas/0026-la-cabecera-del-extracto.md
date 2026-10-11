# 0026 · `extractos[]`: la cabecera de lo que el banco declaró

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **aditivo**: un bloque opcional nuevo. Quien no lo entienda lo ignora |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.0 (entra con ella, pero por sí solo no la habría subido) |
| **Test** | `tests/test_tesoreria.py` (el segundo control, los dos totales, la vía doble y las dos cabeceras de la misma cuenta) y `estandar/conformidad/esquema.json` |

## Motivación

Hasta la 2.0 el saldo que declara un extracto entraba **solo como argumento** de `revisar_tesoreria`
(`saldos_iniciales`). Eso tiene dos consecuencias y ninguna es buena:

1. **Un documento de tesorería guardado no se podía volver a comprobar.** Su cuadre dependía de un dato que no
   viajaba con él. Es literalmente lo que la [enmienda 0008](0008-imputaciones-en-el-documento.md) arregló para las
   imputaciones: «el archivo explica su propio asiento».
2. **El segundo control del extracto era inalcanzable.** `tesoreria.cuadra` acepta un `saldo_final` desde la 8.2 y
   **nadie se lo pasaba nunca**, así que estaba implementado, probado en su módulo, y no se podía alcanzar por la
   api. Un control que no se puede invocar no protege a nadie.

**Y vale por sí mismo, no es simetría.** Una lectura puede pasar la cadena de saldos corridos y fallar el total: si
se pierde la **última** línea del mes, las demás encadenan perfectamente entre sí. Es justo lo que produce un lector
de PDF, y es el caso que esta enmienda caza.

## Fuente

Los mismos nueve extractos reales de agosto de 2026 que dieron la forma del movimiento. Los tres bancos que abren
imprimen en la cabecera el saldo anterior, el total de cargos, el total de abonos y el saldo actual —BanBif con esas
cuatro palabras exactas— más el periodo que cubre la hoja. **La Fuente de la [enmienda 0024](0024-movimientos-y-constancias.md)
ya los enumeraba** como el invariante verificado; lo que faltaba era un sitio donde ponerlos.

## Especificación

Bloque opcional `extractos[]` en la raíz, con `$defs/extracto`. Solo `cuenta` es obligatoria —el `id` del maestro,
igual que en el movimiento—; `desde`, `hasta`, `saldo_inicial`, `saldo_final`, `total_cargos` y `total_abonos` son
opcionales, y **ausente no es cero: es «la hoja no lo dice»**.

- **No es una entrada de operaciones** y por eso no contradice la entrada única de la
  [enmienda 0025](0025-una-sola-entrada-para-tesoreria.md): no lleva movimientos dentro. Es lo que viene impreso
  arriba de la hoja, uno por cuenta y por periodo — no cabe en `libro`, que es uno por documento, ni en el maestro
  de cuentas, que es lo que la empresa **es** y no lo que un periodo **dijo**.
- **Dos cabeceras de la misma cuenta se rechazan.** No es un mes partido en dos hojas: es un documento que declara
  dos saldos iniciales para lo mismo, y no hay regla que diga cuál gana.
- **El bloque y el argumento a la vez para la misma cuenta se rechazan**, por lo mismo. El precedente exacto es
  `imputaciones` contra `imputacion`. El argumento se conserva como segunda vía para quien no construya el
  documento entero.
- **`desde` y `hasta` se reportan y nunca filtran.** Un extracto de agosto con una línea de julio dentro es un
  error de quien leyó el archivo, no algo que el motor deba esconder.
- **Los dos totales se contrastan** con lo que suman las líneas, y es la tercera comprobación: caza lo que el saldo
  final no puede, porque **un cargo y un abono perdidos por el mismo importe dejan el saldo igual**.

La respuesta de `revisar_tesoreria` gana `saldo_final_declarado` por cuenta —hermano de
`saldo_inicial_declarado`—, que es lo que impide creerse un cuadre que solo se comprobó a medias, y el aviso
`TOTAL_DECLARADO_NO_COINCIDE`.

## Qué NO hace

- **No filtra por periodo**, dicho arriba.
- **No obliga a declararlo.** Sin el bloque todo funciona como antes: el saldo inicial se deduce del primer
  movimiento y la cadena se mira de la segunda línea en adelante.
- **No lee ningún banco.** De dónde salen estos cuatro números es de quien lee el archivo; aquí solo se sabe qué
  forma tienen.
