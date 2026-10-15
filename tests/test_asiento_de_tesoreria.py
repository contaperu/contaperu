"""El asiento del dinero **por la api** (12.9): `generar_asiento` sobre un libro de tesorería.

La 12.7 enseñó al núcleo a armar la línea de un movimiento y la 12.8 declaró que el motor origina ese libro; lo
que faltaba era el camino, y es el que esto prueba: `preparar_tesoreria` lee los movimientos, descarta las
relecturas, casa la imputación y lee el maestro de cuentas de la configuración, y `armado.generar_asiento`
despacha por `libro.rasgos.origen` —una sola vez, sin un `if es_tesoreria` más adentro—.

**El destino es un driver de prueba** (`drivers_de_prueba/erp_tesoreria.py`) y no el de serie, por el mismo motivo
por el que `diario_json` probó lo que pedía STARSOFT: el driver que viaja en el paquete declarará el libro cuando
sepa escribir su archivo, y declararlo antes dejaría a `exportar` dando el mensaje engañoso que la 12.6 quitó.
"""
from __future__ import annotations

import copy
import json

import pytest

from contaperu import api, asiento, drivers, tesoreria
from contaperu.pipeline import armado
from drivers_de_prueba import diario_json, erp_tesoreria

CUENTAS = [{"id": "bbva-soles", "banco": "BBVA", "moneda": "PEN", "cuenta_contable": "104101"},
           {"id": "bcp-soles", "banco": "BCP", "moneda": "PEN", "cuenta_contable": "104102"}]
CONFIG = {"usa_centros_costo": False, "cuentas_bancarias": CUENTAS}


class _Entrada:
    def __init__(self, modulo):
        self.name = modulo.NOMBRE
        self._modulo = modulo

    def load(self):
        return self._modulo


@pytest.fixture
def registrados(monkeypatch):
    """Los dos drivers de prueba: el ERP neutral que lleva los tres libros y el legacy que no lleva tesorería."""
    entradas = [_Entrada(erp_tesoreria), _Entrada(diario_json)]
    monkeypatch.setattr(drivers, "entry_points", lambda group: entradas if group == drivers.GRUPO else [])
    drivers.recargar()
    yield
    monkeypatch.undo()
    drivers.recargar()


def _documento(movimientos: list[dict], imputaciones: dict) -> dict:
    return {"open_accounting": api.OPEN_ACCOUNTING,
            "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202610",
                      "tipo": "tesoreria"},
            "movimientos": copy.deepcopy(movimientos),
            "imputaciones_de_movimientos": copy.deepcopy(imputaciones)}


def mov(**campos) -> dict:
    base = {"cuenta": "bbva-soles", "fecha": "2026-10-15", "importe": "2000.00", "sentido": "cargo",
            "moneda": "PEN", "descripcion": "TRANSFERENCIA A TERCEROS", "medio_pago": "003",
            "referencia": "000123", "id_externo": "mov-1"}
    return dict(base, **campos)


def _plano(doc: dict) -> list[tuple]:
    return [(ln["cuenta"], ln["debe_haber"], ln["importe"]) for ln in doc["asiento"]]


# --- las cinco formas, por la api ----------------------------------------------------------------------------

def test_un_pago_a_proveedor_sale_por_la_api_y_cuadra(registrados):
    doc = _documento([mov(contraparte_doc="20602222226")],
                     {"mov-1": {"cuenta_contable": "421201", "contraparte_doc": "20602222226"}})
    r = api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert _plano(r) == [("421201", "D", "2000.00"), ("104101", "H", "2000.00")]
    assert r["_asiento"]["cuadre"]["cuadra"] and r["_asiento"]["lineas"] == 2


