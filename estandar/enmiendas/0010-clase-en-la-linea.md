# 0010 · `clase` obligatoria en cada línea: qué es su cuenta

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | cambio de significado (sube a 1.0) |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 |
| **Test** | `tests/test_clases.py::test_una_compra_de_mercaderia_es_activo_y_no_gasto` |

## Motivación

Los roles `principal` y `tercero` solo significan algo **mirando `libro.tipo`**: en una compra
`principal` es el gasto y `tercero` un pasivo; en una venta, el ingreso y un activo. Y la línea que recibe un ERP de
fuera es exactamente eso, una línea suelta. Sin algo más, quien recibe `6343001` no sabe que es un gasto, y no lo va a
saber mirando el número.

El caso real es el asiento neutral, que **viaja a otro sistema que no tiene el plan de cuentas del emisor**.

## Fuente

`API-DE-REGISTRO.md`, «El papel de cada línea». Los cinco valores son los que QuickBooks
(`Classification`), Xero (`Class`), Merge y Rutter (`classification`) comparten: es el único vocabulario común a los
cuatro. La derivación es el PCGE 2026, Capítulo II: el primer dígito del código es el elemento.

## Especificación

Campo `clase` en la línea del asiento, **obligatorio**: `activo`, `pasivo`, `patrimonio`, `ingreso` o
`gasto` (catálogo `clases`).

**Se deriva del primer dígito de la cuenta**, que es el elemento del PCGE: 1, 2 y 3 → `activo`; 4 → `pasivo`; 5 →
`patrimonio`; 6 y 9 → `gasto`; 7 → `ingreso`. **No del rol**, y el caso que lo prueba es diario: una compra de
mercadería imputada a `201101` tiene `rol: principal` y es un **activo**. Los elementos 8 y 0 no tienen clase, y una
imputación a una de esas cuentas no genera asiento: se dice con su motivo.

Consecuencia: el IGV (`401111`, elemento 4) es `pasivo`. Con `debe_haber: D` la línea dice exactamente lo que pasa
—reduce un tributo por pagar, que es el crédito fiscal—; `activo` al debe afirmaría otra cosa.

**Y la regla que esto habilita:** quien recibe tiene que poder contabilizar una línea con `clase`, `debe_haber` e
`importe` **aunque no conozca su `rol`**. Es lo que permite que el catálogo de roles crezca sin romper a nadie.

**Fuera de la huella**, porque es función total de `cuenta`, que sí entra: excluirla no puede hacer que dos asientos
distintos compartan huella. Eso solo es cierto mientras el motor rechace una clase que contradiga su cuenta.
