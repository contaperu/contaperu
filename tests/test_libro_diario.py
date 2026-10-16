"""El Libro Diario: el libro que el motor no arma, sino que recibe (B13).

Es el cuarto tipo de libro y el primero de su clase. Los tres anteriores salen de hechos que el motor convierte
en asiento —un comprobante, un movimiento—; éste **llega con el asiento hecho**, en el bloque `asiento` del
documento, y tiene que llegar así: armar una planilla pide las reglas de la planilla, y una depreciación el
activo y su vida útil. Ninguna de las dos está en este motor ni va a estarlo.

Lo que sí aporta el motor, y es lo que estos tests fijan: leer cada línea con su contrato, **cuadrarla**, darle
su huella y llevarla a un destino que la declare — o rechazarla nombrando los que sí la llevan.

El caso real que lo destrabó: un Libro Diario 5.1 presentado y aceptado, de un mes de 2026, con 12 094 líneas en
1 441 asientos repartidos en 19 sub-diarios. Vive en `privado/` y no entra aquí; lo que entra son los datos que
dejó, que son éstos y los de la enmienda.
"""
from __future__ import annotations

import json

import pytest

from contaperu import api
from contaperu.errores import DocumentoInvalido

LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202606", "tipo": "diario"}


def _linea(cuenta: str, lado: str, importe: str, clase: str, asiento: str = "pl-06") -> dict:
    """Una línea de diario como la manda un ERP: ya numerada, con su sub-diario y su asiento."""
    return {"cuenta": cuenta, "debe_haber": lado, "importe": importe, "clase": clase,
            "glosa": "Planilla junio", "fecha": "2026-06-30", "sub_diario": "35", "correlativo": "0001",
            "documento": {"id_externo": asiento}}


def _planilla(**extra) -> dict:
    """El asiento que ningún motor de comprobantes puede producir: el gasto de personal contra lo que se le debe."""
    return {"open_accounting": api.OPEN_ACCOUNTING, "libro": LIBRO,
            "asiento": [_linea("621101", "D", "5000.00", "gasto"),
                        _linea("411101", "H", "5000.00", "pasivo")], **extra}


def test_el_motor_no_origina_este_libro_y_lo_dice_en_su_fila():
    """La fila declara lo que el motor NO hace con él, que es casi todo, y esa es la mitad útil de la tabla."""
    rasgos = api.rasgos_de("diario")
    assert rasgos.origen == "asiento", "sus líneas salen del bloque del asiento, no de comprobantes ni movimientos"
    assert rasgos.roles == (), "no emite ninguna línea suya, así que no declara qué papeles caben"
    assert rasgos.sub_diario == "", "ya viene numerado: el CUO es de quien lo mandó"
    assert not (rasgos.da_credito_fiscal or rasgos.lleva_detraccion or rasgos.lleva_honorarios)

    from contaperu.asiento.comprobante import TIPOS_DEL_MOTOR
    assert "diario" not in TIPOS_DEL_MOTOR, "el motor no lo origina, y por eso no está aquí"


def test_un_asiento_de_planilla_entra_cuadra_y_tiene_huella():
    """Lo que el motor aporta a un libro que ya está armado: leerlo, cuadrarlo y darle su huella."""
    respuesta = api.generar_asiento(_planilla(), driver="asiento_contable")
    assert respuesta["_asiento"]["lineas"] == 2
    assert respuesta["_asiento"]["cuadre"]["cuadra"] is True
    assert respuesta["_asiento"]["huella"]
    # Las líneas salen tal cual llegaron: el motor no las rearma ni las renumera.
    assert [ln["cuenta"] for ln in respuesta["asiento"]] == ["621101", "411101"]
    assert respuesta["asiento"][0]["correlativo"] == "0001"


def test_un_asiento_que_no_cuadra_no_sale():
    """La única regla que este libro sí tiene que pasar, y no se negocia: Debe igual a Haber."""
    torcido = _planilla()
    torcido["asiento"][1]["importe"] = "4000.00"
    diagnostico = api.diagnosticar(torcido, driver="asiento_contable")
    assert not diagnostico["listo_para_exportar"]
    assert any("no cuadra" in razon for razon in diagnostico["por_que_no"])
    with pytest.raises(Exception):
        api.exportar_archivo(torcido, driver="asiento_contable")


def test_sin_el_bloque_asiento_se_dice_que_el_motor_no_sabe_armarlo():
    """Un documento de este libro sin su bloque no es un mes vacío: es un documento que no se puede atender.

    Importa que el mensaje lo diga así. «No hay nada que exportar» invitaría a buscar el fallo en los datos,
    cuando lo que pasa es que de este libro el motor no produce líneas, solo las recibe."""
    sin_asiento = {"open_accounting": api.OPEN_ACCOUNTING, "libro": LIBRO}
    with pytest.raises(DocumentoInvalido) as fallo:
        api.generar_asiento(sin_asiento, driver="asiento_contable")
    assert "no sabe armar" in str(fallo.value) or "recibirlas" in str(fallo.value)


