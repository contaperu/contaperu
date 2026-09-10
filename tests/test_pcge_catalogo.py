"""El catálogo oficial del PCGE 2026.

Estos tests vigilan dos cosas distintas. Una, que el dato esté COMPLETO: el catálogo se extrae de
un PDF, y una extracción a medias no se nota mirándola por encima — se nota cuando alguien busca
una cuenta y no está. La otra, que consultar una cuenta que no está en la norma **no sea un
error**: el PCGE llega a cinco dígitos y las divisionarias las abre cada empresa.
"""
from __future__ import annotations

from contaperu import pcge
from contaperu.pcge import catalogo


def test_el_catalogo_esta_completo():
    """Los recuentos son la única forma de cazar una extracción que se dejó páginas.

    Las 77 cuentas madre no son un número redondo elegido a ojo: son las que suman los nueve
    elementos del cuadro de clasificación (10 + 10 + 10 + 10 + 7 + 10 + 8 + 9 + 3).
    """
    c = catalogo.cuentas()
    assert len(c) > 1500
    por_largo: dict[int, int] = {}
    for k in c:
        por_largo[len(k)] = por_largo.get(len(k), 0) + 1
    assert por_largo[2] == 77, "faltan cuentas madre: la extracción se dejó algo"
    assert por_largo[3] > 300 and por_largo[4] > 600 and por_largo[5] > 580


def test_ninguna_cuenta_queda_huerfana_ni_con_el_nombre_a_medias():
    """Dos fallos reales de la extracción, cada uno con su forma de delatarse.

    Las cuentas madre de nombre largo traen el código en su propia línea, en medio del nombre
    (`TRIBUTOS…` / `40` / `PENSIONES…`): sin tratarlo, desaparecen 14, 40, 44, 66 y 76 — y con
    ellas, sus hijas quedan sin madre. Y un nombre que se parte al saltar de página se queda
    colgando en «y» o en «de».
    """
    c = catalogo.cuentas()
    huerfanas = [k for k in c if len(k) > 2 and k[:-1] not in c]
    assert huerfanas == [], f"cuentas sin madre: {huerfanas[:5]}"
    colgando = [k for k, v in c.items() if v["nombre"].rstrip().endswith((" y", " de", " del", " en", " con", " la"))]
    assert colgando == [], f"nombres cortados: {colgando[:5]}"
    assert catalogo.nombre_de("40").endswith("SALUD POR PAGAR")
    assert catalogo.nombre_de("6093") == "Costos vinculados con las compras de materiales, suministros y repuestos"


def test_una_cuenta_que_no_esta_en_la_norma_resuelve_a_su_madre():
    """`603201` es la cuenta real de un constructor y NO está en el PCGE — no puede ser un error."""
    assert catalogo.existe("603201") is False
    r = catalogo.resolver("603201")
    assert r is not None and r["exacta"] is False
    assert r["codigo"] == "6032" and r["nombre"] == "Suministros"
    exacta = catalogo.resolver("706")
    assert exacta["exacta"] is True and exacta["nombre"] == "Descuentos concedidos por pronto pago"
    assert catalogo.resolver("99999") is None          # ni el elemento existe: está mal escrita
    assert catalogo.resolver("") is None


def test_cada_cuenta_trae_la_pagina_que_la_respalda():
    """Sin la página, discutir un nombre obliga a abrir el PDF otra vez."""
    c = catalogo.cuentas()
    assert all(isinstance(v["pagina"], int) and v["pagina"] > 0 for v in c.values())
    assert "PCGE 2026" in catalogo.cargar()["fuente"]


def test_la_busqueda_ignora_tildes_y_mayusculas():
    """Quien escribe «gestion» espera encontrar «Otros gastos de gestión»."""
    codigos = [x["codigo"] for x in pcge.buscar("GESTION")]
    assert "65" in codigos and "659" in codigos
    assert pcge.buscar("") == []
    assert len(pcge.buscar("cuenta", limite=3)) == 3


def test_el_catalogo_no_es_la_tabla_de_equivalencias():
    """Dos cosas distintas viven en `contaperu.pcge` y conviene que nadie las confunda.

    El catálogo tiene los 1615 nombres de la norma. La tabla de adaptación está **vacía a
    propósito** —este proyecto nace en 2026, no hay plan viejo del que traducir— y esa es una
    decisión, no una tarea pendiente: si algún día se llena, será con la cita al lado de cada
    mapeo. Que el catálogo trajera datos NO debe leerse nunca como que la tabla ya trae reglas.
    """
    assert catalogo.cuentas()                       # el catálogo, lleno
    mapeos, _ = pcge.cargar()                       # la tabla, vacía
    assert mapeos == []
    lineas = [{"cuenta": "631101", "glosa": "Flete"}]
    salida, informe = pcge.adaptar(lineas)
    assert salida == lineas and informe.sin_tabla is True and informe.hubo_cambios is False
