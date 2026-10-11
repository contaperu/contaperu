"""El `rol` de una línea se puede DERIVAR de los datos que trae, en todas las líneas que la batería produce.

Es el test que sostiene el retiro del campo. Mientras el motor lo emita y un driver lo lea, el `rol` es un dato del
asiento y quitarlo es un rediseño; si la derivación acierta en **cada** línea, el campo es demostrablemente
redundante para un destino y retirarlo es una línea.

Y es la pregunta de arquitectura que hay detrás (John, 10-oct-2026): **el núcleo se está volviendo la base de un
ERP, y lo que existe para los sistemas de destino no puede vivir en él.** El `rol` lo inventamos nosotros —ningún
estándar abierto del asiento lo tiene; el único precedente es Odoo, con dos vocabularios distintos—, y sirve para
que CONCAR o STARSOFT encuentren la línea que su columna pide sin conocer la cuenta, que la elige cada empresa.

Lo que mide:

- el barrido de todo lo que la batería produce (`test_la_derivacion_reproduce_el_rol_de_cada_linea`);
- los dos casos que ese barrido NO tiene y que son justo los que ejercitan la inversión de sentidos;
- y que los dos términos finos de la regla son **de carga**: si se quitan, algo sale mal. Son los dos sitios donde
  la primera versión de la regla se equivocó.
"""
from __future__ import annotations

import json
import pytest

from contaperu import api
from contaperu.drivers.kit.rol import RolNoDerivable, rol_de
from contaperu.modelo import RASGOS
from util import GOLDEN, IMPUTACIONES, comprobante, imputando

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
# Los cuatro drivers que producen líneas con los dos vocabularios: tres legacy y el neutral del estándar. El rol es
# el mismo —lo pone el motor—, pero la cuenta, el sub-diario y el correlativo cambian, y la derivación no puede
# depender de ninguno de los tres.
DRIVERS = ("concar", "csv", "starsoft", "asiento_contable")


def asiento_de(archivo: str, config: dict, imputacion: dict | None, cuenta: str | None, driver: str) -> list[dict]:
    doc = json.loads((GOLDEN / archivo).read_text(encoding="utf-8"))
    if cuenta:
        doc = imputando(doc, cuenta)
    # `incluir_observados` a propósito: los documentos de SUNAT traen comprobantes con observaciones que bloquean,
    # y sus líneas son líneas igual. Lo que se barre aquí es el asiento entero, no el mes exportable.
    return api.generar_asiento(doc, driver=driver, configuracion=config, imputacion=imputacion,
                               incluir_observados=True)["asiento"]


def test_la_derivacion_reproduce_el_rol_de_cada_linea():
    """La regla acierta en las 324 líneas que la batería produce, con los seis roles del motor.

    Si falla en una, la regla está incompleta: se mira, no se parchea. Ya pasó una vez — ver el test del orden de
    los tramos, más abajo."""
    comprobadas, por_rol = 0, {}
    for archivo, config, imputacion, cuenta in DOCUMENTOS:
        tipo = json.loads((GOLDEN / archivo).read_text(encoding="utf-8"))["libro"]["tipo"]
        for driver in DRIVERS:
            for ln in asiento_de(archivo, config, imputacion, cuenta, driver):
                comprobadas += 1
                por_rol[ln["rol"]] = por_rol.get(ln["rol"], 0) + 1
                assert rol_de(ln, tipo) == ln["rol"], (archivo, driver, ln)

    assert comprobadas >= 324, f"el barrido se encogió: {comprobadas} líneas"
    # Y los seis roles que el motor emite están todos ejercitados: un barrido que no los vea no prueba la regla.
    from contaperu.asiento import ROLES_DEL_MOTOR
    assert set(por_rol) == set(ROLES_DEL_MOTOR), (sorted(por_rol), sorted(ROLES_DEL_MOTOR))


# ── Los dos casos que el barrido no tiene, y que son los que ejercitan la inversión ────────────────────────────

def _asiento(c, tipo: str, config: dict | None = None) -> list[dict]:
    """El asiento de UN comprobante, por la fachada, con el libro del tipo que se pida."""
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608",
                     "tipo": tipo},
           "comprobantes": [c.a_dict() if hasattr(c, "a_dict") else c]}
    # La imputación de un comprobante de prueba va por el argumento `imputacion`, que es por donde la recibe la
    # fachada: `util.comprobante()` la aparta en `IMPUTACIONES` por `id_externo`. Se le pasa SOLO la suya, porque
    # la fachada rechaza —con razón— una imputación que hable de un documento que no está.
    suya = {c.id_externo: IMPUTACIONES[c.id_externo]} if getattr(c, "id_externo", "") in IMPUTACIONES else None
    return api.generar_asiento(doc, driver="csv", configuracion=config or {}, imputacion=suya,
                               incluir_observados=True)["asiento"]


