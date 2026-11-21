"""Pagar compras (15.13.0, enmienda 0035): una parte del reparto por factura, y cada una con su documento.

Pagarle a un proveedor es revertir su 42 contra el banco. Lo que el motor no sabía era **qué factura cancela cada
línea 42**: llevaba el vóucher del banco, y en CONCAR una 42 sin su factura no la cancela en la cuenta corriente del
proveedor. Y tampoco decía **cuánto** se le debe a cada uno: lo ponía quien llamaba, rehaciendo la regla del asiento
de la compra —el total menos la retención de 4ta y la detracción—.

**El vigilante de `por_pagar` no rehace esa cuenta**: arma el asiento de la compra con el motor y comprueba que
`por_pagar` dice exactamente lo que ese asiento dejó en la cuenta del proveedor, documento a documento. Una copia de la
regla en el test pasaría en verde con las dos mal.

La forma del pago es la medida en un pago real que un CONCAR aceptó (sub-diario de bancos, 21-nov-2026; el archivo
vive fuera del repositorio): una 42 por documento —nunca agrupada por proveedor—, cada una con su factura, y al final
una sola 104 con la suma, que es la única que lleva el vóucher.
"""
from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from contaperu import api, asiento, drivers, tesoreria
from contaperu.comprobantes import Comprobante
from contaperu.errores import DocumentoInvalido
from drivers_de_prueba import diario_json, erp_tesoreria
from util import imputando

LIBRO_COMPRAS = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202610", "tipo": "compra"}
PROVEEDOR = "20602222226"
OTRO = "20607777773"


def compra(**campos) -> dict:
    base = {"tipo_cp": "01", "serie": "E001", "numero": "3507", "fecha_emision": "2026-09-24",
            "fecha_vencimiento": "2026-10-24", "contraparte_tipo_doc": "6", "contraparte_doc": PROVEEDOR,
            "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "moneda": "PEN", "base_gravada": "1000.00",
            "igv": "180.00", "total": "1180.00", "id_externo": "c-1"}
    return dict(base, **campos)


SIMPLE = compra()
CON_DETRACCION = compra(serie="F001", numero="00000088", contraparte_doc=OTRO, fecha_emision="2026-10-28",
                        fecha_vencimiento="", id_externo="c-2", detraccion={"codigo": "037", "porcentaje": 12})
HONORARIOS = compra(tipo_cp="02", serie="E001", numero="45", contraparte_tipo_doc="1", contraparte_doc="10456789012",
                    contraparte_nombre="PROFESIONAL DE PRUEBA", base_gravada="0", igv="0", valor_no_gravado="2000.00",
                    total="2000.00", retencion_4ta="160.00", id_externo="c-3", fecha_vencimiento="")
NOTA = compra(tipo_cp="07", serie="E001", numero="12", base_gravada="100.00", igv="18.00", total="118.00",
              ref_tipo_cp="01", ref_serie="E001", ref_numero="3507", fecha_emision="2026-10-02",
              fecha_vencimiento="", id_externo="c-4")


def compras(*comprobantes) -> dict:
    return imputando({"open_accounting": api.OPEN_ACCOUNTING, "libro": dict(LIBRO_COMPRAS),
                      "comprobantes": [copy.deepcopy(c) for c in comprobantes]}, "631101")


def lo_que_la_compra_dejo_en_su_cuenta(doc: dict, driver: str = "csv") -> dict[str, tuple[str, Decimal]]:
    """Del asiento REAL de la compra —el motor, no una cuenta del test—: por serie-número, la cuenta del tercero y su
    saldo acreedor (haber − debe) en esa cuenta."""
    lineas = api.generar_asiento(doc, driver=driver, incluir_observados=True)["asiento"]
    salida: dict[str, tuple[str, Decimal]] = {}
    for fila in api.por_pagar(doc, driver=driver)["documentos"]:
        nombre = f"{fila['serie']}-{fila['numero'].lstrip('0')}"
        suyas = [ln for ln in lineas if ln["cuenta"] == fila["cuenta_contable"]
                 and (ln.get("documento") or {}).get("serie_numero") == nombre]
        assert suyas, f"el asiento de la compra no tiene línea de {fila['cuenta_contable']} para {nombre}"
        saldo = sum((Decimal(ln["importe"]) * (1 if ln["debe_haber"] == "H" else -1) for ln in suyas), Decimal(0))
        salida[nombre] = (fila["cuenta_contable"], saldo)
    return salida


