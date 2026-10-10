"""La constancia de un pago: lo que el pagador dice que pagó, y qué cancela.

**Es por operación**, al revés que el estado de cuenta, que es el mes completo. Lo dijo John el 10-oct-2026 con
esas palabras, y hay tres razones más que lo confirman y que son las que impiden fundirlas en un solo objeto:

- **Son hechos de testigos distintos.** El banco sabe el saldo y no sabe qué cancela cada cargo; la constancia
  sabe qué cancela y no sabe el saldo.
- **Las cardinalidades no cuadran.** Un solo cargo paga un lote de detracciones —se ve en los extractos reales,
  «Pago Detracciones Masivo SUNAT»— y una constancia puede partirse en dos movimientos.
- **Los ciclos de vida difieren.** La constancia existe semanas antes de que llegue el extracto, que es justo lo
  que `tributos.detracciones.estado_de` ya hace hoy sin ningún archivo de banco delante.

**Y vale para cualquier pago**, que es lo que John pidió: «todo tipo de pagos, porque puede llamar a otra cuenta
que no necesariamente proveedor, pagos tributos, pagos de caja chica». Lo que lo consigue es `referencias`, con
cuatro clases y ninguna más. La última, `libre`, es la que evita la trampa en la que cae un modelo de tesorería:
enumerar propósitos de pago. El estándar no sabe cuántos hay y no tiene por qué.

**Ninguna cuenta la elige el motor.** El 104 sale de la cuenta bancaria que el contribuyente declaró —aquí solo se
apunta a ella por su `id`— y la contrapartida sale de la imputación, igual que hoy sale la cuenta de un gasto. Es
la doctrina de `asiento.resolucion.imputado`: sin imputación no hay cuenta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from datetime import date

from ..errores import ErrorContaperu
from ..modelo import CERO, fecha as _fecha, monto as _monto

# Qué cancela un pago. Cuatro clases, y cada una lleva lo mínimo para reconocer lo cancelado sin inventar nada.
COMPROBANTE = "comprobante"      # la 4-tupla de `Comprobante.clave`, que ya existe y no hay que redefinir
TRIBUTO = "tributo"              # código del Catálogo 05 de SUNAT y periodo: el IGV, la renta, el ITF
CUENTA_PROPIA = "cuenta_propia"  # un traspaso entre cuentas del contribuyente, que no se cuenta dos veces
LIBRE = "libre"                  # la caja chica y todo lo demás, en texto
CLASES = (COMPROBANTE, TRIBUTO, CUENTA_PROPIA, LIBRE)

# Lo que cada clase admite. Se declara para que una referencia mal formada se diga por su nombre y no se arrastre.
CLAVES_POR_CLASE = {
    COMPROBANTE: ("tipo_cp", "serie", "numero", "contraparte_doc"),
    TRIBUTO: ("codigo", "periodo"),
    CUENTA_PROPIA: ("cuenta",),
    LIBRE: ("texto",),
}


class ConstanciaInvalida(ErrorContaperu, ValueError):
    """Una constancia que no se puede usar. Dice cuál y por qué."""


@dataclass
class Referencia:
    """Qué cancela el pago, según lo que diga el papel.

    **Solo lo que el documento afirma.** Una constancia de detracción nombra su comprobante, así que eso es un
    hecho; que un cargo de 3 500 corresponda a una factura de 3 500 es una conjetura, y las conjeturas son de
    `conciliar`, que las devuelve con su método y su certeza y **nunca confirma**. Mezclarlas aquí borraría la
    diferencia justo donde más importa."""

    clase: str = ""
    datos: dict = field(default_factory=dict)
    importe: object = None      # cuando el pago se reparte; None es «todo el importe de la constancia»

    def __post_init__(self) -> None:
        self.clase = str(self.clase or "").strip().lower()
        if self.clase not in CLASES:
            raise ConstanciaInvalida(f"Clase de referencia inválida: {self.clase!r} ({' | '.join(CLASES)})")
        self.datos = {str(k): ("" if v is None else str(v)).strip() for k, v in dict(self.datos or {}).items()}
        admitidas = CLAVES_POR_CLASE[self.clase]
        sobran = sorted(set(self.datos) - set(admitidas))
        if sobran:
            raise ConstanciaInvalida(f"Una referencia de clase {self.clase!r} no lleva {', '.join(sobran)}. "
                                     f"Lleva: {', '.join(admitidas)}")
        if not any(self.datos.values()):
            raise ConstanciaInvalida(f"Una referencia de clase {self.clase!r} sin ningún dato no cancela nada")
        if self.importe is not None and self.importe != "":
            self.importe = _monto(self.importe)
            if self.importe <= CERO:
                raise ConstanciaInvalida(f"Importe inválido en una referencia {self.clase!r}: {self.importe}")

    def a_dict(self) -> dict:
        d: dict = {"clase": self.clase, "datos": dict(self.datos)}
        if self.importe is not None and self.importe != "":
            d["importe"] = str(self.importe)
        return d


@dataclass
class Constancia:
    """La prueba de un pago, con lo que el papel dice y nada más."""

    numero: str = ""                 # la llave no inventable: la constancia del BN, el nº de operación del banco
    fecha: date | None = None
    importe: object = CERO
    moneda: str = ""
    medio_pago: str = ""             # Tabla 1 del Anexo 3 de la RS 169-2015, el mismo catálogo que el comprobante
    cuenta_origen: str = ""          # el `id` en `cuentas_bancarias`; NO una cuenta contable y NO un número suelto
    beneficiario: dict | None = None  # {tipo_doc, doc, nombre}; vacío de verdad en un reintegro de caja chica
    concepto: str = ""
    referencias: list = field(default_factory=list)
    origen: str = ""                 # de dónde salió el dato, como en el comprobante
    confianza: object = None         # por debajo de 1 solo tiene sentido en lo que leyó una IA
    datos_originales: dict | None = None

    def __post_init__(self) -> None:
        self.numero = str(self.numero or "").strip()
        self.moneda = str(self.moneda or "").strip().upper()
        self.medio_pago = re.sub(r"[^0-9]", "", str(self.medio_pago or ""))
        self.cuenta_origen = str(self.cuenta_origen or "").strip()
        self.concepto = " ".join(str(self.concepto or "").split())
        self.origen = str(self.origen or "").strip().lower()
        self.fecha = _fecha(self.fecha)
        self.importe = _monto(self.importe)
        self.referencias = [r if isinstance(r, Referencia) else Referencia(**dict(r)) for r in self.referencias]
        if not self.numero:
            raise ConstanciaInvalida("Una constancia necesita su número: es lo único que no se puede inventar")
        if self.fecha is None:
            raise ConstanciaInvalida(f"La constancia {self.numero!r} no tiene fecha. Es el día del pago, que no es "
                                     f"el de la factura: se paga días después, a veces el mes siguiente")
        if self.importe <= CERO:
            raise ConstanciaInvalida(f"La constancia {self.numero!r} no tiene importe: {self.importe}")

    @property
    def repartido(self) -> object:
        """Lo que las referencias dicen cancelar. Una referencia sin importe no suma: vale por el total."""
        return sum((r.importe for r in self.referencias if r.importe not in (None, "")), CERO)

    @property
    def sin_atribuir(self) -> object:
        """Lo que el pago cubre y ninguna referencia reclama.

        **No es un error, y por eso no lo levanta nadie.** Un cargo lleva el ITF dentro, y un pago puede cancelar
        algo que el papel no nombra. El motor lo reporta y nunca lo cierra; quién decide qué es ese resto es del
        contador, por la imputación."""
        if not any(r.importe not in (None, "") for r in self.referencias):
            return CERO
        return (self.importe - self.repartido)

    def a_dict(self) -> dict:
        d: dict = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if f.name == "referencias":
                d[f.name] = [r.a_dict() for r in v]
            elif f.name in ("beneficiario", "datos_originales"):
                if v:
                    d[f.name] = dict(v)
            elif isinstance(v, date):
                d[f.name] = v.isoformat()
            elif f.name in ("importe", "confianza") and v is not None:
                d[f.name] = str(v)
            else:
                d[f.name] = v
        return d

    @classmethod
    def de_dict(cls, d: dict) -> "Constancia":
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(d) - set(validas))
        if desconocidas:
            raise ConstanciaInvalida(f"Claves que no son de una constancia: {', '.join(desconocidas)}. "
                                     f"Las que hay: {', '.join(validas)}")
        return cls(**{nombre: d.get(nombre) for nombre in validas if nombre in d})
