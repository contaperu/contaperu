"""El TXT del **formato 5.3 del PLE: «LIBRO DIARIO - DETALLE DEL PLAN CONTABLE UTILIZADO»**: 8 campos por fila,
separados por `|` y con palote final, **una fila por cada cuenta contable que el contribuyente usó en el periodo**.

Es el hermano del 5.1 y el otro miembro de su par: el grupo 05 del PLE son dos pares —el Libro Diario con su plan de
cuentas, y el simplificado con el suyo—. Y es **donde vive la denominación de la cuenta**, que por eso no está en
cada línea del 5.1: se declara una vez por cuenta y no doce mil veces.

**Lo que no se puede deducir y por eso se exige.** El campo 3 pide cómo llama la EMPRESA a su cuenta —«CAJA CHICA
M.N.»—, y el motor solo conoce el nombre de la divisionaria del PCGE —«Caja»—. No sirve de reemplazo: el catálogo del
PCGE llega hasta cinco dígitos y la empresa desagrega hasta donde quiera. Escribirlo sería declararle a SUNAT una
denominación que el contribuyente no usa, que es la misma clase de invento que una sigla puesta a dedo. Así que este
driver declara `EXIGE = {"denominacion"}` y una cuenta sin nombre **para la exportación** con su lista.

**Su periodicidad la manda SUNAT**, y el motor no la hace cumplir porque no es suya: «obligatorio en el periodo de
enero cada año o cuando se genera el libro electrónico por primera vez; en los demás meses se puede optar por generar
un libro vacío salvo que el Plan Contable sufra modificaciones». Quien integre decide cuándo lo presenta.

El formato, columna a columna, en `datos/sunat/ple_campos.json` (libro `plan_contable`), leído del libro oficial de
estructuras del PLE. Aquí está solo el layout.
"""
from __future__ import annotations

from ...asiento import ComprobanteDelAsiento, CONFIGURACION_DEL_ASIENTO, LineaDiario
from ...modelo import Libro
from ..kit import Opciones, armar_archivo, armar_linea, sanear
from ..kit import nombre_de_libro_electronico as _nombre_de_libro_electronico
from ..ple.comun import BANDERAS, DIA_DEL_NOMBRE, ESTADO_DEL_PERIODO, OPCIONES, OPORTUNIDAD

NOMBRE = "ple_plan"
# Un registro que se presenta a SUNAT, como el 5.1 y como el SIRE.
CANAL = "tributario"
# El mismo formato para los dos libros que el motor genera: el plan de cuentas que se usó en el mes es el mismo
# fichero venga de compras o de ventas.
FORMATOS = {"compra": "ple_5_3", "venta": "ple_5_3"}
# El `charset` dice la verdad de los bytes, y viaja hasta la api, el HTTP y el MCP: va con la `codificacion`
# de `comun.OPCIONES`, que es cp1252 desde la 5.2.
CONTENT_TYPE = "text/plain; charset=windows-1252"
# Lo único que el núcleo tiene que darle, y no se puede deducir de ninguna parte: ver el docstring.
EXIGE = frozenset({"denominacion"})
# Lo mismo que el 5.1: los sub-diarios y la tabla de tipos que el núcleo lee al armar las líneas. Este driver no los
# escribe —no tiene CUO— pero la forma `desde_lineas` arma asientos y el contrato los pide igual.
CONFIGURACION = CONFIGURACION_DEL_ASIENTO

LIBRO_PLAN_CONTABLE = "050300"
CAMPOS = 8

# El día que va DENTRO del campo 1, que es `AAAAMMDD` — a diferencia del `AAAAMM00` del 5.1. El archivo contrastado
# escribe el primero del mes. No confundirlo con el día del NOMBRE del fichero, que va en `00` (`comun.py`).
DIA_DEL_PERIODO = "01"
# El plan que declara el contribuyente, validado contra la tabla 17 de SUNAT, que no está en el motor. El archivo
# contrastado declara `01` en sus 725 filas.
PLAN_DE_CUENTAS = "01"
# SUNAT pide la descripción del plan **solo si el código es `99`**, un plan que su tabla no lista. Con un código del
# catálogo va el guion, como en el archivo contrastado.
SIN_DESCRIPCION_DEL_PLAN = "-"


def nombre(libro: Libro, opciones: Opciones = OPCIONES) -> str:
    """El nombre que SUNAT impone, con el código de este libro: `LE` + RUC + periodo + día + `050300` + …"""
    return _nombre_de_libro_electronico(libro, LIBRO_PLAN_CONTABLE, OPORTUNIDAD, BANDERAS, opciones,
                                        dia=DIA_DEL_NOMBRE)


def fila(cuenta: str, denominacion: str, libro: Libro, opciones: Opciones) -> str:
    """Una cuenta → su fila del 5.3, con los 8 campos en el orden del formato."""
    campos = [
        f"{libro.periodo}{DIA_DEL_PERIODO}",       # 1 periodo, AAAAMMDD
        cuenta,                                     # 2 código de la cuenta contable
        sanear(denominacion, opciones),             # 3 descripción de la cuenta contable
        PLAN_DE_CUENTAS,                            # 4 código del plan de cuentas utilizado
        SIN_DESCRIPCION_DEL_PLAN,                   # 5 descripción del plan: solo si el 4 es `99`
        "",                                         # 6 cuenta contable corporativa: el motor no la tiene
        "",                                         # 7 su descripción: obligatoria solo si la 6 trae dato
        ESTADO_DEL_PERIODO,                         # 8 estado
    ]
    if len(campos) != CAMPOS:
        raise RuntimeError(f"el detalle del plan contable lleva {CAMPOS} campos y se armaron {len(campos)}")
    return armar_linea(campos, opciones)


def desde_lineas(libro: Libro, lineas: list[LineaDiario], config: dict, opciones: Opciones = OPCIONES, *,
                 indice: tuple[ComprobanteDelAsiento, ...] = ()) -> tuple[bytes, dict]:
    """Las líneas del asiento → el plan de cuentas que ese asiento usó, una fila por cuenta distinta y ordenadas.

    **No necesita el índice**, a diferencia del 5.1: no escribe nada de la cabecera de ningún comprobante. Lo que sí
    comprueba es que el driver lleve el tipo de libro, que es la otra mitad de `forma.exigir_indice`.

    Las denominaciones ya están todas: si faltara alguna, el núcleo habría parado antes con `SinDenominacion`, porque
    este driver lo declara en su `EXIGE`. Aquí se leen y punto.
    """
    if FORMATOS.get(libro.tipo) is None:
        raise ValueError(f"Tipo de libro no soportado: {libro.tipo!r}; este driver lleva {sorted(FORMATOS)}")
    denominaciones = config.get("denominacion_cuentas") or {}
    cuentas = sorted({ln.cuenta for ln in lineas if ln.cuenta})
    filas = [fila(cuenta, str(denominaciones.get(cuenta) or ""), libro, opciones) for cuenta in cuentas]
    return armar_archivo(filas, opciones), {"cuentas": len(filas)}
