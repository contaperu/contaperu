"""La mitad del índice que es de un MOVIMIENTO: la cabecera de sus hechos, su tramo de líneas y su identidad.

Gemela de `indice/comprobante.py` y **no una reutilización suya**, por el motivo que explica `CabeceraDeMovimiento`:
aquélla está anclada campo a campo contra el `$defs/comprobante` del estándar. Lo que las dos comparten de verdad
—qué se le pregunta a una entrada sin saber de cuál de los dos se trata— está en `comun.py`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from ...modelo import Libro
from ...modelo.accesores import campo as _de
from ...tesoreria import clave_de as clave_de_movimiento
from ..lineas import LineaDiario


@dataclass(frozen=True)
class CabeceraDeMovimiento:
    """Los hechos de un movimiento que un driver necesita al lado de sus líneas, y que ninguna línea guarda.

    Gemela de `Cabecera` y **no una reutilización**: aquélla está anclada campo a campo contra el `$defs/comprobante`
    del estándar, así que meter un movimiento dentro haría que `como_comprobante()` escribiera un comprobante que no
    existe. Aquí la promesa es la misma con el otro papel: todo hecho del movimiento, ningún dato del proceso —fuera
    quedan `origen`, `confianza`, `datos_originales` y las `referencias`, que son lo que el papel dice que cancela y
    no lo que se asentó—.

    Todo en texto, como en el estándar."""

    cuenta: str = ""                 # el `id` de la cuenta en el maestro, que es como un movimiento la nombra
    cuenta_contable: str = ""        # y la 104 con la que se asentó, que sale del maestro y no del movimiento
    fecha: str = ""
    fecha_valor: str = ""
    descripcion: str = ""            # el texto del banco, no la glosa del libro
    importe: str = "0"
    sentido: str = ""                # cargo | abono, lo que dice el papel
    efecto: str = ""                 # entrada | salida | transferencia, ya compuesto con su imputación
    moneda: str = ""
    referencia: str = ""             # el número que dio el banco
    constancia: str = ""             # el número del papel que lo prueba
    contraparte_tipo_doc: str = ""
    contraparte_doc: str = ""
    contraparte_nombre: str = ""
    medio_pago: str = ""
    itf: str = ""                    # vacío no es cero: es «el banco no lo dice»
    id_externo: str = ""

    def a_dict(self) -> dict:
        """Todos los campos, también los vacíos: un driver recibe la lista completa de hechos para saber que existen.
        Para escribir un movimiento del estándar, `como_movimiento`."""
        return asdict(self)

    def como_movimiento(self) -> dict:
        """Esta cabecera como un `movimiento` del estándar, listo para el bloque `movimientos` de un documento.

        Espejo de `Cabecera.como_comprobante`, y con sus dos mismas diferencias: **fuera lo vacío**, porque el
        estándar distingue «no lo sé» de «es esto» y lo primero se dice omitiendo la clave; y **fuera lo que el
        estándar no declara**, que aquí es `cuenta_contable` —la 104 sale del maestro de cuentas, no del
        movimiento— y `efecto`, que es derivado (`tesoreria.efecto_de`)."""
        fuera = {"cuenta_contable", "efecto"}
        return {k: v for k, v in asdict(self).items() if k not in fuera and v not in ("", None, {}, [])}

    def como_entrada(self) -> dict:
        """Lo mismo que `como_movimiento`, por el nombre que no dice cuál de las dos cabeceras es.

        Existe para que quien escribe el documento del estándar no tenga que preguntar de qué libro viene: la
        clave del bloque la da `entradas_de` desde la tabla, y el contenido lo da el objeto. Las dos de una vez,
        y ni un `if` en el driver."""
        return self.como_movimiento()

    @property
    def clave(self) -> tuple:
        """La misma identidad de duplicados que `Movimiento.clave`, calculada con la misma función."""
        return clave_de_movimiento(self.cuenta, self.referencia, self.fecha, self.sentido, self.importe,
                                   self.descripcion)


@dataclass(frozen=True)
class MovimientoDelAsiento:
    """Un movimiento dentro del asiento del libro. Misma forma que `ComprobanteDelAsiento`, para que `desde`,
    `hasta` y `lineas()` sigan sirviendo sin que nadie tenga que saber de cuál de los dos se trata."""

    posicion: int
    sub_diario: str
    correlativo: str
    desde: int
    hasta: int
    cabecera: CabeceraDeMovimiento

    def lineas(self, todas: Sequence[LineaDiario]) -> list[LineaDiario]:
        return list(todas[self.desde:self.hasta])

    def a_dict(self) -> dict:
        return {"posicion": self.posicion, "sub_diario": self.sub_diario, "correlativo": self.correlativo,
                "lineas": [self.desde, self.hasta], "cabecera": self.cabecera.a_dict()}

    def identidad(self, libro: Libro) -> dict:
        return identidad_de_movimiento(libro, self.cabecera)


def identidad_de_movimiento(libro: Libro, m: Any) -> dict:
    """La identidad estable de un movimiento: **su `clave` escrita**, con el RUC y el libro delante.

    Dos ramas, las mismas dos de `tesoreria.clave_de`: con el número que dio el banco basta ese número, y sin él
    hacen falta la fecha, el sentido, el importe y el texto. Un test comprueba que este diccionario reconstruye esa
    tupla, para que no puedan separarse."""
    cuenta = str(_de(m, "cuenta") or "")
    referencia = str(_de(m, "referencia") or "")
    base = {"ruc": libro.ruc, "libro": libro.tipo, "cuenta": cuenta}
    if referencia:
        return {**base, "referencia": referencia}
    return {**base, "fecha": str(_de(m, "fecha") or ""), "sentido": str(_de(m, "sentido") or ""),
            "importe": str(_de(m, "importe") or ""), "descripcion": str(_de(m, "descripcion") or "")}
