"""Las operaciones de documento a documento, por debajo del servidor MCP."""
from __future__ import annotations

import base64
import io
import zipfile

import pytest

from contaperu import operaciones as op

LIBRO = {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
         "periodo": "202601", "tipo": "compra"}


def test_el_documento_que_sale_declara_la_version_del_estandar():
    doc = op.documento(op.libro_de({"libro": LIBRO}), [])
    assert doc["open_accounting"] == op.OPEN_ACCOUNTING and doc["libro"]["ruc"] == "20601111111"


def test_un_libro_imposible_se_rechaza_con_su_motivo():
    for malo, trozo in (
        ({}, "Falta el bloque"),
        ({"libro": {"ruc": "123", "periodo": "202601", "tipo": "compra"}}, "RUC"),
        ({"libro": {"ruc": "20601111111", "periodo": "202613", "tipo": "compra"}}, "Periodo"),
        ({"libro": {"ruc": "20601111111", "periodo": "202601", "tipo": "inventario"}}, "Tipo de libro"),
    ):
        with pytest.raises(op.DocumentoInvalido, match=trozo):
            op.libro_de(malo)


def test_hay_un_tope_de_comprobantes_por_llamada():
    """Un mes de una PYME son decenas o cientos; miles casi siempre es un error de quien llama."""
    doc = {"libro": LIBRO, "comprobantes": [{"tipo_cp": "01"}] * (op.MAXIMO_COMPROBANTES + 1)}
    with pytest.raises(op.DocumentoInvalido, match="tope"):
        op.comprobantes_de(doc)


def test_exportar_sin_comprobantes_no_genera_un_archivo_vacio():
    with pytest.raises(op.DocumentoInvalido, match="No hay comprobantes"):
        op.exportar({"libro": LIBRO, "comprobantes": []})


def test_los_excluidos_no_entran_en_la_exportacion():
    base = {"tipo_cp": "01", "serie": "F001", "fecha_emision": "2026-01-10",
            "contraparte_doc": "20602222226", "base_gravada": "100", "igv": "18",
            "total": "118"}
    doc = {"libro": LIBRO, "comprobantes": [
        dict(base, numero="1"),
        dict(base, numero="2", excluida=True),
    ]}
    r = op.generar_asiento(doc, {"cuentas": {"gasto": "659999"}})
    assert len({ln["documento"]["serie_numero"] for ln in r["asiento"]}) == 1


def test_leer_un_zip_en_base64():
    """Los archivos entran por el protocolo en base64: un JSON no sabe llevar bytes."""
    from util import XML

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nombre in ("20131312955-01-F001-123.xml", "20131312955-01-F001-124.xml"):
            z.write(XML / nombre, nombre)
    b64 = base64.b64encode(buf.getvalue()).decode()

    doc = op.leer_xml(b64, dict(LIBRO, tipo="venta", periodo="202601"), es_base64=True)
    assert len(doc["comprobantes"]) == 2
    assert doc["_lectura"]["errores"] == []


def test_un_base64_roto_lo_dice():
    with pytest.raises(op.DocumentoInvalido, match="base64"):
        op.leer_xml("esto no es base64 %%%", LIBRO, es_base64=True)


def test_leer_la_propuesta_del_sire():
    """Se lee lo que SUNAT propone y se devuelve como documento del estándar."""
    from util import cargar_golden
    from contaperu import generar as gen

    libro, comprobantes = cargar_golden("compras_202601.json")
    txt = gen.generar(libro, comprobantes, "sire", incluir_errores=True).texto.decode("utf-8")

    doc = op.leer_propuesta_sire(txt, {"ruc": libro.ruc, "razon_social": libro.razon_social,
                                       "periodo": libro.periodo, "tipo": libro.tipo})
    assert len(doc["comprobantes"]) == len(comprobantes)
    assert all(c["origen"] == "sire" for c in doc["comprobantes"])