# --- por_pagar: la regla del asiento de la compra, sin copiarla ------------------------------------------------

@pytest.mark.parametrize("driver", ["csv", "starsoft", "asiento_contable"])
def test_por_pagar_dice_lo_que_el_asiento_de_la_compra_dejo_en_la_cuenta_del_proveedor(driver):
    """La simple, la de la detracción, el recibo por honorarios y la nota de crédito: las cuatro formas en que lo
    que se le paga al tercero NO es el total. **Y en cada sistema** (15.13.1): STARSOFT lleva otra cuenta por pagar, y
    sin el `driver` el pago nombraba la 421201 mientras su compra se provisionaba en la 42120001."""
    doc = compras(SIMPLE, CON_DETRACCION, HONORARIOS, NOTA)
    asentado = lo_que_la_compra_dejo_en_su_cuenta(doc, driver)
    filas = {f"{f['serie']}-{f['numero'].lstrip('0')}": f for f in api.por_pagar(doc, driver=driver)["documentos"]}
    assert set(filas) == set(asentado) == {"E001-3507", "F001-88", "E001-45", "E001-12"}
    for nombre, (cuenta, saldo) in asentado.items():
        assert Decimal(filas[nombre]["por_pagar"]) == saldo, nombre
        assert filas[nombre]["cuenta_contable"] == cuenta


def test_por_pagar_descuenta_la_detraccion_y_la_retencion_y_la_nota_resta():
    filas = {f["id_externo"]: f for f in api.por_pagar(compras(SIMPLE, CON_DETRACCION, HONORARIOS, NOTA))["documentos"]}
    simple, detraida, rh, nota = filas["c-1"], filas["c-2"], filas["c-3"], filas["c-4"]
    assert (simple["total"], simple["detraccion"], simple["retencion_4ta"], simple["por_pagar"]) == (
        "1180.00", "0.00", "0.00", "1180.00")
    # La detracción va al Banco de la Nación, no al proveedor; y su cuenta es la misma 42.
    assert Decimal(detraida["detraccion"]) > 0
    assert Decimal(detraida["por_pagar"]) == Decimal("1180.00") - Decimal(detraida["detraccion"])
    assert detraida["cuenta_contable"] == simple["cuenta_contable"] == "421201"
    # El recibo por honorarios se salda por su propia cuenta, y sin la retención de 4ta.
    assert (rh["retencion_4ta"], rh["por_pagar"]) == ("160.00", "1840.00") and rh["cuenta_contable"].startswith("424")
    # La nota de crédito resta.
    assert nota["por_pagar"] == "-118.00"


def test_por_pagar_trae_lo_que_necesita_la_linea_del_pago():
    """Lo que una parte del reparto necesita para nombrar su factura, y el vencimiento que cae a la emisión."""
    fila = next(f for f in api.por_pagar(compras(CON_DETRACCION))["documentos"])
    assert {k: fila[k] for k in ("tipo_cp", "serie", "numero", "contraparte_doc", "fecha_emision",
                                 "fecha_vencimiento", "moneda")} == {
        "tipo_cp": "01", "serie": "F001", "numero": "00000088", "contraparte_doc": OTRO,
        "fecha_emision": "2026-10-28", "fecha_vencimiento": "2026-10-28", "moneda": "PEN"}
    assert fila["glosa"] == asiento.glosa_de(Comprobante.de_dict(CON_DETRACCION))


def test_por_pagar_toma_la_cuenta_del_sistema_de_la_compra():
    """Sin `driver`, la general; con el de STARSOFT, la suya. Es la diferencia que el vigilante de arriba caza."""
    doc = compras(SIMPLE)
    assert api.por_pagar(doc)["documentos"][0]["cuenta_contable"] == "421201"
    assert api.por_pagar(doc, driver="starsoft")["documentos"][0]["cuenta_contable"] == "42120001"


