"""El formato de un registro de texto: saneado, fechas, importes y números como van al archivo."""
from __future__ import annotations

from collections.abc import Iterable

import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

from ...modelo import Comprobante
from .opciones import Opciones

_CONTROLES = re.compile(r"[\x00-\x1f\x7f]")


def _plegar(texto: str, codificacion: str) -> str:
    """`texto` con cada carácter que `codificacion` no sabe escribir plegado a lo que sí sepa.

    Carácter a carácter a propósito: plegar la cadena entera con un `NFKD` descompone la «Ñ» en «N» más una tilde
    suelta, y cp1252 tiene la «Ñ» pero no esa tilde, así que la perdería. Lo que el destino sabe escribir no se toca;
    lo que no, se descompone y se queda su letra base. Lo que ni así tiene equivalente desaparece, como siempre."""
    salida = []
    for ch in texto:
        try:
            ch.encode(codificacion)
        except UnicodeEncodeError:
            ch = unicodedata.normalize("NFKD", ch).encode(codificacion, "ignore").decode(codificacion)
        salida.append(ch)
    return "".join(salida)


def sanear(texto: str, opciones: Opciones) -> str:
    """Texto apto para un campo del TXT: nunca lleva '|' (es el separador) ni
    saltos de línea, y los espacios van colapsados. Con `opciones.sanear`, además se pliega a lo que
    **`opciones.codificacion` puede escribir** (tildes fuera si el destino no las tiene,
    Ñ → N) y '/' y '\\' → '-' (la Tabla 12 los prohíbe). El '&' se conserva: las
    razones sociales lo llevan.

    **Se pliega al DESTINO y no a ASCII a palo seco, y eso es el arreglo de la 5.2.** Hasta entonces convertía siempre
    a ASCII, así que el PLE escribía «BANOS» donde el libro que SUNAT aceptó escribe «BAÑOS» —con el byte `0xD1`, que
    es cp1252—. Transformar el nombre que el contribuyente le da a su cuenta es elegir por él: lo mismo que este
    repositorio se niega a hacer con el número del comprobante y con la sigla de un tipo. Con `codificacion="cp1252"`
    la Ñ y las tildes sobreviven; con `"ascii"`, el comportamiento de siempre.

    Lo que **no** depende de la bandera, y por eso apagarla nunca fue la salida: quitar los controles, quitar el
    separador y colapsar los espacios. Eso pasa siempre.

    El plegado va **carácter a carácter y no de golpe**, y eso no es un detalle: descomponer la cadena entera primero
    rompe la «Ñ» en «N» más una tilde suelta, y cp1252 —que sí tiene la «Ñ»— no tiene esa tilde suelta, así que la
    descartaría y volveríamos a escribir «BANOS». Se mira cada carácter: el que el destino sabe escribir se queda tal
    cual, y solo el que no se descompone para salvar la letra («Ó» → «O» en ASCII, en vez de desaparecer)."""
    s = _CONTROLES.sub(" ", str(texto or "")).replace("|", " ")
    if opciones.sanear:
        s = _plegar(s, opciones.codificacion)
        s = s.replace("/", "-").replace("\\", "-")
    return " ".join(s.split())


def formatear_fecha(d: date | str | None, opciones: Opciones) -> str:
    """Una fecha como la quiere el formato de destino.

    Acepta el `date` que traen los comprobantes y **también el texto ISO que traen las líneas del asiento**, que es
    como viajan en el estándar: hasta la 2.7 quien tenía una línea escribía `formatear_fecha(celdas.fecha(...))`,
    dos pasos para decir una cosa."""
    if isinstance(d, str):
        d = date.fromisoformat(d) if d.strip() else None
    if d is None:
        return ""
    if opciones.fecha == "AAAAMMDD":
        return d.strftime("%Y%m%d")
    if opciones.fecha == "DD/MM/AAAA":
        return d.strftime("%d/%m/%Y")
    if opciones.fecha == "AAAA-MM-DD":
        return d.isoformat()
    raise ValueError(f"Formato de fecha desconocido: {opciones.fecha!r}")


