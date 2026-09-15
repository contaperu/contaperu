"""El registro de CONTASIS, congelado celda a celda.

Las filas que produce `drivers.contasis.fila` para cada caso quedan en `fixtures/snapshot/contasis_filas.json`, con
el valor y el tipo de cada celda: un `18.0` no es un `"18"`, y una celda vacía no es una con espacios. Se congeló el
12-sep-2026 con las reglas que John revisó contra un registro que CONTASIS importó; los datos son inventados.

Regenerarlo es una decisión, no un trámite: solo cuando una regla cambia a propósito, con su fuente al lado y
mirando el diff del JSON celda por celda.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_snapshot_contasis as t; t.regenerar()"
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from contaperu import api
from contaperu.pipeline import preparacion as prep
from contaperu.drivers import contasis
from contaperu.modelo import Comprobante, Libro

FILAS = Path(__file__).parent / "fixtures" / "snapshot" / "contasis_filas.json"
COMPRAS = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="compra")
VENTAS = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="venta")


def cp(**k) -> Comprobante:
    base = dict(tipo_cp="01", serie="F001", numero="00000123", fecha_emision="2026-08-11",
                fecha_vencimiento="2026-08-18", contraparte_tipo_doc="6", contraparte_doc="20607777773",
                contraparte_nombre="ELECTROMECANICA DE PRUEBA S.R.L.", moneda="PEN", base_gravada="100",
                igv="18", total="118", concepto="Grillete tipo lira 5/8 para torre de alta tensión")
    base.update(k)
    return Comprobante(**base)


NC = dict(tipo_cp="07", serie="FC01", numero="9", ref_tipo_cp="01", ref_serie="F001", ref_numero="00000123",
          ref_fecha="2026-08-01")
# Un plan de cuentas como el de un CONTASIS real: por pagar y por cobrar a cuatro dígitos.
PLAN_CORTO = {"cuentas": {"cxp": {"PEN": "4212", "USD": "4212"}, "clientes": {"PEN": "1212", "USD": "1212"}}}
LARGA = ("Adquisición de materiales eléctricos para el mantenimiento preventivo de la subestación norte "
         "y sus líneas de alimentación")
# El centro de costo también en la segunda columna de centro de costos (John, 13-sep-2026).
CENTRO_2 = {"contasis": {"columnas": {"centro_costo": ["centro_costo", "centro_costo_2"]}}}

# (nombre, campos del comprobante, venta, configuración del RUC encima de la de fábrica)
CASOS: list[tuple[str, dict, bool, dict | None]] = [
    ("factura_pen", {}, False, None),
    ("factura_plan_corto", {}, False, PLAN_CORTO),
    # 100.01 y 18.00 a 3.333 dan 333.33 y 59.99, que suman 393.32; el total, 118.01 × 3.333, da 393.33.
    ("factura_usd_redondeo_a_la_base", dict(moneda="USD", tipo_cambio="3.333", base_gravada="100.01", igv="18.00",
                                             total="118.01"), False, None),
    ("factura_usd_sin_diferencia", dict(moneda="USD", tipo_cambio="3.397", base_gravada="1534.83", igv="276.27",
                                         total="1811.10"), False, None),
    ("boleta_en_compras", dict(tipo_cp="03", serie="0002", numero="4521"), False, None),
    ("boleta_de_persona_natural", dict(tipo_cp="03", serie="0002", numero="4522", contraparte_tipo_doc="1",
                                       contraparte_doc="45678912", contraparte_nombre="QUISPE MAMANI ROSA ELENA",
                                       base_gravada="0", igv="0", inafecto="35", total="35"), False, None),
    ("nota_de_credito", NC, False, None),
    ("nota_de_debito", dict(tipo_cp="08", serie="FD01", numero="3", ref_tipo_cp="01", ref_serie="F001",
                            ref_numero="123", ref_fecha="2026-08-01"), False, None),
    ("destino_dgng", dict(destino_igv="DGNG"), False, None),
    ("destino_dng", dict(destino_igv="DNG"), False, None),
    ("inafecta", dict(base_gravada="0", igv="0", inafecto="118"), False, None),
    ("otros_tributos_con_su_cuenta", dict(otros="5.90", total="123.90"), False,
     {"cuentas": {"otros_tributos": "641101"}}),
    ("otros_tributos_sin_cuenta", dict(otros="5.90", total="123.90"), False, None),
    # Las cuentas de otros tributos y del ICBPER solo van cuando su columna lleva importe.
    ("cuentas_de_otros_tributos_sin_importe", {}, False,
     {"cuentas": {"otros_tributos": "641101", "icbper": "641901"}}),
    # La referencia solo va en las notas: una factura que la trae (de una lectura, por error) no la escribe.
    ("factura_con_una_referencia_que_no_aplica", dict(ref_tipo_cp="01", ref_serie="F001", ref_numero="99",
                                                      ref_fecha="2026-08-01"), False, None),
    ("icbper_con_su_cuenta", dict(icbper="0.50", total="118.50"), False, {"cuentas": {"icbper": "641901"}}),
    ("importacion_dua", dict(tipo_cp="50", serie="", cod_dep_aduanera="118", anio_dua="2026", numero="0012345",
                             concepto="Importación de repuestos"), False, None),
    ("glosa_larga", dict(concepto=LARGA), False, None),
    ("sin_concepto", dict(concepto=""), False, None),
    ("detraccion_no_se_escribe", dict(detraccion={"codigo": "037", "porcentaje": "12"}), False, None),
    ("credito", dict(condicion_pago="credito", fecha_vencimiento="2026-09-10"), False, None),
    ("sin_vencimiento", dict(fecha_vencimiento=None), False, None),
    ("imputacion_cuenta_del_total", dict(id_externo="f1"), False,
     {"imputaciones": {"f1": {"cuenta_contable": "637301", "cuenta_tercero": "469901"}}}),
    ("sin_centros_de_costo", {}, False, {"usa_centros_costo": False}),
    ("cuenta_que_no_lleva_centro", dict(cuenta_contable="603201"), False, None),
    # Las columnas del centro las elige la sección de CONTASIS: la segunda lleva el mismo centro, con la misma regla de
    # la cuenta; y qué cuentas lo llevan es de la contabilidad general.
    ("centro_costo_2", {}, False, CENTRO_2),
    ("centro_costo_2_con_cuenta_que_no_lo_lleva", dict(cuenta_contable="603201"), False, CENTRO_2),
    ("cuentas_con_centro_propias", dict(cuenta_contable="603201"), False, {"cuentas_con_centro": ["60"]}),
    ("ninguna_cuenta_lleva_centro", {}, False, {"cuentas_con_centro": []}),
    ("igv_redondeado_por_item", dict(base_gravada="54.24", igv="9.75", total="63.99"), False, None),
    ("igv_reducido", dict(base_gravada="100", igv="10.5", total="110.5"), False, None),
    ("clasificacion_de_bienes", dict(clasif_bienes="1"), False, None),
    ("venta_factura", dict(cuenta_contable=""), True, None),
    ("venta_centro_costo_2", dict(cuenta_contable=""), True, CENTRO_2),
    ("venta_plan_corto", dict(cuenta_contable="70121"), True, PLAN_CORTO),
    ("venta_boleta_con_dni", dict(tipo_cp="03", serie="B001", numero="9", cuenta_contable="",
                                  contraparte_tipo_doc="1", contraparte_doc="45678912",
                                  contraparte_nombre="QUISPE MAMANI ROSA ELENA"), True, None),
    ("venta_usd", dict(cuenta_contable="", moneda="USD", tipo_cambio="3.55"), True, None),
    ("venta_nota_de_credito", dict(NC, cuenta_contable=""), True, None),
    ("venta_exportacion", dict(cuenta_contable="", base_gravada="0", igv="0", exportacion="1000", total="1000"),
     True, None),
    ("venta_exonerada", dict(cuenta_contable="", base_gravada="0", igv="0", exonerado="118"), True, None),
    ("venta_medio_de_pago_del_entorno", dict(cuenta_contable=""), True, {"contasis": {"medio_pago": "003"}}),
    ("venta_icbper_con_su_cuenta", dict(cuenta_contable="", icbper="0.50", total="118.50"), True,
     {"cuentas": {"icbper": "401891"}}),
    ("venta_credito", dict(cuenta_contable="", condicion_pago="credito", fecha_vencimiento="2026-09-10"), True, None),
]


def contab_de(extra: dict | None) -> dict:
    """La configuración aplicada para CONTASIS, con la imputación del caso, que llega aparte."""
    extra = dict(extra or {})
    imputaciones = extra.pop("imputaciones", None)
    config = prep.config_aplicada(extra, "contasis")
    return {**config, "imputaciones": imputaciones} if imputaciones else config


# La cuenta y el centro que escribe cada caso ya no son del comprobante (open-accounting 0.3): van en su imputación, por
# `id_externo`, fundidos con la que el caso ya traiga —la del caso manda campo a campo, y un reparto va solo—.
CUENTA_DEL_CASO = {"cuenta_contable": "631101", "centro_costo": "OBRA01"}


def armar(caso) -> tuple[Comprobante, dict, bool]:
    _, campos, es_venta, extra = caso
    campos = {**CUENTA_DEL_CASO, **campos}
    legado = {k: v for k in CUENTA_DEL_CASO if (v := campos.pop(k))}
    campos.setdefault("id_externo", "f1")
    extra = dict(extra or {})
    imputaciones = dict(extra.get("imputaciones") or {})
    propia = dict(imputaciones.get(campos["id_externo"]) or {})
    if not propia.get("reparto"):
        propia = {**legado, **propia}
    if propia:
        imputaciones[campos["id_externo"]] = propia
        extra["imputaciones"] = imputaciones
    return cp(**campos), contab_de(extra), es_venta


def fila_de(caso) -> dict:
    c, config, es_venta = armar(caso)
    return contasis.fila(c, VENTAS if es_venta else COMPRAS, config)


def _celda(v):
    """[tipo, valor]: el tipo cuenta tanto como el valor."""
    if isinstance(v, datetime):
        return ["datetime", v.isoformat()]
    return [type(v).__name__, v]


def serializar(caso) -> dict:
    """Solo las celdas que se escriben: una que pasa a vacía desaparece del JSON, y el test lo ve."""
    return {letra: _celda(v) for letra, v in fila_de(caso).items() if v is not None}


def regenerar() -> None:
    """Reescribe el snapshot con el código de hoy. Ver el docstring del módulo antes de usarlo."""
    FILAS.parent.mkdir(parents=True, exist_ok=True)
    datos = {caso[0]: serializar(caso) for caso in CASOS}
    FILAS.write_bytes((json.dumps(datos, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def _cargar() -> dict:
    return json.loads(FILAS.read_text(encoding="utf-8"))


def test_los_casos_no_se_repiten():
    nombres = [c[0] for c in CASOS]
    assert len(nombres) == len(set(nombres))


def test_el_snapshot_cubre_todos_los_casos():
    assert set(_cargar()) == {c[0] for c in CASOS}


@pytest.mark.parametrize("caso", CASOS, ids=[c[0] for c in CASOS])
def test_las_filas_de_contasis_no_cambian_ni_una_celda(caso):
    esperado = _cargar()[caso[0]]
    obtenido = serializar(caso)
    distintas = {letra: (obtenido.get(letra), esperado.get(letra))
                 for letra in set(obtenido) | set(esperado) if obtenido.get(letra) != esperado.get(letra)}
    assert not distintas, f"{caso[0]}: celdas distintas (obtenido, esperado) {distintas}"


@pytest.mark.parametrize("caso", CASOS, ids=[c[0] for c in CASOS])
def test_cada_fila_suma_su_total(caso):
    """Así viene cada fila del registro validado: el total es la suma de sus importes (en compras, J…R y el ICBPER;
    en ventas, I…O y el ICBPER), también en dólares después de convertir."""
    f = fila_de(caso)
    es_venta = caso[2]
    partes = (("I", "J", "K", "L", "M", "N", "O", "AQ") if es_venta
              else ("J", "K", "L", "M", "N", "O", "P", "Q", "R", "AW"))
    assert round(sum(f.get(letra) or 0 for letra in partes), 2) == round(f.get("P" if es_venta else "S") or 0, 2)