def test_por_pagar_lee_la_cuenta_del_tercero_de_la_imputacion():
    """La misma regla que el asiento: un gasto de representación que el contador mandó a otra 42 se paga contra ésa."""
    doc = compras(SIMPLE)
    doc["imputaciones"]["c-1"]["cuenta_tercero"] = "421299"
    assert api.por_pagar(doc)["documentos"][0]["cuenta_contable"] == "421299"


def test_por_pagar_deja_fuera_las_excluidas_y_no_se_para_por_una_observacion():
    excluida = compra(numero="9", id_externo="c-9", excluida=True)
    sin_cuenta = compras(SIMPLE, excluida)
    del sin_cuenta["imputaciones"]["c-1"]            # sin la cuenta de su gasto: el asiento se pararía; el pago, no
    filas = api.por_pagar(sin_cuenta)["documentos"]
    assert [f["id_externo"] for f in filas] == ["c-1"]


def test_por_pagar_es_de_un_libro_de_compras():
    doc = compras(SIMPLE)
    doc["libro"]["tipo"] = "venta"
    with pytest.raises(DocumentoInvalido, match="libro de compras"):
        api.por_pagar(doc)


def test_por_pagar_sale_por_las_puertas():
    operacion = next(o for o in api.OPERACIONES if o.nombre == "por_pagar")
    assert (operacion.metodo, operacion.ruta, operacion.herramienta, operacion.salida) == (
        "POST", "/v1/por_pagar", "por_pagar", "por_pagar")
    import jsonschema
    esquema = api.contrato_openconta()["components"]["schemas"]["por_pagar"]
    jsonschema.validate(api.por_pagar(compras(SIMPLE, CON_DETRACCION, HONORARIOS, NOTA)), esquema)


# --- el asiento del pago: una 42 por documento, cada una con su factura ----------------------------------------

CUENTAS = [{"id": "bcp-soles", "banco": "BCP", "moneda": "PEN", "cuenta_contable": "104101", "sub_diario": "24"}]
CONFIG = {"usa_centros_costo": False, "cuentas_bancarias": CUENTAS}


class _Entrada:
    def __init__(self, modulo):
        self.name = modulo.NOMBRE
        self._modulo = modulo

    def load(self):
        return self._modulo


@pytest.fixture
def registrados(monkeypatch):
    entradas = [_Entrada(erp_tesoreria), _Entrada(diario_json)]
    monkeypatch.setattr(drivers, "entry_points", lambda group: entradas if group == drivers.GRUPO else [])
    drivers.recargar()
    yield
    monkeypatch.undo()
    drivers.recargar()


def parte_de(fila: dict, **campos) -> dict:
    """Una parte del reparto armada con una fila de `por_pagar`, que es como la arma quien paga."""
    return dict({"importe": fila["por_pagar"], "cuenta_contable": fila["cuenta_contable"],
                 "contraparte_doc": fila["contraparte_doc"],
                 "comprobante": {k: fila[k] for k in ("tipo_cp", "serie", "numero", "contraparte_doc",
                                                      "fecha_emision", "fecha_vencimiento")}}, **campos)


def pago(partes: list[dict], *, glosa: str = "PAGOS VARIOS") -> dict:
    total = sum((Decimal(p["importe"]) for p in partes), Decimal(0))
    return {"open_accounting": api.OPEN_ACCOUNTING,
            "libro": {**LIBRO_COMPRAS, "periodo": "202611", "tipo": "tesoreria"},
            "movimientos": [{"cuenta": "bcp-soles", "fecha": "2026-11-03", "importe": str(total), "sentido": "cargo",
                             "moneda": "PEN", "constancia": "0311261348", "id_externo": "pago-1"}],
            "imputaciones_de_movimientos": {"pago-1": {"glosa": glosa, "reparto": partes}}}


