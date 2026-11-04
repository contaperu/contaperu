"""Las reglas del comprobante de un no domiciliado (15.6.0, `tributos/validar.py`).

Cada regla tiene su caso que la hace saltar y el comprobante correcto, que no dice nada: si al romper una línea de la
regla ningún caso cae, falta el caso. Y el registro real que SUNAT aceptó en setiembre de 2026 no da ni un error,
aunque traiga filas que las reglas avisan: por eso esas reglas son avisos.
"""
from __future__ import annotations

import pathlib

import pytest

from contaperu.comprobantes import sire_txt
from contaperu.modelo import Comprobante, Libro
from contaperu.tributos import validar

COMPRAS = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202609", tipo="compra")
VENTAS = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202609", tipo="venta")

# Una suscripción de 100 dólares al 3.750: 375 soles de renta, al 30 %, sin convenio (Estados Unidos), servicio
# digital prestado desde el extranjero, y el IGV de utilización del 18 % de los 375 soles.
BLOQUE = {"pais": "9249", "vinculo": "00", "renta_bruta": "375.00", "deduccion": "0.00", "renta_neta": "375.00",
          "porcentaje": "30", "impuesto_retenido": "112.50", "igv_utilizacion": "67.50", "convenio": "00",
          "tipo_renta": "18", "modalidad": "3"}


def _del_exterior(tipo_cp="91", **cambios) -> Comprobante:
    bloque = {**BLOQUE, **cambios.pop("bloque", {})}
    datos = dict(tipo_cp=tipo_cp, serie="INV", numero="1042", fecha_emision="2026-09-10", contraparte_tipo_doc="0",
                 contraparte_doc="X0000001", contraparte_nombre="PROVEEDOR DEL EXTERIOR", moneda="USD",
                 tipo_cambio="3.750", valor_no_gravado="100.00", total="100.00", origen="manual",
                 no_domiciliado=bloque)
    datos.update(cambios)
    return Comprobante(**datos)


def _codigos(c: Comprobante, libro: Libro = COMPRAS) -> dict[str, str]:
    validar.validar(c, libro)
    return {o.codigo: o.nivel for o in c.observaciones}


def test_el_comprobante_correcto_no_dice_nada():
    assert _codigos(_del_exterior()) == {}


def test_un_no_domiciliado_en_ventas_es_un_error():
    assert _codigos(_del_exterior(), VENTAS)["NO_DOMICILIADO_EN_VENTAS"] == "error"


def test_un_no_domiciliado_con_igv_es_un_error():
    """El 080500 no tiene columnas de base gravada ni de IGV: escrito, ese IGV se perdería sin aviso."""
    c = _del_exterior(base_gravada="100.00", igv="18.00", valor_no_gravado=None, total="118.00")
    assert _codigos(c)["NO_DOMICILIADO_CON_IGV"] == "error"


def test_el_bloque_en_otro_tipo_se_avisa_y_se_ignora():
    c = Comprobante(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-09-10", contraparte_doc="20100047218",
                    contraparte_nombre="PROVEEDOR SAC", base_gravada="100.00", igv="18.00", total="118.00",
                    no_domiciliado={"pais": "9249"})
    assert _codigos(c).get("NO_DOMICILIADO_NO_APLICA") == "aviso"


@pytest.mark.parametrize("clave, valor, codigo", [
    ("pais", "9999", "PAIS_DESCONOCIDO"),
    ("beneficiario_pais", "1234", "PAIS_DESCONOCIDO"),
    ("vinculo", "99", "VINCULO_DESCONOCIDO"),
    ("convenio", "77", "CONVENIO_DESCONOCIDO"),
    ("tipo_renta", "88", "TIPO_RENTA_DESCONOCIDO"),
    ("modalidad", "7", "MODALIDAD_DESCONOCIDA"),
    ("exoneracion", "9", "EXONERACION_DESCONOCIDA"),
])
def test_un_codigo_que_no_esta_en_su_tabla_se_avisa(clave, valor, codigo):
    assert _codigos(_del_exterior(bloque={clave: valor})).get(codigo) == "aviso"


def test_el_peru_como_pais_del_no_domiciliado_se_avisa():
    assert _codigos(_del_exterior(bloque={"pais": "9589"})).get("PAIS_PERU_NO_DOMICILIADO") == "aviso"