def test_un_cobro_una_comision_un_reparto_y_un_traspaso_tambien(registrados):
    """Las otras cuatro formas en un solo mes, que es como llegan: un extracto trae de todo."""
    doc = _documento(
        [mov(id_externo="cobro", sentido="abono", importe="1180.00", referencia="000200",
             contraparte_doc="20607777773"),
         mov(id_externo="comision", importe="15.00", referencia="000201", descripcion="COMISION MANTENIMIENTO"),
         mov(id_externo="reparto", importe="1000.00", referencia="000202", descripcion="PAGO SERVICIOS"),
         mov(id_externo="traspaso", importe="500.00", referencia="000203", descripcion="TRASPASO A BCP")],
        {"cobro": {"cuenta_contable": "121201", "contraparte_doc": "20607777773"},
         "comision": {"cuenta_contable": "639101"},
         "reparto": {"reparto": [{"importe": "600.00", "cuenta_contable": "636301"},
                                 {"importe": "400.00", "cuenta_contable": "632201"}]},
         "traspaso": {"cuenta_propia": "bcp-soles"}})
    r = api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert _plano(r) == [
        ("104101", "D", "1180.00"), ("121201", "H", "1180.00"),          # el cobro
        ("639101", "D", "15.00"), ("104101", "H", "15.00"),              # la comisión
        ("636301", "D", "600.00"), ("632201", "D", "400.00"), ("104101", "H", "1000.00"),   # el reparto
        ("104102", "D", "500.00"), ("104101", "H", "500.00"),            # el traspaso, sus dos patas declaradas
    ]
    assert r["_asiento"]["cuadre"]["cuadra"]
    # Cada movimiento tiene su tramo, y los tramos parten las líneas sin hueco ni solape.
    tramos = [m["lineas"] for m in r["_asiento"]["movimientos"]]
    assert tramos == [[0, 2], [2, 4], [4, 7], [7, 9]]


def test_el_itf_sale_como_su_propio_asiento_dentro_del_tramo_del_movimiento(registrados):
    """Dos asientos y un movimiento: el del pago por su importe, y `6412`/`104` por lo que el banco descontó."""
    doc = _documento([mov(itf="0.10", contraparte_doc="20602222226")],
                     {"mov-1": {"cuenta_contable": "421201"}})
    r = api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert _plano(r) == [("421201", "D", "2000.00"), ("104101", "H", "2000.00"),
                         ("641201", "D", "0.10"), ("104101", "H", "0.10")]
    assert r["_asiento"]["cuadre"]["cuadra"], "cada grupo cuadra, así que el asiento entero también"
    assert r["_asiento"]["movimientos"][0]["lineas"] == [0, 4], "el ITF va en el tramo del movimiento que lo trae"


# --- la respuesta --------------------------------------------------------------------------------------------

def test_la_respuesta_trae_las_dos_claves_y_la_del_libro_llena(registrados):
    """`comprobantes` y `movimientos` van **siempre las dos**, la del origen del libro con sus entradas y la otra
    vacía. Es literalmente cierto —un libro de tesorería no tiene comprobantes— y le ahorra dos formas a quien la
    lee."""
    doc = _documento([mov()], {"mov-1": {"cuenta_contable": "421201"}})
    r = api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert r["_asiento"]["comprobantes"] == []
    assert len(r["_asiento"]["movimientos"]) == 1
    assert r["_asiento"]["movimientos"][0]["identidad"] == {
        "ruc": "20601234567", "libro": "tesoreria", "cuenta": "bbva-soles", "referencia": "000123"}


def test_las_claves_de_la_respuesta_las_dice_la_tabla_de_rasgos():
    """`ORIGENES` se DERIVA de `modelo.RASGOS`, así que el día que la tabla gane una fila con otro origen la
    respuesta gana su clave sola — y el esquema se pone rojo por quedarse atrás, que es lo que se quiere."""
    assert armado.ORIGENES == ("comprobantes", "movimientos")


def test_el_esquema_publicado_acepta_el_asiento_de_tesoreria(registrados):
    """Y con `movimientos` LLENO: un array vacío valida contra cualquier esquema de item, así que un guardián que
    no mire dentro es un guardián que no puede fallar."""
    jsonschema = pytest.importorskip("jsonschema")
    doc = _documento([mov(), mov(id_externo="mov-2", referencia="", importe="15.00",
                                 descripcion="COMISION MANTENIMIENTO")],
                     {"mov-1": {"cuenta_contable": "421201"}, "mov-2": {"cuenta_contable": "639101"}})
    r = api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert len(r["_asiento"]["movimientos"]) == 2
    # Las dos ramas de la identidad: con el número del banco, y sin él.
    assert "referencia" in r["_asiento"]["movimientos"][0]["identidad"]
    assert "descripcion" in r["_asiento"]["movimientos"][1]["identidad"]
    contrato = api.contrato_openconta()
    jsonschema.Draft202012Validator({**contrato, "$ref": "#/components/schemas/asiento"}).validate(r)


