"""Tesorería: el dinero moviéndose, y lo que prueba cada movimiento.

Se llama así y no `banco` por una razón que se ve en cuanto se mira lo que guarda: una constancia de pago de
tributos o el reintegro de una caja chica no son del banco, y una pasarela de pagos tampoco. Es además la palabra
que el propio estándar ya usa — el rol `tesoreria` se define como «el dinero moviéndose: caja, banco o
equivalente, al cobrar o al pagar» (enmienda 0021).

**Qué hay aquí, y qué no.** Hay la forma de tres cosas y una comprobación:

- `CuentaBancaria` — lo que declara el contribuyente, con **su** cuenta contable. Es un argumento, no una tabla.
- `Movimiento` — una línea de un estado de cuenta: el mes completo, visto desde mi cuenta.
- `Constancia` — la prueba de **una** operación, con `referencias` de lo que cancela: un comprobante, un tributo,
  un traspaso propio o texto libre. Eso es lo que la hace servir para cualquier pago.
- `cuadre` — la cadena de saldos del extracto, que es lo que convierte «leí un PDF» en «lo leí bien».

**No hay lectores de ningún banco**, y es a propósito: la forma salió de nueve extractos reales de agosto de 2026,
pero cada parser entra con su archivo delante y su fixture anonimizado. Tampoco hay conciliación —casar un pago con
lo que cancela es el hito D3 y necesita dos archivos— ni asiento de tesorería, que es D6 y espera la norma del ITF
y un archivo que CONCAR haya aceptado. **El motor no emite todavía ninguna línea de rol `tesoreria`**, y
`asiento.TIPOS_DEL_MOTOR` dice por qué: de un comprobante no sale un pago.

**Y nada de esto sale a la red.** El lector que algún día lea un extracto recibirá **bytes**, como ya hacen los de
`lectores`: bajar el archivo del banco es de quien integra, igual que enviar al SIRE. Lo que sí se sabe aquí es qué
forma tiene lo que llegue.

Un dato que el primer parser va a agradecer, y que está en los nueve archivos: **cuatro de ellos no se abren con
una librería estándar** — dos vienen cifrados con contraseña y dos traen la cabecera del PDF rota. Lo difícil de un
extracto peruano no son las columnas.
"""
from __future__ import annotations

from .constancias import (CLASES, CLAVES_POR_CLASE, COMPROBANTE, CUENTA_PROPIA, Constancia, ConstanciaInvalida,
                          LIBRE, Referencia, TRIBUTO)
from .cuadre import CuadreExtracto, ExtractoNoCuadra, cuadra, exigir
from .cuentas import (CuentaBancaria, CuentaInvalida, LARGO_CCI, MONEDAS, banco_del_cci, leer, normalizar_cci)
from .movimientos import ABONO, CARGO, Movimiento, MovimientoInvalido, SENTIDOS, clave_de, sin_duplicados

__all__ = ["ABONO", "CARGO", "CLASES", "CLAVES_POR_CLASE", "COMPROBANTE", "CUENTA_PROPIA", "Constancia",
           "ConstanciaInvalida", "CuadreExtracto", "CuentaBancaria", "CuentaInvalida", "ExtractoNoCuadra",
           "LARGO_CCI", "LIBRE", "MONEDAS", "Movimiento", "MovimientoInvalido", "Referencia", "SENTIDOS", "TRIBUTO",
           "banco_del_cci", "clave_de", "cuadra", "exigir", "leer", "normalizar_cci", "sin_duplicados"]
