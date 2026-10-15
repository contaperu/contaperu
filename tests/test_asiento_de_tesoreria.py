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

import base64
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


# ── El archivo, y el ida y vuelta (12.10) ──────────────────────────────────────────────────────────────────────
#
# Hasta aquí el asiento existía y no había destino al que mandarlo. El driver neutral declara el libro —su formato
# es el estándar mismo, que lleva los tres— y escribe el documento completo; y lo que de verdad prueba que el
# formato sirve es que el archivo **vuelva a entrar y dé lo mismo**, en los dos sentidos: reexportarlo y rearmarlo.

def _exportado(doc: dict, config: dict | None = None) -> tuple[dict, dict]:
    """`api.exportar` hacia el driver neutral, y el archivo ya decodificado."""
    r = api.exportar(doc, driver="asiento_contable", configuracion=config or CONFIG, fecha="2026-10-14")
    return r, json.loads(base64.b64decode(r["contenido_base64"]))


def _mes() -> dict:
    """Un mes con las dos formas que llenan todos los campos: un pago con su ITF y su glosa, y una comisión."""
    return _documento(
        [mov(contraparte_doc="20602222226", itf="0.10"),
         mov(id_externo="mov-2", referencia="000124", importe="15.00", descripcion="COMISION MANTENIMIENTO")],
        {"mov-1": {"cuenta_contable": "421201", "contraparte_doc": "20602222226", "glosa": "PAGO A PROVEEDOR"},
         "mov-2": {"cuenta_contable": "639101"}})


def test_el_driver_neutral_lleva_los_tres_libros_y_el_nombre_lo_dice():
    """El nombre del archivo sale de la tabla desde la 12.10 (`etiqueta_de_archivo`). Hasta entonces lo decidía
    `'VENTAS' if libro.es_venta else 'COMPRAS'` —el último sitio donde el booleano que la 9.0 retiró seguía
    decidiendo algo— y habría llamado «COMPRAS» a un archivo de tesorería."""
    from contaperu.drivers import asiento_contable

    assert sorted(asiento_contable.FORMATOS) == ["compra", "tesoreria", "venta"]
    r, _ = _exportado(_mes())
    assert r["archivo"] == "ASIENTO_CONTABLE_TESORERIA_202610_20601234567.json"
    assert "COMPRAS" not in r["archivo"] and "VENTAS" not in r["archivo"]


def test_el_archivo_lleva_los_cuatro_bloques_y_valida_contra_el_estandar():
    """Los `movimientos`, su imputación, el `asiento` y `_exportacion`. **Con los cuatro el documento se basta**, y
    eso es más de lo que promete el de compras: aquél no escribe su bloque `imputaciones`."""
    jsonschema = pytest.importorskip("jsonschema")
    _, archivo = _exportado(_mes())
    assert sorted(archivo) == ["_exportacion", "asiento", "imputaciones_de_movimientos", "libro", "movimientos",
                               "open_accounting"]
    assert len(archivo["movimientos"]) == 2 and len(archivo["imputaciones_de_movimientos"]) == 2
    # Ni la 104 ni el efecto entran: la primera sale del maestro y el segundo se deriva, y el estándar no los
    # declara en un movimiento.
    assert all("cuenta_contable" not in m and "efecto" not in m for m in archivo["movimientos"])
    jsonschema.Draft202012Validator(api.esquema_open_accounting()).validate(archivo)


def test_el_ida_y_vuelta_reexportando_da_el_mismo_archivo_byte_a_byte():
    """La garantía fuerte del formato: el archivo vuelve a entrar y sale igual. No se rearma —el bloque `asiento`
    que trae manda, igual que en compras (5.2)—, así que ni el orden de las líneas ni la huella se pueden mover."""
    primera, archivo = _exportado(_mes())
    segunda, otra_vez = _exportado(archivo)
    assert segunda["resumen"]["huella"] == primera["resumen"]["huella"]
    assert otra_vez == archivo, "el archivo reexportado tiene que ser el mismo documento"
    assert base64.b64decode(segunda["contenido_base64"]) == base64.b64decode(primera["contenido_base64"])


def test_el_ida_y_vuelta_REARMANDO_tambien_da_la_misma_huella():
    """Y ésta es la que el de compras no puede dar: quitándole el bloque `asiento`, el motor lo **rearma** desde
    los movimientos y su imputación —los dos están en el archivo— y sale la misma huella y las mismas líneas."""
    primera, archivo = _exportado(_mes())
    sin_asiento = {k: v for k, v in archivo.items() if k not in ("asiento", "_exportacion")}
    rearmado = api.generar_asiento(sin_asiento, driver="asiento_contable", configuracion=CONFIG)
    assert rearmado["_asiento"]["huella"] == primera["resumen"]["huella"]
    assert rearmado["asiento"] == archivo["asiento"]


def test_la_respuesta_trae_las_dos_cuentas_y_valida_contra_el_esquema_publicado():
    jsonschema = pytest.importorskip("jsonschema")
    r, _ = _exportado(_mes())
    assert (r["comprobantes"], r["movimientos"]) == (0, 2)
    assert r["_exportacion"]["comprobantes"] == [] and len(r["_exportacion"]["movimientos"]) == 2
    contrato = api.contrato_openconta()
    jsonschema.Draft202012Validator({**contrato, "$ref": "#/components/schemas/exportacion"}).validate(r)


