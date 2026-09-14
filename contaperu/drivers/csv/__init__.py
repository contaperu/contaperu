"""Driver CSV genérico: el asiento en columnas, para quien no tiene un driver propio.

Es la salida de último recurso y, a la vez, la más honesta: escribe las líneas de diario del
estándar `open-accounting` tal cual, una por fila, sin traducir nada al vocabulario de ningún ERP.
Sirve para revisar un asiento en Excel, para cargarlo en un sistema que acepte texto plano y
para escribir un driver nuevo teniendo delante lo que hay que traducir.

Dos decisiones pensadas para el Perú, ambas cambiables al llamar:

- **Separador `;`** — el Excel en español interpreta la coma como decimal, así que un CSV con
  comas se abre en una sola columna. Pasa `separador=","` si el destino es un programa y no una
  persona.
- **BOM UTF-8** — sin él, Excel abre el archivo en la codificación del sistema y las tildes y
  las eñes salen rotas. Pasa `bom=False` si molesta.
"""
from __future__ import annotations

import csv as _csv  # stdlib: los imports absolutos no chocan con el nombre de este paquete
import io
from typing import Any

from ...asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from ...asiento.lineas import LineaDiario
from ..kit import Opciones
from ...modelo import Libro

NOMBRE = "csv"
# Un formato neutral para leer o integrar: proyecta la línea neutral (`drivers.contrato.CANALES`).
CANAL = "intercambio"
OPCIONES = Opciones(fecha="AAAA-MM-DD", extension=".csv")
FORMATOS = {"compra": "csv_asiento", "venta": "csv_asiento"}
CONTENT_TYPE = "text/csv; charset=utf-8"
# No exige nada más que el núcleo: escribe la moneda en ISO y el centro de costo que haya. Un mes sin
# centros sale igual, con la columna vacía.
EXIGE = frozenset()
# Se configura lo que el núcleo lee al armar el asiento, y nada propio: escribe las líneas tal cual.
CONFIGURACION = CONFIGURACION_DEL_ASIENTO

SEPARADOR = ";"

# Una columna por campo de la línea de diario. Los bloques anidados (documento, referencia,
# detracción) se aplanan con prefijo, porque un CSV no sabe anidar.
COLUMNAS: list[tuple[str, str]] = [
    ("sub_diario", "sub_diario"),
    ("correlativo", "correlativo"),
    ("fecha", "fecha"),
    ("cuenta", "cuenta"),
    ("debe_haber", "debe_haber"),
    ("importe", "importe"),
    ("moneda", "moneda"),
    ("tipo_cambio", "tipo_cambio"),
    ("glosa", "glosa"),
    ("contraparte_doc", "contraparte_doc"),
    ("centro_costo", "centro_costo"),
    ("anexo_auxiliar", "anexo_auxiliar"),
    ("documento.tipo", "doc_tipo"),
    ("documento.serie_numero", "doc_serie_numero"),
    ("documento.fecha_emision", "doc_fecha_emision"),
    ("documento.fecha_vencimiento", "doc_fecha_vencimiento"),
    ("referencia.tipo", "ref_tipo"),
    ("referencia.serie_numero", "ref_serie_numero"),
    ("referencia.fecha", "ref_fecha"),
    ("detraccion.codigo_interno", "detraccion_codigo"),
    ("detraccion.tasa", "detraccion_tasa"),
    ("detraccion.base", "detraccion_base"),
    ("tasa_igv", "tasa_igv"),
]


def nombre(libro: Libro, opciones: Opciones = OPCIONES) -> str:
    return f"asiento_{libro.ruc}_{libro.periodo}_{libro.tipo}{opciones.extension}"


def _valor(linea: dict, ruta: str) -> Any:
    if "." not in ruta:
        return linea.get(ruta, "")
    padre, hijo = ruta.split(".", 1)
    return (linea.get(padre) or {}).get(hijo, "")


def desde_lineas(libro: Libro, lineas: list[LineaDiario], config: dict, opciones: Opciones = OPCIONES,
                 separador: str = SEPARADOR, bom: bool = True) -> tuple[bytes, dict]:
    """Líneas neutrales (ya numeradas y cuadradas por el núcleo) → CSV.

    Es el driver de asientos más sencillo que puede escribirse con la forma `desde_lineas` del
    contrato, y por eso sirve de plantilla: traduce vocabulario y nada más."""
    filas = [ln.a_dict() for ln in lineas]
    buf = io.StringIO(newline="")
    escritor = _csv.writer(buf, delimiter=separador, lineterminator="\r\n",
                           quoting=_csv.QUOTE_MINIMAL)
    escritor.writerow([cab for _, cab in COLUMNAS])
    for fila in filas:
        escritor.writerow([_valor(fila, ruta) for ruta, _ in COLUMNAS])

    texto = buf.getvalue()
    return ("﻿" + texto if bom else texto).encode("utf-8"), {"filas": len(filas)}
