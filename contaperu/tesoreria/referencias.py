"""Qué cancela un pago, según lo que diga el papel.

Vive aparte del movimiento porque es una lista dentro de él y tiene sus propias reglas, no porque sea otro hecho:
un movimiento y lo que ese movimiento cancela los afirma **el mismo testigo**.

**Solo lo que el documento afirma.** Una constancia de detracción nombra su comprobante, así que eso es un hecho;
que un cargo de 3 500 corresponda a una factura de 3 500 es una conjetura, y las conjeturas son de `conciliar`, que
las devuelve con su método y su certeza y **nunca confirma**. Mezclarlas aquí borraría la diferencia justo donde más
importa.

**Y vale para cualquier pago**, que es lo que John pidió: «todo tipo de pagos, porque puede llamar a otra cuenta que
no necesariamente proveedor, pagos tributos, pagos de caja chica». Lo que lo consigue son las cuatro clases, y la
última —`libre`— es la que evita la trampa en la que cae un modelo de tesorería: enumerar propósitos de pago. El
estándar no sabe cuántos hay y no tiene por qué.

**Lo que esto NO es: una imputación.** Aquí va lo que el papel dice que se pagó; la cuenta con la que se asienta la
llega en `imputaciones_de_movimientos`. Es la doctrina de `asiento.resolucion.imputado`: sin imputación no hay
cuenta.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..errores import ErrorContaperu
from ..modelo import CERO, monto as _monto

# Qué cancela un pago. Cuatro clases, y cada una lleva lo mínimo para reconocer lo cancelado sin inventar nada.
COMPROBANTE = "comprobante"      # la 4-tupla de `Comprobante.clave`, que ya existe y no hay que redefinir
TRIBUTO = "tributo"              # código del Catálogo 05 de SUNAT y periodo: el IGV, la renta, el ITF
CUENTA_PROPIA = "cuenta_propia"  # un traspaso entre cuentas del contribuyente, que no se cuenta dos veces
LIBRE = "libre"                  # la caja chica y todo lo demás, en texto
CLASES = (COMPROBANTE, TRIBUTO, CUENTA_PROPIA, LIBRE)

# Lo que cada clase admite. Se declara para que una referencia mal formada se diga por su nombre y no se arrastre.
# **Desde la 3.0 del estándar esto está además en el esquema**, con un `if/then` por clase: hasta entonces vivía solo
# aquí, así que un validador que usara el JSON publicado aceptaba lo que el motor rechaza — y el caso de conformidad
# «las cuatro clases, cada una con lo suyo» no podía fallar, porque el esquema no miraba las claves de `datos`.
CLAVES_POR_CLASE = {
    COMPROBANTE: ("tipo_cp", "serie", "numero", "contraparte_doc"),
    TRIBUTO: ("codigo", "periodo"),
    CUENTA_PROPIA: ("cuenta",),
    LIBRE: ("texto",),
}


class ReferenciaInvalida(ErrorContaperu, ValueError):
    """Una referencia que no se puede usar. Dice cuál y por qué, y no la arregla."""


@dataclass
class Referencia:
    """Qué cancela el pago, según lo que diga el papel."""

    clase: str = ""
    datos: dict = field(default_factory=dict)
    importe: object = None      # cuando el pago se reparte; None es «todo el importe del movimiento»

    def __post_init__(self) -> None:
        self.clase = str(self.clase or "").strip().lower()
        if self.clase not in CLASES:
            raise ReferenciaInvalida(f"Clase de referencia inválida: {self.clase!r} ({' | '.join(CLASES)})")
        self.datos = {str(k): ("" if v is None else str(v)).strip() for k, v in dict(self.datos or {}).items()}
        admitidas = CLAVES_POR_CLASE[self.clase]
        sobran = sorted(set(self.datos) - set(admitidas))
        if sobran:
            raise ReferenciaInvalida(f"Una referencia de clase {self.clase!r} no lleva {', '.join(sobran)}. "
                                     f"Lleva: {', '.join(admitidas)}")
        if not any(self.datos.values()):
            raise ReferenciaInvalida(f"Una referencia de clase {self.clase!r} sin ningún dato no cancela nada")
        if self.importe is not None and self.importe != "":
            self.importe = _monto(self.importe)
            if self.importe <= CERO:
                raise ReferenciaInvalida(f"Importe inválido en una referencia {self.clase!r}: {self.importe}")

    def a_dict(self) -> dict:
        d: dict = {"clase": self.clase, "datos": dict(self.datos)}
        if self.importe is not None and self.importe != "":
            d["importe"] = str(self.importe)
        return d
