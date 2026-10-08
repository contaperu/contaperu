"""El contribuyente: en qué régimen tributa y cuándo le vence el mes.

Lo más joven de este paquete (6.1.0) y lo único que **no describe un comprobante ni un formato**, sino a quien
lleva el libro. Por eso es catálogo y no campo del estándar: «¿qué libros estoy obligado a llevar?» se
pregunta sin un documento delante, al dar de alta una empresa.
"""
from __future__ import annotations

import copy
from datetime import date

from .. import _datos
from ..errores import ErrorContaperu


RUTA_REGIMENES = "datos/sunat/regimenes.json"
RUTA_VENCIMIENTOS = "datos/sunat/vencimientos.json"

ESTADOS_DE_REGIMEN = ("vigente", "pendiente_de_fuente")
# Los bloques de reglas de un régimen. Cada uno cita SU artículo —la tasa el 120, los libros el 124, los topes el
# 118—, así que la cita va por bloque y no una sola para toda la tabla, al revés que en `detracciones.json`.
REGLAS_DE_REGIMEN = ("pago_a_cuenta", "libros_obligatorios", "topes")
# Los dos cronogramas de un mes, cada uno de su anexo de la RS 000281-2022.
CRONOGRAMAS = ("declaracion", "atraso_registros")


class CatalogoInvalido(ErrorContaperu, ValueError):
    """Un catálogo de datos existe pero está mal formado. Mejor no arrancar que contestar a medias."""


class SinCronograma(ErrorContaperu, LookupError):
    """Se pidió una fecha que la tabla no trae. Dice qué años conoce: no se calcula ninguno."""


def validar_regimenes(tabla: dict) -> dict:
    """Comprueba que una tabla de regímenes cite lo que afirma, y la devuelve. **Ninguna regla entra sin fuente**:
    si una vigente no cita, o si un régimen declarado pendiente trae una regla de todos modos, no pasa. Ese segundo
    caso es el que de verdad protege, porque es por donde entraría mañana una tasa de memoria.

    Recibe la tabla ya leída y no la ruta, como `pcge.adaptar.cargar_equivalencias`: así la comprueba la batería
    mutándola, y un ERP puede validar la suya antes de pasársela al motor."""
    for nombre, regimen in (tabla.get("regimenes") or {}).items():
        estado = regimen.get("estado")
        if estado not in ESTADOS_DE_REGIMEN:
            raise CatalogoInvalido(
                f"El régimen {nombre!r} tiene un estado desconocido: {estado!r}. Los que hay: "
                f"{', '.join(ESTADOS_DE_REGIMEN)}.")
        reglas = [r for r in REGLAS_DE_REGIMEN if r in regimen]
        if estado == "pendiente_de_fuente":
            if reglas:
                raise CatalogoInvalido(
                    f"El régimen {nombre!r} se declara pendiente de fuente y trae reglas de todos modos "
                    f"({', '.join(reglas)}). Un valor sin su norma leída es la regla sin fuente entrando por la "
                    "puerta de atrás: o se quita, o entra con su cita y el estado pasa a vigente.")
            if not str(regimen.get("por_que") or "").strip():
                raise CatalogoInvalido(
                    f"El régimen {nombre!r} está pendiente de fuente y no dice `por_que`: qué norma hay que leer "
                    "para que entre.")
            continue
        for regla in REGLAS_DE_REGIMEN:
            if not str((regimen.get(regla) or {}).get("cita") or "").strip():
                raise CatalogoInvalido(
                    f"El régimen {nombre!r} está vigente y su {regla!r} no cita la norma que lo respalda. En este "
                    "proyecto ninguna regla contable entra sin fuente.")
    return tabla


def _tabla_de_regimenes() -> dict:
    """La tabla que viaja con el paquete, validada. Si falta el fichero o su fuente, el motor no arranca."""
    tabla = _datos.leer_json(RUTA_REGIMENES)
    if not tabla or not str(tabla.get("fuente") or "").strip():
        raise FileNotFoundError(f"No encuentro la tabla de regímenes tributarios con su fuente ({RUTA_REGIMENES})")
    return validar_regimenes(tabla)


