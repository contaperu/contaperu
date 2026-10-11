"""El `rol` de una línea se DERIVA de los datos que trae, y es lo único que hay desde la 10.0.

El campo salió del estándar en la 2.0: era una etiqueta para los destinos —ningún estándar abierto del asiento lo
tiene; el único precedente es Odoo, con dos vocabularios distintos— y el núcleo no decidía nada por ella. Lo que
queda es la regla, en `drivers/kit/rol.py`, y este fichero es lo que la sostiene.

**Lo que este test medía en la 9.2 y ya no puede medir.** Mientras el motor emitía el campo, aquí se exigía
`rol_de(linea, libro) == linea.rol` en cada una de las 324 líneas que produce la batería, y pasaba. Esa es la
prueba de que la derivación es fiel, y está hecha: `fixtures/snapshot/papeles_derivados.json` la **lleva adelante**
congelando lo que la regla responde hoy, que es exactamente lo que el motor escribía entonces.

Regenerarlo es una decisión, no un trámite: si un papel cambia, cambia a propósito y se dice.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_rol_derivado as t; t.regenerar()"
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from contaperu import api
from contaperu.drivers.kit.rol import RolNoDerivable, rol_de
from contaperu.modelo import RASGOS
from util import GOLDEN, IMPUTACIONES, comprobante, imputando

PAPELES = Path(__file__).parent / "fixtures" / "snapshot" / "papeles_derivados.json"

# Los mismos tres documentos que caracteriza `test_caracterizacion.py`, con su imputación: entre ellos pasan por
# dólares, notas de crédito, detracción, honorarios, boleta, reparto y extemporáneo.
IMPUTACION_CASOS: dict[str, dict] = {
    **{f"c{n:02d}": {"cuenta_contable": "631101", "centro_costo": "OBRA01"} for n in range(1, 13)},
    "c07": {"cuenta_contable": "632101", "centro_costo": "OBRA01"},
    "c08": {"cuenta_contable": "632101", "centro_costo": "OBRA01"},
    "c11": {"reparto": [{"importe": "600.00", "cuenta_contable": "636301", "centro_costo": "SISTEMAS"},
                        {"importe": "400.00", "cuenta_contable": "632201", "centro_costo": "DESARROLLO"}]},
}
SIN_CENTROS = {"usa_centros_costo": False}
DOCUMENTOS = (("compras_202601.json", SIN_CENTROS, None, "659999"),
              ("ventas_202512.json", SIN_CENTROS, None, "701101"),
              ("casos_202608.json", {}, IMPUTACION_CASOS, None))
# Los cuatro drivers que producen líneas con los dos vocabularios: tres legacy y el neutral del estándar. La cuenta,
# el sub-diario y el correlativo cambian entre ellos, y el papel **no puede** depender de ninguno de los tres.
DRIVERS = ("concar", "csv", "starsoft", "asiento_contable")


def asiento_de(archivo: str, config: dict, imputacion: dict | None, cuenta: str | None, driver: str) -> list[dict]:
    doc = json.loads((GOLDEN / archivo).read_text(encoding="utf-8"))
    if cuenta:
        doc = imputando(doc, cuenta)
    # `incluir_observados` a propósito: los documentos de SUNAT traen comprobantes con observaciones que bloquean,
    # y sus líneas son líneas igual. Lo que se barre aquí es el asiento entero, no el mes exportable.
    return api.generar_asiento(doc, driver=driver, configuracion=config, imputacion=imputacion,
                               incluir_observados=True)["asiento"]


def _papeles() -> dict[str, list]:
    """Por documento, el papel derivado de cada línea con su cuenta y su sentido, para que el diff se pueda leer."""
    salida = {}
    for archivo, config, imputacion, cuenta in DOCUMENTOS:
        tipo = json.loads((GOLDEN / archivo).read_text(encoding="utf-8"))["libro"]["tipo"]
        salida[archivo] = [[ln["cuenta"], ln["debe_haber"], rol_de(ln, tipo)]
                           for ln in asiento_de(archivo, config, imputacion, cuenta, "csv")]
    return salida


def regenerar() -> None:
    PAPELES.write_text(json.dumps(_papeles(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"escrito {PAPELES}")


def test_los_papeles_de_un_mes_no_cambian_sin_que_se_decida():
    """Los papeles que la regla responde sobre tres meses reales, congelados.

    Nacieron medidos: en la 9.2 este mismo barrido exigía la igualdad con el `rol` que el motor escribía, en las
    324 líneas de los cuatro drivers, y pasaba. El campo ya no está, así que lo que se vigila es que la respuesta
    no se mueva — y los seis papeles están todos cubiertos, que es lo que hace que el barrido mida algo."""
    congelado = json.loads(PAPELES.read_text(encoding="utf-8"))
    hoy = _papeles()
    assert set(hoy) == set(congelado)
    for archivo in sorted(congelado):
        assert hoy[archivo] == [list(fila) for fila in congelado[archivo]], archivo

    from contaperu.asiento import ROLES_DEL_MOTOR
    vistos = {fila[2] for filas in hoy.values() for fila in filas}
    assert vistos == set(ROLES_DEL_MOTOR), (sorted(vistos), sorted(ROLES_DEL_MOTOR))
    assert sum(len(f) for f in hoy.values()) >= 81, "el barrido se encogió"


def test_el_papel_no_depende_del_destino():
    """Los cuatro drivers dan la MISMA secuencia de papeles para el mismo mes.

    Importa porque la cuenta, el sub-diario y el correlativo sí cambian entre ellos —STARSOFT numera a ocho
    dígitos, el neutral deja el sub-diario vacío—, y un papel que dependiera de eso sería un papel del destino y no
    de la operación. Es lo que la derivación promete al no mirar ni la cuenta ni el sub-diario."""
    for archivo, config, imputacion, cuenta in DOCUMENTOS:
        tipo = json.loads((GOLDEN / archivo).read_text(encoding="utf-8"))["libro"]["tipo"]
        por_driver = {d: [rol_de(ln, tipo) for ln in asiento_de(archivo, config, imputacion, cuenta, d)]
                      for d in DRIVERS}
        iguales = {tuple(v) for v in por_driver.values()}
        assert len(iguales) == 1, (archivo, {d: v[:6] for d, v in por_driver.items()})


# ── Los casos que el barrido no trae, y que son los que ejercitan la inversión ─────────────────────────────────

def _asiento(c, tipo: str, config: dict | None = None) -> list[dict]:
    """El asiento de UN comprobante, por la fachada, con el libro del tipo que se pida."""
    doc = {"open_accounting": api.OPEN_ACCOUNTING,
           "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608",
                     "tipo": tipo},
           "comprobantes": [c.a_dict() if hasattr(c, "a_dict") else c]}
    # La imputación de un comprobante de prueba va por el argumento `imputacion`, que es por donde la recibe la
    # fachada: `util.comprobante()` la aparta en `IMPUTACIONES` por `id_externo`. Se le pasa SOLO la suya, porque
    # la fachada rechaza —con razón— una imputación que hable de un documento que no está.
    suya = {c.id_externo: IMPUTACIONES[c.id_externo]} if getattr(c, "id_externo", "") in IMPUTACIONES else None
    return api.generar_asiento(doc, driver="csv", configuracion=config or {}, imputacion=suya,
                               incluir_observados=True)["asiento"]


def _nc_de_venta():
    return comprobante(tipo_cp="07", serie="F001", numero="9", fecha_emision="2026-08-20",
                       contraparte_doc="20607777773", contraparte_nombre="CLIENTE SAC", moneda="PEN",
                       base_gravada="100", igv="18", total="118", cuenta_contable="701101",
                       ref_fecha="2026-07-31", ref_tipo_cp="01", ref_serie="F001", ref_numero="257")


def test_la_nota_de_credito_de_una_venta_invierte_el_lado_del_tercero():
    """El barrido trae la nota de crédito de COMPRAS y no la de ventas. Es el otro lado del mismo término.

    Importa porque en una nota de crédito los dos sentidos se cambian: el cliente, que en una venta va al Debe,
    aquí va al Haber. Sin el término de la inversión se derivaría como `recorte`."""
    lineas = _asiento(_nc_de_venta(), "venta")
    assert [rol_de(ln, "venta") for ln in lineas] == ["principal", "impuesto", "tercero"]
    lado = {rol_de(ln, "venta"): ln["debe_haber"] for ln in lineas}
    assert lado["tercero"] == "H", "una NC de venta abona al cliente, al revés que una factura"


def test_una_nota_de_credito_de_compra_con_detraccion_deriva_sus_cinco_lineas():
    """El caso que junta los dos términos finos: los sentidos invertidos **y** el par recorte/detracción.

    Es el que hace falta de verdad, porque el `recorte` es la única línea que se separa del `principal` por llevar
    `contraparte_doc`, y con los sentidos cambiados cae al lado contrario del que cae siempre."""
    nc = comprobante(tipo_cp="07", serie="F001", numero="11", fecha_emision="2026-08-20",
                     contraparte_doc="20602222226", contraparte_nombre="PROVEEDOR SAC", moneda="PEN",
                     base_gravada="1000", igv="180", total="1180", cuenta_contable="631101",
                     detraccion={"codigo": "037", "porcentaje": 12},
                     ref_fecha="2026-07-31", ref_tipo_cp="01", ref_serie="F001", ref_numero="257")
    lineas = _asiento(nc, "compra")
    papeles = [rol_de(ln, "compra") for ln in lineas]
    assert sorted(papeles) == ["detraccion", "impuesto", "principal", "recorte", "tercero"], papeles
    # La comprobación que da sentido al caso: con los sentidos invertidos, el tercero va al Debe y el recorte al
    # Haber — justo al revés que en una compra normal.
    lado = dict(zip(papeles, (ln["debe_haber"] for ln in lineas)))
    assert lado["tercero"] == "D" and lado["recorte"] == "H", lado


# ── Los dos términos de carga: si se quitan, la regla se equivoca ──────────────────────────────────────────────

def test_sin_el_termino_de_la_inversion_la_nota_de_credito_sale_mal(monkeypatch):
    """La mutación del término que más fácil se borra, automatizada: se vacía `TIPOS_INVIERTEN` y la nota de
    crédito tiene que salir MAL.

    Si alguien quita la inversión de `rol_de`, este test falla porque la respuesta deja de empeorar al vaciar la
    tabla. Es la forma de que una mutación no sobreviva sin que nadie la ejecute a mano."""
    from contaperu.drivers.kit import rol as modulo

    lineas = _asiento(_nc_de_venta(), "venta")
    del_cliente = next(ln for ln in lineas if rol_de(ln, "venta") == "tercero")

    monkeypatch.setattr(modulo, "TIPOS_INVIERTEN", frozenset())
    assert rol_de(del_cliente, "venta") == "recorte", \
        "la inversión dejó de ser de carga: la regla acierta sin ella, así que una de las dos está mal"


def test_el_cliente_de_una_boleta_es_un_tercero_aunque_no_lleve_documento():
    """El agujero que tenía la primera versión de la regla, convertido en test.

    Preguntaba por `contraparte_doc` ANTES que por el lado, y falló en una línea de las 324: el cliente de una
    **boleta**, que no lleva RUC porque es un consumidor final. El sentido no tiene ese agujero, y el orden de los
    tramos es por esto."""
    bv = comprobante(tipo_cp="03", serie="B001", numero="5003", fecha_emision="2026-08-09", moneda="PEN",
                     base_gravada="100", igv="18", total="118", cuenta_contable="701101")
    lineas = _asiento(bv, "venta")
    del_cliente = next(ln for ln in lineas if ln["cuenta"].startswith("12"))
    assert not del_cliente.get("contraparte_doc"), "si la boleta empieza a traer documento, este test no mide nada"
    assert rol_de(del_cliente, "venta") == "tercero"


def test_el_bloque_manda_sobre_el_lado():
    """El otro orden que importa: la retención y la detracción caen en el lado de la contraparte, así que si el
    tramo del lado fuera primero las llamaría `tercero`. Por eso el bloque se pregunta antes."""
    linea = {"cuenta": "401101", "debe_haber": "H", "importe": "100.00", "clase": "pasivo",
             "contraparte_doc": "20602222226", "retencion": {"codigo": "01", "categoria": "4"}}
    assert rol_de(linea, "compra") == "retencion", "el lado de esta línea es el del tercero en una compra"
    assert rol_de({**linea, "retencion": None}, "compra") == "tercero", "sin el bloque, el lado decide"


# ── Los libros que no declaran roles, y las formas en que se puede llamar ──────────────────────────────────────

def test_un_libro_sin_roles_declarados_no_tiene_nada_que_derivar():
    """Tesorería declara `roles=()` porque el motor no emite ni una línea suya. Pedir el papel de una de sus líneas
    no es un fallo de la regla: es una pregunta sin respuesta todavía, y se dice así."""
    assert RASGOS["tesoreria"].roles == ()
    with pytest.raises(RolNoDerivable) as e:
        rol_de({"cuenta": "104111", "debe_haber": "D", "importe": "100.00"}, "tesoreria")
    assert "compra" in str(e.value) and "venta" in str(e.value), "tiene que decir qué libros SÍ los declaran"


def test_acepta_la_linea_como_objeto_y_como_diccionario():
    """Las dos formas circulan: un driver recibe `LineaDiario` y un test o un ERP de fuera, diccionarios."""
    from datetime import date

    from contaperu.asiento import lineas_del_comprobante
    from contaperu.modelo import Libro

    c = comprobante(tipo_cp="01", serie="F001", numero="123", fecha_emision="2026-08-11",
                    contraparte_doc="20602222226", contraparte_nombre="PROVEEDOR SAC", moneda="PEN",
                    base_gravada="100", igv="18", total="118", cuenta_contable="631101")
    libro = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="compra")
    lineas = lineas_del_comprobante(c, {"imputaciones": IMPUTACIONES},
                                    (date(2026, 8, 1), date(2026, 8, 31)), "0001", libro=libro.rasgos)
    assert lineas, "sin líneas no se mide nada"
    for ln in lineas:
        assert rol_de(ln, libro) == rol_de(ln.a_dict(), libro.rasgos)
    assert [rol_de(ln, libro) for ln in lineas] == ["principal", "impuesto", "tercero"]
