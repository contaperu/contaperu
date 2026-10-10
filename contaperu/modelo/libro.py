"""El libro: la cabecera de lo que se registra —un RUC, un mes, ventas o compras—.

Es lo primero que se valida de un documento y lo que decide todo lo demás: de `Libro.es_venta` cuelga qué
cuentas se usan, qué sub-diario toca y qué columnas escribe cada driver.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields

from .. import vocabulario
from .coerciones import solo_digitos

# Del catálogo del estándar (`vocabulario.TIPOS_LIBRO`), que es la única fuente desde la 1.0.
TIPOS_LIBRO = vocabulario.TIPOS_LIBRO

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
        """La pareja de `es_venta`, y no es redundante: hoy `not es_venta` significa «es compra» en medio centenar
        de sitios, y eso solo es cierto mientras el catálogo tenga dos valores. Con las dos preguntas por separado,
        un tipo de libro nuevo da `False` a las dos y **cada rama tiene que decidir** en vez de heredar «compra»."""
        return self.tipo == "compra"

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