def test_el_resumen_cuenta_lo_que_se_dejo_fuera():
    """«El resumen de una exportación cuenta lo que se dejó fuera», y en tesorería lo que se deja fuera es la
    relectura del mismo extracto. El ITF va aparte de los cargos, con el mismo criterio que `revisar_tesoreria`."""
    doc = _mes()
    doc["movimientos"].append(dict(doc["movimientos"][0], id_externo="mov-1-otra-vez"))
    r, _ = _exportado(doc)
    assert r["resumen"]["movimientos"] == 2 and r["resumen"]["repetidos"] == 1
    assert r["resumen"]["cargos"] == "2015.00" and r["resumen"]["abonos"] == "0.00"
    assert r["resumen"]["itf"] == "0.10", "el ITF no es un cargo del titular hacia un tercero"


def test_el_archivo_de_compras_no_gana_ni_una_clave():
    """El dispatch no toca el otro camino: el documento de una compra sigue siendo el de siempre, sin `movimientos`
    y sin imputaciones. Lo que lo prueba celda a celda es `tests/fixtures/caracterizacion/`."""
    from util import GOLDEN, imputando
    compras = imputando(json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8")), "659999")
    r, archivo = _exportado(compras, {"usa_centros_costo": False})
    assert sorted(archivo) == ["_exportacion", "asiento", "comprobantes", "libro", "open_accounting"]
    assert (r["comprobantes"], r["movimientos"]) == (3, 0)
    assert r["_exportacion"]["movimientos"] == []


def test_un_destino_que_declara_el_libro_y_no_arma_asientos_se_para_en_voz_alta(monkeypatch):
    """Hoy no puede pasar con un driver de serie, y ése es el momento de ponerlo: un registro es una fila por
    comprobante, así que de un libro de movimientos saldría un archivo vacío con pinta de correcto."""
    from contaperu.drivers import contasis
    from contaperu.pipeline.salida import LibroQueEseDestinoNoArma

    assert not drivers.contrato.arma_asientos(contasis)
    monkeypatch.setitem(contasis.FORMATOS, "tesoreria", "contasis_xlsx")
    with pytest.raises(LibroQueEseDestinoNoArma) as e:
        api.exportar(_mes(), driver="contasis", configuracion=CONFIG)
    assert e.value.clave == "libro_que_ese_destino_no_arma" and e.value.driver == "contasis"


def test_una_linea_que_no_dice_de_que_movimiento_es_no_pasa():
    """La vuelta reconoce las líneas por `documento.id_externo`, que es para lo que el estándar lo puso. Sin él no
    se adivina por cuenta ni por importe: saldría un archivo incompleto con pinta de correcto."""
    _, archivo = _exportado(_mes())
    sin_enlace = copy.deepcopy(archivo)
    del sin_enlace["asiento"][0]["documento"]["id_externo"]
    with pytest.raises(asiento.LineaSinMovimiento) as e:
        api.exportar(sin_enlace, driver="asiento_contable", configuracion=CONFIG)
    assert "no dice de qué movimiento es" in str(e.value)

    de_otro = copy.deepcopy(archivo)
    de_otro["asiento"][0]["documento"]["id_externo"] = "mov-que-no-esta"
    with pytest.raises(asiento.LineaSinMovimiento) as e:
        api.exportar(de_otro, driver="asiento_contable", configuracion=CONFIG)
    assert "que no está en el documento" in str(e.value)


def test_las_dos_imputaciones_no_son_configuracion_y_el_motor_lo_dice():
    """Las dos viajan DENTRO de la configuración y ninguna ES configuración, así que ponerlas ahí a mano se
    rechaza diciendo dónde van. La de un movimiento entró en esa lista con la 12.10: hasta entonces
    `armado.config_para` la rechazaba como «clave desconocida» al exportar, que es cierto y no ayuda."""
    from contaperu import configuracion as decl

    assert decl.NO_SON_CONFIGURACION == ("imputaciones", "imputaciones_de_movimientos")
    errores = api.errores_de_configuracion({"imputaciones_de_movimientos": {}})
    assert errores and "del documento" in errores[0]


def test_el_asiento_que_el_documento_TRAE_manda_sobre_el_que_el_motor_derivaria():
    """La promesa de la 5.2, en el camino del dinero: con el bloque `asiento` puesto, el motor **no lo rearma**.

    Importa porque un ERP puede llevar él el asiento —es la puerta que la 5.2 abrió— y rearmarlo le cambiaría las
    cuentas que decidió. Se prueba cambiando una cuenta a mano: si el motor rearmara, saldría la suya."""
    _, archivo = _exportado(_mes())
    a_mano = copy.deepcopy(archivo)
    for linea in a_mano["asiento"]:
        if linea["cuenta"] == "421201":
            linea["cuenta"] = "421202"       # otra divisionaria del mismo pasivo, que el motor no derivaría
    _, escrito = _exportado(a_mano)
    assert [ln["cuenta"] for ln in escrito["asiento"]] == [ln["cuenta"] for ln in a_mano["asiento"]]
    assert "421202" in {ln["cuenta"] for ln in escrito["asiento"]}, "lo que el documento trae no se rearma"


def test_un_asiento_dado_que_no_cuadra_no_pasa():
    """Entrar por la puerta de las líneas dadas no relaja ninguna regla: la partida doble se exige igual."""
    _, archivo = _exportado(_mes())
    descuadrado = copy.deepcopy(archivo)
    descuadrado["asiento"][0]["importe"] = "1999.00"
    with pytest.raises(api.Descuadre):
        api.exportar(descuadrado, driver="asiento_contable", configuracion=CONFIG)
