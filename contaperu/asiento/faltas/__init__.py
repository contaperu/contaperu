"""Lo que puede impedir exportar un mes a un destino: cómo se llama cada falta, con qué excepción se niega el núcleo
y a quién se le pide el dato que falta.

Eran 334 líneas con tres cosas dentro, y desde la 12.12.0 cada una tiene su fichero. El corte no se eligió aquí: lo
marcaban ya los propios rótulos del código, y es el mismo que separa los dos motores del asiento
(`asiento/comprobante.py` y `asiento/movimiento.py`), con el `comun.py` de lo que comparten:

- `comprobante.py` — las once excepciones de un comprobante y la tabla `FALTAS`, cuyas filas se cuentan **por
  comprobante**, por su serie-número;
- `movimiento.py` — lo que impide armar el asiento de un movimiento, que está FUERA de `FALTAS` a propósito
  (12.7) porque un movimiento no se cuenta por serie-número;
- `comun.py` — `NoExportable`, que las dos familias heredan, la forma de una fila (`Falta`), a quién se le pide
  (`CONTADOR`, `SISTEMA`, `PROVEEDOR`) y `LibroQueElMotorNoOrigina`, que no es de un libro ni del otro.

**Lo que se importa no cambió**: aquí se reexportan los mismos nombres, y `contaperu.asiento` los sigue dando
todos. Las reglas que comprueban estas faltas siguen en `resolucion.requisitos`.
"""
from __future__ import annotations

from .comprobante import (FALTA, FALTAS, AnuladaConDeposito, RepartoNoAdmitido, RepartoNoCuadra, SinCentro, SinClase,
                          SinCodigoDeMoneda, SinCodigoDetraccion, SinCorrelativo, SinCuenta, SinDenominacion,
                          SinSigla)
from .comun import CONTADOR, PROVEEDOR, SISTEMA, Falta, LibroQueElMotorNoOrigina, NoExportable
from .movimiento import (CuentaSinClase, LibroQueTodaviaNoSeNumera, MovimientoSinImputar, SinCuentaDeEfectivo,
                         TraspasoEnDosPatas)

__all__ = ["CONTADOR", "SISTEMA", "PROVEEDOR", "NoExportable", "Falta", "FALTA", "FALTAS",
           "LibroQueElMotorNoOrigina",
           "SinSigla", "SinCodigoDeMoneda", "SinDenominacion", "RepartoNoAdmitido", "SinCuenta",
           "SinCodigoDetraccion", "RepartoNoCuadra", "SinCentro", "SinClase", "SinCorrelativo",
           "AnuladaConDeposito",
           "MovimientoSinImputar", "SinCuentaDeEfectivo", "TraspasoEnDosPatas", "LibroQueTodaviaNoSeNumera",
           "CuentaSinClase"]
