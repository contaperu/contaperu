"""`aplicaciones[]`: cuánto de esto cancela aquello (12.3, enmienda 0031).

El bloque que une los tres libros. Lo que estos casos fijan es el contrato, porque **aquí todavía no se suma
nada**: la forma de las dos caras, qué clase cabe en cada una, lo que `propuesto` significa, y que lo que una
aplicación nombra **no tiene que viajar en el documento** —se avisa y no se para—.

Las tres reglas que vienen de la investigación de ocho sistemas (`REFERENCIAS.md`, 12-oct-2026) y que estos casos
hacen cumplir: es un registro aparte con su importe y N a N; **tres pagos para una factura son tres aplicaciones y
el tercero no es especial**; y el saldo se deriva de la suma, así que no hay ningún campo de estado que mantener.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from contaperu import api, aplicaciones as ap
from contaperu.errores import DocumentoInvalido
from contaperu.modelo import Comprobante
from contaperu.pipeline import preparacion as prep
from contaperu.tesoreria import Movimiento

LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202603", "tipo": "compra"}
FACTURA = {"tipo_cp": "01", "serie": "F001", "numero": "123", "contraparte_doc": "20602222226"}

CP = {"clase": "comprobante", "datos": dict(FACTURA)}
MOV = {"clase": "movimiento", "datos": {"id_externo": "mov-7"}}
TRIB = {"clase": "tributo", "datos": {"codigo": "1011", "periodo": "202602"}}


def una(**extra) -> dict:
    return {"de": dict(MOV), "a": dict(CP), "importe": "400.00", "moneda": "PEN",
            "fecha": "2026-03-10", "origen": "manual", **extra}


def doc(*aplicaciones: dict, **extra) -> dict:
    return {"open_accounting": "3.3", "libro": dict(LIBRO), "aplicaciones": list(aplicaciones), **extra}


# --- la forma -----------------------------------------------------------------------------------------------------

def test_una_aplicacion_tiene_dos_caras_un_importe_y_una_fecha():
    a = ap.Aplicacion.de_dict(una())
    assert a.de.clase == "movimiento" and a.a.clase == "comprobante"
    assert a.importe == Decimal("400.00") and a.moneda == "PEN"
    assert a.fecha == date(2026, 3, 10) and a.origen == "manual"
    assert a.a_dict() == una()


def test_la_ida_y_la_vuelta_no_pierde_nada():
    a = ap.Aplicacion.de_dict(una(origen="declarado"))
    assert ap.Aplicacion.de_dict(a.a_dict()).a_dict() == a.a_dict()


def test_el_importe_es_positivo_y_la_direccion_la_dicen_los_nombres():
    """La regla de la casa: ningún importe lleva signo. Lo que distingue quién paga a quién son `de` y `a`."""
    with pytest.raises(ap.AplicacionInvalida, match="no aplica nada"):
        ap.Aplicacion.de_dict(una(importe="0"))


def test_tres_pagos_para_una_factura_son_tres_aplicaciones_y_el_tercero_no_es_especial():
    """El caso canónico, y la razón de que el saldo se derive: ninguna de las tres sabe que cierra la factura, y
    ninguna tiene que saberlo."""
    tres = ap.leer([una(de={"clase": "movimiento", "datos": {"id_externo": f"mov-{i}"}}, importe=importe,
                        fecha=f"2026-0{i}-10")
                    for i, importe in ((1, "400.00"), (2, "400.00"), (3, "480.00"))])
    assert [str(a.importe) for a in tres] == ["400.00", "400.00", "480.00"]
    assert {a.a.clave for a in tres} == {ap.Extremo.de(CP).clave}
    assert len({a.de.clave for a in tres}) == 3


def test_una_factura_de_otro_mes_se_nombra_igual_que_una_de_este():
    """Funciona porque la identidad de un comprobante no lleva el periodo, y es lo que hace posible una factura de
    enero pagada en marzo. Un cero a la izquierda no la cambia: la calcula la misma función que `Comprobante.clave`."""
    c = Comprobante(**dict(FACTURA, fecha_emision="2026-01-15", total="1280.00"))
    assert ap.Extremo.de({"clase": "comprobante", "datos": dict(FACTURA, numero="00123")}).clave[1] == c.clave


# --- qué cabe en cada cara ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("extremo", [MOV, CP])
def test_en_de_cabe_lo_que_paga(extremo: dict):
    assert ap.Aplicacion.de_dict(una(de=dict(extremo))).de.clase == extremo["clase"]


@pytest.mark.parametrize("extremo", [CP, TRIB])
def test_en_a_cabe_lo_que_se_cancela(extremo: dict):
    assert ap.Aplicacion.de_dict(una(a=dict(extremo))).a.clase == extremo["clase"]


def test_un_tributo_no_paga_y_un_movimiento_no_se_cancela():
    """Las dos asimetrías del bloque, dichas en el error."""
    with pytest.raises(ap.AplicacionInvalida, match="no cabe en `de`"):
        ap.Aplicacion.de_dict(una(de=dict(TRIB)))
    with pytest.raises(ap.AplicacionInvalida, match="no cabe en `a`"):
        ap.Aplicacion.de_dict(una(a=dict(MOV)))


@pytest.mark.parametrize("clase, datos", [("libre", {"texto": "caja chica"}), ("cuenta_propia", {"cuenta": "bbva"})])
def test_las_dos_clases_de_referencia_que_NO_son_aplicaciones(clase: str, datos: dict):
    """Son clases legítimas de `referencia_de_pago` y aquí no caben: una aplicación reduce un saldo, y contra un
    texto libre no se deriva nada. Un traspaso entre cuentas propias ya se declara en la imputación."""
    with pytest.raises(ap.AplicacionInvalida, match="Clase inválida"):
        ap.Aplicacion.de_dict(una(a={"clase": clase, "datos": datos}))


def test_una_nota_de_credito_contra_su_factura_es_una_aplicacion():
    """El enlace que hasta hoy había que marcar a mano (`anulada_por_nota`), porque solo la nota apunta hacia atrás.
    Aquí se recorre en el sentido que hace falta."""
    nota = {"clase": "comprobante", "datos": {"tipo_cp": "07", "serie": "FC01", "numero": "9",
                                              "contraparte_doc": "20602222226"}}
    a = ap.Aplicacion.de_dict(una(de=nota, importe="1280.00", origen="declarado"))
    assert a.de.clave[1][0] == "07" and a.a.clave[1][0] == "01"


# --- lo que el modelo no admite -----------------------------------------------------------------------------------

@pytest.mark.parametrize("falta", ["de", "a", "importe", "moneda", "fecha", "origen"])
def test_los_seis_campos_son_obligatorios(falta: str):
    crudo = una()
    del crudo[falta]
    with pytest.raises(ap.AplicacionInvalida):
        ap.Aplicacion.de_dict(crudo)


def test_una_clave_que_no_es_de_una_aplicacion_se_rechaza_y_se_nombra():
    with pytest.raises(ap.AplicacionInvalida, match="glosa"):
        ap.Aplicacion.de_dict(una(glosa="PAGO FACTURA"))


def test_una_clave_que_no_es_de_un_extremo_se_rechaza():
    with pytest.raises(ap.AplicacionInvalida, match="importe"):
        ap.Aplicacion.de_dict(una(de={"clase": "movimiento", "datos": {"id_externo": "m"}, "importe": "1"}))


def test_un_extremo_con_una_clave_que_no_es_de_su_clase():
    with pytest.raises(ap.AplicacionInvalida, match="no lleva serie"):
        ap.Aplicacion.de_dict(una(a={"clase": "tributo", "datos": {"codigo": "1011", "serie": "F001"}}))


def test_un_extremo_sin_ningun_dato_no_nombra_nada():
    with pytest.raises(ap.AplicacionInvalida, match="no nombra nada"):
        ap.Aplicacion.de_dict(una(a={"clase": "comprobante", "datos": {"serie": ""}}))


@pytest.mark.parametrize("moneda", ["PE", "PENN", "pe1", ""])
def test_la_moneda_son_tres_letras_y_se_comprueba_la_forma_no_el_catalogo(moneda: str):
    """La misma decisión que en un movimiento: el catálogo es de SUNAT y puede crecer, así que un código de tres
    letras que hoy no exista no invalida nada."""
    with pytest.raises(ap.AplicacionInvalida, match="Moneda inválida"):
        ap.Aplicacion.de_dict(una(moneda=moneda))


def test_una_moneda_de_tres_letras_que_el_catalogo_no_tenga_vale():
    assert ap.Aplicacion.de_dict(una(moneda="xof")).moneda == "XOF"


def test_un_origen_que_no_dice_si_es_hecho_o_conjetura_se_rechaza():
    with pytest.raises(ap.AplicacionInvalida, match="Origen inválido"):
        ap.Aplicacion.de_dict(una(origen="conciliado"))


# --- `propuesto`: donde vive «propone y nunca confirma» -----------------------------------------------------------

@pytest.mark.parametrize("origen, cuenta", [("declarado", True), ("manual", True), ("propuesto", False)])
def test_una_propuesta_no_cuenta_para_ningun_saldo(origen: str, cuenta: bool):
    """La regla que convierte la doctrina en algo que un test puede poner en rojo. `conciliar` (D3) producirá
    `propuesto`, y por eso no puede mover un saldo sin que una persona la confirme."""
    assert ap.Aplicacion.de_dict(una(origen=origen)).cuenta_para_el_saldo is cuenta


def test_las_confirmadas_son_las_que_no_son_propuestas():
    """Fijado contra el catálogo y no a mano: si entrara un origen nuevo, este test obliga a decidir si cuenta."""
    assert set(ap.CONFIRMADAS) == set(ap.ORIGENES) - {ap.PROPUESTO}


# --- lo que no está en el documento: se avisa, no se para ---------------------------------------------------------

def test_lo_que_una_aplicacion_nombra_no_tiene_que_viajar_en_el_documento():
    """Y no puede exigirse: la factura de enero está en el documento de enero, y su pago se nombra desde marzo."""
    assert prep.aplicaciones_de(doc(una())), "una aplicación sin su comprobante delante tiene que leerse igual"


def test_el_motor_dice_que_nombran_algo_que_no_esta_aqui():
    aplicadas = ap.leer([una()])
    sueltas = ap.sin_documento_declarado(aplicadas)
    assert [s["que"] for s in sueltas] == ["de", "a"]
    assert {s["clase"] for s in sueltas} == {"movimiento", "comprobante"}


def test_con_los_dos_documentos_delante_no_avisa_de_nada():
    c = Comprobante(**dict(FACTURA, fecha_emision="2026-01-15", total="1280.00"))
    m = Movimiento(cuenta="bbva-soles", fecha="2026-03-10", importe="400.00", sentido="cargo", id_externo="mov-7")
    assert ap.sin_documento_declarado(ap.leer([una()]), [c], [m]) == []


def test_un_cero_de_mas_en_el_numero_no_es_una_llave_distinta():
    """Lo que el aviso NO debe cazar: la identidad se normaliza con la misma función que el comprobante."""
    c = Comprobante(**dict(FACTURA, fecha_emision="2026-01-15", total="1280.00"))
    suelta = una(a={"clase": "comprobante", "datos": dict(FACTURA, numero="000123")})
    assert [s["que"] for s in ap.sin_documento_declarado(ap.leer([suelta]), [c])] == ["de"]


def test_un_tributo_no_se_busca_en_el_documento():
    """No hay dónde: un tributo no es un documento de este libro. Avisar de él sería ruido en cada pago de IGV."""
    aplicadas = ap.leer([una(a=dict(TRIB))])
    assert [s["que"] for s in ap.sin_documento_declarado(aplicadas)] == ["de"]


# --- el bloque, por la puerta del documento ----------------------------------------------------------------------

def test_el_bloque_ausente_son_cero_aplicaciones_y_no_un_error():
    assert prep.aplicaciones_de({"libro": dict(LIBRO)}) == ()


def test_el_bloque_tiene_que_ser_una_lista():
    with pytest.raises(DocumentoInvalido, match="tiene que ser una lista"):
        prep.aplicaciones_de({"aplicaciones": {"de": MOV}})


def test_una_aplicacion_ilegible_se_dice_con_su_motivo():
    with pytest.raises(DocumentoInvalido, match="no se pudo leer"):
        prep.aplicaciones_de(doc(una(origen="inventado")))


def test_el_tope_existe_y_dice_que_hacer():
    assert prep.MAXIMO_APLICACIONES > prep.MAXIMO_MOVIMIENTOS, (
        "un pago que cancela diez facturas son diez aplicaciones: el tope tiene que ser mayor que el de movimientos")
    with pytest.raises(DocumentoInvalido, match="el tope es"):
        prep.aplicaciones_de({"aplicaciones": [una()] * (prep.MAXIMO_APLICACIONES + 1)})


# --- el estándar ---------------------------------------------------------------------------------------------------

def test_el_estandar_valida_un_documento_con_aplicaciones():
    pytest.importorskip("jsonschema")
    assert api.verificar_documento(doc(una(), una(a=dict(TRIB)), una(origen="propuesto")))["conforme"] is True


@pytest.mark.parametrize("mala", [
    {"de": MOV, "a": CP, "importe": "1.00", "moneda": "PEN", "fecha": "2026-03-10"},        # sin origen
    {"de": MOV, "a": CP, "importe": "1.00", "moneda": "PEN", "origen": "manual"},           # sin fecha
    {"de": MOV, "a": CP, "importe": "1.00", "fecha": "2026-03-10", "origen": "manual"},     # sin moneda
    {"de": TRIB, "a": CP, "importe": "1.00", "moneda": "PEN", "fecha": "2026-03-10", "origen": "manual"},
    {"de": MOV, "a": MOV, "importe": "1.00", "moneda": "PEN", "fecha": "2026-03-10", "origen": "manual"},
    {"de": MOV, "a": CP, "importe": "1.00", "moneda": "PEN", "fecha": "2026-03-10", "origen": "conciliado"},
    {"de": MOV, "a": {"clase": "comprobante", "datos": {"codigo": "1011"}}, "importe": "1.00",
     "moneda": "PEN", "fecha": "2026-03-10", "origen": "manual"},
])
def test_el_estandar_rechaza_una_aplicacion_mal_formada(mala: dict):
    pytest.importorskip("jsonschema")
    assert api.verificar_documento(doc(mala))["conforme"] is False


def test_el_esquema_y_el_motor_admiten_las_mismas_clases_en_cada_cara():
    """Lo que la 3.0 aprendió con `referencia_de_pago`: mientras las claves vivían solo en Python, un validador que
    usara el JSON publicado aceptaba lo que el motor rechaza."""
    esquema = api.esquema_open_accounting()["$defs"]["aplicacion"]["properties"]
    assert set(esquema["de"]["allOf"][1]["properties"]["clase"]["enum"]) == set(ap.CLASES_QUE_PAGAN)
    assert set(esquema["a"]["allOf"][1]["properties"]["clase"]["enum"]) == set(ap.CLASES_QUE_SE_CANCELAN)
    assert set(esquema["origen"]["enum"]) == set(ap.ORIGENES)


def test_el_esquema_y_el_motor_admiten_las_mismas_claves_por_clase():
    extremo = api.esquema_open_accounting()["$defs"]["extremo_de_aplicacion"]
    assert set(extremo["properties"]["clase"]["enum"]) == set(ap.CLASES)
    publicadas = {rama["if"]["properties"]["clase"]["const"]:
                  tuple(rama["then"]["properties"]["datos"]["propertyNames"]["enum"])
                  for rama in extremo["allOf"]}
    assert publicadas == {clase: tuple(claves) for clase, claves in ap.CLAVES_POR_CLASE.items()}


def test_las_claves_del_comprobante_son_las_mismas_que_en_una_referencia():
    """No se reescriben: son la misma forma de nombrar lo mismo, y dos listas separadas se habrían separado."""
    from contaperu.tesoreria import referencias

    assert ap.CLAVES_POR_CLASE["comprobante"] == referencias.CLAVES_POR_CLASE["comprobante"]
    assert ap.CLAVES_POR_CLASE["tributo"] == referencias.CLAVES_POR_CLASE["tributo"]