def test_el_diagnostico_no_rellena_con_ceros_lo_que_es_de_otro_libro():
    """Lo mismo que la 13.0 arregló en tesorería, aplicado desde el primer día a éste.

    Un diario no tiene comprobantes, ni observaciones, ni detracciones, ni sub-diarios que contar. Publicar esas
    claves en cero diría «se miró y no hay» donde la verdad es «aquí eso no existe»."""
    diagnostico = api.diagnosticar(_planilla(), driver="asiento_contable")
    assert diagnostico["totales"] == {"lineas": 2, "asientos": 1}
    for ajena in ("bloqueantes", "avisos", "detracciones_pendientes", "resumen_por_contraparte", "sub_diarios"):
        assert ajena not in diagnostico, f"{ajena} es del comprobante y no tiene nada que decir de un diario"
    assert diagnostico["cuadre"]["cuadra"] is True


def test_un_destino_que_no_lo_declara_lo_rechaza_nombrando_los_que_si():
    """La degradación que el estándar promete para un tipo de libro: la hace el destino, no el documento.

    CONCAR no lo lleva porque nadie ha visto un Excel suyo con un asiento de planilla dentro, y el PLE tampoco
    **todavía** —escribiría un TXT vacío, porque sus filas salen del índice y este libro no tiene—."""
    for driver in ("concar", "contasis", "sire", "ple"):
        diagnostico = api.diagnosticar(_planilla(), driver=driver)
        assert not diagnostico["listo_para_exportar"]
        assert any("no lleva" in razon and "diario" in razon for razon in diagnostico["por_que_no"]), driver


def test_el_archivo_neutral_vuelve_a_entrar_y_rearma_lo_mismo():
    """El ida y vuelta cerrado, como en tesorería: lo que sale vuelve a entrar y da lo mismo por los dos lados."""
    exportado = api.exportar_archivo(_planilla(), driver="asiento_contable")
    assert exportado.archivo == "ASIENTO_CONTABLE_DIARIO_202606_20601234567.json"

    devuelta = json.loads(exportado.contenido.decode("utf-8"))
    assert devuelta["libro"]["tipo"] == "diario"
    assert len(devuelta["asiento"]) == 2

    primera = api.generar_asiento(_planilla(), driver="asiento_contable")["_asiento"]["huella"]
    segunda = api.generar_asiento(devuelta, driver="asiento_contable")["_asiento"]["huella"]
    assert primera == segunda, "rearmarlo tiene que dar la misma huella"
    assert api.exportar_archivo(devuelta, driver="asiento_contable").contenido == exportado.contenido


def test_el_csv_lo_escribe_y_su_columna_de_rol_sale_vacia():
    """El rol de una línea de diario no se deriva, y la columna sale vacía en vez de romper.

    La regla del rol lee el lado contra el del libro o la cuenta contra el elemento 10 del PCGE. Un diario no
    fija lado y sus líneas pueden ser cualquier cosa, así que derivar sería adivinar. Que el CSV lo escriba igual
    es lo que permite que un destino neutral lleve este libro."""
    from contaperu.drivers.kit.rol import rol_de

    assert rol_de(_linea("621101", "D", "5000.00", "gasto"), api.rasgos_de("diario")) == ""
    texto = api.exportar_archivo(_planilla(), driver="csv").contenido.decode("utf-8-sig")
    assert "621101" in texto and "411101" in texto


def test_dos_asientos_distintos_se_cuentan_como_dos():
    """Un asiento es un CUO, y en el estándar los une `documento.id_externo`. Es lo que cuenta `totales.asientos`."""
    dos = {"open_accounting": api.OPEN_ACCOUNTING, "libro": LIBRO,
           "asiento": [_linea("621101", "D", "5000.00", "gasto", asiento="pl-06"),
                       _linea("411101", "H", "5000.00", "pasivo", asiento="pl-06"),
                       # La depreciación del mes: el gasto contra la depreciación ACUMULADA, que es `activo`
                       # (contra-activo) y no pasivo — el elemento 3 no se mueve, que es la regla que el repo
                       # ya tenía escrita sobre este asiento.
                       _linea("681401", "D", "300.00", "gasto", asiento="dep-06"),
                       _linea("391301", "H", "300.00", "activo", asiento="dep-06")]}
    diagnostico = api.diagnosticar(dos, driver="asiento_contable")
    assert diagnostico["totales"] == {"lineas": 4, "asientos": 2}
