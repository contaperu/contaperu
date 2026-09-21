"""El .xlsx de CONCAR (cabecera y formatos de celda de la plantilla oficial) y el punto de entrada `desde_lineas` del
contrato: las líneas neutrales del libro, ya numeradas y cuadradas, proyectadas con la cabecera de su comprobante.
"""
from __future__ import annotations

from typing import Any

from ...asiento.faltas import NoExportable
from ...asiento.indice import ComprobanteDelAsiento
from ...asiento.lineas import LineaDiario
from ...asiento.resolucion import etiquetas_sub_diario, limites_del_periodo
from ...modelo import Libro
from ..kit import Opciones, nombre_de_archivo
from ..kit import xlsx as kit_xlsx
from . import datos, proyeccion  # noqa: F401  (`datos` es un nombre que la 0.10 dejaba ver aquí)
from .datos import (ANCHOS, AUTOFILTRO, CABECERAS, COLUMNAS_FECHA, COLUMNAS_IMPORTE, COLUMNAS_TEXTO, EXIGE,  # noqa: F401
                    FORMATOS, HOJA, OPCIONES, PANEL)

# Hasta la 1.x este módulo reexportaba, con aviso, lo que dejaba ver en la 0.10 para armar el asiento él mismo
# (`construir`, `numerar`, `huella`…). La 2.0 lo retiró con el resto de la compatibilidad con la 0.x: el asiento lo
# arma el núcleo y el archivo se pide a `contaperu.api.exportar_archivo`.

# CONCAR numera el asiento con MM + cuatro dígitos (`asiento.numerar_en_orden`).
MAXIMO_CORRELATIVO = 9999


class CorrelativoDesborda(NoExportable):
    """Un sub-diario pasaría de 9999: CONCAR numera el asiento con MM + cuatro dígitos (`asiento.numerar`),
    y un quinto dígito no cabe en su importación. `sub_diarios` es {sub-diario: hasta dónde llegaría}."""

    clave = "sub_diario_desborda"

    def __init__(self, sub_diarios: dict[str, int]):
        super().__init__("; ".join(f"El sub-diario {s} llegaría a {n}: supera los 4 dígitos que admite CONCAR"
                                   for s, n in sub_diarios.items()))
        self.sub_diarios = sub_diarios


def nombre(libro: Libro, opciones: Opciones = OPCIONES) -> str:
    return nombre_de_archivo(datos.NOMBRE, libro, opciones)


def escribir_xlsx(filas: list[dict[str, Any]]) -> bytes:
    from openpyxl.styles import Alignment, Font, PatternFill

    libro_excel, hoja = kit_xlsx.libro_con_hoja(HOJA)
    # Formato de la plantilla oficial de CONCAR: titulos
    # en azul marino con letra blanca, notas sin relleno con la fila alta, panel
    # congelado en A4 y autofiltro sobre la fila de formatos.
    relleno_titulo = PatternFill(start_color="191970", end_color="191970", fill_type="solid")
    letra_titulo = Font(name="Aptos Narrow", size=11, bold=True, color="FFFFFF")
    letra_nota = Font(name="Aptos Narrow", size=11)
    letra_datos = Font(name="Aptos Narrow", size=11)
    alineado_titulo = Alignment(horizontal="center", vertical="center", wrap_text=True)
    alineado_nota = Alignment(vertical="top", wrap_text=True)
    alineado_formato = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for columna, titulo in CABECERAS["titulos"].items():
        celda = hoja[f"{columna}1"]
        celda.value, celda.fill, celda.font, celda.alignment = titulo, relleno_titulo, letra_titulo, alineado_titulo
    for columna, nota in CABECERAS["notas"].items():
        celda = hoja[f"{columna}2"]
        celda.value, celda.font, celda.alignment = nota, letra_nota, alineado_nota
    for columna, formato in CABECERAS["formatos"].items():
        celda = hoja[f"{columna}3"]
        celda.value, celda.font, celda.alignment = formato, letra_nota, alineado_formato
    hoja["A3"].font = Font(name="Aptos Narrow", size=11, bold=True)
    hoja.row_dimensions[1].height = 45
    hoja.row_dimensions[2].height = 120
    hoja.row_dimensions[3].height = 30
    for numero_fila, fila in enumerate(filas, start=4):
        hoja.row_dimensions[numero_fila].height = 15.8
        for columna, valor in fila.items():
            if valor == "" or valor is None:
                continue
            celda = hoja[f"{columna}{numero_fila}"]
            celda.value = valor
            celda.font = letra_datos
            if columna in COLUMNAS_FECHA:
                celda.number_format = "dd/mm/yyyy"
            elif columna in COLUMNAS_IMPORTE and isinstance(valor, (int, float)):
                celda.number_format = "#,##0.00"
            elif columna in COLUMNAS_TEXTO:
                celda.number_format = "@"
    for columna, ancho in ANCHOS.items():
        hoja.column_dimensions[columna].width = ancho
    hoja.freeze_panes = PANEL
    hoja.auto_filter.ref = AUTOFILTRO
    return kit_xlsx.a_bytes(libro_excel)


