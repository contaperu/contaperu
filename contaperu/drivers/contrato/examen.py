"""El examen que pasa cualquier driver registrado: lo que declara, contrastado con la taxonomía.

Devuelve **una lista con todo lo que está mal**, no la primera pega: quien escribe un driver quiere la
cuenta entera de una vez. `tests/test_contrato_drivers.py` lo corre contra los de serie y contra los de
terceros, y un driver que no lo pasa se ignora con aviso en vez de escribir un archivo a medias.
"""
from __future__ import annotations

from typing import Any

from ... import configuracion as _declaracion
from ...asiento.configuracion import CONFIGURACION_DEL_ASIENTO, MONEDAS_CODIGO
from ...configuracion import Campo, Columna
from ...modelo import TIPOS_LIBRO
from ..kit import Opciones, OpcionesArchivo
from ..kit import columnas as _columnas_de_linea
from .accesores import (arma_asientos, canal, configuracion, forma, lleva_cuentas, vocabulario)
from .taxonomia import (DATOS_CON_COLUMNAS, _CUENTAS_DEL_PLAN, _LINEAS_CON_ANEXO,
                        CANAL_OBLIGATORIO_DESDE, CANALES, CANALES_RESERVADOS, CLAVES_LEGACY, EXIGE_POSIBLES_ASIENTO, EXIGE_POSIBLES_REGISTRO, FORMAS, VOCABULARIOS, _CLAVES_QUE_NO_SON_DE_UNA_SECCION, _CUENTAS_GENERALES)

def incumplimientos(modulo: Any) -> list[str]:
    """Lo que le falta a un driver para cumplir el contrato. Lista vacía = cumple."""
    problemas: list[str] = []
    nombre = getattr(modulo, "NOMBRE", None)
    if not isinstance(nombre, str) or not nombre.strip():
        problemas.append("falta NOMBRE (texto)")
    formatos = getattr(modulo, "FORMATOS", None)
    if not isinstance(formatos, dict) or not formatos:
        problemas.append("falta FORMATOS ({'venta'|'compra': identificador})")
    elif set(formatos) - set(TIPOS_LIBRO):
        problemas.append(f"FORMATOS solo admite las claves {TIPOS_LIBRO}")
    opciones = getattr(modulo, "OPCIONES", None)
    f = forma(modulo)
    if f == "linea" and not isinstance(opciones, Opciones):
        problemas.append("falta OPCIONES (una kit.Opciones)")
    elif f != "linea" and not isinstance(opciones, (Opciones, OpcionesArchivo)):
        problemas.append("falta OPCIONES (una kit.Opciones o una kit.OpcionesArchivo)")
    if not callable(getattr(modulo, "nombre", None)):
        problemas.append("falta nombre(libro, opciones)")
    if not f:
        problemas.append("no implementa ninguna forma: " + ", ".join(FORMAS))
    elif f != "linea" and not isinstance(getattr(modulo, "CONTENT_TYPE", None), str):
        problemas.append("un driver de archivo declara su CONTENT_TYPE")
    excluye = getattr(modulo, "EXCLUYE_TIPOS", None)
    if excluye is not None and not all(isinstance(t, str) for t in excluye):
        problemas.append("EXCLUYE_TIPOS son códigos SUNAT en texto")
    declarado = getattr(modulo, "EXIGE", None)
    if declarado is not None:
        posibles = EXIGE_POSIBLES_REGISTRO if f == "desde_comprobantes" else EXIGE_POSIBLES_ASIENTO
        if f == "linea":
            problemas.append("EXIGE no lo declara un registro tributario (forma `linea`): no lleva cuentas")
        elif isinstance(declarado, str) or not all(isinstance(x, str) for x in declarado):
            problemas.append("EXIGE es un conjunto de textos")
        elif set(declarado) - posibles:
            problemas.append(f"EXIGE solo admite {sorted(posibles)}; sobra {sorted(set(declarado) - posibles)}")
    if hasattr(modulo, "no_caben") and not callable(getattr(modulo, "no_caben")):
        problemas.append("no_caben es una función: no_caben(libro, comprobantes, config)")
    declaradas = getattr(modulo, "COLUMNAS_DE_LINEA", None)
    if declaradas is not None:
        if f != "desde_lineas":
            problemas.append("COLUMNAS_DE_LINEA es de un driver `desde_lineas`: sus columnas leen la línea del comprobante")
        problemas += _columnas_de_linea.problemas(declaradas)
    return (problemas + _incumplimientos_del_canal(modulo, f) + _incumplimientos_del_vocabulario(modulo, f)
            + _incumplimientos_de_la_configuracion(modulo))