def test_un_pago_de_dos_facturas_lleva_cada_una_en_su_linea_y_el_banco_al_final(registrados):
    filas = api.por_pagar(compras(SIMPLE, CON_DETRACCION))["documentos"]
    r = api.generar_asiento(pago([parte_de(f) for f in filas]), driver="erp_tesoreria", configuracion=CONFIG)
    neto = Decimal(filas[1]["por_pagar"])
    plano = [(ln["cuenta"], ln["debe_haber"], ln["importe"], ln.get("contraparte_doc", "")) for ln in r["asiento"]]
    assert plano == [("421201", "D", "1180.00", PROVEEDOR), ("421201", "D", str(neto), OTRO),
                     ("104101", "H", str(Decimal("1180.00") + neto), plano[2][3])]
    assert r["_asiento"]["cuadre"]["cuadra"]
    primera, segunda, banco = (ln["documento"] for ln in r["asiento"])
    # Cada 42 con SU factura, escrita como la escribe la línea de su compra: sin ceros a la izquierda, y el
    # vencimiento que cae a la emisión.
    assert {k: primera.get(k) for k in ("tipo_cp", "serie_numero", "fecha_emision", "fecha_vencimiento")} == {
        "tipo_cp": "01", "serie_numero": "E001-3507", "fecha_emision": "2026-09-24", "fecha_vencimiento": "2026-10-24"}
    assert {k: segunda.get(k) for k in ("tipo_cp", "serie_numero", "fecha_emision", "fecha_vencimiento")} == {
        "tipo_cp": "01", "serie_numero": "F001-88", "fecha_emision": "2026-10-28", "fecha_vencimiento": "2026-10-28"}
    # Y solo la del banco con el vóucher (enmienda 0032): sin tipo de la Tabla 10, la fecha del pago.
    assert "tipo_cp" not in banco and banco["serie_numero"] == "0311261348"
    assert banco["fecha_emision"] == "2026-11-03" and banco["id_externo"] == "pago-1"


def test_la_42_de_cada_factura_sale_igual_que_la_de_su_compra(registrados):
    """El documento de la 42 del pago es el mismo que el de la 42 de la compra, campo a campo: es por donde el
    sistema de destino casa la provisión con su pago."""
    doc = compras(SIMPLE, CON_DETRACCION)
    de_la_compra = {(ln["documento"]["serie_numero"]): ln["documento"]
                    for ln in api.generar_asiento(doc, driver="csv", incluir_observados=True)["asiento"]
                    if ln["cuenta"] == "421201" and ln["debe_haber"] == "H"}
    filas = api.por_pagar(doc)["documentos"]
    r = api.generar_asiento(pago([parte_de(f) for f in filas]), driver="erp_tesoreria", configuracion=CONFIG)
    for ln in r["asiento"][:2]:
        suyo = de_la_compra[ln["documento"]["serie_numero"]]
        for clave in ("tipo_cp", "serie_numero", "fecha_emision", "fecha_vencimiento"):
            assert ln["documento"].get(clave) == suyo.get(clave), clave


def test_varias_facturas_del_mismo_proveedor_no_se_agrupan(registrados):
    otra = compra(numero="3508", id_externo="c-5", total="590.00", base_gravada="500.00", igv="90.00")
    filas = api.por_pagar(compras(SIMPLE, otra))["documentos"]
    r = api.generar_asiento(pago([parte_de(f) for f in filas]), driver="erp_tesoreria", configuracion=CONFIG)
    assert [(ln["cuenta"], ln["importe"], ln["documento"].get("serie_numero")) for ln in r["asiento"]] == [
        ("421201", "1180.00", "E001-3507"), ("421201", "590.00", "E001-3508"), ("104101", "1770.00", "0311261348")]


def test_la_parte_toma_el_tercero_de_su_comprobante_si_no_trae_el_suyo(registrados):
    fila = api.por_pagar(compras(SIMPLE))["documentos"][0]
    parte = parte_de(fila)
    del parte["contraparte_doc"]
    r = api.generar_asiento(pago([parte]), driver="erp_tesoreria", configuracion=CONFIG)
    assert r["asiento"][0]["contraparte_doc"] == PROVEEDOR


