"""El .xlsx de CONCAR (cabecera y formatos de celda de la plantilla oficial) y el
punto de entrada `construir` que exige el contrato de `generar.py`.
"""
from __future__ import annotations

import io
from typing import Any

from ...modelo import Comprobante, Libro
from ... import partida_doble
from ...formato import Opciones
from ...asiento.resolucion import etiquetas_sub_diario, exigir_requisitos, limites_del_periodo, numerar
from ...asiento.huella import huella
from ...asiento.motor import lineas_del_comprobante
from ..contrato import EXIGE_NUCLEO_ASIENTO
from . import proyeccion
from .datos import (ANCHOS, AUTOFILTRO, CABECERAS, COLUMNAS_FECHA, COLUMNAS_IMPORTE, COLUMNAS_TEXTO, EXIGE, FORMATOS,
                    HOJA, OPCIONES, PANEL)


class CorrelativoDesborda(Exception):
    """Un sub-diario pasaría de 9999: CONCAR numera el asiento con MM + cuatro dígitos (`asiento.numerar`),
    y un quinto dígito no cabe en su importación. `sub_diarios` es {sub-diario: hasta dónde llegaría}."""

    def __init__(self, sub_diarios: dict[str, int]):
        super().__init__("; ".join(f"El sub-diario {s} llegaría a {n}: supera los 4 dígitos que admite CONCAR"
                                   for s, n in sub_diarios.items()))
        self.sub_diarios = sub_diarios


def nombre(libro: Libro, opciones: Opciones = OPCIONES) -> str:
    return f"CONCAR_{libro.ruc}_{libro.periodo}_{'VENTAS' if libro.es_venta else 'COMPRAS'}{opciones.extension}"


def escribir_xlsx(filas: list[dict[str, Any]]) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    libro_excel = openpyxl.Workbook()
    hoja = libro_excel.active
    hoja.title = HOJA
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
    salida = io.BytesIO()
    libro_excel.save(salida)
    return salida.getvalue()


def construir(libro: Libro, comprobantes: list[Comprobante], config: dict, correlativos: dict[str, int],
              opciones: Opciones = OPCIONES) -> tuple[bytes, dict]:
    """Comprobantes (ya seleccionados y en orden) → bytes del .xlsx + resumen para `contab_exportaciones`."""
    if FORMATOS.get(libro.tipo) is None:
        raise ValueError("Tipo de libro no soportado")
    es_venta = libro.es_venta
    # Lo que CONCAR no puede importar sin: lo del núcleo (tipo con equivalencia, cuenta) y lo que
    # este driver declara en EXIGE (centro de costo donde la cuenta lo lleva, moneda con código).
    exigir_requisitos(comprobantes, config, es_venta, EXIGE_NUCLEO_ASIENTO | EXIGE)
    # Los limites del mes del proceso: cada asiento se fecha por comprobante
    # dentro de ellos (regla del 30-ago-2026; el detalle vive en `asiento.lineas_del_comprobante`).
    limites = limites_del_periodo(libro)
    numeros, rangos = numerar(comprobantes, config, libro.periodo, correlativos, es_venta)
    # CONCAR numera con MM + cuatro dígitos: un sub-diario que pase de 9999 no se importa. Hasta el
    # 11-sep-2026 lo comprobaba el portal antes de llamar aquí; la regla es de este formato.
    desbordan = {s: r["hasta"] for s, r in rangos.items() if r.get("desborda")}
    if desbordan:
        raise CorrelativoDesborda(desbordan)
    # La contabilidad sale en lineas neutrales; aqui solo se proyectan a las columnas de CONCAR.
    lineas, filas = [], []
    for c in comprobantes:
        propias = lineas_del_comprobante(c, config, limites, numeros[id(c)], opciones, es_venta)
        lineas.extend(propias)
        filas.extend(proyeccion.filas(c, propias, config))
    # El asiento tiene que cuadrar ANTES de escribir un solo byte. Por construccion siempre
    # cuadra, asi que esto es una red de seguridad: si salta, hay un error de verdad.
    cuadre = partida_doble.exigir(lineas)
    resumen = {
        "filas_excel": len(filas),
        "fechas": "por comprobante (extemporáneos al " + limites[0].strftime("%d/%m/%Y") + ")",
        "sub_diarios": {s: {"etiqueta": etiquetas_sub_diario(config).get(s, s), **r} for s, r in rangos.items()},
        "debe": str(cuadre.debe), "haber": str(cuadre.haber),
        # La huella del contenido (asiento/huella.py): con ella quien guarde este resumen reconoce la
        # tanda si vuelve a salir. Va aquí porque este resumen es lo que el portal persiste.
        "huella": huella(lineas),
    }
    return escribir_xlsx(filas), resumen
