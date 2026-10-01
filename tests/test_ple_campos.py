"""El mapa del Libro Diario 5.1 (`datos/sunat/ple_campos.json`) dice la verdad sobre el código.

Es el hermano de `test_sire_campos.py`, con una diferencia que viene del formato: el del SIRE se **lee** y se
**escribe**, así que allí el mapa se confronta con las dos puntas —el lector y el driver—. Un 5.1 solo se **escribe**:
no hay lector, y por eso aquí se confronta con una sola punta.

Mientras el driver `ple` no exista, lo que se puede comprobar ya es todo lo que no depende de él, que es casi todo:
que la numeración sea la del formato, que cada columna que dice venir de la línea exista de verdad en `LineaDiario`,
que cada hueco lleve escrito su motivo y que no haya un valor de `escritura` o de `visto` sin describir. Es lo que
impide que el mapa y el modelo se separen en silencio, que es justo el accidente que el del SIRE vino a evitar.

Lo que falta —que las 21 columnas del mapa sean las 21 que el driver escribe, en su orden— entra con el driver.
"""
from __future__ import annotations

import pytest

from contaperu import catalogos
from contaperu.drivers.kit import columnas as kit_columnas

# El formato que el motor escribe hoy, y cuántas columnas tiene según SUNAT.
FORMATO = catalogos.FORMATO_PLE
COLUMNAS = 21
# Las columnas que salen tal cual de un campo de la línea del asiento: son las que tienen que existir en el modelo.
DE_LA_LINEA = {"de_la_linea"}


@pytest.fixture(scope="module")
def mapa() -> dict:
    return catalogos.campos_del_ple()


@pytest.fixture(scope="module")
def campos(mapa) -> list[dict]:
    return catalogos.columnas_del_ple()


def test_la_numeracion_es_la_del_formato(mapa, campos):
    """Los números son los del formato de SUNAT, de 1 a 21 sin huecos, y el mapa dice cuántos son."""
    libro = mapa["libros"][FORMATO]
    assert libro["columnas"] == COLUMNAS == len(campos)
    assert [c["n"] for c in campos] == list(range(1, COLUMNAS + 1))
    # Las 21 se informan: a diferencia del SIRE, este formato no tiene columnas de relleno al final.
    assert libro["campos_informados"] == COLUMNAS


def test_toda_columna_de_la_linea_existe_en_el_modelo(campos):
    """El candado principal: una columna que diga venir de `linea.X` tiene que poder leerse de una línea de verdad.

    Si alguien renombra un campo de `LineaDiario` y no toca el mapa, este test lo dice. Se comprueba contra
    `kit.columnas.rutas()`, que es la misma lista con la que el contrato valida las columnas de un driver, así que
    las rutas con punto (`documento.tipo_cp`) valen igual aquí."""
    rutas = set(kit_columnas.rutas())
    declarados = {c["campo"] for c in campos if c["escritura"] in DE_LA_LINEA}
    assert declarados, "ninguna columna dice venir de la línea; el mapa no puede estar bien"
    assert declarados <= rutas, f"columnas que el modelo no tiene: {sorted(declarados - rutas)}"


def test_ninguna_columna_sin_campo_se_queda_sin_motivo(campos):
    """La regla del mapa: una columna que no sale de un campo de la línea **dice por qué**.

    Es lo que separa «esta columna la compone el driver» de «se nos olvidó»."""
    sin_motivo = [c["n"] for c in campos if not c["campo"] and not (c.get("motivo") or "").strip()]
    assert not sin_motivo, f"columnas sin campo y sin motivo: {sin_motivo}"


def test_toda_columna_con_campo_dice_de_donde_lo_saca(campos):
    """Y al revés: si declara un campo, su `escritura` tiene que ser de las que leen uno."""
    mal = [c["n"] for c in campos if c["campo"] and c["escritura"] not in DE_LA_LINEA]
    assert not mal, f"columnas que declaran un campo pero no dicen leerlo de la línea: {mal}"


def test_las_escrituras_y_los_vistos_estan_descritos(mapa, campos):
    """Ningún valor se usa sin estar en su diccionario: el mapa se explica solo, sin ir al código."""
    for clave, diccionario in (("escritura", "escrituras"), ("visto", "visto")):
        usados = {c[clave] for c in campos}
        descritos = set(mapa[diccionario])
        assert usados <= descritos, f"{clave} sin describir: {sorted(usados - descritos)}"
        for valor, frase in mapa[diccionario].items():
            assert frase.strip(), f"{diccionario}[{valor}] no dice nada"


