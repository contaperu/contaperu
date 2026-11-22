"""Cómo se nombra un comprobante para una persona o un ERP, y cómo se lee de vuelta un nombre que alguien escribió.

Son las dos caras de lo mismo y por eso viven juntas, al lado de la identidad (`clave_de`):

- **`nombre_del_comprobante`** escribe «01 F001-123»: el tipo de la Tabla 10 y la serie-número **tal como vienen
  en el documento**, y con `con_contraparte=True` el documento de la contraparte delante, «20602222226 01 F001-123».
  Es, byte a byte, el nombre que ya salía en `api.errores_de()[i]["comprobante"]`, y no por casualidad: era
  `pipeline.seleccion.etiqueta`, que hasta la 15.15 no se publicaba porque «no decide nada, da formato a un nombre»
  —su dependencia, `serie_y_numero`, sí era pública—. El motivo dejó de valer por los hechos: ese formato **ya era
  un contrato**, porque sale en una respuesta pública, y la aplicación en producción lo copió byte a byte para
  nombrar sus comprobantes igual que el motor. Una copia de un formato es la que acaba diciendo «F001-7634» en un
  aviso y «01 F001-0007634» en otro del mismo modal (le pasó a esa aplicación). `etiqueta` sigue siendo el nombre
  interno, y ahora es ESTA función.
- **`leer_nombre_del_comprobante`** hace el camino de vuelta: de lo que escribe una persona o manda un ERP
  —«F001-0123», «01 F001-123», «20602222226 F001-123», «20602222226 01 F001-0123»— a sus cuatro partes
  **normalizadas como la clave del motor** (`clave_de`): el tipo con sus dos dígitos, la serie en mayúsculas, el
  número sin ceros delante y el documento solo con sus dígitos. Lo normaliza el propio `Comprobante`, así que no
  hay una segunda copia de la regla: «0123» y «123» son el mismo número porque `Comprobante.clave` dice que lo son.

**Lo que no se entiende, falla** (`ValueError`, con lo que no se entendió y cómo se escribe), en vez de adivinar.
Tres decisiones con su porqué:

- **Sin guion no hay nombre que leer.** `serie_y_numero` nombra por su número un documento sin serie (un DUA, un
  recibo de servicios), así que «123» podría ser ese documento… o cualquier comprobante numerado 123 de cualquier
  serie. Leerlo casaría con lo que no es, y un lote que borra por nombre se llevaría otro. Esos documentos se
  nombran, pero su nombre no se puede leer de vuelta: se piden por su `id_externo`.
- **Un solo guion.** La serie y el número de SUNAT no llevan ninguno, y con dos no se sabe dónde acaba la serie: el
  número de una factura del exterior puede ser «INV-001».
- **El tipo es de uno o dos dígitos, y el documento, todo lo demás que tenga dígitos.** Con dos palabras delante,
  la primera es el documento y la segunda el tipo; con una, se decide por su forma. Una sigla de un sistema
  contable —«FT»— no es ninguna de las dos: depende de la configuración de cada contribuyente y no se traduce.

Lo vacío del resultado es lo que el nombre NO dijo, no un valor: «F001-123» no dice el tipo ni el proveedor, y
quien busca con él compara solo las partes que vinieron. **No se deduce el tipo de la serie**: la E001 la llevan
el recibo por honorarios y también la factura emitida desde SOL.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ..modelo.coerciones import serie_y_numero, solo_digitos
from .comprobante import Comprobante

# Las cuatro partes de un nombre, en el orden de `clave_de`.
PARTES = ("tipo_cp", "serie", "numero", "contraparte_doc")

# Lo que se escribe para nombrar un comprobante, y lo que dicen los rechazos.
EJEMPLO = "«F001-123», «01 F001-123» o «20602222226 01 F001-123»"


def _comprobante(comprobante: Comprobante | Mapping[str, Any]) -> Comprobante:
    """Un `Comprobante`, o uno armado con las cuatro partes de un diccionario —una fila de un ERP, un comprobante de
    un documento—, normalizadas por el propio constructor. Sin tipo, sin tipo: el `01` de fábrica no se inventa."""
    if isinstance(comprobante, Comprobante):
        return comprobante
    if not isinstance(comprobante, Mapping):
        raise ValueError("Se nombra un Comprobante o un diccionario con tipo_cp, serie, numero y contraparte_doc")
    return Comprobante(**{parte: str(comprobante.get(parte) or "") for parte in PARTES})


def nombre_del_comprobante(comprobante: Comprobante | Mapping[str, Any], *, con_contraparte: bool = False) -> str:
    """El nombre de un comprobante para una persona o un ERP: «01 F001-123», y con `con_contraparte=True`, el
    documento de la contraparte delante, «20602222226 01 F001-123».

    La serie y el número van **como vienen en el documento**, ceros incluidos: es el nombre que ya da
    `api.errores_de` y el que ve el contador en su pantalla. Quien lo lea con `leer_nombre_del_comprobante` recibe el
    número sin ellos. En compras, el documento delante es lo que distingue la F001-123 de dos proveedores; en ventas
    no hace falta, porque el emisor es uno."""
    c = _comprobante(comprobante)
    nombre = f"{c.tipo_cp} {serie_y_numero(c.serie, c.numero)}".strip()
    documento = (c.contraparte_doc or "").strip()
    return f"{documento} {nombre}" if con_contraparte and documento else nombre


def _es_tipo(palabra: str) -> bool:
    return palabra.isascii() and palabra.isdigit() and len(palabra) <= 2


def leer_nombre_del_comprobante(texto: str) -> dict[str, str]:
    """Las cuatro partes de un nombre escrito por una persona o un ERP, normalizadas como la clave del motor:
    `{"tipo_cp", "serie", "numero", "contraparte_doc"}`, con `""` en lo que el nombre no dijo.

        leer_nombre_del_comprobante("20602222226 01 F001-0123")
        → {"tipo_cp": "01", "serie": "F001", "numero": "123", "contraparte_doc": "20602222226"}

    Lanza `ValueError` con lo que no entendió."""
    limpio = re.sub(r"\s*-\s*", "-", " ".join(str(texto or "").split()))
    palabras = limpio.split()
    if not palabras:
        raise ValueError(f"Un nombre vacío no dice qué comprobante es: se escribe como {EJEMPLO}")
    if len(palabras) > 3:
        raise ValueError(f"«{limpio}» tiene {len(palabras)} partes y un nombre tiene a lo sumo tres —el documento "
                         f"de la contraparte, el tipo y la serie-número—, como {EJEMPLO}")
    *delante, cual = palabras
    serie, guion, numero = cual.partition("-")
    if not guion:
        raise ValueError(f"«{cual}» no dice serie y número: van unidos por un guion, como «F001-123». Un documento sin "
                         "serie no se puede pedir por su nombre: pídelo por su id_externo")
    if "-" in numero:
        raise ValueError(f"«{cual}» tiene más de un guion y no se sabe dónde acaba la serie: pídelo por su id_externo")
    if not serie or not numero:
        raise ValueError(f"A «{cual}» le falta {'la serie' if not serie else 'el número'}: se escribe como «F001-123»")
    documento = tipo = ""
    if len(delante) == 2:
        documento, tipo = delante
        if not _es_tipo(tipo):
            sigla = "" if tipo.isdigit() else (": una sigla de un sistema contable depende de su configuración y "
                                               "no se traduce")
            raise ValueError(f"«{tipo}» no es un tipo de la Tabla 10 de SUNAT, que son dos dígitos como «01»{sigla}")
    elif delante:
        if _es_tipo(delante[0]):
            tipo = delante[0]
        else:
            documento = delante[0]
    if documento and not solo_digitos(documento):
        raise ValueError(f"«{documento}» no es un tipo de la Tabla 10 de SUNAT ni un documento de identidad: el nombre "
                         f"se escribe como {EJEMPLO}")
    clave = Comprobante(tipo_cp=tipo, serie=serie, numero=numero, contraparte_doc=documento).clave
    return dict(zip(PARTES, clave))
