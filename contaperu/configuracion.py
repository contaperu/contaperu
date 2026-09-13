"""La configuración contable DECLARADA: qué se configura, cómo se valida y cómo se le explica a quien la edita.

`contaperu` sirve a cualquier aplicación que se construya encima, y cada una guarda la configuración contable de sus
empresas a su manera. Lo que comparten es la FORMA de esa configuración, y esa forma la declara el motor, no la
aplicación (John, 13-sep-2026: «la configuración es importante para que genere»). Cada clave se declara una vez, con
un `Campo`, y de esa única declaración salen tres cosas que antes vivían en tres sitios:

- sus valores por defecto (`por_defecto`);
- la validación de lo que llega (`validar`), con un mensaje por error que dice dónde está: una clave ignorada en
  silencio exporta con el valor de fábrica sin que nadie se entere;
- la descripción con la que una aplicación pinta su pantalla (`describir`), que le pide al motor en vez de copiarla.

Y un sistema contable declara además en qué columnas de su archivo puede ir un dato (`Columna`): el dato se guarda
una vez y la configuración de ese sistema elige dónde sale.

La configuración se declara en tres sitios, cada uno con lo suyo: lo general de la contabilidad, que sirve a
cualquier sistema, aquí (`CONFIGURACION_GENERAL`); lo que el núcleo lee al armar un asiento, en
`asiento/configuracion.py`; y lo propio de cada sistema contable, en su driver (`CONFIGURACION` y
`COLUMNAS_ELEGIBLES`, en su `datos.py`). La maquinaria no tiene dependencias: la usan el núcleo y los drivers.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

_ESPERADO = {"texto": "un texto", "booleano": "verdadero o falso", "numero": "un número", "lista": "una lista",
             "mapa": "un objeto", "objeto": "un objeto"}


@dataclass(frozen=True)
class Campo:
    """Una clave de la configuración.

    `tipo` es `texto`, `booleano`, `numero`, `lista`, `mapa` (claves libres que cumplen `claves`, cada valor como
    `valores`) u `objeto` (solo las claves de `campos`). `patron` es la expresión regular que un texto cumple entero.
    `por_defecto` en None deja la clave fuera de los valores por defecto; en un objeto, sus `campos` los arman.
    `titulo`, `ayuda` y `grupo` son para la pantalla de quien la edita."""
    clave: str
    tipo: str
    por_defecto: Any = None
    titulo: str = ""
    ayuda: str = ""
    grupo: str = ""
    patron: str = ""
    admite_nulo: bool = False
    campos: tuple[Campo, ...] = ()
    claves: str = ""
    valores: Campo | None = None


@dataclass(frozen=True)
class Columna:
    """Una columna del archivo de un sistema contable que puede recibir un dato.

    `columna` la nombra en la configuración (`columnas`), con el título de su Excel (`titulo`); `letra` dice dónde
    está en cada libro (`{"compra": "AI", "venta": "Z"}`). La `fija` va siempre y la `marcada` viene elegida de
    fábrica. En un driver de asientos, `rol` y `campo` dicen qué campo de qué línea neutral la llena."""
    columna: str
    titulo: str
    letra: dict[str, str]
    fija: bool = False
    marcada: bool = False
    ayuda: str = ""
    rol: str = ""
    campo: str = ""


class ConfiguracionInvalida(ValueError):
    """La configuración no cumple lo declarado. `errores` los trae todos, cada uno con su ruta, para arreglarlos de
    una vez y no de uno en uno."""

    def __init__(self, errores: list[str]):
        super().__init__("La configuración no es válida: " + "; ".join(errores))
        self.errores = list(errores)


def _como_llego(valor: Any) -> str:
    if valor is None:
        return "nulo"
    if isinstance(valor, bool):
        return "verdadero" if valor else "falso"
    if isinstance(valor, (int, float)):
        return f"el número {valor}"
    if isinstance(valor, str):
        return f'el texto "{valor}"'
    if isinstance(valor, list):
        return "una lista"
    if isinstance(valor, dict):
        return "un objeto"
    return type(valor).__name__


def _ruta(donde: str, clave: str) -> str:
    return f"{donde}.{clave}" if donde else clave


def _es_del_tipo(valor: Any, tipo: str) -> bool:
    if tipo == "texto":
        return isinstance(valor, str)
    if tipo == "booleano":
        return isinstance(valor, bool)
    if tipo == "numero":
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)
    if tipo == "lista":
        return isinstance(valor, list)
    return isinstance(valor, dict)


def _errores_del_valor(valor: Any, campo: Campo, donde: str) -> list[str]:
    if valor is None:
        return [] if campo.admite_nulo else [f"`{donde}`: se esperaba {_ESPERADO[campo.tipo]} y llegó nulo"]
    if not _es_del_tipo(valor, campo.tipo):
        return [f"`{donde}`: se esperaba {_ESPERADO[campo.tipo]} y llegó {_como_llego(valor)}"]
    if campo.tipo == "texto" and campo.patron and not re.fullmatch(campo.patron, valor):
        return [f"`{donde}`: {_como_llego(valor)} no cumple el patrón {campo.patron}"]
    errores: list[str] = []
    if campo.tipo == "lista" and campo.valores is not None:
        for i, item in enumerate(valor):
            errores += _errores_del_valor(item, campo.valores, f"{donde}[{i}]")
    elif campo.tipo == "mapa":
        for clave, item in valor.items():
            if campo.claves and not re.fullmatch(campo.claves, str(clave)):
                errores.append(f"`{_ruta(donde, str(clave))}`: la clave no cumple el patrón {campo.claves}")
            elif campo.valores is not None:
                errores += _errores_del_valor(item, campo.valores, _ruta(donde, str(clave)))
    elif campo.tipo == "objeto":
        errores += _errores_del_objeto(valor, campo.campos, donde)
    return errores


def _errores_del_objeto(valor: dict, campos: tuple[Campo, ...], donde: str, ignorar: tuple[str, ...] = ()) -> list[str]:
    por_clave = {c.clave: c for c in campos}
    errores: list[str] = []
    for clave, item in valor.items():
        if clave in ignorar:
            continue
        campo = por_clave.get(clave)
        if campo is None:
            errores.append(f"`{_ruta(donde, str(clave))}`: clave desconocida; las que hay: {', '.join(por_clave)}")
        else:
            errores += _errores_del_valor(item, campo, _ruta(donde, clave))
    return errores


def _errores_de_columnas(valor: Any, columnas: dict[str, tuple[Columna, ...]], donde: str) -> list[str]:
    if not isinstance(valor, dict):
        return [f"`{donde}`: se esperaba un objeto {{dato: [columna, …]}} y llegó {_como_llego(valor)}"]
    errores: list[str] = []
    for dato, elegidas in valor.items():
        ruta = _ruta(donde, str(dato))
        declaradas = {c.columna: c for c in columnas.get(dato, ())}
        if not declaradas:
            errores.append(f"`{ruta}`: ese dato no se elige por columnas; los que sí: {', '.join(columnas)}")
            continue
        if not isinstance(elegidas, list) or not all(isinstance(x, str) for x in elegidas):
            errores.append(f"`{ruta}`: se esperaba una lista de columnas y llegó {_como_llego(elegidas)}")
            continue
        for x in elegidas:
            if x not in declaradas:
                errores.append(f'`{ruta}`: "{x}" no es una de sus columnas; las que hay: {", ".join(declaradas)}')
        repetidas = sorted({x for x in elegidas if elegidas.count(x) > 1})
        if repetidas:
            errores.append(f"`{ruta}`: columna repetida: {', '.join(repetidas)}")
        for c in declaradas.values():
            if c.fija and c.columna not in elegidas:
                errores.append(f'`{ruta}`: falta "{c.columna}", que es fija: el dato va siempre en ella')
    return errores


def validar(valor: Any, campos: tuple[Campo, ...], columnas: dict[str, tuple[Columna, ...]] | None = None,
            donde: str = "") -> list[str]:
    """Lo que `valor` no cumple de lo declarado, un mensaje por error con su ruta. Lista vacía = cumple.

    Una clave que falta no es un error: vale su valor por defecto. Una que sobra sí, porque nadie la va a leer. Con
    `columnas`, la clave `columnas` elige para cada dato entre las declaradas, y la fija no puede faltar."""
    if not isinstance(valor, dict):
        return [f"`{donde or 'configuración'}`: se esperaba un objeto y llegó {_como_llego(valor)}"]
    errores = _errores_del_objeto(valor, campos, donde, ignorar=("columnas",) if columnas else ())
    if columnas and "columnas" in valor:
        errores += _errores_de_columnas(valor["columnas"], columnas, _ruta(donde, "columnas"))
    return errores


def _defecto(campo: Campo) -> Any:
    if campo.por_defecto is not None:
        return copy.deepcopy(campo.por_defecto)
    if campo.tipo == "objeto" and campo.campos:
        return por_defecto(campo.campos)
    return None


def por_defecto(campos: tuple[Campo, ...], columnas: dict[str, tuple[Columna, ...]] | None = None) -> dict:
    """Los valores por defecto de lo declarado, como se guardan: se pueden volver a pasar tal cual. En `columnas`, las
    fijas y las marcadas de cada dato, en el orden en que se declararon. Cada llamada devuelve una copia nueva."""
    salida = {c.clave: valor for c in campos if (valor := _defecto(c)) is not None}
    if columnas:
        salida["columnas"] = {dato: [c.columna for c in declaradas if c.fija or c.marcada]
                              for dato, declaradas in columnas.items()}
    return salida


def _describir_campo(campo: Campo) -> dict:
    descripcion: dict[str, Any] = {"clave": campo.clave, "tipo": campo.tipo, "titulo": campo.titulo,
                                   "ayuda": campo.ayuda, "grupo": campo.grupo}
    valor = _defecto(campo)
    if valor is not None:
        descripcion["por_defecto"] = valor
    if campo.patron:
        descripcion["patron"] = campo.patron
    if campo.admite_nulo:
        descripcion["admite_nulo"] = True
    if campo.campos:
        descripcion["campos"] = [_describir_campo(c) for c in campo.campos]
    if campo.claves:
        descripcion["claves"] = campo.claves
    if campo.valores is not None:
        descripcion["valores"] = _describir_campo(campo.valores)
    return descripcion


def describir(campos: tuple[Campo, ...], columnas: dict[str, tuple[Columna, ...]] | None = None) -> dict:
    """Lo declarado, en JSON: cada campo con su tipo, su valor por defecto, su patrón y sus textos, y cada columna
    elegible con su título, su letra en cada libro y si es fija o viene marcada. Es lo que pinta una pantalla."""
    descripcion: dict[str, Any] = {"campos": [_describir_campo(c) for c in campos]}
    if columnas:
        descripcion["columnas"] = {
            dato: [{"columna": c.columna, "titulo": c.titulo, "letra": dict(c.letra), "fija": c.fija,
                    "marcada": c.marcada, "ayuda": c.ayuda} for c in declaradas]
            for dato, declaradas in columnas.items()}
    return descripcion


# ── Lo general de la contabilidad: sirve a cualquier sistema contable ────────────────────────────────────────────────

_CUENTA = r"^([0-9]{2,12})?$"      # de 2 a 12 dígitos, como la valida la pantalla; vacía = sin cuenta


def _cuenta_por_moneda(clave: str, titulo: str, soles: str, dolares: str, ayuda: str) -> Campo:
    return Campo(clave, "objeto", titulo=titulo, ayuda=ayuda, grupo="cuentas", campos=(
        Campo("PEN", "texto", soles, titulo="Soles", grupo="cuentas", patron=_CUENTA),
        Campo("USD", "texto", dolares, titulo="Dólares", grupo="cuentas", patron=_CUENTA)))


CONFIGURACION_GENERAL: tuple[Campo, ...] = (
    Campo("cuentas", "objeto", titulo="Cuentas", grupo="cuentas", campos=(
        # VACÍA a propósito: en la práctica es el comodín «63/65», que no es una cuenta. La pone la imputación de cada
        # documento o la configuración de la empresa.
        Campo("gasto", "texto", "", titulo="Cuenta de gasto por defecto", grupo="cuentas", patron=_CUENTA,
              ayuda="La que se usa cuando el comprobante no trae ninguna. Vacía, se elige en cada comprobante."),
        _cuenta_por_moneda("cxp", "Facturas, boletas y tickets por pagar", "421201", "421202",
                           "Las compras normales a un proveedor con RUC."),
        # La factura afecta a detracción (SUNAT) lleva su propia cuenta por pagar, la MISMA en las dos monedas.
        _cuenta_por_moneda("cxp_detraccion", "Detracciones por pagar", "421203", "421203",
                           "La línea de la detracción de las facturas afectas; el proveedor sigue en la suya."),
        _cuenta_por_moneda("honorarios", "Recibos por honorarios por pagar", "424101", "424102",
                           "Lo que le debes al profesional independiente."),
        Campo("retencion_4ta", "texto", "401721", titulo="Renta de 4ta que le retienes", grupo="cuentas",
              patron=_CUENTA, ayuda="Solo cuando el recibo por honorarios muestra la retención."),
        Campo("igv", "texto", "401111", titulo="IGV", grupo="cuentas", patron=_CUENTA,
              ayuda="Crédito fiscal en las compras, débito fiscal en las ventas."),
        _cuenta_por_moneda("clientes", "Facturas y boletas emitidas por cobrar", "121201", "121202",
                           "La cuenta por cobrar del cliente."),
        Campo("ventas", "texto", "701101", titulo="Cuenta de ingreso por defecto", grupo="cuentas", patron=_CUENTA,
              ayuda="La que se usa cuando la venta no trae ninguna."),
        # Vacías a propósito: son cuentas de cada empresa, y sin ellas su columna sale en blanco (el registro de
        # CONTASIS las lleva cuando su columna trae importe).
        Campo("otros_tributos", "texto", "", titulo="Otros tributos y cargos", grupo="cuentas", patron=_CUENTA,
              ayuda="La cuenta de los otros tributos y cargos del documento. Vacía, esa columna sale en blanco."),
        Campo("icbper", "texto", "", titulo="ICBPER", grupo="cuentas", patron=_CUENTA,
              ayuda="La cuenta del impuesto a las bolsas de plástico. Vacía, esa columna sale en blanco."),
    )),
    # ¿Esta empresa lleva centros de costo (obras, proyectos, áreas)? Apagado, el centro no sale en ninguna columna
    # aunque el documento traiga uno, y la aplicación deja de pedirlo: hay empresas que no los usan.
    Campo("usa_centros_costo", "booleano", True, titulo="Usa centros de costo", grupo="centros",
          ayuda="Apagado, el centro de costo deja de pedirse y de salir en el archivo."),
    # La lista de la empresa. El motor no la lee —el centro de cada documento llega en su imputación—, pero se declara
    # para que una aplicación sepa dónde guardarla.
    Campo("centros_costo", "lista", titulo="Centros de costo", grupo="centros",
          ayuda="Los centros de costo de la empresa, con su código y su nombre.",
          valores=Campo("", "objeto", grupo="centros", campos=(Campo("codigo", "texto", titulo="Código"),
                                                               Campo("nombre", "texto", titulo="Nombre")))),
    # QUÉ cuentas lo llevan, por PREFIJO (el contador, 09-sep-2026): «la cuenta 63 y 65 tiene habilitado el centro de
    # costo, pero cuando es una cuenta 60 por defecto no se debe asignar un centro de costo». En el sistema contable
    # esa marca vive en cada cuenta del plan; aquí se declara por prefijo, que es lo que un estudio sabe decir. El `70`
    # va para que las ventas lleven su centro. Casa por `startswith`, así que "6311" también vale. Lista VACÍA es una
    # respuesta legítima (ninguna cuenta lo lleva) y no es lo mismo que ausente (los de fábrica): ver `lleva_centro`.
    Campo("cuentas_con_centro", "lista", ["63", "65", "70"], titulo="Cuentas que llevan centro de costo",
          grupo="centros", ayuda="Por el inicio de la cuenta: 63 y 65 sí, 60 no.",
          valores=Campo("", "texto", grupo="centros", patron=r"^[0-9]{1,6}$")),
    # Tasa por código SUNAT, por si el comprobante no la trae. De los apéndices vigentes del SPOT
    # (orientacion.sunat.gob.pe), cruzados POR NOMBRE con el Catálogo 54: en esa página la columna "código" es el
    # numeral dentro del anexo, no el código del comprobante (ahí "14" es Leche, que en el catálogo es 023, mientras
    # 014 son Carnes). Cruzarlo por número sale mal.
    Campo("detraccion_tasas", "mapa", {"008": 4, "009": 10, "010": 15, "012": 12, "019": 10, "020": 12, "021": 10,
                                       "022": 12, "024": 10, "025": 10, "026": 10, "027": 4, "030": 4, "037": 12},
          titulo="Tasa de cada detracción", grupo="detracciones", claves=r"^[0-9]{3}$",
          ayuda="El porcentaje por código SUNAT, para el comprobante que no lo trae.",
          valores=Campo("", "numero", grupo="detracciones")),
    # Nombre oficial (Catálogo 54 de SUNAT, Anexo N.° 8): la pantalla dice "030 · Contratos de construcción" en vez de
    # un código a secas. El motor no lo lee.
    Campo("detraccion_nombres", "mapa", {
        "008": "Madera", "009": "Arena y piedra", "010": "Residuos, subproductos, desechos, recortes y desperdicios",
        "012": "Intermediación laboral y tercerización", "019": "Arrendamiento de bienes muebles",
        "020": "Mantenimiento y reparación de bienes muebles", "021": "Movimiento de carga",
        "022": "Otros servicios empresariales", "024": "Comisión mercantil",
        "025": "Fabricación de bienes por encargo", "026": "Servicio de transporte de personas",
        "027": "Servicio de transporte de bienes por vía terrestre", "030": "Contratos de construcción",
        "037": "Demás servicios gravados con el IGV"},
          titulo="Nombre de cada detracción", grupo="detracciones", claves=r"^[0-9]{3}$",
          ayuda="El nombre del Catálogo 54 de SUNAT, para que un código diga algo.",
          valores=Campo("", "texto", grupo="detracciones")),
)
