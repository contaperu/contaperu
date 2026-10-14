"""Tesorería: el dinero moviéndose, y lo que lo prueba.

Se llama así y no `banco` por una razón que se ve en cuanto se mira lo que guarda: una constancia de pago de
tributos o el reintegro de una caja chica no son del banco, y una pasarela de pagos tampoco. Es además la palabra
que el propio estándar ya usa — el rol `tesoreria` se define como «el dinero moviéndose: caja, banco o
equivalente, al cobrar o al pagar» (enmienda 0021).

**Qué hay aquí, y qué no.** Hay la forma de dos cosas y una comprobación:

- `CuentaBancaria` — lo que declara el contribuyente, con **su** cuenta contable. Es un argumento, no una tabla.
- `Movimiento` — **el item de operación, y la única entrada de un libro de tesorería** (John, 11-oct-2026): venga
  de una línea de extracto o de una constancia de pago, al motor llega con esta forma, con su `origen` diciendo de
  dónde salió y sus `referencias` diciendo qué cancela si el papel lo dice. Hasta la 2.0 del estándar eran dos
  bloques; el porqué de la fusión está en `movimientos.py`.
- `Extracto` — **la cabecera** de lo que el banco declaró de una cuenta en un periodo: su saldo anterior, su
  saldo actual y sus dos totales. No es una entrada de operaciones; es lo que permite comprobar un documento
  guardado y lo que caza una línea perdida al final del mes.
- `ImputacionDeMovimiento` — **lo que el ERP decide** porque el motor lo necesita y el papel no lo dice: la
  cuenta de la otra cara, su centro, el reparto cuando un cargo se parte, y el traspaso declarado. La 104 no sale
  de aquí: sale del maestro.
- `Referencia` — lo que un pago cancela: un comprobante, un tributo, un traspaso propio o texto libre. Es lo que
  hace que esto sirva para cualquier pago sin enumerar propósitos.
- `cuadre` — la cadena de saldos del extracto, que es lo que convierte «leí un PDF» en «lo leí bien». **Es una
  función para quien parsea, y desde la 12.0 la api ya no la llama**: `cuadra` significa «ninguna línea
  contradijo la cadena», así que sin líneas con `saldo` devuelve verde sin haber mirado nada — y un ERP que manda
  operaciones estructuradas no trae saldos nunca. Lo que `revisar_tesoreria` sí comprueba es lo que el banco
  **declaró** en su cabecera contra la suma de lo que llegó, que es aritmética y no puede pasar en vacío.

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

from .cuadre import CuadreExtracto, ExtractoNoCuadra, cuadra, exigir
from .extractos import Extracto, ExtractoInvalido, por_cuenta
from .imputaciones import (ImputacionDeMovimiento, ImputacionInvalida, Parte, efecto_de,
                           glosa_de_movimiento, leer as leer_imputaciones)
from .cuentas import (CuentaBancaria, CuentaInvalida, LARGO_CCI, MONEDAS, banco_del_cci, leer,
                      normalizar_cci, por_id, sin_cuenta_declarada)
from .movimientos import (ABONO, API, ARCHIVO, CARGO, EFECTOS_DE_UN_MOVIMIENTO, ENTRADA, LECTURA_ASISTIDA, MANUAL,
                          ORIGENES, PDF_TEXTO, SALIDA, SENTIDOS, TRANSFERENCIA, VISION, Movimiento,
                          MovimientoInvalido, clave_de, sin_duplicados)
from .referencias import (CLASES, CLAVES_POR_CLASE, COMPROBANTE, CUENTA_PROPIA, LIBRE, Referencia,
                          ReferenciaInvalida, TRIBUTO)

__all__ = ["ABONO", "API", "ARCHIVO", "CARGO", "CLASES", "CLAVES_POR_CLASE", "COMPROBANTE", "CUENTA_PROPIA",
           "CuadreExtracto", "CuentaBancaria", "CuentaInvalida", "EFECTOS_DE_UN_MOVIMIENTO", "ENTRADA", "Extracto",
           "ExtractoInvalido", "ExtractoNoCuadra", "ImputacionDeMovimiento", "ImputacionInvalida", "LARGO_CCI",
           "LECTURA_ASISTIDA", "LIBRE", "MANUAL", "MONEDAS", "Movimiento", "MovimientoInvalido", "ORIGENES",
           "PDF_TEXTO", "Parte", "Referencia", "ReferenciaInvalida", "SALIDA", "SENTIDOS", "TRANSFERENCIA",
           "TRIBUTO", "VISION",
           "banco_del_cci", "clave_de", "cuadra", "efecto_de", "exigir", "glosa_de_movimiento", "leer",
           "leer_imputaciones",
           "normalizar_cci",
           "por_cuenta", "por_id", "sin_cuenta_declarada", "sin_duplicados"]