def _tabla_de_vencimientos() -> dict:
    """Los dos cronogramas, cada uno con la fuente de su anexo."""
    tabla = _datos.leer_json(RUTA_VENCIMIENTOS)
    if not tabla or not all(str((tabla.get("fuentes") or {}).get(c) or "").strip() for c in CRONOGRAMAS):
        raise FileNotFoundError(
            f"No encuentro los cronogramas de vencimiento con la fuente de sus dos anexos ({RUTA_VENCIMIENTOS})")
    return tabla


_REGIMENES = _tabla_de_regimenes()
_VENCIMIENTOS = _tabla_de_vencimientos()


def regimenes_tributarios() -> dict:
    """Los regímenes tributarios del Perú y lo que cada uno obliga, con su cita: la tasa y la base de su pago a
    cuenta, los libros que obliga a llevar —por su código del PLE— y los topes que sacan de él.

    Tabla parcial a propósito: hoy solo el Régimen Especial, que es el que tiene su norma leída. Un régimen sin su
    texto delante se declara `pendiente_de_fuente` y dice qué hay que leer, en vez de traer una tasa de memoria. El
    motor **no calcula** la cuota: publica la tasa para que la calcule quien integra. Cada llamada devuelve una
    copia."""
    return copy.deepcopy(_REGIMENES)


def cronogramas_de_vencimiento() -> dict:
    """Cuándo vence un mes, por año y por periodo: la fecha de la declaración y el pago (anexo I) y la fecha máxima
    de atraso del registro electrónico de ventas y de compras (anexo II), por cada uno de los diez dígitos de RUC y
    para los buenos contribuyentes y las UESP.

    Las fechas son texto `AAAA-MM-DD`. Solo los años que SUNAT publicó resueltos: esta es la única tabla del motor
    que envejece, y por eso no se calcula el año que falta. Cada llamada devuelve una copia."""
    return copy.deepcopy(_VENCIMIENTOS)


def anios_con_cronograma() -> list[str]:
    """Los años cuyos cronogramas trae el motor."""
    return sorted(_VENCIMIENTOS["anios"])


def _vence(cronograma: str, periodo: str, ultimo_digito_ruc: str | int, buen_contribuyente: bool) -> date:
    mes = (_VENCIMIENTOS["anios"].get(str(periodo)[:4]) or {}).get(cronograma, {}).get(str(periodo))
    if not mes:
        raise SinCronograma(
            f"No tengo el cronograma de {cronograma!r} del periodo {periodo!r}. Los años que conozco: "
            f"{', '.join(anios_con_cronograma())}. La resolución fija el cronograma en días hábiles y SUNAT publica "
            "la tabla resuelta de cada año: el año que falta se añade copiándola, no calculándolo.")
    columna = "buenos_contribuyentes" if buen_contribuyente else str(ultimo_digito_ruc)[-1:]
    if columna not in mes:
        raise SinCronograma(f"{ultimo_digito_ruc!r} no es el último dígito de un RUC: se espera uno de 0 a 9.")
    return date.fromisoformat(mes[columna])


def vence_la_declaracion(periodo: str, ultimo_digito_ruc: str | int, *, buen_contribuyente: bool = False) -> date:
    """La fecha en que vence la declaración y el pago del periodo (`AAAAMM`), por el último dígito del RUC.

    Anexo I de la RS 000281-2022/SUNAT. **No mira el reloj**: si queda tiempo o no lo dice quien llama, comparando
    con la fecha de hoy, que es suya."""
    return _vence("declaracion", periodo, ultimo_digito_ruc, buen_contribuyente)


def vence_el_registro(periodo: str, ultimo_digito_ruc: str | int, *, buen_contribuyente: bool = False) -> date:
    """La fecha máxima de atraso del Registro de Ventas e Ingresos y del Registro de Compras electrónicos del
    periodo (`AAAAMM`), por el último dígito del RUC.

    Anexo II de la misma resolución, y **vence antes que la declaración**: el registro se cierra para poder
    declarar. El periodo es «el mes al que corresponde el registro de operaciones según las normas de la
    materia»."""
    return _vence("atraso_registros", periodo, ultimo_digito_ruc, buen_contribuyente)