def test_sin_vencimiento_la_42_lleva_la_emision_como_la_de_su_compra(registrados):
    """Quien arma la parte a mano puede no mandar el vencimiento; la línea hace lo que hace la de la compra."""
    parte = {"importe": "1180.00", "cuenta_contable": "421201", "contraparte_doc": PROVEEDOR,
             "comprobante": {"tipo_cp": "01", "serie": "E001", "numero": "3507", "fecha_emision": "2026-09-24"}}
    r = api.generar_asiento(pago([parte]), driver="erp_tesoreria", configuracion=CONFIG)
    assert r["asiento"][0]["documento"]["fecha_vencimiento"] == "2026-09-24"


def test_una_parte_sin_comprobante_sigue_con_el_voucher(registrados):
    """Quien no use el bloque recibe lo de siempre: el documento del vóucher en todas las líneas."""
    r = api.generar_asiento(pago([{"importe": "50.00", "cuenta_contable": "639101"}]), driver="erp_tesoreria",
                            configuracion=CONFIG)
    assert all(ln["documento"].get("serie_numero") == "0311261348" for ln in r["asiento"])
    assert all("tipo_cp" not in ln["documento"] for ln in r["asiento"])


# --- el bloque, validado en la puerta -----------------------------------------------------------------------------

@pytest.mark.parametrize("comprobante, motivo", [
    ({"tipo_cp": "01", "serie": "E001"}, "tipo_cp. y su .numero"),
    ({"serie": "E001", "numero": "1"}, "tipo_cp. y su .numero"),
    ({"tipo_cp": "01", "numero": "1", "importe": "5.00"}, "no lleva importe"),
    ({"tipo_cp": "01", "numero": "1", "fecha_emision": "2026-13-01"}, "Fecha inválida"),
    ({"tipo_cp": "01", "numero": "1", "contraparte_doc": OTRO}, "una de las dos está mal"),
    ("E001-3507", "es un objeto"),
])
def test_el_comprobante_de_una_parte_se_valida(comprobante, motivo):
    with pytest.raises(tesoreria.ImputacionInvalida, match=motivo):
        tesoreria.Parte(importe="10.00", cuenta_contable="421201", contraparte_doc=PROVEEDOR, comprobante=comprobante)


def test_el_comprobante_de_una_parte_se_normaliza_y_vuelve_igual():
    parte = tesoreria.Parte(importe="10.00", cuenta_contable="421201",
                            comprobante={"tipo_cp": " 01 ", "serie": "E001", "numero": "3507",
                                         "contraparte_doc": "20602222226 ", "fecha_emision": "2026-10-24",
                                         "fecha_vencimiento": None})
    assert parte.comprobante == {"tipo_cp": "01", "serie": "E001", "numero": "3507",
                                 "contraparte_doc": PROVEEDOR, "fecha_emision": "2026-10-24"}
    assert parte.a_dict()["comprobante"] == parte.comprobante
    assert "comprobante" not in tesoreria.Parte(importe="10.00", cuenta_contable="639101").a_dict()


# --- el sub-diario de cada cuenta bancaria ------------------------------------------------------------------------

def test_cada_cuenta_bancaria_declara_su_sub_diario_y_no_hay_uno_de_fabrica():
    leidas = tesoreria.leer([{"id": "bcp", "moneda": "PEN", "cuenta_contable": "104101", "sub_diario": " 24 "},
                             {"id": "bbva", "moneda": "PEN", "cuenta_contable": "104102"}])
    assert [c.sub_diario for c in leidas] == ["24", ""]
    r = api.validar_cuentas_bancarias([c.a_dict() for c in leidas])
    assert [c["sub_diario"] for c in r["cuentas"]] == ["24", ""]
    cuentas = next(c for c in api.describir_configuracion()["general"]["campos"] if c["clave"] == "cuentas_bancarias")
    sub_diario = next(c for c in cuentas["valores"]["campos"] if c["clave"] == "sub_diario")
    assert sub_diario["tipo"] == "texto" and not sub_diario.get("por_defecto")     # sin valor de muestra
