"""El documento `open-accounting` que produce el driver del asiento, congelado entero.

Es el hermano del snapshot de CONCAR y existe por lo mismo: ese Excel llevaba un año importándose en producción y un
refactor no tiene derecho a cambiarlo. Aquí el consumidor no es un sistema instalado sino **cualquier ERP que parta
del estándar**, y desde la 3.9 este documento es la salida principal para quien no tiene un sistema contable legacy.
Hasta entonces no había ningún snapshot suyo: `lineas_neutrales.json` prometía serlo y no lo era —se genera en
vocabulario legacy, y por eso se llama `lineas_legacy.json` desde la 3.9—.

Congela el documento completo: sus tres bloques y `_exportacion` con su huella. Lo único que se quita antes de
comparar es `_exportacion.motor`, que cambia en cada versión y movería el snapshot sin que nada de contabilidad
hubiera cambiado; se comprueba aparte.

**La política de regeneración no es la del snapshot de CONCAR.** Este puede crecer: el estándar gana bloques y campos
de forma aditiva, y un campo nuevo en un comprobante es legítimo. Lo que no lo es es que un movimiento QUITE una clave
o CAMBIE un valor: para un ERP ya integrado eso es una rotura, y entonces el diff se mira dato por dato y se anuncia
en el CHANGELOG.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_snapshot_del_documento as t; t.regenerar()"
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from contaperu import api

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshot"
DOCUMENTO = SNAPSHOT / "documento_del_estandar.json"

LIBROS = {"compra": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
                     "periodo": "202608", "tipo": "compra"},
          "venta": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
                    "periodo": "202608", "tipo": "venta"}}

BASE = {"tipo_cp": "01", "serie": "F001", "numero": "00000123", "fecha_emision": "2026-08-11",
        "fecha_vencimiento": "2026-08-18", "contraparte_tipo_doc": "6", "contraparte_doc": "20607777773",
        "contraparte_nombre": "ELECTROMECANICA DE PRUEBA S.R.L.", "moneda": "PEN",
        "base_gravada": "100.00", "igv": "18.00", "total": "118.00", "id_externo": "f1"}

# Cada caso vigila algo que el ASIENTO por sí solo no puede contar, que es la razón de que el bloque `comprobantes`
# exista. El nombre dice qué.
CASOS: list[tuple[str, str, dict]] = [
    # 100 gravado + 50 exonerado: el asiento los funde en una línea de gasto de 150, y solo el comprobante dice que
    # 50 no estaban gravados. Es el caso que destapó la carencia.
    ("compra_mixta_gravado_y_exonerado", "compra",
     {"base_gravada": "100.00", "igv": "18.00", "exonerado": "50.00", "total": "168.00",
      "destino_igv": "DGNG", "concepto": "Materiales varios de obra"}),
    # El tipo de cambio no está en ninguna línea si el comprobante no lo trae, y sin él el mes no vuelve a entrar.
    ("factura_usd_con_tipo_de_cambio", "compra",
     {"moneda": "USD", "tipo_cambio": "3.750", "base_gravada": "1000.00", "igv": "180.00", "total": "1180.00",
      "concepto": "Rodamientos importados"}),
    # El motivo del Catálogo 09 decide el tratamiento, y el asiento solo invierte los sentidos.
    ("nota_de_credito_con_tipo_nota", "compra",
     {"tipo_cp": "07", "serie": "FC01", "numero": "00000045", "tipo_nota": "06",
      "ref_tipo_cp": "01", "ref_serie": "F001", "ref_numero": "00000123", "ref_fecha": "2026-08-11",
      "base_gravada": "100.00", "igv": "18.00", "total": "118.00", "concepto": "Devolucion de mercaderia"}),
    # Sin constancia depositada, el comodín `999999999` NO viaja; la cuenta del Banco de la Nación sí, y no está en
    # ninguna línea.
    ("compra_con_detraccion_sin_constancia", "compra",
     {"base_gravada": "1000.00", "igv": "180.00", "total": "1180.00", "concepto": "Servicio de transporte de carga",
      "detraccion": {"codigo": "027", "cuenta": "00-123-456789"}}),
    # Y con el vóucher pegado sale tal cual: lo que se descarta es el comodín, no el dato.
    ("detraccion_con_constancia_pegada", "compra",
     {"base_gravada": "1000.00", "igv": "180.00", "total": "1180.00", "concepto": "Servicio de transporte de carga",
      "detraccion": {"codigo": "027", "cuenta": "00-123-456789",
                     "nro_constancia": "00123456789", "fecha_constancia": "2026-08-20"}}),
    # La retención de 4ta que MUESTRA el recibo por honorarios: una línea propia en el asiento y su importe aquí.
    ("honorarios_con_retencion", "compra",
     {"tipo_cp": "02", "serie": "R001", "numero": "00000007", "contraparte_tipo_doc": "1",
      "contraparte_doc": "45678912", "contraparte_nombre": "CONSULTOR INDEPENDIENTE",
      "base_gravada": "0.00", "igv": "0.00", "exonerado": "5000.00", "total": "5000.00",
      "retencion": "400.00", "concepto": "Asesoria de ingenieria"}),
    # En una venta con concepto propio, el nombre del cliente ya no cabe en la glosa: solo el comprobante lo lleva.
    ("venta_con_concepto_lleno", "venta",
     {"contraparte_doc": "20131312955", "contraparte_nombre": "CONSTRUCTORA DEL NORTE SAC",
      "base_gravada": "5000.00", "igv": "900.00", "total": "5900.00",
      "concepto": "Alquiler de andamios agosto"}),
    # Un servicio público, de los tipos en que SUNAT exige la fecha de vencimiento.
    ("recibo_de_servicios_publicos", "compra",
     {"tipo_cp": "14", "serie": "0001", "numero": "00098765", "fecha_vencimiento": "2026-09-05",
      "contraparte_doc": "20100017491", "contraparte_nombre": "EMPRESA DE ENERGIA",
      "base_gravada": "800.00", "igv": "144.00", "total": "944.00", "concepto": "Energia electrica obra"}),
]

IMPUTACION = {"f1": {"cuenta_contable": "631101"}}
CONFIG = {"usa_centros_costo": False}


def documento_de(caso) -> dict:
    _, libro, campos = caso
    return {"open_accounting": api.OPEN_ACCOUNTING, "libro": LIBROS[libro],
            "comprobantes": [{**BASE, **campos}]}


def serializar(caso) -> dict:
    """El archivo que produce el driver, tal cual, sin la versión del motor.

    `_exportacion.motor` se quita porque cambia en cada versión: dejarlo dentro haría que este snapshot se moviera sin
    que nada de contabilidad hubiera cambiado, y un snapshot que se mueve solo deja de vigilar."""
    exportado = api.exportar_archivo(documento_de(caso), driver="asiento_contable",
                                     configuracion=CONFIG, imputacion=IMPUTACION)
    documento = json.loads(exportado.contenido)
    documento["_exportacion"].pop("motor", None)
    return documento


def _cargar() -> dict:
    return json.loads(DOCUMENTO.read_text(encoding="utf-8"))


def regenerar() -> None:
    """Reescribe el snapshot con el código de hoy. Ver el docstring del módulo antes de usarlo."""
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    congelado = {caso[0]: serializar(caso) for caso in CASOS}
    DOCUMENTO.write_bytes((json.dumps(congelado, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


@pytest.mark.parametrize("caso", CASOS, ids=[c[0] for c in CASOS])
def test_el_documento_es_el_congelado(caso):
    assert serializar(caso) == _cargar()[caso[0]]


def test_el_snapshot_cubre_todos_los_casos():
    """Un caso nuevo sin regenerar, o uno que desaparece, se ve aquí y no en un fallo suelto."""
    assert set(_cargar()) == {c[0] for c in CASOS}


def test_la_version_del_motor_viaja_pero_no_se_congela():
    """Se saca del snapshot a propósito, así que se comprueba aparte: el archivo sí la lleva."""
    exportado = api.exportar_archivo(documento_de(CASOS[0]), driver="asiento_contable",
                                     configuracion=CONFIG, imputacion=IMPUTACION)
    assert json.loads(exportado.contenido)["_exportacion"]["motor"] == api.__version__


def test_cada_caso_lleva_los_tres_bloques_del_estandar():
    """Lo que hace que el documento se baste, comprobado en los ocho y no en uno."""
    for nombre, documento in _cargar().items():
        assert list(documento) == ["open_accounting", "libro", "comprobantes", "asiento", "_exportacion"], nombre
        assert documento["comprobantes"] and documento["asiento"], nombre
