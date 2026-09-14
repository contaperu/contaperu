"""El índice del asiento: qué líneas son de qué comprobante, con la cabecera de hechos de cada uno (1.0).

Las líneas neutrales llevan la contabilidad y nada más, y así la huella solo cambia si cambia un asiento. Pero un sistema
contable escribe cada fila con hechos del COMPROBANTE que ninguna línea guarda: la glosa de la cabecera, la tasa del IGV
calculada desde su base y su IGV —y no desde la tasa de la línea, que ya viene redondeada—, el documento de la
contraparte, el `id_externo` con el que la aplicación lo reconoce. El índice los lleva al lado de las líneas, fuera de
ellas y fuera de la huella:

    lineas, rangos, indice = asiento.lineas_e_indice_del_libro(libro, comprobantes, config, correlativos)
    for entrada in indice:
        filas = proyectar(entrada.cabecera, entrada.lineas(lineas))

Lo recibe el driver de asientos que lo acepta (`desde_lineas(..., *, indice=())`, `drivers.contrato.acepta_indice`),
y es de donde sale lo que la respuesta dice de cada comprobante. Todo va en texto, como en el estándar: un importe es
su `Decimal` escrito, sin redondear nada.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from .lineas import LineaDiario


@dataclass(frozen=True)
class Cabecera:
    """Los hechos de un comprobante que un driver necesita al escribir sus filas y que no son de ninguna línea."""

    tipo_cp: str = ""
    serie: str = ""
    numero: str = ""
    fecha_emision: str = ""
    contraparte_doc: str = ""
    contraparte_nombre: str = ""
    condicion_pago: str = ""
    id_externo: str = ""
    moneda: str = ""
    glosa: str = ""              # la del comprobante, en mayúsculas y sin cortar (`asiento.glosa_de`)
    base_gravada: str = "0"
    igv: str = "0"
    total: str = "0"

    def a_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ComprobanteDelAsiento:
    """Un comprobante dentro del asiento del libro: su posición entre los que salieron, su sub-diario y su correlativo,
    el tramo de líneas que le toca (`desde` incluido, `hasta` excluido) y su cabecera."""

    posicion: int
    sub_diario: str
    correlativo: str
    desde: int
    hasta: int
    cabecera: Cabecera

    def lineas(self, todas: Sequence[LineaDiario]) -> list[LineaDiario]:
        """Las líneas de este comprobante dentro de las del libro."""
        return list(todas[self.desde:self.hasta])

    def a_dict(self) -> dict:
        return {"posicion": self.posicion, "sub_diario": self.sub_diario, "correlativo": self.correlativo,
                "lineas": [self.desde, self.hasta], "cabecera": self.cabecera.a_dict()}
