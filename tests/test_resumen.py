"""`resumen` y `por_cuenta`: cuánto es un libro y en qué cuentas cayó.

Un caso por cada cosa que se puede equivocar **en silencio**, que en un resumen es casi todo: una cifra
mal sumada cuadra consigo misma y nadie la audita. El caso que trajo estas dos funciones al motor es el
mejor ejemplo: la primera aplicación que las escribió se quedó con el `07` donde el motor dice
`("07", "87")`, así que una nota de crédito de no domiciliado le sumaba en vez de restarle, y su total
cuadraba con su propia tabla.
"""
from __future__ import annotations

import pytest

from contaperu import api, resumen, validar
from contaperu.modelo import Comprobante, Libro

LIBRO = {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608", "tipo": "compra"}
FACTURA = {"tipo_cp": "01", "serie": "E001", "numero": "871", "fecha_emision": "2026-08-10",
           "contraparte_doc": "20602222226", "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
           "base_gravada": "1000.00", "igv": "180.00", "total": "1180.00"}


def cs(*comprobantes: dict) -> list[Comprobante]:
    return [Comprobante.de_dict(c) for c in comprobantes]


def doc(*comprobantes: dict, **libro) -> dict:
    return {"open_accounting": "1.0", "libro": dict(LIBRO, **libro), "comprobantes": list(comprobantes)}


# ── Lo que suma y lo que no ──────────────────────────────────────────────────────────────────

def test_una_nota_de_credito_resta_y_la_de_no_domiciliado_tambien():
    """**El caso que trajo esta función al motor.** El `87` es una nota de crédito de no domiciliado, y
    quien copia la regla se queda con el `07` porque es la que ve todos los días."""
    for tipo_cp in ("07", "87"):
        r = resumen.del_libro(cs(FACTURA, dict(FACTURA, numero="872", tipo_cp=tipo_cp,
                                               base_gravada="100.00", igv="18.00", total="118.00")))
        assert r["totales"]["PEN"] == {"base_gravada": "900.00", "igv": "162.00",
                                       "total": "1062.00", "sumados": 2}, tipo_cp
    # Y una nota de DÉBITO suma, que es lo que la hace la hermana y no la misma cosa.
    r = resumen.del_libro(cs(FACTURA, dict(FACTURA, numero="873", tipo_cp="08",
                                           base_gravada="100.00", igv="18.00", total="118.00")))
    assert r["totales"]["PEN"]["total"] == "1298.00"


def test_dos_monedas_no_se_suman_en_ninguna_clave():
    """Convertir dentro de un resumen sería una cifra nueva sin caso (descarte declarado del estándar), y
    sumar importes nominales de dos monedas no da ningún total. Así que no hay dónde leerlo mal."""
    r = resumen.del_libro(cs(FACTURA, dict(FACTURA, numero="872", moneda="USD", tipo_cambio="3.750",
                                           base_gravada="200.00", igv="36.00", total="236.00")))
    assert list(r["totales"]) == ["PEN", "USD"], "soles primero, que es como se lee un total peruano"
    assert r["totales"]["USD"] == {"base_gravada": "200.00", "igv": "36.00", "total": "236.00", "sumados": 1}
    # Ni una clave fuera de las monedas: si algún día apareciera un «total general», sería una conversión.
    assert all(len(m) == 3 for m in r["totales"]), r["totales"]


def test_lo_excluido_y_lo_duplicado_se_cuentan_y_no_suman():
    """Y se cuentan **aparte**, porque son dos cosas distintas: una la apartó el contador y la otra es una
    copia. Los cuatro números no se solapan y suman `recibidos`, así que nadie tiene que restar dos claves
    para obtener la tercera — que es justo el error que este recuento viene a quitar."""
    r = resumen.del_libro(cs(FACTURA,
                             dict(FACTURA, numero="872", total="999.00", excluida=True),
                             dict(FACTURA, numero="873", total="888.00", estado="duplicada")))
    assert r["recuento"] == {"recibidos": 3, "excluidos": 1, "duplicados": 1, "sumados": 1}
    assert r["recuento"]["recibidos"] == sum(r["recuento"][k] for k in ("excluidos", "duplicados", "sumados"))
    assert r["totales"]["PEN"]["total"] == "1180.00"


def test_un_libro_sin_nada_que_sumar_no_tiene_monedas():
    """No un cero en soles: **ninguna moneda**. Un cero en PEN diría que hubo soles, y no hubo nada."""
    r = resumen.del_libro(cs(dict(FACTURA, excluida=True)))
    assert r["totales"] == {} and r["recuento"] == {"recibidos": 1, "excluidos": 1, "duplicados": 0,
                                                   "sumados": 0}
    assert resumen.del_libro([])["totales"] == {}


def test_los_centimos_no_se_pierden():
    """`Decimal` de punta a punta: en coma flotante, tres importes de un céntimo dan 0.030000000000000002."""
    r = resumen.del_libro(cs(dict(FACTURA, base_gravada="0.01", igv="0.01", total="0.02"),
                             dict(FACTURA, numero="872", base_gravada="0.01", igv="0.01", total="0.02"),
                             dict(FACTURA, numero="873", base_gravada="0.01", igv="0.01", total="0.02")))
    assert r["totales"]["PEN"] == {"base_gravada": "0.03", "igv": "0.03", "total": "0.06", "sumados": 3}


def test_el_resumen_no_valida_y_lo_dice():
    """Quien marca una fila como duplicada es `revisar`, que necesita las claves de los otros periodos. Si
    esto validara, el mismo documento daría cifras distintas según lo hubieran revisado antes o no."""
    dos_iguales = cs(FACTURA, dict(FACTURA))
    assert resumen.del_libro(dos_iguales)["recuento"]["sumados"] == 2, "sin revisar, las dos suman"

    revisados = cs(FACTURA, dict(FACTURA))
    validar.revisar(revisados, Libro(**{k: v for k, v in LIBRO.items()}))
    r = resumen.del_libro(revisados)
    assert r["recuento"] == {"recibidos": 2, "excluidos": 0, "duplicados": 1, "sumados": 1}


def test_el_resumen_es_del_libro_y_no_de_un_destino():
    """Un recibo por honorarios no viaja en el TXT del SIRE, y **sí está en el libro**. Por eso esto no
    recibe driver: lo que iría a un destino concreto ya lo dice `diagnosticar`, y son dos cifras distintas
    a propósito."""
    honorarios = dict(FACTURA, tipo_cp="02", numero="874", base_gravada="0", igv="0", total="500.00",
                      retencion="40.00")
    r = resumen.del_libro(cs(FACTURA, honorarios))
    assert r["recuento"]["sumados"] == 2 and r["totales"]["PEN"]["total"] == "1680.00"


# ── Agrupado por contraparte ─────────────────────────────────────────────────────────────────

def test_agrupa_por_documento_y_no_por_nombre():
    """El mismo RUC llega escrito de tres maneras según quién lo leyera —un XML, un modelo, la propuesta
    del SIRE—, así que por el nombre saldría partido en tres y el informe diría que le compras poco a
    cada uno. La etiqueta es el nombre **más reciente** que trajo alguna de sus filas."""
    r = resumen.del_libro(cs(dict(FACTURA, contraparte_nombre="FERRETERIA DEL SUR S.A.C."),
                             dict(FACTURA, numero="872", contraparte_nombre="FERRETERIA DEL SUR SAC",
                                  base_gravada="500.00", igv="90.00", total="590.00"),
                             dict(FACTURA, numero="873", contraparte_doc="20512333797",
                                  contraparte_nombre="OTRA COSA SAC", base_gravada="4000.00",
                                  igv="720.00", total="4720.00")),
                          agrupar_por="contraparte")
    assert r["agrupado_por"] == "contraparte" and len(r["grupos"]) == 2
    # De más a menos, que es la pregunta que se hace («a quién le compré más»).
    primero, segundo = r["grupos"]
    assert primero["clave"] == "20512333797" and primero["totales"]["PEN"]["total"] == "4720.00"
    assert segundo["clave"] == "20602222226" and segundo["totales"]["PEN"]["total"] == "1770.00"
    assert segundo["etiqueta"] == "FERRETERIA DEL SUR SAC", "el nombre más reciente de sus filas"
    assert segundo["recuento"]["sumados"] == 2


def test_una_contraparte_sin_nada_que_sumar_no_es_un_grupo():
    """Un proveedor cuyas dos filas están excluidas no es un proveedor de ese mes: es ruido en la lista."""
    r = resumen.del_libro(cs(FACTURA, dict(FACTURA, numero="872", contraparte_doc="20512333797",
                                           excluida=True)), agrupar_por="contraparte")
    assert [g["clave"] for g in r["grupos"]] == ["20602222226"]


def test_sin_agrupar_no_hay_grupos_y_la_forma_es_la_misma():
    """La misma estructura con y sin agrupación: un agente no tiene que aprender dos."""
    r = resumen.del_libro(cs(FACTURA))
    assert r["agrupado_por"] == "" and r["grupos"] == []
    con = resumen.del_libro(cs(FACTURA), agrupar_por="contraparte")
    assert set(con["grupos"][0]) == {"clave", "etiqueta", "recuento", "totales"}
    assert con["grupos"][0]["totales"] == r["totales"], "el grupo único suma lo mismo que el libro"


def test_una_agrupacion_que_no_existe_se_niega_y_dice_las_que_hay():
    with pytest.raises(ValueError, match="No sé agrupar por"):
        resumen.del_libro(cs(FACTURA), agrupar_por="mes")


# ── El pre-mayor ─────────────────────────────────────────────────────────────────────────────

LINEAS = [
    {"cuenta": "631101", "rol": "principal", "clase": "gasto", "debe_haber": "D", "importe": "1000.00",
     "moneda": "PEN"},
    {"cuenta": "401111", "rol": "igv", "clase": "pasivo", "debe_haber": "D", "importe": "180.00",
     "moneda": "PEN"},
    {"cuenta": "421201", "rol": "tercero", "clase": "pasivo", "debe_haber": "H", "importe": "1080.00",
     "moneda": "PEN"},
    {"cuenta": "421201", "rol": "detraccion_tercero", "clase": "pasivo", "debe_haber": "H",
     "importe": "100.00", "moneda": "PEN"},
]


def test_una_cuenta_con_dos_papeles_los_dice_los_dos():
    """Con una detracción, la cuenta por pagar sale DOS veces en el mismo asiento: como tercero y como la
    parte que va al Banco de la Nación. Quedarse con el primer papel esconde el segundo —el importe está,
    el papel no— y en una lista de diez cuentas eso no se nota."""
    r = resumen.por_cuenta(LINEAS)
    por_cuenta = {c["cuenta"]: c for c in r["cuentas"]}
    assert por_cuenta["421201"]["roles"] == ["detraccion_tercero", "tercero"]
    assert por_cuenta["421201"]["lineas"] == 2
    assert por_cuenta["421201"]["por_moneda"]["PEN"] == {"debe": "0.00", "haber": "1180.00"}
    assert [c["cuenta"] for c in r["cuentas"]] == ["401111", "421201", "631101"], "por código de cuenta"


def test_el_cuadre_del_pre_mayor_es_el_mismo_que_el_de_cuadrar():
    """No se suma dos veces: el pre-mayor le pide el cuadre a `partida_doble`, la misma función que
    `cuadrar`. Así los dos no pueden discrepar por construcción, sin necesidad de un test que lo vigile
    — y este test es la prueba de que se hizo así y no a mano."""
    r = resumen.por_cuenta(LINEAS)
    assert r["cuadre"] == api.cuadrar(LINEAS)
    assert r["cuadre"]["cuadra"] is True and r["cuadre"]["debe"] == r["cuadre"]["haber"] == "1180.00"


def test_el_cuadre_por_moneda_dice_lo_que_el_global_no_puede():
    """Dos monedas cuyos descuadres se compensan salen **cuadradas en el total** y descuadradas cada una.
    Es la única razón por la que esa clave existe."""
    mezcla = [
        {"cuenta": "631101", "debe_haber": "D", "importe": "100.00", "moneda": "PEN"},
        {"cuenta": "421201", "debe_haber": "H", "importe": "90.00", "moneda": "PEN"},
        {"cuenta": "631101", "debe_haber": "H", "importe": "10.00", "moneda": "USD"},
    ]
    r = resumen.por_cuenta(mezcla)
    assert r["cuadre"]["cuadra"] is True, "en el total se compensan"
    assert r["por_moneda"]["PEN"]["cuadra"] is False and r["por_moneda"]["PEN"]["diferencia"] == "10.00"
    assert r["por_moneda"]["USD"]["cuadra"] is False
    assert list(r["por_moneda"]) == ["PEN", "USD"]


def test_el_pre_mayor_acepta_lo_que_devuelve_generar_asiento():
    """La entrada es la salida de `generar_asiento`, sin tocar nada por el camino."""
    # La cuenta llega en la imputación y por `id_externo`, que es donde vive desde la 3.0: en el
    # comprobante el motor ya no la admite.
    armado = api.generar_asiento(doc(dict(FACTURA, id_externo="fila-8")), driver="asiento_neutral",
                                 imputacion={"fila-8": {"cuenta_contable": "631101"}})
    r = resumen.por_cuenta(armado["asiento"])
    assert r["cuadre"] == api.cuadrar(armado["asiento"])
    assert {c["cuenta"] for c in r["cuentas"]} == {ln["cuenta"] for ln in armado["asiento"]}
    assert all(c["roles"] for c in r["cuentas"]), "el papel de cada línea lo pone el motor al armarla"


# ── Por la api, que es por donde entra cualquiera ────────────────────────────────────────────

def test_por_la_api_el_resumen_dice_de_que_libro_es():
    """Un total sin decir de qué RUC y de qué mes es una trampa. Y es lo que impide que alguien cosa doce
    de estos y los presente como un resumen anual sin que se vea: cada uno dice su periodo."""
    r = api.resumen(doc(FACTURA))
    assert r["libro"] == {"ruc": "20601111111", "periodo": "202608", "tipo": "compra"}
    assert r["totales"]["PEN"]["total"] == "1180.00"
    assert api.resumen(doc(FACTURA), agrupar_por="contraparte")["grupos"][0]["clave"] == "20602222226"
