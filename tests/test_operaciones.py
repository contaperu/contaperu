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
    assert doc["pe_ledger"] == op.PE_LEDGER and doc["libro"]["ruc"] == "20601111111"


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
            "total": "118", "cuenta_contable": "659999"}
    doc = {"libro": LIBRO, "comprobantes": [
        dict(base, numero="1"),
        dict(base, numero="2", excluida=True),
    ]}
    r = op.generar_asiento(doc)
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
    txt = gen.generar(libro, comprobantes, "sire", incluir_errores=True).txt.decode("utf-8")

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
    anidada = op.configuracion({"concar": {"cuentas": {"igv": "401199"}}})
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


def test_los_campos_del_registro_viajan_intactos():
    """`condicion_pago` y `cuenta_tercero` entran y salen por cada operación sin que nadie los pierda, y la
    cuenta del registro manda en el asiento: la línea del proveedor lleva la que escribió el contador."""
    from util import XML

    base = {"tipo_cp": "01", "serie": "F001", "numero": "7", "fecha_emision": "2026-01-10",
            "contraparte_doc": "20602222226", "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
            "base_gravada": "100", "igv": "18", "total": "118", "cuenta_contable": "659999"}
    doc = {"libro": LIBRO, "comprobantes": [dict(base, condicion_pago="credito", cuenta_tercero="469901")]}

    revisado = op.revisar(doc)["comprobantes"][0]
    assert (revisado["condicion_pago"], revisado["cuenta_tercero"]) == ("credito", "469901")

    def cuentas_del_tercero(documento):
        return [ln["cuenta"] for ln in op.generar_asiento(documento)["asiento"] if ln["rol"] == "tercero"]

    assert cuentas_del_tercero(doc) == ["469901"]
    # Vacía: la de la configuración por moneda, exactamente como antes de que existiera el campo.
    assert cuentas_del_tercero({"libro": LIBRO, "comprobantes": [base]}) == ["421201"]

    assert "469901" in op.exportar(doc, "csv")["texto"]

    ventas = {"ruc": "20131312955", "razon_social": "EMISOR DE PRUEBA S.A.C.", "periodo": "202601", "tipo": "venta"}
    xml = base64.b64encode((XML / "20131312955-01-F001-123.xml").read_bytes()).decode()
    assert op.leer_xml(xml, ventas, es_base64=True)["comprobantes"][0]["condicion_pago"] == "credito"
