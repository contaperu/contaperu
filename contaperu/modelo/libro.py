"""El libro: la cabecera de lo que se registra —un RUC, un mes, ventas o compras—.

Es lo primero que se valida de un documento y lo que decide todo lo demás: de su tipo cuelga qué cuentas se usan,
qué sub-diario toca y qué columnas escribe cada driver.

**Y desde la 9.0 eso cuelga de una tabla y no de un booleano**, que es el cambio que rompe. Hasta la 8.x el motor
preguntaba `libro.es_venta` en medio centenar de sitios y usaba `not es_venta` para decir «es compra»: correcto
mientras el catálogo tuviera dos valores, y un error silencioso en cuanto tuviera tres. La 8.2 puso una puerta que
lo paraba; la 9.0 lo arregla, que es distinto — **ahora cada tipo de libro declara lo que el motor necesita saber
de él**, y añadir uno es añadir una fila en vez de auditar cincuenta `if`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields

from .. import vocabulario
from .coerciones import solo_digitos

# Del catálogo del estándar (`vocabulario.TIPOS_LIBRO`), que es la única fuente desde la 1.0.
TIPOS_LIBRO = vocabulario.TIPOS_LIBRO


@dataclass(frozen=True)
class Rasgos:
    """Lo que el motor necesita saber de un libro para armar su asiento, declarado en vez de deducido.

    **Cada campo era un `if es_venta` repartido por el núcleo.** Juntarlos tiene tres efectos que valen la mayor
    que cuesta: se ve de un vistazo en qué se diferencian dos libros, un libro nuevo es una fila, y lo que el
    motor todavía no sabe hacer se nota — porque hay que rellenar el campo y no hay con qué.

    `sentido_principal` es el del HECHO: en una venta el ingreso va al haber, en una compra el gasto va al debe.
    La contraparte va al contrario, y por eso no se declara: se deriva."""

    tipo: str
    sub_diario: str             # la clave de configuración que nombra su sub-diario
    cuenta_contraparte: str     # la clave de `cuentas` con la que se salda: a quién se le debe o quién debe
    sentido_principal: str      # 'D' | 'H'
    da_credito_fiscal: bool     # el IGV entra como crédito (compras) o como débito del que se recauda (ventas)
    lleva_detraccion: bool
    lleva_honorarios: bool      # el recibo por honorarios y su retención de 4ta
    origen: str                 # de qué bloque del documento salen sus líneas

    @property
    def es_venta(self) -> bool:
        return self.tipo == "venta"

    @property
    def es_compra(self) -> bool:
        return self.tipo == "compra"

    @property
    def sentido_contraparte(self) -> str:
        """Al revés que el hecho, siempre. Es la partida doble, y por eso se deriva en vez de declararse."""
        return "D" if self.sentido_principal == "H" else "H"


# Los libros que el motor sabe ORIGINAR, con lo que los distingue. Son los mismos de `asiento.TIPOS_DEL_MOTOR`:
# aquella tupla dice cuáles, esta tabla dice en qué se diferencian.
#
# El catálogo del estándar puede crecer sin que crezca esta tabla, y no es una inconsistencia: el catálogo dice
# qué libros existen y esto dice cuáles sabe armar el motor. Uno que esté allí y no aquí se rechaza nombrando los
# que sí (`asiento.LibroQueElMotorNoOrigina`).
RASGOS: dict[str, "Rasgos"] = {
    "venta": Rasgos(tipo="venta", sub_diario="sub_diario_ventas", cuenta_contraparte="clientes",
                    sentido_principal="H", da_credito_fiscal=False, lleva_detraccion=False,
                    lleva_honorarios=False, origen="comprobantes"),
    "compra": Rasgos(tipo="compra", sub_diario="sub_diario_compras", cuenta_contraparte="cxp",
                     sentido_principal="D", da_credito_fiscal=True, lleva_detraccion=True,
                     lleva_honorarios=True, origen="comprobantes"),
}


class LibroSinRasgos(ValueError):
    """Se pidieron los rasgos de algo que el motor no sabe armar, o de un booleano de antes de la 9.0."""


def rasgos_de(libro: Rasgos | Libro | str) -> Rasgos:
    """Los rasgos de lo que sea que te hayan pasado: unos rasgos, un `Libro` o el tipo por su nombre.

    Es generoso a propósito —quien llama pasa lo que tenga— con una excepción que es el motivo de que exista:
    **un `bool` da un error que dice qué hacer**. Hasta la 8.x estas funciones recibían `es_venta`, y un `True`
    que se colara elegiría la rama equivocada en silencio, que es justo lo que la 9.0 viene a quitar."""
    if isinstance(libro, Rasgos):
        return libro
    if isinstance(libro, bool):
        cual = "venta" if libro else "compra"
        raise LibroSinRasgos(
            f"Esto recibía `es_venta: bool` hasta la 8.x y desde la 9.0 recibe los rasgos del libro. "
            f"En vez de {libro!r}, pasa `libro.rasgos`, o `modelo.RASGOS[{cual!r}]` si no tienes el libro.")
    tipo = getattr(libro, "tipo", libro)
    rasgos = RASGOS.get(str(tipo or "").strip().lower())
    if rasgos is None:
        raise LibroSinRasgos(f"El motor no sabe armar el asiento de un libro {tipo!r}: "
                             f"origina {', '.join(sorted(RASGOS))}")
    return rasgos


@dataclass
class Libro:
    """El registro que se genera: un RUC, un mes, ventas o compras."""

    ruc: str
    razon_social: str
    periodo: str  # 'AAAAMM'
    tipo: str     # 'venta' | 'compra'

    def __post_init__(self) -> None:
        self.ruc = solo_digitos(self.ruc)
        self.periodo = solo_digitos(self.periodo)[:6]
        self.razon_social = " ".join(str(self.razon_social or "").split())
        self.tipo = str(self.tipo or "").strip().lower()
        if len(self.ruc) != 11:
            raise ValueError(f"RUC inválido: {self.ruc!r} (11 dígitos)")
        if not re.fullmatch(r"20[0-9]{2}(0[1-9]|1[0-2])", self.periodo):
            raise ValueError(f"Periodo inválido: {self.periodo!r} (AAAAMM)")
        if self.tipo not in TIPOS_LIBRO:
            raise ValueError(f"Tipo de libro inválido: {self.tipo!r} ({'|'.join(sorted(TIPOS_LIBRO))})")

    @property
    def anio(self) -> int:
        return int(self.periodo[:4])

    @property
    def mes(self) -> int:
        return int(self.periodo[4:6])

    @property
    def es_venta(self) -> bool:
        return self.tipo == "venta"

    @property
    def es_compra(self) -> bool:
        """La pareja de `es_venta`, y no es redundante: hasta la 8.x `not es_venta` significaba «es compra» en medio
        centenar de sitios, y eso solo era cierto mientras el catálogo tuviera dos valores. Con las dos preguntas por
        separado, un tipo de libro nuevo da `False` a las dos y **cada rama tiene que decidir** en vez de heredar
        «compra». Lo sigue preguntando lo que tiene el libro en la mano —los lectores, `validar`, los drivers—;
        lo que recibe el eje por parámetro recibe los `rasgos`."""
        return self.tipo == "compra"

    @property
    def rasgos(self) -> Rasgos:
        """Lo que el motor necesita saber de este libro. Es lo que se le pasa al núcleo desde la 9.0."""
        return rasgos_de(self.tipo)

    def a_dict(self) -> dict[str, str]:
        return {"ruc": self.ruc, "razon_social": self.razon_social, "periodo": self.periodo, "tipo": self.tipo}

    @classmethod
    def de_dict(cls, d: dict) -> "Libro":
        """**Lo desconocido NO se ignora** (7.0). Hasta la 6.5 se filtraba en silencio, y era el último sitio del
        estándar donde pasaba: un dato que se cuela sin error es un dato que se pierde sin aviso.

        Dejaba al lector **más laxo que el esquema publicado**, que rechaza por su `additionalProperties: false`
        (`estandar/open-accounting.schema.json`, `$defs.libro`). Es el mismo agujero que la 4.0 cerró para el
        comprobante, y el CHANGELOG de entonces dio por hecho que «faltaba solo el comprobante»: faltaba también
        el libro. De ahí sale la forma de este rechazo —nombrar TODAS las sobrantes, no reventar en la primera—.

        **Las claves `_` tampoco pasan**, y aquí es más estricto que el comprobante a propósito: `$defs.libro` es
        el único bloque del esquema sin `patternProperties: {"^_": …}`, así que el estándar no admite una anotación
        del productor dentro del libro. Su sitio es la raíz del documento.

        **El mensaje dice las cuatro que hay** en vez de señalar una válvula: el comprobante puede mandar lo que
        el motor no entiende a `datos_originales`, y el libro no tiene dónde. El molde es
        `configuracion._errores_del_objeto`, que lista las claves válidas por eso mismo.

        Lo que **falta** sigue llegando vacío: `razon_social` es opcional en la práctica —los golden traen tres
        claves— y lo que no se puede suponer lo rechaza la validación del libro con su propio `ValueError`.
        """
        if not isinstance(d, dict):
            raise ValueError("El libro tiene que ser un objeto con ruc, razon_social, periodo y tipo")
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(d) - set(validas))
        if desconocidas:
            raise ValueError(f"Claves que no son de un libro: {', '.join(desconocidas)}. "
                             f"Las que hay: {', '.join(validas)}")
        return cls(**{nombre: d.get(nombre, "") for nombre in validas})

