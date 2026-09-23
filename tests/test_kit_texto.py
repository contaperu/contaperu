"""El formateo compartido del kit, probado por sí mismo.

Estas funciones las usan varios drivers y no tenían ni un test directo: se cubrían de refilón por el archivo que
salía. Una regla que solo se prueba por su resultado final no dice dónde se rompió.

El caso que las trajo aquí: el CSV declaraba `Opciones(fecha="AAAA-MM-DD")` —lo que de verdad escribe, porque la
línea neutral lleva la fecha en ISO— y `formatear_fecha` no conocía ese valor. Nadie se estrellaba porque el CSV no
pasa por aquí, pero su propio docstring lo ofrece como plantilla para un driver de terceros, que sí lo haría.
"""
from __future__ import annotations

from datetime import date

import pytest

from contaperu.drivers import concar, csv as driver_csv, sire
from contaperu.drivers.kit import Opciones
from contaperu.drivers.kit.texto import formatear_fecha

UN_DIA = date(2026, 9, 22)


@pytest.mark.parametrize("formato, esperado", [
    ("AAAAMMDD", "20260922"),       # el SIRE
    ("DD/MM/AAAA", "22/09/2026"),   # CONCAR, CONTASIS y STARSOFT
    ("AAAA-MM-DD", "2026-09-22"),   # el ISO del estándar, el que escribe el CSV
])
def test_los_tres_formatos_de_fecha_que_se_declaran(formato, esperado):
    assert formatear_fecha(UN_DIA, Opciones(fecha=formato)) == esperado


def test_sin_fecha_no_se_inventa_ninguna():
    assert formatear_fecha(None, Opciones(fecha="AAAAMMDD")) == ""


def test_un_formato_que_nadie_implementa_se_niega_en_vez_de_adivinar():
    with pytest.raises(ValueError, match="Formato de fecha desconocido"):
        formatear_fecha(UN_DIA, Opciones(fecha="MM-DD-AAAA"))


@pytest.mark.parametrize("modulo", [sire, concar, driver_csv])
def test_el_formato_que_declara_cada_driver_de_serie_existe(modulo):
    """Lo que un driver declara en sus `Opciones` tiene que poder escribirse. Declararlo y que no exista era
    documentación que miente, y se descubría al copiarla."""
    assert formatear_fecha(UN_DIA, modulo.OPCIONES)
