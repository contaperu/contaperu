"""Cuándo vence un mes: la declaración y el atraso del registro electrónico, los dos de la misma resolución.

Esto puede vivir en un núcleo sin reloj porque **no es un reloj**: dado un periodo y el último dígito del RUC
devuelve una fecha, y la respuesta no cambia según cuándo se pregunte. Es la misma figura que
`validar.PLAZO_ANOTACION_MESES`. Lo que necesita el hoy —si queda tiempo, si hay mora— no está, y
`tests/test_frontera.py` sigue prohibiendo el reloj en el núcleo.

Las tablas se copian de las que publica SUNAT, así que el riesgo real es un dedo torcido en una de las 168 celdas.
Contra eso van dos cosas: unas **anclas** transcritas a mano de la tabla oficial, y las **propiedades** del anexo
—los grupos de dígitos, el mes de vencimiento, el día que crece con el dígito y el registro que cierra antes que la
declaración—, que son las que cazan un desalineamiento de columnas en cualquier fila.
"""
from __future__ import annotations

from datetime import date

import pytest

from contaperu import api, catalogos

# Transcritas a mano de las tablas publicadas por SUNAT para 2026 (anexos I y II de la RS 000281-2022):
# sunat.gob.pe/orientacion/cronogramas/2026/cObligacionMensual2026.html y .../cronoRegistroC-V-2026.html
ANCLAS_DECLARACION = {
    ("202601", "0"): date(2026, 2, 16),
    ("202603", "1"): date(2026, 4, 20),
    ("202606", "4"): date(2026, 7, 20),
    ("202609", "3"): date(2026, 10, 20),
    ("202611", "9"): date(2026, 12, 24),
    ("202612", "0"): date(2027, 1, 18),
}
ANCLAS_ATRASO = {
    ("202601", "0"): date(2026, 2, 13),
    ("202605", "0"): date(2026, 6, 12),
    ("202608", "7"): date(2026, 9, 18),
    ("202609", "3"): date(2026, 10, 19),
    ("202611", "4"): date(2026, 12, 21),
    ("202612", "0"): date(2027, 1, 15),
}
PERIODOS_2026 = [f"2026{mes:02d}" for mes in range(1, 13)]
DIGITOS = list("0123456789")


def test_las_dos_tablas_traen_el_ano_entero_con_la_fuente_de_su_anexo():
    """Los dos cronogramas salen de la MISMA resolución, un anexo cada uno, y cada fuente lo dice."""
    tabla = catalogos.cronogramas_de_vencimiento()
    assert catalogos.anios_con_cronograma() == ["2026"]
    for cronograma in catalogos.CRONOGRAMAS:
        assert "281-2022" in tabla["fuentes"][cronograma]
        assert sorted(tabla["anios"]["2026"][cronograma]) == PERIODOS_2026


@pytest.mark.parametrize("clave,esperada", sorted(ANCLAS_DECLARACION.items()))
def test_la_declaracion_vence_cuando_dice_el_anexo_i(clave, esperada):
    periodo, digito = clave
    assert catalogos.vence_la_declaracion(periodo, digito) == esperada


@pytest.mark.parametrize("clave,esperada", sorted(ANCLAS_ATRASO.items()))
def test_el_registro_se_atrasa_hasta_donde_dice_el_anexo_ii(clave, esperada):
    periodo, digito = clave
    assert catalogos.vence_el_registro(periodo, digito) == esperada


def test_el_registro_cierra_antes_que_la_declaracion():
    """La propiedad que ordena los dos anexos: el registro se cierra para poder declarar, así que su fecha máxima de
    atraso nunca es posterior a la del vencimiento de la declaración. Comprobado en los 12 × 11 casos del año — si
    alguna vez se cruzan, o se copió una tabla en el sitio de la otra, o SUNAT cambió de criterio."""
    for periodo in PERIODOS_2026:
        for digito in DIGITOS:
            assert catalogos.vence_el_registro(periodo, digito) <= catalogos.vence_la_declaracion(periodo, digito)
        assert (catalogos.vence_el_registro(periodo, "0", buen_contribuyente=True)
                <= catalogos.vence_la_declaracion(periodo, "0", buen_contribuyente=True))


