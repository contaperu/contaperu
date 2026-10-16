"""Lo que los cinco formatos comparten: sacar un dato de un texto que ya no tiene columnas.

Un PDF de constancia es una tabla, y al pasarlo a texto la tabla se deshace. Lo que queda no es basura, pero
tampoco es el papel: **una etiqueta y su valor pueden salir en cualquier orden**, y a veces pegados. Del BCP:

    00229545Número de operación          ← el valor DELANTE y sin espacio
    Fecha de proceso 15/05/2026 - 03:10 pm   ← el valor detrás, normal

Por eso aquí no hay un «parsear línea a línea»: hay `junto_a`, que busca el valor **a los dos lados** de su
etiqueta. Es la única forma de que el lector no dependa de qué librería sacó el texto, que es precisamente lo que
el motor no controla —recibe texto, nunca un PDF—.

Y por eso también hay `cuadrar_tres`: cuando el orden de los valores no se puede confiar, lo que sí se puede es la
aritmética. Tres importes de los que uno es la suma de los otros dos se identifican sin mirar dónde salieron, y si
no cuadran el lector **se niega** en vez de adivinar. Es la misma idea que `tesoreria.cuadre` aplica al extracto:
lo que convierte «leí un PDF» en «lo leí bien».
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ...errores import ErrorContaperu
from ...modelo import monto as _monto


class ConstanciaIlegible(ErrorContaperu, ValueError):
    """El texto no tiene lo que su formato promete, o lo tiene y no cuadra.

    Se levanta en vez de devolver un movimiento a medias: un pago mal leído entra al libro y nadie lo nota, y
    eso es peor que no leerlo. El mensaje dice **qué** falta, porque quien integra tiene el PDF delante."""


#: Cómo nombra cada banco la moneda, en el símbolo o en la palabra. No es un catálogo con fuente: es lo que
#: estos papeles escriben, y por eso vive aquí y no en `datos/`. Lo que sale es el código ISO del estándar.
MONEDA_POR_PALABRA = {
    "S/": "PEN", "S/.": "PEN", "SOLES": "PEN", "PEN": "PEN",
    "$": "USD", "US$": "USD", "DOLARES": "USD", "DÓLARES": "USD", "USD": "USD",
}

_IMPORTE = r"-?\d{1,3}(?:,\d{3})*\.\d{2}|-?\d+\.\d{2}"
_SIMBOLO = r"S/\.?|US\$|\$"


def junto_a(texto: str, etiqueta: str, patron: str = r"[^\n]+") -> str:
    """El valor que acompaña a una etiqueta, esté **detrás o delante** de ella en la misma línea.

    Devuelve cadena vacía si la etiqueta no aparece: el que pregunta decide si eso es un fallo. Se prueba primero
    por detrás, que es el caso normal; sólo si ahí no hay nada se mira delante, que es como sale el BCP cuando la
    celda de la etiqueta y la del valor caen en el mismo renglón.

    **No cruza el salto de línea**, y eso no es un detalle: en el BCP «Tipo de operación» sale en un renglón y
    «Estado» en el siguiente, así que admitir el salto devolvía `Estado` como si fuera el tipo de la operación —un
    dato equivocado con toda la pinta de ser bueno—. Que una etiqueta sin valor devuelva vacío es lo correcto:
    significa que en ese papel el valor no está al lado, y hay que ir a buscarlo de otra manera."""
    esc = re.escape(etiqueta).replace(r"\ ", r"[ \t]+")
    detras = re.search(rf"{esc}[ \t]*:?[ \t]*({patron})", texto, re.IGNORECASE)
    if detras and detras.group(1).strip():
        return detras.group(1).strip()
    delante = re.search(rf"({patron}?)[ \t]*{esc}", texto, re.IGNORECASE)
    return delante.group(1).strip() if delante else ""


def linea_con(texto: str, trozo: str) -> str:
    """El renglón entero que contiene un trozo de texto. Vacío si ninguno lo contiene.

    Es la salida para cuando el valor no está al lado de su etiqueta sino solo en su propia línea, que es como el
    BCP escribe el tipo de la operación. Buscar la línea por lo que dice —y no por dónde está— hace que el dato
    salga completo: `Transferencia a otros bancos locales - Diferida` y no solo la parte que se reconoció."""
    for linea in texto.splitlines():
        if trozo.lower() in linea.lower():
            return linea.strip()
    return ""


def importes(texto: str) -> list[Decimal]:
    """Todos los importes de un trozo de texto, en el orden en que salieron, ya en `Decimal`."""
    hallados = []
    for crudo in re.findall(_IMPORTE, texto):
        try:
            hallados.append(_monto(crudo.replace(",", "")))
        except (InvalidOperation, ValueError):
            continue
    return hallados


def importe(texto: str, etiqueta: str) -> Decimal:
    """El importe que sigue a una etiqueta. Se niega si no hay ninguno, porque un pago sin importe no es un pago."""
    trozo = junto_a(texto, etiqueta, rf"(?:{_SIMBOLO})?\s*{_IMPORTE}")
    hallados = importes(trozo)
    if not hallados:
        raise ConstanciaIlegible(f"no se encontró un importe junto a «{etiqueta}»")
    return hallados[0]


def moneda(texto: str) -> str:
    """El código ISO de la moneda, del símbolo o de la palabra que el banco escriba. Vacío si no la dice.

    No se supone PEN por defecto: tres de los seis papeles que fundaron este lector son en dólares, y un importe
    con la moneda equivocada es un asiento equivocado."""
    for palabra, iso in MONEDA_POR_PALABRA.items():
        if re.search(rf"(?<![A-Za-zÁÉÍÓÚ]){re.escape(palabra)}(?![A-Za-zÁÉÍÓÚ])", texto, re.IGNORECASE):
            return iso
    return ""


def fecha(texto: str) -> date | None:
    """La primera fecha del texto, venga `dd/mm/aaaa` (BCP, BBVA masivos) o `aaaa-mm-dd` (BBVA operación).

    El año viene completo en los cinco formatos, que es la diferencia con un extracto —ahí la línea trae día y mes
    y el año está en la cabecera—. Aquí no hay nada que adivinar, y el núcleo sigue sin reloj."""
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    criollo = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", texto)
    if criollo:
        anio = int(criollo.group(3))
        return date(anio + 2000 if anio < 100 else anio, int(criollo.group(2)), int(criollo.group(1)))
    return None


def fecha_de(texto: str, etiqueta: str) -> date | None:
    """La fecha que acompaña a una etiqueta."""
    return fecha(junto_a(texto, etiqueta, r"[\d/\-]{8,10}[^\n]*"))


def cuadrar_tres(hallados: list[Decimal], que: str) -> tuple[Decimal, Decimal]:
    """De tres importes donde uno es la suma de los otros dos, devuelve `(parte_mayor, parte_menor)`.

    Existe porque en el BCP el orden en que salen los tres **no es el de sus etiquetas** —la tabla es de dos
    columnas y el texto las intercala—, así que posicionarlos sería jugárselo a cómo extrajo el texto quien lo
    extrajo. La aritmética, en cambio, no depende de eso: hay una sola partición de tres números en la que uno es
    la suma. Si no la hay, el lector se niega, y eso es la comprobación de que leyó bien."""
    if len(hallados) != 3:
        raise ConstanciaIlegible(f"{que}: se esperaban tres importes y salieron {len(hallados)}")
    for i, total in enumerate(hallados):
        otros = [v for j, v in enumerate(hallados) if j != i]
        if otros[0] + otros[1] == total:
            return (max(otros), min(otros))
    raise ConstanciaIlegible(f"{que}: los tres importes no cuadran, ninguno es la suma de los otros dos "
                             f"({', '.join(str(v) for v in hallados)})")


def digitos(texto: str) -> str:
    """Un número de cuenta como lo escribe el banco, reducido a sus dígitos: `191-1111111-0-11` y
    `19111111110 11` son la misma cuenta, y es así como se compara con la que declaró el contribuyente."""
    return re.sub(r"\D", "", texto)


#: Por debajo de esto dos números no se declaran la misma cuenta ni coincidiendo: el cargo de un papel llega con
#: la cuenta larga y el maestro puede tenerla corta —o al revés, con el CCI—, así que se comparan por contención;
#: con pocos dígitos eso casa cualquier cosa.
MINIMO_PARA_RECONOCER = 8

#: Y cuando ni contenerse sirve, la cola. Lo enseñó el BBVA: la **misma** cuenta sale escrita
#: `0119-9900-0000000100` en la planilla y `01199900000000000100` en la operación suelta, porque la segunda mete
#: dos dígitos de control en medio. Ninguna contiene a la otra, pero las dos acaban en el número de cuenta, que
#: es lo que identifica. Diez dígitos de cola es toda la cuenta en los tres bancos que han pasado por aquí.
DIGITOS_DE_LA_COLA = 10


def cuenta_declarada(numero: str, cuentas) -> str:
    """El `id` con que el contribuyente llama a la cuenta que el papel nombra por su número.

    `Movimiento.cuenta` **no es un número de cuenta**, es la llave del maestro, y el motor lo exige. Así que un
    lector de constancias no puede trabajar sin el maestro, y eso está bien: significa que lo que entra al libro
    está apuntando a una cuenta que el contribuyente declaró, con su 104 y su moneda, y no a unos dígitos que
    nadie reconoce.

    Se compara por **contención de dígitos** en los dos sentidos y, si eso no basta, **por la cola**: los bancos
    escriben la misma cuenta de varias maneras —`191-1111111-0-11`, `0119-9900-0000000100`, el CCI de 20— y una
    de ellas mete dígitos de control en medio, con lo que ninguna contiene a la otra. Lo que no cambia es en qué
    acaba. Si no hay a quién apuntar, se dice el número tal cual salió: es lo único que quien integra necesita
    para añadirlo a su maestro."""
    del_papel = digitos(numero)
    if len(del_papel) >= MINIMO_PARA_RECONOCER:
        for cuenta in cuentas or ():
            for suyo in (digitos(getattr(cuenta, "numero", "")), digitos(getattr(cuenta, "cci", ""))):
                if len(suyo) < MINIMO_PARA_RECONOCER:
                    continue
                if (suyo in del_papel or del_papel in suyo
                        or suyo[-DIGITOS_DE_LA_COLA:] == del_papel[-DIGITOS_DE_LA_COLA:]):
                    return cuenta.id
    raise ConstanciaIlegible(
        f"la cuenta de cargo del papel ({numero}) no es ninguna de las que declara el maestro; "
        f"declárala en `cuentas_bancarias` con su cuenta contable y su moneda")