def _incumplimientos_del_vocabulario(modulo: Any, f: str) -> list[str]:
    declarado = getattr(modulo, "VOCABULARIO", None)
    if declarado is None:
        return []
    if declarado not in VOCABULARIOS:
        return [f"VOCABULARIO {declarado!r} no existe; los que hay: {', '.join(VOCABULARIOS)}"]
    if declarado != "neutral":
        return []
    problemas = []
    if f != "desde_lineas":
        problemas.append("un driver neutral recibe las líneas del estándar: su forma es `desde_lineas`")
    if canal(modulo) != "intercambio":
        problemas.append("un driver neutral entrega a un ERP: su canal es `intercambio`")
    legacy = sorted({c.clave for c in configuracion(modulo) if isinstance(c, Campo)} & CLAVES_LEGACY)
    if legacy:
        problemas.append("un driver neutral no declara vocabulario legacy en CONFIGURACION: " + ", ".join(legacy))
    if "moneda" in (getattr(modulo, "EXIGE", None) or ()):
        problemas.append("un driver neutral no exige el código de la moneda: la moneda va en ISO")
    return problemas


def _incumplimientos_del_canal(modulo: Any, f: str) -> list[str]:
    declarado = getattr(modulo, "CANAL", None)
    if declarado is None:
        return [f"un driver declara CANAL ({', '.join(CANALES)}): es obligatorio desde la "
                f"{CANAL_OBLIGATORIO_DESDE} y de él sale el grupo del destino"]
    if declarado in CANALES_RESERVADOS:
        return [f"CANAL {declarado!r} está reservado y no se admite en la 1.0: {CANALES_RESERVADOS[declarado]}"]
    if declarado not in CANALES:
        return [f"CANAL {declarado!r} no existe; los canales son {', '.join(CANALES)}"]
    if not f:
        return []
    if declarado == "legacy":
        problemas = []
        if not lleva_cuentas(modulo):
            problemas.append("un driver legacy lleva cuentas: su forma es desde_lineas o desde_comprobantes")
        if not hasattr(modulo, "EXIGE"):
            problemas.append("un driver legacy declara EXIGE: lo que su sistema no puede importar sin (vacío si nada)")
        return problemas
    # Un tributario escribe un registro de texto para SUNAT, y hasta la 4.2 eso quería decir una fila por
    # comprobante, que es la forma `linea` y la del SIRE. El Libro Diario del PLE rompió el supuesto sin romper la
    # regla: también es un registro de texto para SUNAT, pero **su fila es una línea del asiento**, no un
    # comprobante —una compra con detracción son cinco filas—, así que su forma es `desde_lineas`. Lo que la regla
    # protege sigue en pie: un tributario no escribe un Excel ni un JSON.
    if declarado == "tributario" and f not in ("linea", "desde_lineas"):
        return ["un driver tributario escribe un registro de texto para SUNAT: su forma es `linea` "
                "(una fila por comprobante) o `desde_lineas` (una fila por línea del asiento)"]
    if declarado == "intercambio" and f != "desde_lineas":
        return ["un driver de intercambio proyecta la línea del comprobante: su forma es `desde_lineas`"]
    return []


def _incumplimientos_de_la_configuracion(modulo: Any) -> list[str]:
    declarada = getattr(modulo, "CONFIGURACION", None)
    columnas = getattr(modulo, "COLUMNAS_ELEGIBLES", None)
    cuentas = getattr(modulo, "CUENTAS_POR_DEFECTO", None)
    if (declarada is not None or columnas is not None or cuentas is not None) and not lleva_cuentas(modulo):
        return ["CONFIGURACION, COLUMNAS_ELEGIBLES y CUENTAS_POR_DEFECTO son de un driver que lleva cuentas: un "
                "registro tributario no se configura"]
    problemas: list[str] = []
    if cuentas is not None:
        problemas += _incumplimientos_de_las_cuentas(cuentas)
    if declarada is not None:
        if isinstance(declarada, (str, bytes, dict)) or not all(isinstance(c, Campo) for c in declarada):
            problemas.append("CONFIGURACION es una tupla de configuracion.Campo")
        else:
            claves = [c.clave for c in declarada]
            repetidas = sorted({k for k in claves if claves.count(k) > 1})
            if repetidas:
                problemas.append(f"CONFIGURACION repite claves: {', '.join(repetidas)}")
            reservadas = sorted(set(claves) & _CLAVES_QUE_NO_SON_DE_UNA_SECCION)
            if reservadas:
                problemas.append("CONFIGURACION no declara claves de lo general ni reservadas: "
                                 + ", ".join(reservadas))
            errores = _declaracion.validar(_declaracion.por_defecto(tuple(declarada)), tuple(declarada))
            if errores:
                problemas.append("los valores por defecto de CONFIGURACION no cumplen lo declarado: "
                                 + "; ".join(errores))
    if arma_asientos(modulo) and vocabulario(modulo) != "neutral":
        propias = {c.clave for c in configuracion(modulo) if isinstance(c, Campo)}
        faltan = [c.clave for c in CONFIGURACION_DEL_ASIENTO if c.clave not in propias]
        if faltan:
            problemas.append("un driver de asientos incluye en CONFIGURACION las claves del asiento "
                             "(asiento.CONFIGURACION_DEL_ASIENTO), que el núcleo lee al armar sus líneas; faltan: "
                             + ", ".join(faltan))
    exigido = getattr(modulo, "EXIGE", None)
    if (arma_asientos(modulo) and isinstance(exigido, (set, frozenset, list, tuple)) and "moneda" in exigido
            and MONEDAS_CODIGO not in {c.clave for c in configuracion(modulo) if isinstance(c, Campo)}):
        problemas.append("un driver que exige `moneda` declara `monedas_codigo` en CONFIGURACION: de ahí lee el núcleo "
                         "el código de cada moneda")
    if columnas is not None:
        problemas += _incumplimientos_de_las_columnas(modulo, columnas)
    return problemas


