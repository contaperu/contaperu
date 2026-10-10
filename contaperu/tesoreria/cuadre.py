"""El extracto se valida solo, y eso es lo mejor que tiene.

Los tres bancos que se pudieron abrir traen **dos controles encima del mismo dato**: el bloque de totales de la
cabecera o del pie —«Saldo Anterior, Total Cargos, Total Abonos, Saldo Actual» en BanBif; «Saldo Final al 30 de
Junio» y los dos acumulados en Scotiabank; el «SALDO A SU FAVOR» de BBVA— y, línea a línea, **el saldo corrido**.

Eso convierte «leí un PDF» en «lo leí bien». Un lector de extractos es un parseador de texto de ancho fijo sobre
un PDF que a veces viene de una impresora de *mainframe*: se equivoca callado, se salta una línea, pega dos
columnas. El saldo corrido lo delata en el acto — si la cadena no encaja, el parseo está mal y no hace falta un
humano para verlo.

Es la misma idea que `contable.partida_doble`, y por el mismo motivo escrito allí: «antes de que esto fuera una
función, el motor exportaba igual aunque no cuadraran». Aquí todavía no hay nada que exportar, y la función entra
igual: **es lo que cualquier lector futuro tiene que llamar antes de decir que leyó un mes.**

**Sin tolerancia**, como la partida doble. Un céntimo de diferencia en un extracto no es un redondeo: es una línea
mal leída.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..errores import ErrorContaperu
from ..modelo import CENTIMO, CERO, monto as _monto
from .movimientos import Movimiento


class ExtractoNoCuadra(ErrorContaperu):
    """La cadena de saldos del extracto no encaja. Lleva el resultado para decir en qué línea se rompió."""

    def __init__(self, resultado: "CuadreExtracto") -> None:
        self.resultado = resultado
        super().__init__(str(resultado))


@dataclass(frozen=True)
class CuadreExtracto:
    cuadra: bool
    saldo_inicial: Decimal
    saldo_final: Decimal            # el que resulta de aplicar los movimientos
    cargos: Decimal
    abonos: Decimal
    movimientos: int
    rompe_en: int                   # el índice (1 = la primera) donde el saldo corrido dejó de encajar; 0 = ninguno
    diferencia: Decimal             # en esa línea: el saldo que trae menos el que sale de la cadena

    def __str__(self) -> str:
        if self.cuadra:
            return (f"El extracto cuadra: {self.movimientos} movimientos, {self.saldo_inicial} → "
                    f"{self.saldo_final} (cargos {self.cargos}, abonos {self.abonos})")
        return (f"El saldo corrido del extracto se rompe en el movimiento {self.rompe_en} de {self.movimientos}: "
                f"trae un saldo que difiere en {self.diferencia} del que sale de la cadena. "
                f"Casi siempre es una línea mal leída, no un error del banco")

    def a_dict(self) -> dict:
        return {"cuadra": self.cuadra, "saldo_inicial": str(self.saldo_inicial),
                "saldo_final": str(self.saldo_final), "cargos": str(self.cargos), "abonos": str(self.abonos),
                "movimientos": self.movimientos, "rompe_en": self.rompe_en,
                "diferencia": str(self.diferencia)}


def cuadra(movimientos: list, saldo_inicial: object = CERO, saldo_final: object = None) -> CuadreExtracto:
    """Aplica los movimientos al saldo inicial y comprueba la cadena.

    Dos comprobaciones, y la primera es la que más vale: **si una línea trae su propio saldo, tiene que ser el que
    sale de la cadena**, y la primera que no lo sea se señala por su posición. Un lector que se salta una línea o
    pega dos columnas lo descubre aquí y no en el cierre.

    La segunda es el total: el saldo que resulta tiene que ser el que declara la cabecera. `saldo_final=None`
    significa que el archivo no lo dice y entonces no se comprueba — no se inventa.

    Un movimiento **sin** saldo propio no rompe nada: se le aplica su importe y se sigue. Hay extractos que solo
    dan el saldo al final de cada día.

    **El ITF se descuenta aparte, y esto lo enseñó el archivo real.** En BBVA no está dentro del importe: va en su
    propia columna y el saldo corrido lo resta igual. Con las cifras del extracto de agosto de 2026,
    1 070 867,80 − 4 960,00 da 1 065 907,80 y el banco imprime 1 065 907,60 — los veinte céntimos que faltan son
    el ITF de esa línea. Sin esto, el primer lector de BBVA habría «cuadrado mal» en la segunda fila del mes."""
    saldo = _monto(saldo_inicial)
    cargos = abonos = CERO
    rompe_en, diferencia = 0, CERO
    for n, m in enumerate(movimientos, start=1):
        mov = m if isinstance(m, Movimiento) else Movimiento.de_dict(m)
        if mov.es_cargo:
            cargos += mov.importe
            saldo -= mov.importe
        else:
            abonos += mov.importe
            saldo += mov.importe
        # Siempre resta, cobre o pague: el impuesto a las transacciones financieras lo paga el titular de la
        # cuenta en los dos sentidos. Cuando el banco lo asienta como un movimiento propio —Scotiabank escribe
        # «IMPUESTO A LOS DÉBITOS»— llega como un cargo más y este campo va vacío.
        if mov.itf is not None:
            saldo -= mov.itf
        saldo = saldo.quantize(CENTIMO)
        if mov.saldo is not None and not rompe_en and mov.saldo != saldo:
            rompe_en, diferencia = n, (mov.saldo - saldo).quantize(CENTIMO)
    declarado = None if saldo_final is None or saldo_final == "" else _monto(saldo_final)
    if declarado is not None and not rompe_en and declarado != saldo:
        rompe_en, diferencia = len(movimientos), (declarado - saldo).quantize(CENTIMO)
    return CuadreExtracto(
        cuadra=(rompe_en == 0), saldo_inicial=_monto(saldo_inicial), saldo_final=saldo,
        cargos=cargos.quantize(CENTIMO), abonos=abonos.quantize(CENTIMO),
        movimientos=len(movimientos), rompe_en=rompe_en, diferencia=diferencia,
    )


def exigir(movimientos: list, saldo_inicial: object = CERO, saldo_final: object = None) -> CuadreExtracto:
    """Como `cuadra`, pero levanta `ExtractoNoCuadra` si la cadena no encaja.

    Es lo que un lector llama al terminar de leer un archivo: devolver movimientos que no cuadran es devolver un
    mes que nadie ha comprobado, con la solidez aparente que da venir de un motor con tests."""
    r = cuadra(movimientos, saldo_inicial, saldo_final)
    if not r.cuadra:
        raise ExtractoNoCuadra(r)
    return r
