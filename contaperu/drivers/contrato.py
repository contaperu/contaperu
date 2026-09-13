"""El contrato de un driver de salida: lo que tiene que exponer para que el núcleo lo use.

El mismo documento sale de dos maneras —como registro o como asiento (`estandar/LEEME.md`, «Dos familias de
salida, un solo documento»)—, y hay cuatro formas de driver. Un driver implementa una:

**Familia registro** — una fila por comprobante, sin asiento:

- **`linea(c, libro, idx, opciones) -> str`** — un archivo de texto, una línea por comprobante. Es el TXT
  del SIRE: un registro tributario, que se escribe desde el comprobante y no lleva cuentas.
- **`desde_comprobantes(libro, comprobantes, config, opciones) -> (bytes, resumen)`** — el archivo de un sistema
  contable que importa su registro de compras o de ventas y arma el asiento él mismo (CONTASIS). Recibe los comprobantes y la configuración, con la imputación de cada documento dentro, y
  **no decide ninguna cuenta**: las lee de `asiento.partes_de` (la de la base, o sus partes si hay reparto) y
  de `asiento.cuenta_tercero` (la del total), que las resuelven igual que para el asiento de CONCAR. No numera:
  el correlativo es del asiento, y el asiento lo arma el destino. El núcleo exige la cuenta ANTES de llamarlo.

**Familia asiento** — las líneas de la partida doble:

- **`construir(libro, comprobantes, config, correlativos, opciones) -> (bytes, resumen)`** — un archivo
  entero armado a partir de los comprobantes. Es la forma del Excel de CONCAR, que nació antes que
  la línea neutral.
- **`desde_lineas(libro, lineas, config, opciones) -> (bytes, resumen)`** — un archivo de asientos armado
  a partir de las LÍNEAS NEUTRALES de `open-accounting` (`asiento.LineaDiario`), ya numeradas y cuadradas.
  **Es la forma para un driver de asientos nuevo** (SISCONT, STARSOFT…): el driver solo
  traduce vocabulario, y la contabilidad —cuentas, sentidos, detracción, numeración— la pone el núcleo
  una sola vez para todos. El núcleo exige el cuadre ANTES de llamarlo.

Todas exponen además `NOMBRE`, `FORMATOS` ({'venta'|'compra': identificador de la salida}),
`OPCIONES` (una `formato.Opciones`) y `nombre(libro, opciones) -> str`; las tres de archivo, su
`CONTENT_TYPE`. Opcional: `EXCLUYE_TIPOS`, los tipos SUNAT que ese destino no lleva; y, en un driver que
lleva cuentas, `EXIGE`: lo que ese sistema no puede importar sin y que el núcleo, si no se lo dicen, deja
pasar (`EXIGE_POSIBLES_ASIENTO`; en uno de registro, `EXIGE_POSIBLES_REGISTRO`). Lo que el núcleo exige se declare o
no (`EXIGE_NUCLEO_ASIENTO`, `EXIGE_NUCLEO_REGISTRO`) es aquello sin lo que no hay nada que escribir: la cuenta
contable, y en un asiento además la equivalencia del tipo, de la que sale el sub-diario. `exige(modulo)` devuelve
la unión, y es lo que `diagnosticar` lee para decidir si un mes está listo **para ese destino** — la idea
viene de Codat `options` y Merge `/meta` (ver `REFERENCIAS.md`): el destino declara qué exige antes de
que nadie escriba un byte.

Y opcional en cualquier forma, `no_caben(libro, comprobantes, config) -> {motivo: [comprobantes]}`: lo que su
formato no puede llevar aunque la contabilidad esté completa —una moneda que no tiene, un código más largo que su
columna—. `diagnosticar` lo lista antes de exportar y el núcleo se niega con `NoCabe` antes de escribir un byte
(hoy, en la forma `desde_comprobantes`): un código no se corta ni una moneda se inventa.

Y en un driver que lleva cuentas, lo que se configura en su sección (`CONFIGURACION`, una tupla de
`configuracion.Campo`) y en qué columnas de su archivo puede ir un dato (`COLUMNAS_ELEGIBLES`, de
`configuracion.Columna`). Un driver de asientos declara al menos las claves del asiento
(`asiento.CONFIGURACION_DEL_ASIENTO`), que el núcleo lee al armar sus líneas. De lo declarado salen los valores por
defecto de su sección, su validación y la descripción con la que una aplicación pinta su pantalla
(`seccion_por_defecto`, `describir`): cada aplicación construida con el motor configura cada sistema según lo que
necesita cada empresa, sin copiar nada.

Los `Protocol` de abajo son la documentación tipada; lo que el registro comprueba de verdad al cargar
un driver de terceros es `incumplimientos()`, y `tests/test_contrato_drivers.py` es el examen que pasa
cualquier driver registrado.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from .. import configuracion as _declaracion
from ..asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from ..asiento.faltas import NoExportable
from ..asiento.motor import CENTRO_EN_ANEXO
from ..configuracion import CONFIGURACION_GENERAL, Campo, Columna
from ..formato import Opciones
from ..modelo import TIPOS_LIBRO, Comprobante, Libro

if TYPE_CHECKING:
    from ..asiento.lineas import LineaDiario

# En orden de preferencia: si un driver expone dos, el núcleo usa la primera.
FORMAS = ("desde_lineas", "desde_comprobantes", "construir", "linea")
FAMILIA = {"linea": "registro", "desde_comprobantes": "registro", "construir": "asiento", "desde_lineas": "asiento"}

# Lo que un driver de asientos PUEDE exigir (el núcleo sabe generar sin ello): el centro de costo en
# las cuentas que lo llevan, y que la moneda tenga código en el destino. Lo que exige el núcleo a todos:
# la cuenta contable de cada línea y la equivalencia del tipo SUNAT (de ella sale el sub-diario).
EXIGE_POSIBLES_ASIENTO = frozenset({"centro_costo", "moneda"})
EXIGE_NUCLEO_ASIENTO = frozenset({"cuenta_contable", "tipo_cp"})
# Y a uno de registro que lleva cuentas (`desde_comprobantes`), el núcleo le exige la cuenta —la columna con la
# que el destino arma su asiento— y nada del sub-diario ni de su equivalencia, que son del asiento. Puede exigir
# el centro de costo, y `cuenta_unica`: que ningún documento reparta su base entre varias cuentas, porque el destino
# lleva una por fila y arma un asiento por fila (CONTASIS, John 12-sep-2026). La moneda no: su código
# (`monedas_codigo`) es el de la configuración del asiento; lo que un registro no puede escribir en su propio
# vocabulario lo dice su `no_caben`.
EXIGE_POSIBLES_REGISTRO = frozenset({"centro_costo", "cuenta_unica"})
EXIGE_NUCLEO_REGISTRO = frozenset({"cuenta_contable"})

# Los datos que un sistema contable elige en qué columnas de su archivo escribir (`COLUMNAS_ELEGIBLES`). Hoy, el centro
# de costo (John, 13-sep-2026): se guarda una vez y la sección de cada sistema elige dónde sale.
DATOS_CON_COLUMNAS = frozenset({"centro_costo"})
# Las líneas neutrales que pueden llevar el centro en su anexo auxiliar (`asiento.lineas_del_comprobante`).
_LINEAS_CON_ANEXO = frozenset({"principal", "tercero"})
# Lo que ninguna sección puede declarar: lo general y lo que el núcleo reserva.
_CLAVES_QUE_NO_SON_DE_UNA_SECCION = frozenset({c.clave for c in CONFIGURACION_GENERAL} | {"columnas", "imputaciones"})


class Driver(Protocol):
    NOMBRE: str
    FORMATOS: dict[str, str]
    OPCIONES: Opciones

    def nombre(self, libro: Libro, opciones: Opciones = ...) -> str: ...


class DriverRegistroTexto(Driver, Protocol):
    def linea(self, c: Comprobante, libro: Libro, idx: int, opciones: Opciones = ...) -> str: ...


class DriverRegistroArchivo(Driver, Protocol):
    CONTENT_TYPE: str
    EXIGE: frozenset[str]     # opcional; subconjunto de EXIGE_POSIBLES_REGISTRO

    def desde_comprobantes(self, libro: Libro, comprobantes: list[Comprobante], config: dict,
                           opciones: Opciones = ...) -> tuple[bytes, dict]: ...


class DriverAsientoComprobantes(Driver, Protocol):
    CONTENT_TYPE: str
    EXIGE: frozenset[str]     # opcional; subconjunto de EXIGE_POSIBLES_ASIENTO

    def construir(self, libro: Libro, comprobantes: list[Comprobante], config: dict,
                  correlativos: dict[str, int], opciones: Opciones = ...) -> tuple[bytes, dict]: ...


class DriverAsientoLineas(Driver, Protocol):
    CONTENT_TYPE: str
    EXIGE: frozenset[str]     # opcional; subconjunto de EXIGE_POSIBLES_ASIENTO

    def desde_lineas(self, libro: Libro, lineas: list[LineaDiario], config: dict,
                     opciones: Opciones = ...) -> tuple[bytes, dict]: ...


def forma(modulo: Any) -> str:
    """Cuál de las cuatro formas implementa el driver (la preferida si expone varias); '' si ninguna."""
    return next((f for f in FORMAS if callable(getattr(modulo, f, None))), "")


def familia(modulo: Any) -> str:
    """'registro' (una fila por comprobante: `linea`, `desde_comprobantes`) o 'asiento' (`construir`,
    `desde_lineas`); '' si no implementa ninguna forma."""
    return FAMILIA.get(forma(modulo), "")


def lleva_cuentas(modulo: Any) -> bool:
    """¿Necesita la configuración contable del contribuyente? Todo driver que lleva cuentas: los de asientos y el
    registro de un sistema contable (`desde_comprobantes`). El registro tributario (`linea`), no."""
    return forma(modulo) in ("desde_lineas", "construir", "desde_comprobantes")


def arma_asientos(modulo: Any) -> bool:
    """¿Arma asientos, y necesita por eso además los correlativos? Las dos formas de la familia asiento."""
    return familia(modulo) == "asiento"


def exige(modulo: Any) -> frozenset[str]:
    """Todo lo que ese destino exige para exportar: lo del núcleo para su forma más lo que el driver declara en
    `EXIGE`. Un registro tributario (forma `linea`) no exige nada de esto: no lleva cuentas."""
    declarado = frozenset(getattr(modulo, "EXIGE", None) or ())
    if arma_asientos(modulo):
        return EXIGE_NUCLEO_ASIENTO | declarado
    if forma(modulo) == "desde_comprobantes":
        return EXIGE_NUCLEO_REGISTRO | declarado
    return frozenset()


def configuracion(modulo: Any) -> tuple[Campo, ...]:
    """Lo que se configura en la sección del driver (su `CONFIGURACION`); vacío si no declara nada."""
    return tuple(getattr(modulo, "CONFIGURACION", None) or ())


def columnas_elegibles(modulo: Any) -> dict[str, tuple[Columna, ...]]:
    """En qué columnas de su archivo puede ir cada dato (su `COLUMNAS_ELEGIBLES`); vacío si no declara ninguna."""
    return {dato: tuple(declaradas) for dato, declaradas in (getattr(modulo, "COLUMNAS_ELEGIBLES", None) or {}).items()}


def seccion_por_defecto(modulo: Any) -> dict:
    """Los valores por defecto de la sección del driver, como se guardan, con sus `columnas` fijas y marcadas."""
    return _declaracion.por_defecto(configuracion(modulo), columnas_elegibles(modulo))


def describir(modulo: Any) -> dict:
    """La sección del driver en JSON, para pintar su pantalla: sus campos y sus columnas elegibles."""
    return {"sistema": modulo.NOMBRE, **_declaracion.describir(configuracion(modulo), columnas_elegibles(modulo))}


def centro_en_anexo(modulo: Any, config: dict) -> frozenset[str]:
    """Qué líneas neutrales llevan el centro en su anexo auxiliar para ESTE driver: las de las columnas que la
    configuración eligió para el centro (`columnas.centro_costo`) o, si no eligió, las marcadas de fábrica. Un driver
    que no declara columnas lleva lo del estándar (`asiento.CENTRO_EN_ANEXO`)."""
    declaradas = columnas_elegibles(modulo).get("centro_costo")
    if not declaradas:
        return CENTRO_EN_ANEXO
    elegidas = ((config or {}).get("columnas") or {}).get("centro_costo")
    if elegidas is None:
        elegidas = [c.columna for c in declaradas if c.fija or c.marcada]
    return frozenset(c.rol for c in declaradas if c.campo == "anexo_auxiliar" and c.columna in elegidas)


class NoCabe(NoExportable):
    """Comprobantes que el formato del destino no puede llevar, por motivo (lo dice el driver en `no_caben`). El
    núcleo se niega antes de escribir nada, igual que con un tipo sin sigla."""

    clave = "no_cabe"

    def __init__(self, motivos: dict[str, list[Comprobante]]):
        unicos = list({id(c): c for lista in motivos.values() for c in lista}.values())
        mensaje = f"{len(unicos)} comprobante(s) que el formato del destino no puede llevar: " + "; ".join(motivos)
        super().__init__(mensaje, unicos)
        self.motivos = motivos


def no_caben(modulo: Any, libro: Libro, comprobantes: list[Comprobante], config: dict) -> dict[str, list[Comprobante]]:
    """Lo que el driver dice que no cabe en su formato (su `no_caben`, opcional), sin los motivos vacíos."""
    declarado = getattr(modulo, "no_caben", None)
    if not callable(declarado):
        return {}
    return {motivo: list(lista) for motivo, lista in (declarado(libro, comprobantes, config) or {}).items() if lista}


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
    if not isinstance(getattr(modulo, "OPCIONES", None), Opciones):
        problemas.append("falta OPCIONES (una formato.Opciones)")
    if not callable(getattr(modulo, "nombre", None)):
        problemas.append("falta nombre(libro, opciones)")
    f = forma(modulo)
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
    return problemas + _incumplimientos_de_la_configuracion(modulo)


def _incumplimientos_de_la_configuracion(modulo: Any) -> list[str]:
    declarada = getattr(modulo, "CONFIGURACION", None)
    columnas = getattr(modulo, "COLUMNAS_ELEGIBLES", None)
    if (declarada is not None or columnas is not None) and not lleva_cuentas(modulo):
        return ["CONFIGURACION y COLUMNAS_ELEGIBLES son de un driver que lleva cuentas: un registro tributario no se "
                "configura"]
    problemas: list[str] = []
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
    if arma_asientos(modulo):
        propias = {c.clave for c in configuracion(modulo) if isinstance(c, Campo)}
        faltan = [c.clave for c in CONFIGURACION_DEL_ASIENTO if c.clave not in propias]
        if faltan:
            problemas.append("un driver de asientos incluye en CONFIGURACION las claves del asiento "
                             "(asiento.CONFIGURACION_DEL_ASIENTO), que el núcleo lee al armar sus líneas; faltan: "
                             + ", ".join(faltan))
    if columnas is not None:
        problemas += _incumplimientos_de_las_columnas(modulo, columnas)
    return problemas


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
                                     "línea neutral la llena: la fija, con el centro_costo de la principal; las demás, "
                                     "con el anexo_auxiliar de la principal o del tercero")
            elif c.rol or c.campo:
                problemas.append(f"COLUMNAS_ELEGIBLES[{dato!r}]: {c.columna!r} no lleva rol ni campo, que son de las "
                                 "líneas neutrales de un driver de asientos")
    return problemas