def test_un_libro_de_compras_responde_exactamente_lo_mismo_mas_la_clave_vacia(registrados):
    """El dispatch no toca el camino de los comprobantes: lo que cambia en su respuesta es `movimientos: []` y
    nada más — ni una línea, ni la huella. Lo congelado en `tests/fixtures/caracterizacion/` lo enseña entero."""
    from util import GOLDEN, imputando
    compras = imputando(json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8")), "659999")
    r = api.generar_asiento(compras, driver="erp_tesoreria", configuracion={"usa_centros_costo": False})
    assert r["_asiento"]["movimientos"] == []
    assert len(r["_asiento"]["comprobantes"]) == 3 and r["_asiento"]["cuadre"]["cuadra"]


# --- lo que para, y con qué razón ----------------------------------------------------------------------------

def test_un_documento_sin_movimientos_lo_dice_con_sus_palabras(registrados):
    """El gemelo verdadero de «No hay comprobantes que procesar», que es lo que decía hasta la 12.6 cuando se le
    pedía el asiento de un libro de tesorería."""
    doc = _documento([], {})
    with pytest.raises(api.DocumentoInvalido) as e:
        api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert "No hay movimientos que procesar." in str(e.value)


def test_un_movimiento_sin_imputar_para_lo_que_revisar_tesoreria_solo_avisaba(registrados):
    """La misma falta, dos tratos: **mirar no obliga a nada** y asentar sí, porque sin la contrapartida no hay
    línea que escribir. Los dos la nombran igual y por el mismo movimiento."""
    doc = _documento([mov(), mov(id_externo="mov-2", referencia="000124", importe="50.00")],
                     {"mov-1": {"cuenta_contable": "421201"}})
    revision = api.revisar_tesoreria(doc, CUENTAS)
    assert revision["sin_imputar"] == ["000124"]
    assert any(a["codigo"] == "MOVIMIENTO_SIN_IMPUTAR" for a in revision["avisos"])
    with pytest.raises(asiento.MovimientoSinImputar) as e:
        api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert e.value.cuales == ["000124"] and e.value.clave == "movimiento_sin_imputar"


def test_una_cuenta_que_el_maestro_no_declara_para_el_asiento(registrados):
    """`revisar_tesoreria` avisa `CUENTA_NO_DECLARADA`; asentar para, porque la 104 **no se deriva**."""
    doc = _documento([mov(cuenta="scotiabank-soles")], {"mov-1": {"cuenta_contable": "421201"}})
    assert any(a["codigo"] == "CUENTA_NO_DECLARADA" for a in api.revisar_tesoreria(doc, CUENTAS)["avisos"])
    with pytest.raises(asiento.SinCuentaDeEfectivo) as e:
        api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert e.value.cuales == ["scotiabank-soles"] and "no está en el maestro" in e.value.motivo


def test_una_cuenta_declarada_sin_su_cuenta_contable_tambien(registrados):
    doc = _documento([mov()], {"mov-1": {"cuenta_contable": "421201"}})
    config = {**CONFIG, "cuentas_bancarias": [{"id": "bbva-soles", "banco": "BBVA", "moneda": "PEN"}]}
    with pytest.raises(asiento.SinCuentaDeEfectivo) as e:
        api.generar_asiento(doc, driver="erp_tesoreria", configuracion=config)
    assert "sin su cuenta contable" in e.value.motivo


def test_un_traspaso_declarado_por_sus_dos_patas_para_antes_de_contar_el_dinero_dos_veces(registrados):
    doc = _documento(
        [mov(id_externo="ida", importe="500.00", referencia="000300", sentido="cargo", cuenta="bbva-soles"),
         mov(id_externo="vuelta", importe="500.00", referencia="000301", sentido="abono", cuenta="bcp-soles")],
        {"ida": {"cuenta_propia": "bcp-soles"}, "vuelta": {"cuenta_propia": "bbva-soles"}})
    with pytest.raises(asiento.TraspasoEnDosPatas) as e:
        api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert e.value.cuales == ["bcp-soles ↔ bbva-soles por 500.00"]


def test_dos_cuentas_con_el_mismo_id_para_el_asiento_con_su_motivo(registrados):
    """El `id` es la llave con la que un movimiento nombra su cuenta, así que dos iguales paran — y lo dicen antes
    de armar una línea, porque el maestro se indexa al empezar.

    Se intentó además validarlo al preparar, «para decirlo en la puerta», y la línea **no compraba nada**: al
    romperla no caía ni un test. Se quitó en vez de escribirle un test que la justificara."""
    doc = _documento([mov()], {"mov-1": {"cuenta_contable": "421201"}})
    config = {**CONFIG, "cuentas_bancarias": CUENTAS + [dict(CUENTAS[0], banco="OTRO")]}
    with pytest.raises(tesoreria.CuentaInvalida) as e:
        api.generar_asiento(doc, driver="erp_tesoreria", configuracion=config)
    assert "bbva-soles" in str(e.value)


def test_un_destino_legacy_dice_que_ese_libro_todavia_no_se_numera(registrados):
    """Con vocabulario legacy hace falta un sub-diario, y el de tesorería espera el archivo real que lo pida. Hasta
    la 12.8 esto reventaba con un `KeyError` pelado que no era un `ErrorContaperu`."""
    doc = _documento([mov()], {"mov-1": {"cuenta_contable": "421201"}})
    # El driver legacy de prueba no declara el libro, así que primero habla el formato; con él declarado, el que
    # habla es la numeración. Se prueban los dos, que son dos negativas distintas.
    with pytest.raises(drivers.LibroQueElDestinoNoLleva):
        api.generar_asiento(doc, driver="diario_json", configuracion=CONFIG)
    diario_json.FORMATOS["tesoreria"] = "diario_json"
    try:
        with pytest.raises(asiento.LibroQueTodaviaNoSeNumera) as e:
            api.generar_asiento(doc, driver="diario_json", configuracion=CONFIG)
        assert e.value.clave == "libro_que_todavia_no_se_numera"
    finally:
        del diario_json.FORMATOS["tesoreria"]


# --- lo que no se asienta dos veces --------------------------------------------------------------------------

def test_una_relectura_con_solape_no_asienta_el_mismo_dinero_dos_veces(registrados):
    """Bajar el extracto dos veces es lo normal. `preparar_tesoreria` descarta el repetido por su clave, al
    contrario que `preparar`, que devuelve «todos» para que quien llama los cuente."""
    uno = mov()
    doc = _documento([uno, dict(uno, id_externo="mov-1-otra-vez")], {"mov-1": {"cuenta_contable": "421201"}})
    r = api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert r["_asiento"]["lineas"] == 2 and len(r["_asiento"]["movimientos"]) == 1


def test_la_imputacion_de_un_repetido_no_se_rechaza_por_huerfana(registrados):
    """Se casa contra TODOS los movimientos y no solo contra los que entran: rechazar la imputación del que se
    descartó por repetido sería castigar una relectura."""
    uno = mov()
    doc = _documento([uno, dict(uno, id_externo="mov-1-otra-vez")],
                     {"mov-1": {"cuenta_contable": "421201"},
                      "mov-1-otra-vez": {"cuenta_contable": "421201"}})
    r = api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG)
    assert r["_asiento"]["lineas"] == 2