def test_la_nota_de_credito_de_una_venta_invierte_el_lado_del_tercero():
    """El barrido trae la nota de crédito de COMPRAS y no la de ventas. Es el otro lado del mismo término.

    Importa porque en una nota de crédito los dos sentidos se cambian: el cliente, que en una venta va al Debe,
    aquí va al Haber. Sin el término de la inversión se derivaría como `recorte`."""
    nc = comprobante(tipo_cp="07", serie="F001", numero="9", fecha_emision="2026-08-20",
                     contraparte_doc="20607777773", contraparte_nombre="CLIENTE SAC", moneda="PEN",
                     base_gravada="100", igv="18", total="118", cuenta_contable="701101",
                     ref_fecha="2026-07-31", ref_tipo_cp="01", ref_serie="F001", ref_numero="257")
    lineas = _asiento(nc, "venta")
    del_cliente = [ln for ln in lineas if ln["rol"] == "tercero"]
    assert len(del_cliente) == 1 and del_cliente[0]["debe_haber"] == "H", "una NC de venta abona al cliente"
    for ln in lineas:
        assert rol_de(ln, "venta") == ln["rol"], ln


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
    roles = [ln["rol"] for ln in lineas]
    assert sorted(roles) == ["detraccion", "impuesto", "principal", "recorte", "tercero"], roles
    for ln in lineas:
        assert rol_de(ln, "compra") == ln["rol"], ln
    # Y la comprobación que da sentido al caso: con los sentidos invertidos, el tercero va al Debe y el recorte al
    # Haber — justo al revés que en una compra normal.
    lado = {ln["rol"]: ln["debe_haber"] for ln in lineas}
    assert lado["tercero"] == "D" and lado["recorte"] == "H", lado


# ── Los dos términos de carga: si se quitan, la regla se equivoca ──────────────────────────────────────────────

def test_sin_el_termino_de_la_inversion_la_nota_de_credito_sale_mal(monkeypatch):
    """La mutación del término que más fácil se borra, automatizada: se vacía `TIPOS_INVIERTEN` y la nota de
    crédito tiene que salir MAL.

    Si alguien quita la inversión de `rol_de`, este test falla porque la respuesta deja de empeorar al vaciar la
    tabla. Es la forma de que una mutación no sobreviva sin que nadie la ejecute a mano."""
    from contaperu.drivers.kit import rol as modulo

    nc = comprobante(tipo_cp="07", serie="F001", numero="9", fecha_emision="2026-08-20",
                     contraparte_doc="20607777773", contraparte_nombre="CLIENTE SAC", moneda="PEN",
                     base_gravada="100", igv="18", total="118", cuenta_contable="701101",
                     ref_fecha="2026-07-31", ref_tipo_cp="01", ref_serie="F001", ref_numero="257")
    del_cliente = next(ln for ln in _asiento(nc, "venta") if ln["rol"] == "tercero")
    assert rol_de(del_cliente, "venta") == "tercero"

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
    del_cliente = next(ln for ln in _asiento(bv, "venta") if ln["rol"] == "tercero")
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
    """Tesorería declara `roles=()` porque el motor no emite ni una línea suya. Pedir el rol de una de sus líneas
    no es un fallo de la regla: es una pregunta sin respuesta todavía, y se dice así."""
    assert RASGOS["tesoreria"].roles == ()
    with pytest.raises(RolNoDerivable) as e:
        rol_de({"cuenta": "104111", "debe_haber": "D", "importe": "100.00"}, "tesoreria")
    assert "compra" in str(e.value) and "venta" in str(e.value), "tiene que decir qué libros SÍ los declaran"


def test_acepta_la_linea_como_objeto_y_como_diccionario():
    """Las dos formas circulan: un driver recibe `LineaDiario` y un test o un ERP de fuera, diccionarios."""
    from contaperu.asiento import lineas_del_comprobante
    from contaperu.modelo import Libro

    c = comprobante(tipo_cp="01", serie="F001", numero="123", fecha_emision="2026-08-11",
                    contraparte_doc="20602222226", contraparte_nombre="PROVEEDOR SAC", moneda="PEN",
                    base_gravada="100", igv="18", total="118", cuenta_contable="631101")
    libro = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="compra")
    from datetime import date
    lineas = lineas_del_comprobante(c, {"imputaciones": IMPUTACIONES},
                                    (date(2026, 8, 1), date(2026, 8, 31)), "0001", libro=libro.rasgos)
    assert lineas, "sin líneas no se mide nada"
    for ln in lineas:
        assert rol_de(ln, libro) == rol_de(ln.a_dict(), libro.rasgos) == ln.rol
