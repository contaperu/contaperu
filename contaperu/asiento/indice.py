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

from ..modelo import Libro, clave_de, identidad_de
from .huella import huella
from .lineas import LineaDiario


@dataclass(frozen=True)
class Cabecera:
    """Los hechos de un comprobante que un driver necesita al escribir sus filas y que no son de ninguna línea.

    **La regla, desde la 1.4.0: aquí está TODO hecho contable o tributario del comprobante, y ningún dato del
    proceso que lo produjo.** Lo hace cumplir `tests/test_cabecera.py`, que la compara contra el esquema del
    estándar: si el estándar gana un campo, o entra aquí o entra en la lista de los que no son hechos.

    Nació con trece campos, los que CONCAR necesitaba, y eso bastó mientras el único driver de asientos escribía
    contabilidad pura. STARSOFT rompió el supuesto: su plantilla mezcla el asiento con el registro tributario en la
    misma fila, así que pide el destino del IGV, el valor no gravado y los datos de la DUA. Un driver de REGISTRO
    (SIRE, CONTASIS) siempre los tuvo, porque recibe el comprobante entero; uno de ASIENTOS no, y se caían aquí.

    Fuera quedan los siete del proceso —`origen`, `confianza`, `archivo_nombre`, `datos_originales`, `estado`,
    `excluida`, `observaciones`—: dicen de dónde salió el dato y qué opina la validación, no qué pasó. Un driver
    que mirara `confianza` estaría decidiendo contabilidad con la certeza de un modelo de lenguaje.

    Todo en texto, como en el estándar: un importe es su `Decimal` escrito, sin redondear nada.
    """

    # Identificación
    tipo_cp: str = ""
    serie: str = ""
    numero: str = ""
    numero_final: str = ""           # solo rangos: boletas consolidadas del día
    fecha_emision: str = ""
    condicion_pago: str = ""
    id_externo: str = ""
    # Contraparte
    contraparte_tipo_doc: str = ""   # tipo de documento de identidad: 6 RUC, 1 DNI, 4 CE, 7 pasaporte
    contraparte_doc: str = ""
    contraparte_nombre: str = ""
    glosa: str = ""                  # la del comprobante, en mayúsculas y sin cortar (`asiento.glosa_de`)
    # Importes
    moneda: str = ""
    base_gravada: str = "0"
    igv: str = "0"
    dscto_base: str = "0"            # qué parte de la base informa el SIRE como descuento; no resta al total
    dscto_igv: str = "0"
    exonerado: str = "0"
    inafecto: str = "0"
    exportacion: str = "0"
    isc: str = "0"
    base_ivap: str = "0"
    ivap: str = "0"
    icbper: str = "0"
    otros: str = "0"
    total: str = "0"
    retencion: str = "0"             # la de renta de 4ta que MUESTRA el recibo por honorarios
    # Solo compras
    destino_igv: str = "DG"          # DG gravadas | DGNG mixtas | DNG no gravadas
    valor_no_gravado: str = "0"      # YA RESUELTO: si el comprobante no lo trae, exonerado + inafecto
    anio_dua: str = ""
    cod_dep_aduanera: str = ""
    clasif_bienes: str = ""
    id_contrato: str = ""

    def a_dict(self) -> dict[str, str]:
        return asdict(self)


    @property
    def clave(self) -> tuple[str, str, str, str]:
        """La misma identidad de duplicados que `Comprobante.clave`, calculada con la misma función.

        La tiene para que `modelo.identidad_de` —que solo lee `.clave`— sirva igual para un comprobante y para la
        cabecera de su tramo. Sin esto, quien tiene el índice y no los comprobantes —un driver— tendría que
        rehacer la normalización del número y del documento, que es de donde salen los duplicados."""
        return clave_de(self.tipo_cp, self.serie, self.numero, self.contraparte_doc)


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


def exportacion_de(libro: Libro, lineas: Sequence[LineaDiario], indice: Sequence[ComprobanteDelAsiento]) -> dict:
    """Lo que hay que saber de un asiento para reconocerlo después: su huella y, por comprobante, su identidad, el
    tramo de líneas que le toca (`[desde, hasta)`) y la huella de ese tramo. Los tramos parten las líneas sin dejar
    hueco ni solaparse.

    Se arma aquí, y no en la capa de respuesta, porque **quien lo necesita lo tiene en la mano en dos sitios**: la
    respuesta del API lo pone en `_exportacion`, y un driver que escriba el documento del estándar puede llevarlo
    dentro del archivo, que es lo que el estándar admite en su raíz (`estandar/LEEME.md`, las claves `_`). Hasta la
    3.1 vivía solo en `pipeline/salida.py` y el archivo salía sin ello: quien recibiera el JSON a secas se quedaba
    sin la clave con la que no repetir un comprobante."""
    return {"huella": huella(lineas),
            "comprobantes": [{"identidad": identidad_de(libro, entrada.cabecera),
                              "lineas": [entrada.desde, entrada.hasta],
                              "huella": huella(entrada.lineas(lineas))} for entrada in indice]}
