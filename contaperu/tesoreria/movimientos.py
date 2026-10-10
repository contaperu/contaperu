"""Una línea de un estado de cuenta: lo que el banco dice que pasó en mi cuenta.

**Es un hecho de un testigo concreto**, y por eso no es lo mismo que una constancia. El banco ve su lado de la
cuenta y sabe cuánto entró y cuánto salió; no sabe qué cancela cada cargo. La constancia lo sabe y no sabe el
saldo. Son dos objetos, y John lo dijo antes de que se escribiera: «la constancia de transferencia es por
operación y un estado de cuenta es todo completo».

**La forma salió de nueve extractos reales de producción**, de agosto de 2026, de tres bancos que abren —BBVA,
Scotiabank y BanBif—. Lo que tienen los tres: la cuenta con su CCI, una moneda, un periodo en la cabecera, y por
línea la fecha de operación, la fecha valor, una descripción, el importe y el saldo corrido.

Lo que **no** comparten, y que esta clase normaliza:

- **El signo.** BBVA trae una sola columna con el importe negativo cuando es un cargo; Scotiabank y BanBif traen
  dos columnas. Aquí el importe es **siempre positivo** y el sentido va aparte, que es la misma regla que ya rige
  en `LineaDiario.debe_haber` y en el par `otros` / `dscto_otros` del comprobante.
- **El ITF.** BBVA lo da **en una columna de la línea** y un total al pie; Scotiabank lo da como **un movimiento
  propio** («IMPUESTO A LOS DÉBITOS»); en el extracto de BanBif no aparece. Aquí cabe de las dos formas: como campo
  cuando el banco lo adjunta, y como un movimiento más cuando el banco lo asienta aparte. **Y nunca se calcula**:
  lo da el banco. Lo que falta para asentarlo es su norma, que es el hito D6.
- **El año.** Las líneas traen día y mes (`03-08`); el año está en la cabecera. Quien lee el archivo lo baja: aquí
  llega ya completo, porque el núcleo no tiene reloj con el que adivinarlo.

Lo que cada banco da y nadie más —el `ORIG` de Scotiabank, el `CAN` y la oficina de BBVA— viaja en
`datos_originales` sin interpretar, igual que en el comprobante.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields
from datetime import date

from ..errores import ErrorContaperu
from ..modelo import CERO, fecha as _fecha, monto as _monto

# Hacia dónde va el dinero, visto desde MI cuenta. Son las dos palabras que los tres bancos usan, con sus sinónimos:
# BBVA titula la columna «CARGO/ABONO», Scotiabank «CARGO | ABONO» y BanBif «Débito | Crédito».
CARGO = "cargo"
ABONO = "abono"
SENTIDOS = (CARGO, ABONO)


class MovimientoInvalido(ErrorContaperu, ValueError):
    """Una línea de extracto que no se puede usar. Dice cuál y por qué, y no la arregla."""


@dataclass
class Movimiento:
    """Una línea del estado de cuenta, normalizada."""

    cuenta: str = ""                    # el `id` de la cuenta en `cuentas_bancarias`, no un número suelto
    fecha: date | None = None           # la de la operación
    fecha_valor: date | None = None     # cuándo cuenta para el saldo; los tres bancos la dan y casi siempre coincide
    descripcion: str = ""
    importe: object = CERO              # SIEMPRE positivo: el signo lo dice `sentido`
    sentido: str = ""
    moneda: str = ""
    saldo: object = None                # el saldo corrido DESPUÉS de esta línea; None si el banco no lo da
    referencia: str = ""                # el número que pone el banco: `N° OPER` en BBVA, `REFERENCIA` en Scotiabank
    itf: object = None                  # cuando el banco lo adjunta a la línea (BBVA). None no es cero: es «no dice»
    id_externo: str = ""                # el de quien integra, para reconocerlo cuando vuelva
    datos_originales: dict | None = None

    def __post_init__(self) -> None:
        self.cuenta = str(self.cuenta or "").strip()
        self.descripcion = " ".join(str(self.descripcion or "").split())
        self.sentido = str(self.sentido or "").strip().lower()
        self.moneda = str(self.moneda or "").strip().upper()
        self.referencia = str(self.referencia or "").strip()
        self.id_externo = str(self.id_externo or "").strip()
        self.fecha = _fecha(self.fecha)
        self.fecha_valor = _fecha(self.fecha_valor) or self.fecha
        self.importe = _monto(self.importe)
        if self.saldo is not None and self.saldo != "":
            self.saldo = _monto(self.saldo)
        if self.itf is not None and self.itf != "":
            self.itf = _monto(self.itf)
        if not self.cuenta:
            raise MovimientoInvalido("Un movimiento necesita la cuenta a la que pertenece")
        if self.fecha is None:
            raise MovimientoInvalido(f"Movimiento sin fecha en la cuenta {self.cuenta!r}: el año lo baja de la "
                                     f"cabecera quien lee el archivo, porque el núcleo no tiene reloj")
        if self.sentido not in SENTIDOS:
            raise MovimientoInvalido(f"Sentido inválido en la cuenta {self.cuenta!r}: {self.sentido!r} "
                                     f"({' | '.join(SENTIDOS)})")
        # No hay comprobación de importe negativo, y no es un olvido: `modelo.monto` **ya devuelve el valor
        # absoluto** —«el signo no es parte del dato»—, así que un `-4960.00` del extracto de BBVA llega aquí
        # convertido. Eso es lo que hace falta: el lector mira el signo de la columna para poner `sentido` y pasa
        # el importe tal cual. Un `if importe < 0` aquí sería código que no puede ejecutarse nunca.

    @property
    def es_cargo(self) -> bool:
        return self.sentido == CARGO

    @property
    def clave(self) -> tuple:
        """La identidad de un movimiento, que es lo que impide duplicar al releer un mes con solape.

        Con la referencia del banco basta y sobra: es suya y no se repite dentro de una cuenta. Sin ella —BanBif no
        la da— se cae a lo que siempre hay: cuenta, fecha, sentido, importe y descripción. **Eso puede colisionar a
        propósito**: dos comisiones idénticas el mismo día son dos movimientos y una sola clave, así que un lector
        sin referencia tiene que desempatar con el orden del archivo. Se dice aquí para que nadie lo descubra
        contando mal."""
        return clave_de(self.cuenta, self.referencia, self.fecha, self.sentido, self.importe, self.descripcion)

    def a_dict(self) -> dict:
        d = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if f.name == "datos_originales":
                if v:
                    d[f.name] = dict(v)
            elif isinstance(v, date):
                d[f.name] = v.isoformat()
            elif v is None:
                d[f.name] = None
            else:
                d[f.name] = str(v) if f.name in ("importe", "saldo", "itf") else v
        return d

    @classmethod
    def de_dict(cls, d: dict) -> "Movimiento":
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(d) - set(validas))
        if desconocidas:
            raise MovimientoInvalido(f"Claves que no son de un movimiento: {', '.join(desconocidas)}. "
                                     f"Las que hay: {', '.join(validas)}")
        return cls(**{nombre: d.get(nombre) for nombre in validas if nombre in d})


def clave_de(cuenta: str, referencia: str, fecha: date | None, sentido: str, importe: object,
             descripcion: str = "") -> tuple:
    """La clave sin construir el objeto, para calcularla desde una fila de una base.

    Es el mismo recurso que `modelo.clave_de` para el comprobante, y por el mismo motivo: quien guarda movimientos
    los deduplica contra lo que ya tiene sin instanciar nada."""
    ref = re.sub(r"\s+", "", str(referencia or ""))
    if ref:
        return (str(cuenta or "").strip(), ref)
    return (str(cuenta or "").strip(), "", fecha, str(sentido or "").lower(), str(importe),
            " ".join(str(descripcion or "").split()).upper())


def sin_duplicados(movimientos: list) -> tuple[list, list]:
    """Separa los que entran de los que ya estaban, por su clave y conservando el orden.

    Devuelve `(nuevos, repetidos)` en vez de filtrar en silencio: releer un mes con solape es lo normal —se baja el
    extracto dos veces— y lo que el que integra necesita saber es **cuántos se descartaron**, no solo cuántos
    quedaron. Es el criterio de salida del hito D2: «una relectura con solape no duplica»."""
    vistas: set[tuple] = set()
    nuevos: list = []
    repetidos: list = []
    for m in movimientos:
        clave = m.clave if isinstance(m, Movimiento) else Movimiento.de_dict(m).clave
        (repetidos if clave in vistas else nuevos).append(m)
        vistas.add(clave)
    return nuevos, repetidos
