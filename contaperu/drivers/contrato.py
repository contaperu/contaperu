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

- **`desde_lineas(libro, lineas, config, opciones, *, indice=()) -> (bytes, resumen)`** — un archivo de asientos
  armado a partir de las LÍNEAS NEUTRALES de `open-accounting` (`asiento.LineaDiario`), ya numeradas y cuadradas.
  **Es la forma de todo driver de asientos**, CONCAR incluido desde la 1.0: el driver solo traduce vocabulario, y la
  contabilidad —cuentas, sentidos, detracción, numeración— la pone el núcleo una sola vez para todos. El núcleo exige
  el cuadre ANTES de llamarlo. Si la firma acepta `indice`, recibe además qué tramo de líneas es de qué comprobante,
  con la cabecera de sus hechos (`asiento.indice`): lo que un formato escribe en cada fila y la línea no guarda.
- **`construir(libro, comprobantes, config, correlativos, opciones) -> (bytes, resumen)`** — un archivo entero armado
  a partir de los comprobantes. Era la forma del Excel de CONCAR hasta la 0.10; un driver de terceros que la use
  sigue funcionando con un `AvisoDriver`, y se retira en la 2.0.

**El canal** — a QUIÉN se entrega lo que sale (la familia dice QUÉ se entrega). Cada driver declara su `CANAL`:

- **`legacy`** — un sistema contable instalado que importa un archivo (CONCAR, CONTASIS; STARSOFT y SISCONT cuando
  entren). Lleva cuentas y declara `EXIGE`, lo que su sistema no puede importar sin (vacío si nada).
- **`tributario`** — un registro que se presenta a SUNAT (el SIRE). Forma `linea`, sin cuentas ni configuración.
- **`intercambio`** — un formato neutral para leer o integrar (el CSV). Forma `desde_lineas`: proyecta la línea.

Cada canal se presenta en uno de los tres grupos de destinos del motor (`GRUPOS`): `tributario` es el **SIRE**, `legacy`
es **legacy** e `intercambio` es **ERP**. `drivers_disponibles` dice el grupo de cada driver.

**El vocabulario** — con qué palabras recibe sus líneas un driver de asientos (`VOCABULARIO`, 1.1). `legacy`, el de
siempre: siglas, sub-diarios, correlativos y el documento comodín de la detracción. `neutral`: las líneas del estándar
sin nada de eso, por `rol` y código SUNAT, para un ERP (el driver `asiento_neutral`). Un driver neutral es de canal
`intercambio`, no declara claves legacy en su configuración y el núcleo solo le exige la cuenta.

`api_erp`, escribir el cuerpo de la API de un ERP moderno, queda reservado (hito A5): el contrato lo rechaza. Un driver
de terceros sin `CANAL` se registra con un `AvisoDriver` y se trata como `legacy` durante la 1.x.

Todas exponen además `NOMBRE`, `FORMATOS` ({'venta'|'compra': identificador de la salida}),
`OPCIONES` (una `kit.Opciones`, o una `kit.OpcionesArchivo` en un driver de archivo) y `nombre(libro, opciones) -> str`; las tres de archivo, su
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
columna—. `diagnosticar` lo lista antes de exportar y el núcleo se niega con `NoCabe` antes de escribir un byte, en
toda forma que lleva cuentas: un código no se corta ni una moneda se inventa.

Y opcional en un driver `desde_lineas` de columnas simples, `COLUMNAS_DE_LINEA` (1.1): el formato declarado como tabla
de `kit.columnas.ColumnaDeLinea` —cabecera, campo de la línea que la llena y su fuente—, que escribe `kit.columnas`. El
contrato exige que cada columna diga su fuente y lea un campo que existe.

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

import inspect
from typing import TYPE_CHECKING, Any, Protocol

from .. import configuracion as _declaracion
from ..asiento.configuracion import CONFIGURACION_DEL_ASIENTO, MONEDAS_CODIGO
from ..asiento.faltas import NoExportable
from ..asiento.motor import CENTRO_EN_ANEXO
from ..configuracion import CONFIGURACION_GENERAL, Campo, Columna
from ..modelo import TIPOS_LIBRO, Comprobante, Libro
from .kit import Opciones, OpcionesArchivo
from .kit import columnas as _columnas_de_linea

if TYPE_CHECKING:
    from ..asiento.indice import ComprobanteDelAsiento
    from ..asiento.lineas import LineaDiario