def formatear_monto(d: Any, opciones: Opciones | Any, negativo: bool = False) -> str:
    """Un importe o un porcentaje con dos decimales, y el cero escrito como diga el formato (`opciones.cero`).

    El valor viene siempre positivo del modelo; el signo se decide aquí. Acepta `Decimal`, texto o nada, porque
    los drivers lo llaman con lo que trae la línea: hasta la 2.7 STARSOFT tenía su propio `con_dos_decimales`
    para eso, con una tercera política del cero, y CONTASIS una cuarta con `float()`. Lo que no se entiende como
    número vuelve tal cual, en vez de reventar en mitad de un archivo."""
    if d is None or d == "":
        return opciones.cero
    try:
        valor = Decimal(str(d))
    except (ArithmeticError, ValueError):
        return str(d)
    if valor == 0:
        return opciones.cero
    s = f"{valor:.2f}"
    return f"-{s}" if negativo else s


def formatear_cambio(c: Comprobante, opciones: Opciones) -> str:
    if c.moneda == "PEN":
        return opciones.tc_pen
    return f"{c.tipo_cambio:.3f}" if c.tipo_cambio else ""


def formatear_numero(numero: str, opciones) -> str:
    """Número del comprobante tal como va al archivo. Por defecto SIN ceros a la izquierda
    (`00028806` → `28806`): SUNAT identifica el comprobante por su número y los ceros son cosmética del emisor. Vale
    con cualquier opciones que digan `sin_ceros`."""
    n = (numero or "").strip()
    if getattr(opciones, "sin_ceros", True) and n.isdigit():
        return n.lstrip("0") or "0"
    return n


def negativo(c: Comprobante, opciones) -> bool:
    return getattr(opciones, "signo_nc", True) and c.es_nota_credito


def armar_linea(campos: list[str], opciones: Opciones) -> str:
    linea = "|".join(campos)
    return linea + "|" if opciones.palote_final else linea


def armar_archivo(lineas: Iterable[str], opciones: Opciones) -> bytes:
    """Las líneas ya armadas → los bytes del archivo: las une con su salto, cierra con uno más y codifica.

    Vivía dentro de `pipeline/salida.py`, en la rama de la forma `linea`, que era la del SIRE y de nadie más. Sale
    aquí al aparecer el segundo registro de texto para SUNAT —el Libro Diario del PLE, que por la forma de su fila es
    un driver `desde_lineas` y no pasa por esa rama—, para que **la política de codificación viva en un solo sitio**:
    es la misma convergencia que la 2.3 hizo con el ZIP, que hasta entonces solo sabía hacer la rama de texto.

    La codificación no es un detalle, y desde la 5.2 **la gobierna `opciones.codificacion` en las dos ramas**. Antes
    solo la leía la rama saneada, y la otra llevaba `cp1252` escrito a mano: el campo quedaba muerto justo donde hacía
    falta, porque poner `codificacion="cp1252"` no tenía ningún efecto si el driver no saneaba.

    Tras `sanear()` el texto ya está plegado a esa codificación y `encode` no puede fallar. Sin sanear se escribe con
    `errors="replace"`, que es lo que evita que un carácter raro de una glosa tumbe una exportación entera.

    Un archivo sin ninguna línea son cero bytes, no un salto suelto: un TXT vacío que SUNAT recibiera con una línea en
    blanco sería una fila vacía, no un archivo vacío."""
    cuerpo = opciones.nueva_linea.join(lineas)
    if cuerpo:
        cuerpo += opciones.nueva_linea
    if opciones.sanear:
        return cuerpo.encode(opciones.codificacion)      # tras sanear() ya está plegado: no puede fallar
    return cuerpo.encode(opciones.codificacion, errors="replace")
