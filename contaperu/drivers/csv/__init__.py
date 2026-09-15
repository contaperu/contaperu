"""Driver CSV genérico: el asiento en columnas, para quien no tiene un driver propio.

Es la salida de último recurso y, a la vez, la más honesta: escribe las líneas de diario del
estándar `open-accounting` tal cual, una por fila, sin traducir nada al vocabulario de ningún ERP.
Sirve para revisar un asiento en Excel, para cargarlo en un sistema que acepte texto plano y
para escribir un driver nuevo teniendo delante lo que hay que traducir.

Desde la 1.1 está **declarado como tabla** (`kit.columnas`): cada columna dice qué campo de la línea la llena y de
dónde sale, y el kit escribe el archivo. Es el ejemplo de un driver declarativo, y sale byte a byte igual que antes.

Dos decisiones pensadas para el Perú, ambas cambiables al llamar:

- **Separador `;`** — el Excel en español interpreta la coma como decimal, así que un CSV con
  comas se abre en una sola columna. Pasa `separador=","` si el destino es un programa y no una
  persona.
- **BOM UTF-8** — sin él, Excel abre el archivo en la codificación del sistema y las tildes y
  las eñes salen rotas. Pasa `bom=False` si molesta.
"""
from __future__ import annotations

from ...asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from ...asiento.lineas import LineaDiario
from ..kit import Opciones
from ..kit.columnas import ColumnaDeLinea, escribir_csv
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

# La fuente de cada columna es el propio estándar: el CSV escribe la línea neutral, un campo por columna.
_FUENTE = "estandar/LEEME.md, «Las líneas del asiento»: la línea neutral de open-accounting, un campo por columna"

# Una columna por campo de la línea de diario. Los bloques anidados (documento, referencia,
# detracción) se aplanan con prefijo, porque un CSV no sabe anidar.
COLUMNAS_DE_LINEA: tuple[ColumnaDeLinea, ...] = tuple(
    ColumnaDeLinea(cabecera, ruta, _FUENTE, clase) for ruta, cabecera, clase in (
        ("sub_diario", "sub_diario", "texto"),
        ("correlativo", "correlativo", "texto"),
        ("fecha", "fecha", "fecha"),
        ("cuenta", "cuenta", "texto"),
        ("debe_haber", "debe_haber", "texto"),
        ("importe", "importe", "importe"),
        ("moneda", "moneda", "texto"),
        ("tipo_cambio", "tipo_cambio", "numero"),
        ("glosa", "glosa", "texto"),
        ("contraparte_doc", "contraparte_doc", "texto"),
        ("centro_costo", "centro_costo", "texto"),
        ("anexo_auxiliar", "anexo_auxiliar", "texto"),
        ("documento.tipo", "doc_tipo", "texto"),
        ("documento.serie_numero", "doc_serie_numero", "texto"),
        ("documento.fecha_emision", "doc_fecha_emision", "fecha"),
        ("documento.fecha_vencimiento", "doc_fecha_vencimiento", "fecha"),
        ("referencia.tipo", "ref_tipo", "texto"),
        ("referencia.serie_numero", "ref_serie_numero", "texto"),
        ("referencia.fecha", "ref_fecha", "fecha"),
        ("detraccion.codigo_interno", "detraccion_codigo", "texto"),
        ("detraccion.tasa", "detraccion_tasa", "numero"),
        ("detraccion.base", "detraccion_base", "importe"),
        ("tasa_igv", "tasa_igv", "numero"),
        # Lo que un driver necesita para traducir sin adivinar (B5, 1.0): el papel de la línea y los códigos SUNAT del
        # documento y de su referencia. Van al final para no mover las columnas de siempre.
        ("rol", "rol", "texto"),
        ("documento.tipo_cp", "doc_tipo_cp", "texto"),
        ("referencia.tipo_cp", "ref_tipo_cp", "texto"),
    ))
# La forma de la 0.10, pares (ruta, cabecera), para quien la lea: se conserva durante la 1.x.
COLUMNAS: list[tuple[str, str]] = [(columna.ruta, columna.cabecera) for columna in COLUMNAS_DE_LINEA]


def nombre(libro: Libro, opciones: Opciones = OPCIONES) -> str:
    return f"asiento_{libro.ruc}_{libro.periodo}_{libro.tipo}{opciones.extension}"


def desde_lineas(libro: Libro, lineas: list[LineaDiario], config: dict, opciones: Opciones = OPCIONES,
                 separador: str = SEPARADOR, bom: bool = True) -> tuple[bytes, dict]:
    """Líneas neutrales (ya numeradas y cuadradas por el núcleo) → CSV.

    Es el driver de asientos más sencillo que puede escribirse con la forma `desde_lineas` del
    contrato, y por eso sirve de plantilla: traduce vocabulario y nada más."""
    lineas = list(lineas)
    return escribir_csv(lineas, COLUMNAS_DE_LINEA, separador, bom), {"filas": len(lineas)}
