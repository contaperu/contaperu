"""La cuenta bancaria del contribuyente: lo que declara quien llama, no una tabla del motor.

**Es un argumento, no estado.** El §6 de la hoja de ruta lo dice sin rodeos: el periodo, el cierre y el plan de
cuentas como tabla viva son del ERP, y lo que puede vivir aquí es su contrato. Así que esto no guarda cuentas: las
recibe, las valida y las devuelve. El molde es el de `imputaciones` y `correlativos`, que ya lo hacen.

**La cuenta contable la pone el contribuyente, cuenta por cuenta.** Cada cuenta corriente tiene su divisionaria —la
de soles no es la de dólares, y la del Banco de la Nación tampoco—, así que el motor no la deriva ni la supone: la
104 del PCGE es un dato de la empresa, igual que la cuenta de un gasto. Fue la decisión de John del 10-oct-2026, y
tiene precedente: la 3.0 retiró un comodín que imputaba a mercaderías en silencio toda compra sin cuenta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields

from ..errores import ErrorContaperu

# El Código de Cuenta Interbancario: **20 dígitos en cuatro grupos**, 3 + 3 + 12 + 2.
#
# La estructura está verificada contra dos extractos reales de agosto de 2026, que lo imprimen con su separación a
# la vista: `011 307 000100028777 69` (BBVA) y `009-202-000003675511-34` (Scotiabank). Los tres primeros dígitos son
# la empresa del sistema financiero, los tres siguientes su oficina, los doce la cuenta y los dos últimos el control.
#
# **Lo que NO está aquí es el catálogo de códigos de banco**, y es a propósito: no se ha conseguido su fuente
# publicada. Escribirlo de memoria —`011` BBVA, `009` Scotiabank, los dos que sí constan en esos extractos, y el
# resto adivinados— sería una regla sin fuente, que es la primera que no se negocia. Es el dato que el hito D8
# espera. Mientras tanto el banco se declara por su nombre y el código se transporta sin interpretar.
LARGO_CCI = 20
PATRON_CCI = re.compile(r"^[0-9]{20}$")
# Las dos monedas que un extracto peruano trae. Una cuenta es de UNA moneda: no existe la cuenta mixta, y por eso
# cada extracto declara la suya en la cabecera y nunca mezcla.
MONEDAS = ("PEN", "USD")


class CuentaInvalida(ErrorContaperu, ValueError):
    """Una cuenta declarada que no se puede usar: el motor dice cuál y por qué, y no la arregla."""


def normalizar_cci(cci: str) -> str:
    """El CCI sin su separación, que cada banco escribe a su manera.

    BBVA lo imprime con espacios y Scotiabank con guiones; los dos son el mismo número. Quitar lo que no es dígito
    es la única normalización que admite: **no se rellena con ceros a la izquierda**, porque un CCI corto no es un
    CCI al que le falten ceros, es un dato mal copiado."""
    return re.sub(r"[^0-9]", "", str(cci or ""))


def banco_del_cci(cci: str) -> str:
    """Los tres primeros dígitos: la empresa del sistema financiero. Vacío si el CCI no tiene la forma.

    Sirve para decir si dos cuentas son del mismo banco sin preguntarlo, que es lo que una conciliación necesita
    para distinguir un traspaso entre cuentas propias de un pago a un tercero. **No traduce el código a un nombre**:
    para eso haría falta el catálogo que todavía no tiene fuente."""
    limpio = normalizar_cci(cci)
    return limpio[:3] if PATRON_CCI.fullmatch(limpio) else ""


@dataclass
class CuentaBancaria:
    """Una cuenta del contribuyente, tal como la declara quien llama.

    Lo mínimo para que una conciliación tenga contra qué casar: **de quién es la cuenta, en qué moneda, y con qué
    cuenta contable se asienta**. Todo lo demás —el nombre comercial del producto, la oficina, el ejecutivo— es del
    banco y no se modela: viaja en `datos_originales`, que el motor pasa sin interpretar."""

    id: str = ""                    # cómo la nombra el contribuyente; es la llave con la que un movimiento apunta
    banco: str = ""                 # el nombre, tal cual: el código no se traduce porque no hay catálogo con fuente
    numero: str = ""                # el número de cuenta como lo escribe el banco
    cci: str = ""
    moneda: str = ""
    cuenta_contable: str = ""       # la 104x del contribuyente, que el motor NO deriva
    datos_originales: dict | None = None

    def __post_init__(self) -> None:
        self.id = str(self.id or "").strip()
        self.banco = " ".join(str(self.banco or "").split())
        self.numero = str(self.numero or "").strip()
        self.cci = normalizar_cci(self.cci)
        self.moneda = str(self.moneda or "").strip().upper()
        self.cuenta_contable = re.sub(r"[^0-9]", "", str(self.cuenta_contable or ""))
        if not self.id:
            raise CuentaInvalida("Una cuenta bancaria necesita un `id`: es con lo que un movimiento la nombra")
        if not self.numero and not self.cci:
            raise CuentaInvalida(f"La cuenta {self.id!r} no tiene número ni CCI: no hay forma de reconocerla")
        if self.cci and not PATRON_CCI.fullmatch(self.cci):
            raise CuentaInvalida(f"CCI inválido en la cuenta {self.id!r}: {self.cci!r} "
                                 f"({LARGO_CCI} dígitos; tiene {len(self.cci)})")
        if self.moneda not in MONEDAS:
            raise CuentaInvalida(f"Moneda inválida en la cuenta {self.id!r}: {self.moneda!r} "
                                 f"({' | '.join(MONEDAS)})")

    @property
    def codigo_de_banco(self) -> str:
        """El código del CCI, cuando hay CCI. Vacío no significa «otro banco»: significa que no se declaró."""
        return banco_del_cci(self.cci)

    def a_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "datos_originales"}
        if self.datos_originales:
            d["datos_originales"] = dict(self.datos_originales)
        return d

    @classmethod
    def de_dict(cls, d: dict) -> "CuentaBancaria":
        """Rechaza lo que no reconoce, nombrándolo: un dato que se cuela sin error es un dato que se pierde sin
        aviso, y el lector no puede ser más laxo que lo que se publica."""
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(d) - set(validas))
        if desconocidas:
            raise CuentaInvalida(f"Claves que no son de una cuenta bancaria: {', '.join(desconocidas)}. "
                                 f"Las que hay: {', '.join(validas)}")
        return cls(**{nombre: d.get(nombre) for nombre in validas if nombre in d})


def leer(cuentas: list | None) -> tuple[CuentaBancaria, ...]:
    """Las cuentas que aporta quien llama, validadas y con sus `id` sin repetir.

    Sin cuentas no pasa nada: es un argumento opcional, y su ausencia no cambia ningún comportamiento. Es la misma
    promesa que hacen `plan_de_cuentas*` y `padron*` cuando entren."""
    leidas = tuple(c if isinstance(c, CuentaBancaria) else CuentaBancaria.de_dict(c) for c in (cuentas or []))
    vistos: dict[str, int] = {}
    for c in leidas:
        vistos[c.id] = vistos.get(c.id, 0) + 1
    repetidos = sorted(k for k, n in vistos.items() if n > 1)
    if repetidos:
        raise CuentaInvalida(f"Hay cuentas bancarias con el mismo `id`: {', '.join(repetidos)}. "
                             f"El `id` es la llave con la que un movimiento las nombra, así que tiene que ser único")
    return leidas
