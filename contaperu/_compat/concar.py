"""`drivers.concar.construir` de la 0.10: el Excel armado desde los comprobantes, con la misma firma.

Desde la 1.0 CONCAR tiene la forma `desde_lineas` del contrato: el pipeline arma, numera y cuadra las líneas, y el
driver las proyecta con la cabecera de cada comprobante (`asiento.indice`). Se llega aquí por
`contaperu.drivers.concar.construir`, que avisa con `RutaObsoleta`; da las mismas celdas y el mismo resumen
(`tests/test_asiento_concar.py`).
"""
from __future__ import annotations

from .. import partida_doble
from ..asiento.huella import huella
from ..asiento.motor import lineas_del_comprobante
from ..asiento.resolucion import etiquetas_sub_diario, exigir_requisitos, limites_del_periodo, numerar
from ..drivers.concar import datos, proyeccion
from ..drivers.concar.datos import EXIGE, FORMATOS, OPCIONES
from ..drivers.concar.xlsx import CorrelativoDesborda, escribir_xlsx
from ..drivers.contrato import EXIGE_NUCLEO_ASIENTO, centro_en_anexo
from ..drivers.kit import Opciones
from ..modelo import Comprobante, Libro


def construir(libro: Libro, comprobantes: list[Comprobante], config: dict, correlativos: dict[str, int],
              opciones: Opciones = OPCIONES) -> tuple[bytes, dict]:
    """Comprobantes (ya seleccionados y en orden) → bytes del .xlsx + el resumen que guarda quien exporta."""
    if FORMATOS.get(libro.tipo) is None:
        raise ValueError("Tipo de libro no soportado")
    es_venta = libro.es_venta
    exigir_requisitos(comprobantes, config, es_venta, EXIGE_NUCLEO_ASIENTO | EXIGE)
    limites = limites_del_periodo(libro)
    numeros, rangos = numerar(comprobantes, config, libro.periodo, correlativos, es_venta)
    desbordan = {s: r["hasta"] for s, r in rangos.items() if r.get("desborda")}
    if desbordan:
        raise CorrelativoDesborda(desbordan)
    anexos = centro_en_anexo(datos, config)
    lineas, filas = [], []
    for c in comprobantes:
        propias = lineas_del_comprobante(c, config, limites, numeros[id(c)], opciones, es_venta, anexos)
        lineas.extend(propias)
        filas.extend(proyeccion.filas(c, propias, config))
    cuadre = partida_doble.exigir(lineas)
    resumen = {
        "filas": len(filas),
        "fechas": "por comprobante (extemporáneos al " + limites[0].strftime("%d/%m/%Y") + ")",
        "sub_diarios": {s: {"etiqueta": etiquetas_sub_diario(config).get(s, s), **r} for s, r in rangos.items()},
        "debe": str(cuadre.debe), "haber": str(cuadre.haber),
        "huella": huella(lineas),
    }
    return escribir_xlsx(filas), resumen
