"""El contrato de un driver de salida: lo que tiene que exponer para que el núcleo lo use.

El mismo documento sale de dos maneras —como registro o como asiento (`estandar/LEEME.md`, «Dos familias de
salida, un solo documento»)—, y hay cuatro formas de driver. Un driver implementa una:

**Familia registro** — una fila por comprobante, sin asiento:

- **`linea(c, libro, idx, op) -> str`** — un archivo de texto, una línea por comprobante. Es el TXT
  del SIRE: un registro tributario, que se escribe desde el comprobante y no lleva cuentas.
- **`desde_comprobantes(libro, comprobantes, contab, op) -> (bytes, resumen)`** — el archivo de un sistema
  contable que importa su registro de compras o de ventas y arma el asiento él mismo (CONTASIS). Recibe los comprobantes y la configuración, con la imputación de cada documento dentro, y
  **no decide ninguna cuenta**: las lee de `asiento.partes_de` (la de la base, o sus partes si hay reparto) y
  de `asiento.cuenta_tercero` (la del total), que las resuelven igual que para el asiento de CONCAR. No numera:
  el correlativo es del asiento, y el asiento lo arma el destino. El núcleo exige la cuenta ANTES de llamarlo.

**Familia asiento** — las líneas de la partida doble:

- **`construir(libro, comprobantes, contab, correlativos, op) -> (bytes, resumen)`** — un archivo
  entero armado a partir de los comprobantes. Es la forma del Excel de CONCAR, que nació antes que
  la línea neutral.
- **`desde_lineas(libro, lineas, contab, op) -> (bytes, resumen)`** — un archivo de asientos armado
  a partir de las LÍNEAS NEUTRALES de `open-accounting` (`asiento.LineaDiario`), ya numeradas y cuadradas.
  **Es la forma para un driver de asientos nuevo** (SISCONT, STARSOFT…): el driver solo
  traduce vocabulario, y la contabilidad —cuentas, sentidos, detracción, numeración— la pone el núcleo
  una sola vez para todos. El núcleo exige el cuadre ANTES de llamarlo.

Todas exponen además `NOMBRE`, `FORMATOS` ({'venta'|'compra': identificador de la salida}),
`OPCIONES` (una `formato.Opciones`) y `nombre(libro, op) -> str`; las tres de archivo, su
`CONTENT_TYPE`. Opcional: `EXCLUYE_TIPOS`, los tipos SUNAT que ese destino no lleva; y, en un driver que
lleva cuentas, `EXIGE`: lo que ese sistema no puede importar sin y que el núcleo, si no se lo dicen, deja
pasar (`EXIGE_POSIBLES`; en uno de registro, `EXIGE_POSIBLES_REGISTRO`). Lo que el núcleo exige se declare o
no (`EXIGE_NUCLEO`, `EXIGE_NUCLEO_REGISTRO`) es aquello sin lo que no hay nada que escribir: la cuenta
contable, y en un asiento además la equivalencia del tipo, de la que sale el sub-diario. `exige(mod)` devuelve
la unión, y es lo que `diagnosticar` lee para decidir si un mes está listo **para ese destino** — la idea
viene de Codat `options` y Merge `/meta` (ver `REFERENCIAS.md`): el destino declara qué exige antes de
que nadie escriba un byte.

Y opcional en cualquier forma, `no_caben(libro, comprobantes, contab) -> {motivo: [comprobantes]}`: lo que su
formato no puede llevar aunque la contabilidad esté completa —una moneda que no tiene, un código más largo que su
columna—. `diagnosticar` lo lista antes de exportar y el núcleo se niega con `NoCabe` antes de escribir un byte
(hoy, en la forma `desde_comprobantes`): un código no se corta ni una moneda se inventa.

Los `Protocol` de abajo son la documentación tipada; lo que el registro comprueba de verdad al cargar
un driver de terceros es `incumplimientos()`, y `tests/test_contrato_drivers.py` es el examen que pasa
cualquier driver registrado.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from ..formato import Opciones
from ..modelo import Comprobante, Libro

if TYPE_CHECKING:
    from ..asiento.lineas import LineaDiario

# En orden de preferencia: si un driver expone dos (el CSV conserva `construir` por compatibilidad),
# el núcleo usa la primera.
FORMAS = ("desde_lineas", "desde_comprobantes", "construir", "linea")
FAMILIA = {"linea": "registro", "desde_comprobantes": "registro", "construir": "asiento", "desde_lineas": "asiento"}
TIPOS_LIBRO = ("venta", "compra")

# Lo que un driver de asientos PUEDE exigir (el núcleo sabe generar sin ello): el centro de costo en
# las cuentas que lo llevan, y que la moneda tenga código en el destino. Lo que exige el núcleo a todos:
# la cuenta contable de cada línea y la equivalencia del tipo SUNAT (de ella sale el sub-diario).
EXIGE_POSIBLES = frozenset({"centro_costo", "moneda"})
EXIGE_NUCLEO = frozenset({"cuenta_contable", "tipo_cp"})
# Y a uno de registro que lleva cuentas (`desde_comprobantes`), el núcleo le exige la cuenta —la columna con la
# que el destino arma su asiento— y nada del sub-diario ni de su equivalencia, que son del asiento. Puede exigir
# el centro de costo, y `cuenta_unica`: que ningún documento reparta su base entre varias cuentas, porque el destino
# lleva una por fila y arma un asiento por fila (CONTASIS, John 12-sep-2026). La moneda no: su código
# (`monedas_codigo`) es el de la configuración del asiento; lo que un registro no puede escribir en su propio
# vocabulario lo dice su `no_caben`.
EXIGE_POSIBLES_REGISTRO = frozenset({"centro_costo", "cuenta_unica"})
EXIGE_NUCLEO_REGISTRO = frozenset({"cuenta_contable"})


class Driver(Protocol):
    NOMBRE: str
    FORMATOS: dict[str, str]
    OPCIONES: Opciones

    def nombre(self, libro: Libro, op: Opciones = ...) -> str: ...


class DriverTexto(Driver, Protocol):
    def linea(self, c: Comprobante, libro: Libro, idx: int, op: Opciones = ...) -> str: ...


class DriverRegistro(Driver, Protocol):
    CONTENT_TYPE: str
    EXIGE: frozenset[str]     # opcional; subconjunto de EXIGE_POSIBLES_REGISTRO

    def desde_comprobantes(self, libro: Libro, comprobantes: list[Comprobante], contab: dict,
                           op: Opciones = ...) -> tuple[bytes, dict]: ...


class DriverArchivo(Driver, Protocol):
    CONTENT_TYPE: str
    EXIGE: frozenset[str]     # opcional; subconjunto de EXIGE_POSIBLES

    def construir(self, libro: Libro, comprobantes: list[Comprobante], contab: dict,
                  correlativos: dict[str, int], op: Opciones = ...) -> tuple[bytes, dict]: ...


class DriverAsientos(Driver, Protocol):
    CONTENT_TYPE: str
    EXIGE: frozenset[str]     # opcional; subconjunto de EXIGE_POSIBLES

    def desde_lineas(self, libro: Libro, lineas: list[LineaDiario], contab: dict,
                     op: Opciones = ...) -> tuple[bytes, dict]: ...


def forma(mod: Any) -> str:
    """Cuál de las cuatro formas implementa el driver (la preferida si expone varias); '' si ninguna."""
    return next((f for f in FORMAS if callable(getattr(mod, f, None))), "")


def familia(mod: Any) -> str:
    """'registro' (una fila por comprobante: `linea`, `desde_comprobantes`) o 'asiento' (`construir`,
    `desde_lineas`); '' si no implementa ninguna forma."""
    return FAMILIA.get(forma(mod), "")


def necesita_config(mod: Any) -> bool:
    """¿Necesita la configuración contable del contribuyente? Todo driver que lleva cuentas: los de asientos y el
    registro de un sistema contable (`desde_comprobantes`). El registro tributario (`linea`), no."""
    return forma(mod) in ("desde_lineas", "construir", "desde_comprobantes")


def necesita_asiento(mod: Any) -> bool:
    """¿Arma asientos, y necesita por eso además los correlativos? Las dos formas de la familia asiento."""
    return familia(mod) == "asiento"


def exige(mod: Any) -> frozenset[str]:
    """Todo lo que ese destino exige para exportar: lo del núcleo para su forma más lo que el driver declara en
    `EXIGE`. Un registro tributario (forma `linea`) no exige nada de esto: no lleva cuentas."""
    declarado = frozenset(getattr(mod, "EXIGE", None) or ())
    if necesita_asiento(mod):
        return EXIGE_NUCLEO | declarado
    if forma(mod) == "desde_comprobantes":
        return EXIGE_NUCLEO_REGISTRO | declarado
    return frozenset()


class NoCabe(ValueError):
    """Comprobantes que el formato del destino no puede llevar, por motivo (lo dice el driver en `no_caben`). El
    núcleo se niega antes de escribir nada, igual que con un tipo sin equivalencia."""

    def __init__(self, motivos: dict[str, list[Comprobante]]):
        cuantos = len({id(c) for lista in motivos.values() for c in lista})
        super().__init__(f"{cuantos} comprobante(s) que el formato del destino no puede llevar: " + "; ".join(motivos))
        self.motivos = motivos


def no_caben(mod: Any, libro: Libro, comprobantes: list[Comprobante], contab: dict) -> dict[str, list[Comprobante]]:
    """Lo que el driver dice que no cabe en su formato (su `no_caben`, opcional), sin los motivos vacíos."""
    declarado = getattr(mod, "no_caben", None)
    if not callable(declarado):
        return {}
    return {motivo: list(lista) for motivo, lista in (declarado(libro, comprobantes, contab) or {}).items() if lista}


def incumplimientos(mod: Any) -> list[str]:
    """Lo que le falta a un driver para cumplir el contrato. Lista vacía = cumple."""
    problemas: list[str] = []
    nombre = getattr(mod, "NOMBRE", None)
    if not isinstance(nombre, str) or not nombre.strip():
        problemas.append("falta NOMBRE (texto)")
    formatos = getattr(mod, "FORMATOS", None)
    if not isinstance(formatos, dict) or not formatos:
        problemas.append("falta FORMATOS ({'venta'|'compra': identificador})")
    elif set(formatos) - set(TIPOS_LIBRO):
        problemas.append(f"FORMATOS solo admite las claves {TIPOS_LIBRO}")
    if not isinstance(getattr(mod, "OPCIONES", None), Opciones):
        problemas.append("falta OPCIONES (una formato.Opciones)")
    if not callable(getattr(mod, "nombre", None)):
        problemas.append("falta nombre(libro, op)")
    f = forma(mod)
    if not f:
        problemas.append("no implementa ninguna forma: " + ", ".join(FORMAS))
    elif f != "linea" and not isinstance(getattr(mod, "CONTENT_TYPE", None), str):
        problemas.append("un driver de archivo declara su CONTENT_TYPE")
    excluye = getattr(mod, "EXCLUYE_TIPOS", None)
    if excluye is not None and not all(isinstance(t, str) for t in excluye):
        problemas.append("EXCLUYE_TIPOS son códigos SUNAT en texto")
    declarado = getattr(mod, "EXIGE", None)
    if declarado is not None:
        posibles = EXIGE_POSIBLES_REGISTRO if f == "desde_comprobantes" else EXIGE_POSIBLES
        if f == "linea":
            problemas.append("EXIGE no lo declara un registro tributario (forma `linea`): no lleva cuentas")
        elif isinstance(declarado, str) or not all(isinstance(x, str) for x in declarado):
            problemas.append("EXIGE es un conjunto de textos")
        elif set(declarado) - posibles:
            problemas.append(f"EXIGE solo admite {sorted(posibles)}; sobra {sorted(set(declarado) - posibles)}")
    if hasattr(mod, "no_caben") and not callable(getattr(mod, "no_caben")):
        problemas.append("no_caben es una función: no_caben(libro, comprobantes, contab)")
    return problemas