def _incumplimientos_de_las_cuentas(cuentas: Any) -> list[str]:
    """Lo que `CUENTAS_POR_DEFECTO` no cumple. Se valida contra el bloque `cuentas` de lo general —las mismas claves y
    el mismo formato—, porque va a fundirse encima de él: una clave que no existe ahí no la leería nadie, y una cuenta
    con un formato que la declaración rechaza entraría por la puerta de atrás en la configuración de cada empresa."""
    if not isinstance(cuentas, dict):
        return ["CUENTAS_POR_DEFECTO es un objeto con las claves de `cuentas`, como se guardan"]
    if not cuentas:
        return ["CUENTAS_POR_DEFECTO vacío es no declararlo: un sistema que numera como el PCGE no lo pone"]
    return _declaracion.validar(cuentas, _CUENTAS_GENERALES + _CUENTAS_DEL_PLAN, donde="CUENTAS_POR_DEFECTO")


def _incumplimientos_de_las_columnas(modulo: Any, columnas: Any) -> list[str]:
    if not isinstance(columnas, dict):
        return ["COLUMNAS_ELEGIBLES es un dict {dato: (configuracion.Columna, …)}"]
    problemas: list[str] = []
    libros = sorted(getattr(modulo, "FORMATOS", None) or {})
    de_asientos = arma_asientos(modulo)
    for dato, declaradas in columnas.items():
        if dato not in DATOS_CON_COLUMNAS:
            problemas.append(f"COLUMNAS_ELEGIBLES: {dato!r} no se elige por columnas; los que sí: "
                             f"{', '.join(sorted(DATOS_CON_COLUMNAS))}")
            continue
        if (isinstance(declaradas, (str, bytes)) or not declaradas
                or not all(isinstance(c, Columna) for c in declaradas)):
            problemas.append(f"COLUMNAS_ELEGIBLES[{dato!r}] es una tupla de configuracion.Columna")
            continue
        nombres = [c.columna for c in declaradas]
        if len(set(nombres)) != len(nombres):
            problemas.append(f"COLUMNAS_ELEGIBLES[{dato!r}] repite columnas")
        if sum(1 for c in declaradas if c.fija) != 1:
            problemas.append(f"COLUMNAS_ELEGIBLES[{dato!r}] lleva una sola columna fija: la principal")
        for c in declaradas:
            if sorted(c.letra) != libros:
                problemas.append(f"COLUMNAS_ELEGIBLES[{dato!r}]: la letra de {c.columna!r} va por cada libro de "
                                 f"FORMATOS ({', '.join(libros)})")
            if de_asientos:
                llena = ((c.campo == "centro_costo" and c.rol == "principal" and c.fija)
                         or (c.campo == "anexo_auxiliar" and c.rol in _LINEAS_CON_ANEXO and not c.fija))
                if not llena:
                    problemas.append(f"COLUMNAS_ELEGIBLES[{dato!r}]: en un driver de asientos, {c.columna!r} dice qué "
                                     "línea del comprobante la llena: la fija, con el centro_costo de la principal; las demás, "
                                     "con el anexo_auxiliar de la principal o del tercero")
            elif c.rol or c.campo:
                problemas.append(f"COLUMNAS_ELEGIBLES[{dato!r}]: {c.columna!r} no lleva rol ni campo, que son de las "
                                 "líneas del asiento de un driver de asientos")
    return problemas
