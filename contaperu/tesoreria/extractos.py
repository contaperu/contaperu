"""La cabecera de un extracto: lo que el banco DECLARA de una cuenta en un periodo.

**No es una entrada de operaciones** —no lleva movimientos dentro— y por eso no contradice la entrada única: es lo
que viene impreso arriba de la hoja, y es por definición uno por cuenta y por periodo. No cabe en `libro`, que es
uno por documento, ni en el maestro de cuentas, que es lo que la empresa **es** y no lo que un periodo **dijo**.

**Lo que arregla.** Hasta la 2.0 del estándar esos saldos entraban solo como argumento de `revisar_tesoreria`, así
que un documento de tesorería guardado **no se podía volver a comprobar**: su cuadre dependía de un dato que no
viajaba con él. Es literalmente lo que la enmienda 0008 arregló para las imputaciones —«el archivo explica su
propio asiento»— y lo que faltaba aquí.

Y había un hueco peor: `cuadre.cuadra` acepta un `saldo_final` y **nadie se lo pasaba nunca**, de modo que el
segundo control del extracto estaba implementado y era inalcanzable por la api.

**La forma salió de los mismos nueve extractos** de agosto de 2026 que dieron la del movimiento: los tres bancos
que abren imprimen en la cabecera el saldo anterior, el total de cargos, el total de abonos y el saldo actual
—BanBif con esas cuatro palabras exactas— más el periodo. Nada de esto se inventa: o está en la hoja o no viene.

**Los dos controles encima del mismo dato**, que es lo que los hace valer: la cadena de saldos corridos comprueba
cada línea contra la siguiente, y esto comprueba el total contra lo que el banco dijo. Una lectura puede pasar el
primero y fallar el segundo —si se perdió una línea entera al final del mes, la cadena de las demás encadena— y es
justo el caso que un lector de PDF produce.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date

from ..errores import ErrorContaperu
from ..modelo import fecha as _fecha, monto as _monto


class ExtractoInvalido(ErrorContaperu, ValueError):
    """Una cabecera de extracto que no se puede usar. Dice cuál y por qué."""


@dataclass
class Extracto:
    """La cabecera de un extracto, normalizada. Solo `cuenta` es obligatoria: lo demás lo imprime quien lo imprime."""

    cuenta: str = ""                  # el `id` de la cuenta en el maestro, igual que en el movimiento
    desde: date | None = None         # el periodo que cubre la hoja. Se reporta y NUNCA filtra
    hasta: date | None = None
    saldo_inicial: object = None      # None no es cero: es «la hoja no lo dice»
    saldo_final: object = None
    total_cargos: object = None
    total_abonos: object = None

    def __post_init__(self) -> None:
        self.cuenta = str(self.cuenta or "").strip()
        self.desde = _fecha(self.desde)
        self.hasta = _fecha(self.hasta)
        for campo in ("saldo_inicial", "saldo_final", "total_cargos", "total_abonos"):
            valor = getattr(self, campo)
            if valor is not None and valor != "":
                setattr(self, campo, _monto(valor))
            else:
                setattr(self, campo, None)
        if not self.cuenta:
            raise ExtractoInvalido("Un extracto necesita el `id` de la cuenta a la que pertenece")
        if self.desde and self.hasta and self.hasta < self.desde:
            raise ExtractoInvalido(f"El extracto de {self.cuenta!r} acaba antes de empezar: "
                                   f"{self.hasta.isoformat()} < {self.desde.isoformat()}")

    def a_dict(self) -> dict:
        d: dict = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, date):
                d[f.name] = v.isoformat()
            elif v is None:
                d[f.name] = None
            else:
                d[f.name] = str(v) if f.name != "cuenta" else v
        return d

    @classmethod
    def de_dict(cls, d: dict) -> "Extracto":
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(d) - set(validas))
        if desconocidas:
            raise ExtractoInvalido(f"Claves que no son de un extracto: {', '.join(desconocidas)}. "
                                   f"Las que hay: {', '.join(validas)}")
        return cls(**{nombre: d.get(nombre) for nombre in validas if nombre in d})


def por_cuenta(extractos) -> dict:
    """Los extractos por el `id` de su cuenta, **rechazando dos del mismo**.

    Dos cabeceras de la misma cuenta en un documento no es un mes partido en dos hojas: es un documento que declara
    dos saldos iniciales para lo mismo, y no hay regla que diga cuál gana. Si hace falta mandar dos periodos, van
    en dos documentos — que es lo que el `libro` ya impone por su `periodo`."""
    salida: dict = {}
    for e in extractos or ():
        x = e if isinstance(e, Extracto) else Extracto.de_dict(e)
        if x.cuenta in salida:
            raise ExtractoInvalido(f"Dos extractos de la cuenta {x.cuenta!r} en el mismo documento: no hay regla "
                                   f"que diga cuál de los dos saldos manda. Van en dos documentos")
        salida[x.cuenta] = x
    return salida