def test_cada_fuente_dice_de_donde_sale(mapa):
    """Ninguna regla sin fuente, y aquí son seis: la estructura oficial, el formato, el nivel de la cuenta, la
    estructura electrónica, los códigos de libro y el archivo con el que se contrastó."""
    fuentes = mapa["fuentes"]
    assert set(fuentes) == {"estructura", "formato", "nivel_de_la_cuenta", "estructura_electronica",
                            "codigos_de_libro", "contraste"}
    for nombre, texto in fuentes.items():
        assert len(texto.strip()) > 40, f"la fuente {nombre} no dice nada"
    # El nivel de la cuenta es el que manda el artículo 6, y la fuente lo cita con sus dos umbrales.
    assert "artículo 6" in fuentes["nivel_de_la_cuenta"]
    assert "100 UIT" in fuentes["nivel_de_la_cuenta"]


def test_el_mapa_sale_de_la_estructura_oficial_y_no_de_deducciones(mapa):
    """Hasta el 1-oct-2026 este mapa se dedujo de un archivo presentado, y tenía dos columnas mal rotuladas y unos
    códigos `[por confirmar]`. Ahora sale del libro de estructuras que publica SUNAT, leído campo a campo, así que
    **no puede quedar nada por confirmar**: lo que no se sepa, no se escribe.

    El caso que lo trae: el campo 5 del 5.1 se rotuló «denominación de la cuenta» porque iba vacío y la norma la
    hace opcional. No era eso — es el **código de la Unidad de Operación**, y la denominación no está en el 5.1 en
    absoluto: vive en el 5.3."""
    for nombre, texto in mapa["fuentes"].items():
        assert "[por confirmar]" not in texto, f"la fuente {nombre} todavía deduce algo"
    assert "estructura" in mapa["fuentes"] and "SUNAT" in mapa["fuentes"]["estructura"]
    # El rótulo que estaba mal, y el que lo corrige.
    campo5 = next(c for c in catalogos.columnas_del_ple() if c["n"] == 5)
    assert "Unidad de Operación" in campo5["nombre"]


def test_el_mapa_trae_los_dos_libros_del_par(mapa):
    """El grupo 05 son dos pares: cada diario con su detalle del plan contable al lado. El motor escribe el par del
    diario completo —5.1 y 5.3— que es del que hay archivo aceptado.

    El 5.3 es donde vive la **denominación de la cuenta**, y por eso el 5.1 no la lleva en cada línea: se declara
    una vez por cuenta y no 12 094 veces."""
    assert set(mapa["libros"]) == {"diario", "plan_contable"}
    plan = mapa["libros"]["plan_contable"]
    assert plan["formato"] == "5.3" and plan["codigo"] == "050300" and plan["columnas"] == 8
    assert len(catalogos.columnas_del_ple("plan_contable")) == 8
    # El periodo del 5.3 lleva día; el del 5.1, no. Confundirlos nombra mal el fichero por dentro.
    assert plan["periodo"] == "AAAAMMDD" and mapa["libros"]["diario"]["periodo"] == "AAAAMM00"
    # La denominación es obligatoria y el motor no la tiene: la declara el contribuyente.
    denominacion = next(c for c in plan["campos"] if c["n"] == 3)
    assert denominacion["obligatorio"] and denominacion["escritura"] == "del_contribuyente"


def test_la_periodicidad_del_plan_contable_esta_dicha(mapa):
    """SUNAT no lo pide todos los meses, y eso no se puede deducir del archivo: «obligatorio en el periodo de enero
    cada año o cuando se genera el libro electrónico por primera vez»."""
    nota = mapa["libros"]["plan_contable"]["nota"]
    assert "enero" in nota and "primera vez" in nota


def test_los_codigos_de_libro_no_se_confunden_con_los_del_sire(mapa):
    """El despiste que este bloque existe para cazar: el SIRE usa `140400` y `080400`, y los registros del PLE son
    `140100` y `080100`. Confundirlos nombraría el archivo de forma que SUNAT lo rechaza."""
    codigos = mapa["codigos_de_libro"]["codigos"]
    assert codigos["050100"].startswith("Libro Diario")
    assert "Compras" in codigos["080100"] and "Ventas" in codigos["140100"]
    from contaperu.drivers import sire
    assert sire.LIBRO_COMPRAS not in codigos and sire.LIBRO_VENTAS not in codigos


def test_la_cuenta_contable_es_la_columna_4(campos):
    """El hallazgo que sostiene todo el mapa: SUNAT pide el código de la cuenta contable, y la denominación de al
    lado es opcional para quien usa más de cuatro dígitos de subcuenta — por eso va vacía."""
    cuenta = next(c for c in campos if c["n"] == 4)
    assert cuenta["campo"] == "cuenta"
    denominacion = next(c for c in campos if c["n"] == 5)
    assert denominacion["escritura"] == "vacia" and denominacion["visto"] == "nunca"