def test_la_configuracion_de_partida_se_puede_sobreescribir():
    de_serie = op.configuracion()
    mia = op.configuracion({"cuentas": {"igv": "401112"}})
    assert de_serie["cuentas"]["igv"] == "401111"
    assert mia["cuentas"]["igv"] == "401112"
    # Lo que no se toca se conserva: la fusion es en profundidad, no un reemplazo.
    assert mia["cuentas"]["cxp"]["PEN"] == de_serie["cuentas"]["cxp"]["PEN"]


def test_la_configuracion_que_sale_se_puede_volver_a_meter():
    """El viaje que hace cualquiera: pedir la de partida, cambiarle algo y devolverla.

    Si esto no funcionara, los cambios se ignorarian EN SILENCIO y el asiento saldria con
    las cuentas de serie sin que nadie se enterara."""
    mia = op.configuracion()
    mia["cuentas"]["gasto"] = "631201"
    mia["sub_diario_compras"] = "07"

    efectiva = op.configuracion(mia)

    assert efectiva["cuentas"]["gasto"] == "631201"
    assert efectiva["sub_diario_compras"] == "07"
    assert efectiva["cuentas"]["igv"] == "401111"          # lo demas intacto


def test_tambien_se_acepta_la_forma_anidada_de_las_aplicaciones():
    anidada = op.configuracion({"contabilidad": {"cuentas": {"igv": "401199"}}})
    assert anidada["cuentas"]["igv"] == "401199"


def test_un_xml_suelto_en_base64_se_lee(tmp_path):
    """Regresion: el contenido llegaba con el nombre 'entrada.zip', que forzaba la rama del
    ZIP, y un XML perfectamente valido se rechazaba con 'el ZIP esta danado'. Mandar un
    archivo en base64 es justo lo natural desde un agente."""
    from util import XML

    xml = (XML / "20131312955-01-F001-123.xml").read_bytes()
    libro = {"ruc": "20131312955", "razon_social": "EMISOR DE PRUEBA SAC",
             "periodo": "202601", "tipo": "venta"}

    doc = op.leer_xml(base64.b64encode(xml).decode(), libro, es_base64=True)

    assert len(doc["comprobantes"]) == 1 and doc["_lectura"]["errores"] == []
    # Y el mismo XML como texto da exactamente lo mismo.
    assert doc["comprobantes"] == op.leer_xml(xml.decode("utf-8"), libro)["comprobantes"]



def test_la_condicion_de_pago_y_el_id_externo_viajan_en_el_documento():
    """Son hechos del documento: entran y salen por cada operación sin que nadie los pierda."""
    from util import XML

    doc = {"libro": LIBRO, "comprobantes": [dict(BASE, condicion_pago="credito", id_externo="fila-7")]}
    revisado = op.revisar(doc)["comprobantes"][0]
    assert (revisado["condicion_pago"], revisado["id_externo"]) == ("credito", "fila-7")

    ventas = {"ruc": "20131312955", "razon_social": "EMISOR DE PRUEBA S.A.C.", "periodo": "202601", "tipo": "venta"}
    xml = base64.b64encode((XML / "20131312955-01-F001-123.xml").read_bytes()).decode()
    assert op.leer_xml(xml, ventas, es_base64=True)["comprobantes"][0]["condicion_pago"] == "credito"


BASE = {"tipo_cp": "01", "serie": "F001", "numero": "8", "fecha_emision": "2026-01-10",
        "contraparte_doc": "20602222226", "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
        "base_gravada": "100", "igv": "18", "total": "118", "id_externo": "fila-8"}


def _del_rol(asiento: dict, *roles: str) -> list[tuple[str, str]]:
    return [(ln["cuenta"], ln["importe"]) for ln in asiento["asiento"] if ln["rol"] in roles]


