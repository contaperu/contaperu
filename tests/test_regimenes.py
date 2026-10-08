"""El régimen tributario del contribuyente, como datos: qué libros le obliga a llevar y cómo tributa.

El caso que motiva la tabla (7-oct-2026): para decirle a un contribuyente del Régimen Especial cuánto paga hace
falta la tasa del art. 120, y para decirle qué libros lleva, el art. 124 — y ninguno de los dos estaba en el motor.
Entran como datos y no como código porque la pregunta «¿qué libros estoy obligado a llevar?» se hace SIN un
documento delante, al dar de alta una empresa: haría falta un libro para preguntar por los libros.

Un test por regla, y cada uno cita su artículo en el docstring: si al cambiar un número de la tabla ninguno cae,
falta el test. Los dos primeros son los que protegen la regla de la casa —ninguna regla contable sin fuente— y el
segundo es el que de verdad importa, porque es por donde entraría mañana una tasa de memoria.
"""
from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from contaperu import api, catalogos


def tabla() -> dict:
    return catalogos.regimenes_tributarios()


def test_la_tabla_vive_en_el_motor_con_su_fuente():
    """La tabla es del motor y dice de dónde sale. Los cuatro regímenes se declaran: el que no tiene su norma leída
    dice que está pendiente y qué hay que leer, en vez de faltar sin explicación.

    Igualdad de conjuntos y no un conteo, como en `test_catalogos.py`: un régimen nuevo pone esto rojo y hay que
    decidirlo a mano, que es justo lo que se quiere."""
    del_motor = tabla()
    assert del_motor["fuente"].strip()
    assert set(del_motor["regimenes"]) == {"especial", "general", "mype_tributario", "nuevo_rus"}
    assert [r for r, d in del_motor["regimenes"].items() if d["estado"] == "vigente"] == ["especial"]
    for nombre, regimen in del_motor["regimenes"].items():
        if regimen["estado"] == "pendiente_de_fuente":
            assert regimen["por_que"].strip(), f"{nombre} no dice qué norma hay que leer"


def test_un_regimen_vigente_sin_cita_no_entra():
    """La regla que manda: ninguna regla contable sin fuente (`ARQUITECTURA.md`). Se le quita la cita a cada uno de
    los tres bloques del Régimen Especial, por separado, y los tres tienen que detener la carga: la tasa cita el
    art. 120, los libros el 124 y los topes el 118, así que una cita por tabla no bastaría."""
    for bloque in catalogos.REGLAS_DE_REGIMEN:
        mutada = copy.deepcopy(tabla())
        mutada["regimenes"]["especial"][bloque].pop("cita")
        with pytest.raises(catalogos.CatalogoInvalido, match=bloque):
            catalogos.validar_regimenes(mutada)


def test_un_regimen_pendiente_que_trae_un_valor_tampoco_entra():
    """El agujero que este test tapa: declarar el Régimen General «pendiente de fuente» y ponerle una tasa de todos
    modos. Sería la regla sin fuente entrando por la puerta de atrás, y sin esto nadie lo vería."""
    mutada = copy.deepcopy(tabla())
    mutada["regimenes"]["general"]["pago_a_cuenta"] = {"tasa": "1.5"}
    with pytest.raises(catalogos.CatalogoInvalido, match="pendiente de fuente"):
        catalogos.validar_regimenes(mutada)

    sin_porque = copy.deepcopy(tabla())
    sin_porque["regimenes"]["general"].pop("por_que")
    with pytest.raises(catalogos.CatalogoInvalido, match="por_que"):
        catalogos.validar_regimenes(sin_porque)


def test_un_estado_que_no_existe_no_entra():
    """Solo dos estados, y el tercero que alguien escriba no pasa en silencio: si pasara, un régimen con un estado
    raro se saltaría las dos comprobaciones de arriba."""
    mutada = copy.deepcopy(tabla())
    mutada["regimenes"]["especial"]["estado"] = "casi"
    with pytest.raises(catalogos.CatalogoInvalido, match="estado desconocido"):
        catalogos.validar_regimenes(mutada)


def test_la_cuota_del_rer_es_el_uno_y_medio_por_ciento_cancelatorio():
    """Ley del Impuesto a la Renta, art. 120 inciso a): «una cuota ascendente a 1.5% … de sus ingresos netos
    mensuales provenientes de sus rentas de tercera categoría»; inciso b): el pago «tiene carácter cancelatorio».

    Cancelatorio es la mitad que se olvida: significa que la cuota mensual agota el impuesto de tercera categoría y
    no hay regularización anual. La tasa es TEXTO y la lee `Decimal`, como la de las detracciones."""
    pago = tabla()["regimenes"]["especial"]["pago_a_cuenta"]
    assert Decimal(pago["tasa"]) == Decimal("1.5")
    assert pago["cancelatorio"] is True
    assert pago["base"] == "ingresos_netos_mensuales_de_tercera_categoria"
    assert "120" in pago["cita"] and "1086" in pago["cita"]


def test_el_rer_lleva_dos_registros_y_la_cita_es_el_124():
    """Ley del Impuesto a la Renta, art. 124: «Los sujetos del presente Régimen están obligados a llevar un Registro
    de Compras y un Registro de Ventas de acuerdo con las normas vigentes sobre la materia».

    **Es el 124 y no el 124-A**, y por eso el test lo comprueba en el texto de la cita: el 124-A es la declaración
    jurada anual del inventario, y confundirlos haría que el motor afirmara una obligación que no es esa. Dos
    registros y nada más —ni Diario, ni Mayor, ni Inventarios y Balances— es lo que hace que el motor le sirva al
    RER sin plan de cuentas y sin asiento."""
    libros = tabla()["regimenes"]["especial"]["libros_obligatorios"]
    assert libros["codigos_ple"] == ["080100", "140100"]
    assert "art. 124:" in libros["cita"]
    assert "124-A" in libros["nota"], "la nota tiene que avisar de la confusión con el 124-A"


def test_los_libros_obligatorios_son_codigos_de_libro_que_el_motor_publica():
    """Los libros se nombran por su código del PLE, que el motor ya publica con su fuente, y no por `libro.tipo`:
    ese catálogo del estándar dice lo que el motor ESCRIBE —venta o compra—, no lo que la ley obliga a llevar.

    Un código inventado haría que la tabla mintiera y nadie lo notaría: es el mismo guardián que
    `test_los_codigos_de_detraccion_de_concar_son_de_la_tabla_del_motor`."""
    del_ple = set(catalogos.campos_del_ple()["codigos_de_libro"]["codigos"])
    for nombre, regimen in tabla()["regimenes"].items():
        citados = set((regimen.get("libros_obligatorios") or {}).get("codigos_ple") or [])
        sobran = sorted(citados - del_ple)
        assert not sobran, f"{nombre} cita códigos de libro que el motor no publica: {sobran}"


def test_cada_llamada_devuelve_una_copia():
    """Un consumidor que mute la respuesta no envenena el proceso, como en `detracciones.tabla_del_motor()`."""
    primera = tabla()
    primera["regimenes"]["especial"]["pago_a_cuenta"]["tasa"] = "99"
    assert tabla()["regimenes"]["especial"]["pago_a_cuenta"]["tasa"] == "1.5"


def test_sale_por_la_fachada():
    """Y por la fachada dice lo mismo que el núcleo: es lo que leen las tres puertas."""
    assert api.regimenes_tributarios() == catalogos.regimenes_tributarios()