def test_el_vencimiento_cae_en_el_mes_siguiente_al_periodo():
    """Un mes se declara al mes siguiente, y el de diciembre en enero del año que viene. Caza un año mal copiado,
    que es el error que no se ve leyendo la tabla."""
    for periodo in PERIODOS_2026:
        anio, mes = int(periodo[:4]), int(periodo[4:])
        siguiente = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        for vence in (catalogos.vence_la_declaracion, catalogos.vence_el_registro):
            fecha = vence(periodo, "0")
            assert (fecha.year, fecha.month) == siguiente, f"{periodo} vence en {fecha}"


def test_los_digitos_que_el_anexo_agrupa_vencen_el_mismo_dia():
    """El anexo agrupa los dígitos de dos en dos —2 y 3, 4 y 5, 6 y 7, 8 y 9— y aquí están abiertos los diez, que es
    como llega un RUC. Abrirlos es lo que evita que cada ERP repita el agrupamiento y alguno lo haga mal; este test
    comprueba que al abrirlos no se desalineó ninguna columna."""
    for periodo in PERIODOS_2026:
        for vence in (catalogos.vence_la_declaracion, catalogos.vence_el_registro):
            for par in ("23", "45", "67", "89"):
                assert vence(periodo, par[0]) == vence(periodo, par[1]), f"{periodo}: {par} no coinciden"
            assert vence(periodo, "0") != vence(periodo, "1"), f"{periodo}: el 0 y el 1 no van juntos en el anexo"


def test_el_dia_crece_con_el_digito_y_el_buen_contribuyente_va_al_final():
    """La forma del anexo: el vencimiento avanza con el último dígito del RUC, y los buenos contribuyentes y las
    UESP van después de todos, que es el plazo adicional que reconoce su régimen."""
    for periodo in PERIODOS_2026:
        for vence in (catalogos.vence_la_declaracion, catalogos.vence_el_registro):
            fechas = [vence(periodo, d) for d in DIGITOS]
            assert fechas == sorted(fechas), f"{periodo}: el día no crece con el dígito"
            assert vence(periodo, "9", buen_contribuyente=True) >= fechas[-1]


def test_un_ano_que_no_esta_se_niega_diciendo_cuales_conoce():
    """La única tabla del motor que envejece, y por eso no calcula: la resolución fija el cronograma en días
    hábiles, y derivar un año pediría el calendario de feriados y de días no laborables, que cambia por decreto.
    Mejor negarse que inventar una fecha de vencimiento."""
    with pytest.raises(catalogos.SinCronograma, match="2026"):
        catalogos.vence_la_declaracion("202701", "3")
    with pytest.raises(catalogos.SinCronograma, match="2026"):
        catalogos.vence_el_registro("202512", "3")


def test_lo_que_no_es_un_digito_de_ruc_se_niega():
    with pytest.raises(catalogos.SinCronograma, match="último dígito"):
        catalogos.vence_la_declaracion("202609", "x")


def test_el_ruc_entero_vale_igual_que_su_ultimo_digito():
    """Se acepta el RUC completo y se usa su último dígito: quien integra tiene el RUC, no el dígito suelto."""
    assert (catalogos.vence_la_declaracion("202609", "20601234567")
            == catalogos.vence_la_declaracion("202609", "7"))
    assert catalogos.vence_la_declaracion("202609", 7) == catalogos.vence_la_declaracion("202609", "7")


def test_cada_llamada_devuelve_una_copia_y_sale_por_la_fachada():
    primera = catalogos.cronogramas_de_vencimiento()
    primera["anios"]["2026"]["declaracion"]["202601"]["0"] = "1999-01-01"
    assert catalogos.cronogramas_de_vencimiento()["anios"]["2026"]["declaracion"]["202601"]["0"] == "2026-02-16"
    assert api.cronogramas_de_vencimiento() == catalogos.cronogramas_de_vencimiento()
