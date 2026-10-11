# 0027 · `imputaciones_de_movimientos`: la contrapartida la pone el ERP

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **aditivo**: un bloque opcional nuevo. Quien no lo entienda lo ignora |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.0 (entra con ella, pero por sí solo no la habría subido) |
| **Test** | `tests/test_tesoreria.py` (las tres formas y sus exclusiones, el reparto exacto, el traspaso declarado y la llave huérfana) y `estandar/conformidad/esquema.json` |

## Motivación

Es la decisión de John del 11-oct-2026: **la contrapartida de un movimiento la imputa su ERP**, como ya hace con la
cuenta de una compra. Y su frase define el bloque: *«las imputaciones sirven para traer datos que el ERP tiene que
poner porque el motor estándar lo necesita»*.

**Y no tenía dónde ponerse.** El bloque `imputaciones` se casa **solo por el `id_externo` de un comprobante** —hay
un `allOf` en la raíz que lo exige—, y `Movimiento.id_externo` existía sin que nadie lo consumiera. Así que la
decisión no era expresable: un movimiento llegaba al motor con su 104 del maestro y sin la otra cara.

La doctrina es la que rige desde la 1.0 para el comprobante: **el motor no elige ninguna cuenta, la recibe**, y si
falta lo dice en vez de inventar una. Lo que esta enmienda añade es el sitio donde decirla, y el aviso
`MOVIMIENTO_SIN_IMPUTAR`, que es el `sin_cuenta` del dinero.

## Fuente

No es una norma: es una decisión de arquitectura, y su fuente es el precedente del propio estándar —la
[enmienda 0008](0008-imputaciones-en-el-documento.md), que metió las imputaciones en el documento— más la decisión
de John del 12-sep-2026 que la 0.3 ejecutó quitando `cuenta_contable` y `centro_costo` del comprobante: **las
cuentas viven en la aplicación y llegan aparte.**

## Especificación

Bloque opcional `imputaciones_de_movimientos` en la raíz, por `id_externo` del movimiento, con
`$defs/imputacion_de_movimiento` y `$defs/parte_de_imputacion_de_movimiento`.

| Campo | Qué es |
|---|---|
| `cuenta_contable` | la contrapartida, cuando es una. **La 104 no sale de aquí**: sale de `CuentaBancaria.cuenta_contable` del maestro |
| `centro_costo` | — |
| `contraparte_doc` | el documento del tercero cuando el papel no lo dijo y el contador lo sabe. Sin él, un destino que llene su anexo auxiliar lo deja vacío |
| `cuenta_propia` | el `id` de **otra** cuenta del maestro: declara el traspaso |
| `reparto[]` | `{importe` **obligatorio**`, cuenta_contable, centro_costo, contraparte_doc}` |

**Las tres formas se excluyen**, porque contestan la misma pregunta de tres maneras: una cuenta sola, un `reparto`,
o un `cuenta_propia`. Dos a la vez no tienen respuesta — «¿cuál mandaría?», que es el precedente exacto de la
imputación de un comprobante.

**El reparto suma el importe del movimiento, exacto y sin tolerancia, y el ITF queda fuera** (son sus dos líneas
propias, que esperan su norma). Y aquí **bloquea**, no se reporta: el informe `sin_atribuir` existe porque «qué es
ese resto lo decide el contador por la imputación», y esto ya **es** la imputación, así que un reparto que no cuadra
no es un dato que falte sino una decisión mal hecha.

**Con el bloque, cada movimiento necesita su `id_externo`**, no vacío, por un `allOf` condicional calcado del de
`imputaciones`. Y **una llave que no es de ningún movimiento se rechaza**: una llave mal escrita dejaría ese
movimiento sin su cuenta y **sin aviso**. Se contrasta contra los movimientos **tal como llegaron**, antes de
deduplicar: si una relectura descarta el movimiento al que apuntaba, la llave no deja de ser correcta.

### El traspaso, que es lo que esto desbloquea

`cuenta_propia` es **la única vía declarada** para afirmar el efecto `transferencia`. Ese tercer valor del catálogo
existe porque la **NIC 7 §9** excluye de los flujos de efectivo los traspasos entre partidas de efectivo, así que
hay que poder nombrarlo para dejarlo fuera y no contarlo dos veces. Y `Movimiento.efecto` **nunca** lo devuelve —ni
lo hará—, porque una línea sola no puede saber que es la mitad de un par: eso es una afirmación sobre dos
movimientos. La otra vía es `conciliar`, que **propone y nunca confirma** (el hito D3).

La respuesta de `revisar_tesoreria` gana `imputados`, `sin_imputar` y `transferencias_declaradas`, más los avisos
`MOVIMIENTO_SIN_IMPUTAR` (`pedir_a: contador`) y `CUENTA_PROPIA_NO_DECLARADA`.

## Por qué es un bloque aparte y no una extensión de `imputaciones`

Tres razones, y la primera es dirimente:

1. **El espacio de llaves colisionaría.** `imputaciones` significa «por `id_externo` de comprobante». Un ERP tiene
   secuencias de id independientes para sus facturas y sus movimientos, así que `"fila-12"` puede ser las dos
   cosas. Compartir el espacio obligaría a exigir unicidad **entre bloques**, que es un requisito nuevo sobre quien
   ya produce documentos: eso es cambiar lo que existe, no añadir.
2. **Los campos no son los mismos.** `$defs/imputacion` lleva `cuenta_tercero` («la cuenta del total: 42 en
   compras, 12 en ventas»), `detraccion_codigo` y `anulada_por_nota`, que un movimiento no tiene; y su `reparto`
   divide solo la base, mientras un movimiento no tiene base ni IGV. Reusando el `$def`, una imputación de
   movimiento podría llevar `anulada_por_nota` **legalmente**, y `additionalProperties: false` dejaría de poder
   decir que no es suyo.
3. **El `allOf` de la raíz tendría que crecer mal**: exige `id_externo` en cada comprobante cuando hay
   imputaciones, así que imputar solo movimientos obligaría a ponérselo a comprobantes que nadie imputa.

## Qué NO hace

- **No asienta.** Sigue siendo D6. Lo que esto cierra es el contrato: el ERP ya puede decir todo lo que el motor
  necesitará, y lo que falta para asentar es la tasa del ITF con su norma y un archivo del sub-diario de bancos que
  CONCAR haya aceptado.
- **No dice qué cancela el pago.** Eso viaja en `movimiento.referencias[]` si el papel lo dice, y casarlo es D3.
  Aquí va **la cuenta**, no el documento, y una parte del reparto **no** puede apuntar a un comprobante.
- **No añade un argumento a la fachada.** Una sola vía: no hay nadie integrado por ahí a quien conservar, y así se
  evita la asimetría que `imputacion_del_documento` tiene que explicar para los comprobantes.
- **No toca `RASGOS["tesoreria"]`.** Sus cuatro campos siguen vacíos, y los roles se declararán **medidos**, el día
  que el motor emita la primera línea.