def test_la_cuenta_llega_solo_en_la_imputacion():
    """Desde open-accounting 0.3 la cuenta y el centro no son campos del comprobante: llegan en la imputación, por
    `id_externo`, y lo que no traiga sale de la configuración. Un documento que todavía los trae se rechaza en la
    puerta: perder su cuenta en silencio sería peor."""
    doc = {"libro": LIBRO, "comprobantes": [BASE]}
    config = {"cuentas": {"gasto": "659999"}}
    assert _del_rol(op.generar_asiento(doc, config), "principal", "tercero") == [("659999", "100.00"), ("421201", "118.00")]

    imputacion = {"fila-8": {"cuenta_contable": "637301", "cuenta_tercero": "469901"}}
    assert _del_rol(op.generar_asiento(doc, config, imputacion=imputacion), "principal", "tercero") == [
        ("637301", "100.00"), ("469901", "118.00")]
    # Solo la cuenta del total: la de la base sale de la configuración.
    solo_total = {"fila-8": {"cuenta_tercero": "469901"}}
    assert _del_rol(op.generar_asiento(doc, config, imputacion=solo_total), "principal") == [("659999", "100.00")]

    assert "469901" in op.exportar(doc, "csv", config, imputacion=imputacion)["texto"]
    assert "cuenta_contable" not in op.revisar(doc)["comprobantes"][0]
    with pytest.raises(op.DocumentoInvalido, match="imputación"):
        op.generar_asiento({"libro": LIBRO, "comprobantes": [dict(BASE, cuenta_contable="659999")]})


def test_el_reparto_da_una_linea_por_parte_y_tiene_que_cuadrar():
    """El reparto divide la base: una línea de gasto por parte, con el IGV y el proveedor intactos. Si no suma la
    base del asiento, `diagnosticar` lo dice y exportar se niega; a una parte sin cuenta le falta la cuenta."""
    from decimal import Decimal

    from contaperu.asiento import RepartoNoCuadra

    doc = {"libro": LIBRO, "comprobantes": [BASE]}
    reparto = [{"importe": "60", "cuenta_contable": "636301", "centro_costo": "SISTEMAS"},
               {"importe": "40", "cuenta_contable": "632201", "centro_costo": "DESARROLLO"}]
    asiento = op.generar_asiento(doc, imputacion={"fila-8": {"reparto": reparto}})
    assert _del_rol(asiento, "principal") == [("636301", "60.00"), ("632201", "40.00")]
    assert [importe for _, importe in _del_rol(asiento, "igv", "tercero")] == ["18.00", "118.00"]
    lineas = asiento["asiento"]
    assert (sum(Decimal(ln["importe"]) for ln in lineas if ln["debe_haber"] == "D")
            == sum(Decimal(ln["importe"]) for ln in lineas if ln["debe_haber"] == "H"))

    corto = {"fila-8": {"reparto": reparto[:1]}}
    d = op.diagnosticar(doc, driver="csv", imputacion=corto)
    assert len(d["faltantes"]["reparto_que_no_cuadra"]) == 1 and d["listo_para_exportar"] is False
    with pytest.raises(RepartoNoCuadra):
        op.exportar(doc, "csv", imputacion=corto)

    sin_cuenta = {"fila-8": {"reparto": [dict(reparto[0], cuenta_contable=""), reparto[1]]}}
    assert len(op.diagnosticar(doc, driver="csv", imputacion=sin_cuenta)["faltantes"]["sin_cuenta"]) == 1


def test_una_imputacion_ambigua_o_de_otro_documento_se_rechaza_en_la_puerta():
    """Un reparto con cuenta al lado no dice cuál manda; una llave que no es de ningún documento haría salir ese
    documento con la cuenta por defecto sin avisar. Las dos se rechazan antes de armar nada."""
    doc = {"libro": LIBRO, "comprobantes": [BASE]}
    ambigua = {"fila-8": {"reparto": [{"importe": "100", "cuenta_contable": "636301"}], "cuenta_contable": "659999"}}
    with pytest.raises(op.DocumentoInvalido, match="reparto"):
        op.generar_asiento(doc, imputacion=ambigua)
    with pytest.raises(op.DocumentoInvalido, match="fila-9"):
        op.generar_asiento(doc, imputacion={"fila-9": {"cuenta_contable": "659999"}})