def test_los_correlativos_no_se_usan_en_tesoreria(registrados):
    """Con vocabulario neutral el motor no numera, así que `correlativos` no tiene dónde aplicarse: ni se escribe
    en ninguna línea ni aparece un rango de sub-diario."""
    doc = _documento([mov()], {"mov-1": {"cuenta_contable": "421201"}})
    r = api.generar_asiento(doc, driver="erp_tesoreria", configuracion=CONFIG, correlativos={"06": 50})
    assert r["_asiento"]["sub_diarios"] == {}
    assert all(not ln.get("correlativo") and not ln.get("sub_diario") for ln in r["asiento"])


# --- el maestro, en la configuración -------------------------------------------------------------------------

def test_el_maestro_se_publica_como_configuracion(registrados):
    """Decisión de John (13-oct-2026): es lo que la empresa ES —sus cuentas, con la 104 de cada una— y no lo que un
    periodo dijo, así que viaja en la configuración y `describir_configuracion` lo publica para que una aplicación
    sepa dónde guardarlo."""
    general = {campo["clave"]: campo for campo in api.describir_configuracion()["general"]["campos"]}
    assert general["cuentas_bancarias"]["tipo"] == "lista"
    assert general["cuentas_bancarias"]["grupo"] == "cuentas"


def test_sin_maestro_declarado_el_asiento_dice_que_le_falta_la_104(registrados):
    """Y no sale con una cuenta inventada, que es lo que la regla «sin imputación no hay cuenta» promete también
    para el dinero."""
    doc = _documento([mov()], {"mov-1": {"cuenta_contable": "421201"}})
    with pytest.raises(asiento.SinCuentaDeEfectivo):
        api.generar_asiento(doc, driver="erp_tesoreria", configuracion={"usa_centros_costo": False})