# A quién se entrega lo que sale. Un eje distinto de la familia (registro o asiento), que dice qué se entrega.
CANALES = {
    "legacy": "un sistema contable instalado que importa un archivo",
    "tributario": "un registro que se presenta a SUNAT",
    "intercambio": "un formato neutral para leer o integrar",
}
# Lo que tiene nombre y todavía no existe: el contrato lo rechaza diciendo por qué.
CANALES_RESERVADOS = {
    "api_erp": "escribir el cuerpo de la API de un ERP moderno es el hito A5 de la hoja de ruta, fuera de la 1.0: el "
               "envío y los reintentos son de la aplicación",
}
# Cómo se trata durante la 1.x un driver de terceros que no declara su canal.
CANAL_POR_DEFECTO = "legacy"
# Cómo se presenta cada canal en la arquitectura del motor (John, 15-sep-2026): lo que sale va al SIRE, a un sistema
# legacy o a un ERP. El canal es la regla que hace cumplir el contrato; el grupo, cómo se nombra ante quien integra.
GRUPOS = {"tributario": "sire", "legacy": "legacy", "intercambio": "erp"}

# Con qué vocabulario arma el núcleo las líneas de un driver de asientos (1.1): `legacy` —siglas, sub-diarios,
# correlativos y el documento comodín de la detracción, lo que importan CONCAR y los de su familia— o `neutral`, las
# líneas del estándar sin nada de eso, por `rol` y código SUNAT, para los ERP que vienen. La contabilidad es la misma.
VOCABULARIOS = ("legacy", "neutral")
VOCABULARIO_POR_DEFECTO = "legacy"
# Lo que el núcleo exige a un driver neutral: la cuenta de cada línea. La equivalencia del tipo no, porque no hay sigla
# ni sub-diario que sacar de ella.
EXIGE_NUCLEO_NEUTRAL = frozenset({"cuenta_contable"})
# El vocabulario legacy de la configuración del asiento: lo que un driver neutral no declara.
CLAVES_LEGACY = frozenset({c.clave for c in CONFIGURACION_DEL_ASIENTO} | {MONEDAS_CODIGO})

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

    def desde_lineas(self, libro: Libro, lineas: list[LineaDiario], config: dict, opciones: Opciones = ..., *,
                     indice: tuple[ComprobanteDelAsiento, ...] = ...) -> tuple[bytes, dict]: ...


def forma(modulo: Any) -> str:
    """Cuál de las cuatro formas implementa el driver (la preferida si expone varias); '' si ninguna."""
    return next((f for f in FORMAS if callable(getattr(modulo, f, None))), "")


def familia(modulo: Any) -> str:
    """'registro' (una fila por comprobante: `linea`, `desde_comprobantes`) o 'asiento' (`construir`,
    `desde_lineas`); '' si no implementa ninguna forma."""
    return FAMILIA.get(forma(modulo), "")


def canal(modulo: Any) -> str:
    """A quién se entrega lo que sale: el `CANAL` que declara el driver, o `legacy` si no lo declara (1.x)."""
    return getattr(modulo, "CANAL", None) or CANAL_POR_DEFECTO


def declara_canal(modulo: Any) -> bool:
    return bool(getattr(modulo, "CANAL", None))


def grupo(modulo: Any) -> str:
    """El grupo de destinos al que entrega: `sire`, `legacy` o `erp`, según su canal; '' si el canal no existe."""
    return GRUPOS.get(canal(modulo), "")


def vocabulario(modulo: Any) -> str:
    """Con qué vocabulario recibe sus líneas: el `VOCABULARIO` que declara, o `legacy` si no lo declara."""
    return getattr(modulo, "VOCABULARIO", None) or VOCABULARIO_POR_DEFECTO


def acepta_indice(modulo: Any) -> bool:
    """¿Su `desde_lineas` recibe el índice de cada comprobante? Lo decide su firma: un parámetro `indice` o `**kwargs`.
    Así un driver de terceros escrito antes de la 1.0 sigue funcionando sin él."""
    funcion = getattr(modulo, "desde_lineas", None)
    if not callable(funcion):
        return False
    try:
        parametros = inspect.signature(funcion).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(p.name == "indice" or p.kind is p.VAR_KEYWORD for p in parametros)


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
        nucleo = EXIGE_NUCLEO_NEUTRAL if vocabulario(modulo) == "neutral" else EXIGE_NUCLEO_ASIENTO
        return nucleo | declarado
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
            problemas.append("COLUMNAS_DE_LINEA es de un driver `desde_lineas`: sus columnas leen la línea neutral")
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
        return []
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
    if declarado == "tributario" and f != "linea":
        return ["un driver tributario escribe un registro de texto para SUNAT: su forma es `linea`"]
    if declarado == "intercambio" and f != "desde_lineas":
        return ["un driver de intercambio proyecta la línea neutral: su forma es `desde_lineas`"]
    return []


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
