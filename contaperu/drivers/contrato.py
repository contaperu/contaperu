"""El contrato de un driver de salida: lo que tiene que exponer para que el núcleo lo use.

Hay tres formas, y un driver implementa una:

- **`linea(c, libro, idx, op) -> str`** — un archivo de texto, una línea por comprobante. Es el TXT
  del SIRE: un registro tributario, que se escribe desde el comprobante y no desde el asiento.
- **`construir(libro, comprobantes, contab, correlativos, op) -> (bytes, resumen)`** — un archivo
  entero armado a partir de los comprobantes. Es la forma del Excel de CONCAR, que nació antes que
  la línea neutral.
- **`desde_lineas(libro, lineas, contab, op) -> (bytes, resumen)`** — un archivo de asientos armado
  a partir de las LÍNEAS NEUTRALES de `pe-ledger` (`asiento.LineaDiario`), ya numeradas y cuadradas.
  **Es la forma para un driver de asientos nuevo** (SISCONT, STARSOFT, CONTASIS…): el driver solo
  traduce vocabulario, y la contabilidad —cuentas, sentidos, detracción, numeración— la pone el núcleo
  una sola vez para todos. El núcleo exige el cuadre ANTES de llamarlo.

Todas exponen además `NOMBRE`, `FORMATOS` ({'venta'|'compra': identificador de la salida}),
`OPCIONES` (una `formato.Opciones`) y `nombre(libro, op) -> str`; las dos de archivo, su
`CONTENT_TYPE`. Opcional: `EXCLUYE_TIPOS`, los tipos SUNAT que ese destino no lleva; y, en un driver de
asientos, `EXIGE`: lo que ese ERP no puede importar sin y que el núcleo, si no se lo dicen, deja pasar
(`EXIGE_POSIBLES`). La cuenta contable y la equivalencia del tipo los exige el núcleo a todo driver de
asientos, se declare o no (`EXIGE_NUCLEO`): sin ellos no hay línea que armar. `exige(mod)` devuelve la
unión, y es lo que `diagnosticar` lee para decidir si un mes está listo **para ese destino** — la idea
viene de Codat `options` y Merge `/meta` (ver `REFERENCIAS.md`): el destino declara qué exige antes de
que nadie escriba un byte.

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
FORMAS = ("desde_lineas", "construir", "linea")
TIPOS_LIBRO = ("venta", "compra")

# Lo que un driver de asientos PUEDE exigir (el núcleo sabe generar sin ello): el centro de costo en
# las cuentas que lo llevan, y que la moneda tenga código en el destino. Lo que exige el núcleo a todos:
# la cuenta contable de cada línea y la equivalencia del tipo SUNAT (de ella sale el sub-diario).
EXIGE_POSIBLES = frozenset({"centro_costo", "moneda"})
EXIGE_NUCLEO = frozenset({"cuenta_contable", "tipo_cp"})


class Driver(Protocol):
    NOMBRE: str
    FORMATOS: dict[str, str]
    OPCIONES: Opciones

    def nombre(self, libro: Libro, op: Opciones = ...) -> str: ...


class DriverTexto(Driver, Protocol):
    def linea(self, c: Comprobante, libro: Libro, idx: int, op: Opciones = ...) -> str: ...


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
    """Cuál de las tres formas implementa el driver (la preferida si expone varias); '' si ninguna."""
    return next((f for f in FORMAS if callable(getattr(mod, f, None))), "")


def necesita_asiento(mod: Any) -> bool:
    """¿Necesita la configuración contable y los correlativos? Las dos formas de archivo, sí."""
    return forma(mod) in ("desde_lineas", "construir")


def exige(mod: Any) -> frozenset[str]:
    """Todo lo que ese destino exige para exportar: lo del núcleo más lo que el driver declara en
    `EXIGE`. Un registro tributario (forma `linea`) no exige nada de esto: no arma asientos."""
    if forma(mod) != "linea" and forma(mod):
        return EXIGE_NUCLEO | frozenset(getattr(mod, "EXIGE", None) or ())
    return frozenset()


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
        if f == "linea":
            problemas.append("EXIGE solo lo declara un driver de asientos: un registro tributario no arma asientos")
        elif isinstance(declarado, str) or not all(isinstance(x, str) for x in declarado):
            problemas.append("EXIGE es un conjunto de textos")
        elif set(declarado) - EXIGE_POSIBLES:
            problemas.append(f"EXIGE solo admite {sorted(EXIGE_POSIBLES)}; sobra {sorted(set(declarado) - EXIGE_POSIBLES)}")
    return problemas