def test_la_renta_neta_que_no_es_la_bruta_menos_la_deduccion_se_avisa():
    codigos = _codigos(_del_exterior(bloque={"deduccion": "75.00", "renta_neta": "375.00"}))
    assert codigos.get("RENTA_NETA_NO_CUADRA") == "aviso"
    # Con la deducción bien restada, calla — y el impuesto vuelve a cuadrar con la neta nueva.
    assert "RENTA_NETA_NO_CUADRA" not in _codigos(
        _del_exterior(bloque={"deduccion": "75.00", "renta_neta": "300.00", "impuesto_retenido": "90.00"}))


def test_el_impuesto_que_no_es_la_neta_por_la_tasa_se_avisa():
    assert _codigos(_del_exterior(bloque={"impuesto_retenido": "100.00"})).get("IMPUESTO_RETENIDO_NO_CUADRA") == "aviso"
    # Dentro de la tolerancia, calla: el real lo cuadra a medio céntimo.
    assert "IMPUESTO_RETENIDO_NO_CUADRA" not in _codigos(_del_exterior(bloque={"impuesto_retenido": "112.53"}))


def test_una_exoneracion_con_impuesto_retenido_se_avisa():
    assert _codigos(_del_exterior(bloque={"exoneracion": "1"})).get("EXONERACION_CON_IMPUESTO") == "aviso"


def test_el_convenio_que_no_es_el_del_pais_se_avisa_con_el_sugerido():
    c = _del_exterior(bloque={"pais": "9211", "convenio": "00"})       # Chile, sin su convenio
    assert _codigos(c).get("CONVENIO_NO_ES_DEL_PAIS") == "aviso"
    texto = next(o.texto for o in c.observaciones if o.codigo == "CONVENIO_NO_ES_DEL_PAIS")
    assert "Chile" in texto
    # Japón tiene convenio y la tabla no le da código: el motor no puede decir cuál es, así que no avisa.
    assert "CONVENIO_NO_ES_DEL_PAIS" not in _codigos(_del_exterior(bloque={"pais": "9399", "convenio": "09"}))


def test_el_igv_de_utilizacion_que_no_es_el_18_por_ciento_en_soles_se_avisa():
    assert _codigos(_del_exterior(bloque={"igv_utilizacion": "18.00"})).get("IGV_UTILIZACION_NO_CUADRA") == "aviso"
    # Un cero es que no hubo, y no se avisa.
    assert "IGV_UTILIZACION_NO_CUADRA" not in _codigos(_del_exterior(bloque={"igv_utilizacion": "0.00"}))


def test_un_91_sin_bloque_no_se_observa_todavia():
    """Los 91 que entraron antes de la 15.6 no traen el bloque. No se les avisa: lo que el 080500 exige lo pedirá su
    driver al exportar, y no se tiñe de observado un mes que ya estaba bien."""
    assert _codigos(_del_exterior(no_domiciliado=None)) == {}


# ── El registro real ──────────────────────────────────────────────────────────────────────────────────────────────
PRIVADO = pathlib.Path(__file__).parent / "fixtures" / "privado" / "sire"


def test_el_registro_real_no_da_ningun_error():
    """SUNAT lo aceptó: ninguna regla puede bloquearlo. Que avise de alguna fila —un país que es el Perú, un convenio
    que no es el del país— es justo lo que se espera, y no se mira cuál."""
    archivos = sorted(PRIVADO.glob("LE*080500*.txt")) if PRIVADO.is_dir() else []
    if not archivos:
        pytest.skip("sin el registro de no domiciliados real en tests/fixtures/privado/sire (fuera de Git)")
    nombre = archivos[0].name
    libro = Libro(ruc=nombre[2:13], razon_social="", periodo=nombre[13:19], tipo="compra")
    comprobantes = sire_txt.parsear(archivos[0].read_bytes(), libro, archivo_nombre=nombre)
    for c in comprobantes:
        validar.validar(c, libro)
    errores = sorted({o.codigo for c in comprobantes for o in c.observaciones if o.nivel == "error"})
    assert errores == [], f"el registro real que SUNAT aceptó da errores: {errores}"