def _numero(entrada: ComprobanteDelAsiento) -> int:
    """El número del asiento dentro de su sub-diario: lo que sigue a los dos dígitos del mes."""
    return int(entrada.correlativo[2:])


def _desbordan(indice: tuple[ComprobanteDelAsiento, ...]) -> dict[str, int]:
    hasta: dict[str, int] = {}
    for entrada in indice:
        hasta[entrada.sub_diario] = max(hasta.get(entrada.sub_diario, 0), _numero(entrada))
    return {s: n for s, n in hasta.items() if n > MAXIMO_CORRELATIVO}


def _sub_diarios(indice: tuple[ComprobanteDelAsiento, ...], config: dict) -> dict[str, dict]:
    """El rango de cada sub-diario, como lo guarda quien exporta para proponer el siguiente: su etiqueta, desde y hasta
    qué número llegó, cuántos comprobantes lleva, los dos códigos `MMNNNN` y si desborda."""
    etiquetas = etiquetas_sub_diario(config)
    rangos: dict[str, dict] = {}
    for entrada in indice:
        n = _numero(entrada)
        rango = rangos.setdefault(entrada.sub_diario, {"etiqueta": etiquetas.get(entrada.sub_diario, entrada.sub_diario),
                                                      "desde": n, "hasta": n, "comprobantes": 0, "mes": entrada.correlativo[:2]})
        rango["hasta"] = n
        rango["comprobantes"] += 1
    for rango in rangos.values():
        mes = rango.pop("mes")
        rango["desde_codigo"], rango["hasta_codigo"] = f"{mes}{rango['desde']:04d}", f"{mes}{rango['hasta']:04d}"
        rango["desborda"] = rango["hasta"] > MAXIMO_CORRELATIVO
    return rangos


def desde_lineas(libro: Libro, lineas: list[LineaDiario], config: dict, opciones: Opciones = OPCIONES, *,
                 indice: tuple[ComprobanteDelAsiento, ...] = ()) -> tuple[bytes, dict]:
    """Las líneas neutrales del libro, numeradas y cuadradas por el núcleo → el .xlsx y lo que CONCAR suma al resumen.

    Cada fila lleva hechos de la cabecera de su comprobante que la línea no guarda: la glosa de la columna F y la tasa
    entera del IGV de la AO, que se redondea desde el IGV y la base del comprobante y no desde la tasa ya redondeada de
    la línea. Los trae el `indice`. Antes de escribir nada se niega si un sub-diario pasa de 9999."""
    if FORMATOS.get(libro.tipo) is None:
        raise ValueError("Tipo de libro no soportado")
    if lineas and not indice:
        raise ValueError("CONCAR escribe cada fila con la cabecera de su comprobante: necesita el `indice` del asiento")
    desbordan = _desbordan(indice)
    if desbordan:
        raise CorrelativoDesborda(desbordan)
    filas: list[dict[str, Any]] = []
    for entrada in indice:
        filas.extend(proyeccion.filas(entrada.cabecera, entrada.lineas(lineas), config))
    primero, _ = limites_del_periodo(libro)
    resumen = {"fechas": "por comprobante (extemporáneos al " + primero.strftime("%d/%m/%Y") + ")",
               "sub_diarios": _sub_diarios(indice, config)}
    return escribir_xlsx(filas), resumen
