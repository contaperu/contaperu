"""Lo que impide armar el asiento de un MOVIMIENTO (12.7).

Las cinco van FUERA de `FALTAS` por el mismo motivo que `LibroQueElMotorNoOrigina`: esa tabla reparte faltas **por
comprobante** —las cuenta por su serie-número y las reparte entre `bloqueantes` y `avisos`—, y un movimiento no
tiene ni una cosa ni la otra. Lo que sí comparten con ella es el trato: un `NoExportable` con su `clave`, que es lo
que una puerta atrapa y traduce.

Y las dos primeras **endurecen tres avisos que ya existen**: `revisar_tesoreria` dice hoy `MOVIMIENTO_SIN_IMPUTAR`
—la primera—, y `CUENTA_NO_DECLARADA` y `CUENTA_BANCARIA_SIN_CUENTA_CONTABLE` —las dos ramas de la segunda— sin
parar nada, porque mirar no obliga a nada. Asentar sí: ahí lo que falta ya no se puede reportar, porque no hay línea
que escribir sin ello.
"""
from __future__ import annotations

from .comun import NoExportable


class MovimientoSinImputar(NoExportable):
    """Movimientos sin su contrapartida: el otro lado del asiento no lo pone el motor.

    Es «sin imputación no hay cuenta» aplicado al dinero. La 104 sale del maestro de cuentas, pero contra qué se
    salda —un gasto, la cuenta de un proveedor, un tributo— lo decide el contador, y adivinarlo sería imputar en
    silencio a un comodín que nadie eligió, que es exactamente lo que la 3.0 quitó de los comprobantes."""

    clave = "movimiento_sin_imputar"

    def __init__(self, cuales: list[str]):
        super().__init__(f"{len(cuales)} movimiento(s) sin imputación, así que no hay con qué saldarlos: "
                         + ", ".join(cuales))
        self.cuales = list(cuales)


class SinCuentaDeEfectivo(NoExportable):
    """La cuenta de efectivo de un movimiento no se puede resolver: su `id` no está en el maestro, o está y no
    declara su cuenta contable.

    **El motor no deriva la 104**: la declara el contribuyente en su maestro, porque cada empresa abre las
    divisionarias que quiere. Sin ella no hay una de las dos patas."""

    clave = "sin_cuenta_de_efectivo"

    def __init__(self, cuales: list[str], motivo: str = ""):
        super().__init__(f"{len(cuales)} cuenta(s) de efectivo sin resolver ({motivo}): " + ", ".join(cuales))
        self.cuales = list(cuales)
        self.motivo = motivo


class TraspasoEnDosPatas(NoExportable):
    """Un traspaso entre cuentas propias declarado por sus DOS movimientos.

    Un traspaso ya tiene sus dos patas en un solo asiento —es el único efecto cuyas dos cuentas están declaradas—,
    así que asentar también el movimiento espejo contaría el mismo dinero dos veces. Se para en vez de elegir uno
    de los dos, porque elegirlo sería una decisión del contador y no del motor.

    **Un falso positivo posible**: dos traspasos reales de ida y vuelta por el mismo importe en el mismo mes. Vale
    la pena: pararlos es un aviso que alguien lee, y contarlos dos veces es un saldo falso que nadie ve."""

    clave = "traspaso_en_dos_patas"

    def __init__(self, cuales: list[str]):
        super().__init__(f"{len(cuales)} traspaso(s) declarados por sus dos movimientos, que contarían el dinero "
                         "dos veces: " + ", ".join(cuales))
        self.cuales = list(cuales)


class LibroQueTodaviaNoSeNumera(NoExportable):
    """Un libro que el motor origina y cuyo sub-diario todavía no tiene clave de configuración.

    Es la otra mitad de `LibroQueElMotorNoOrigina`, y la separa una distinción que tesorería hizo visible: el motor
    **sabe armar** su asiento y **no sabe numerarlo**, porque numerar es por sub-diario y el suyo espera un archivo
    real que diga cuál es. Con vocabulario neutral no hace falta —ese documento no lleva correlativo—, así que lo
    que esto para es el camino legacy, que si no reventaría con un `KeyError` pelado fuera del contrato de errores.
    """

    clave = "libro_que_todavia_no_se_numera"

    def __init__(self, tipo: str):
        super().__init__(f"El asiento de un libro {tipo!r} todavía no se numera: su sub-diario no tiene clave de "
                         "configuración, y entra con el archivo real que lo pida. Sin numerar sí sale, con el "
                         "vocabulario neutral del estándar")
        self.tipo = tipo


class CuentaSinClase(NoExportable):
    """Una cuenta de un elemento del PCGE que no tiene clase contable: el 8 y el 0.

    Es `SinClase` para el dinero, y va aparte porque aquélla cuenta COMPROBANTES y aquí lo que hay son cuentas:
    nombrar la cuenta es más útil que nombrar el movimiento, porque el arreglo está en la imputación o en el
    maestro."""

    clave = "cuenta_sin_clase"

    def __init__(self, cuentas: list[str]):
        super().__init__(f"{len(cuentas)} cuenta(s) de un elemento sin clase contable (el 8 y el 0 del PCGE no la "
                         "tienen): " + ", ".join(cuentas))
        self.cuentas = list(cuentas)
