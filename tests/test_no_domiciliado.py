"""El bloque del no domiciliado en el comprobante (enmienda 0007, open-accounting 4.1).

Lo que el registro de compras de no domiciliados del SIRE (el 080500) pide de una factura del exterior y que el resto
del comprobante no dice. Estos casos fijan las tres cosas que pueden fallar sin que nada lo diga: que el bloque admita
algo que no es suyo, que normalice distinto que el esquema publicado, y que se pierda entre el comprobante y el
documento que escribe un driver.
"""
from __future__ import annotations

import json
import pathlib

import jsonschema
import pytest

from contaperu import api
from contaperu.asiento.comprobante import cabecera_de
from contaperu.comprobantes.comprobante import CLAVES_NO_DOMICILIADO, Comprobante

BLOQUE = {"pais": "9249", "domicilio": "UNA CALLE DEL EXTERIOR", "vinculo": "0", "renta_bruta": "375",
          "deduccion": "0", "renta_neta": "375", "porcentaje": "30", "impuesto_retenido": 112.5,
          "igv_utilizacion": "67.50", "convenio": "", "tipo_renta": "18", "modalidad": "3"}


def _del_exterior(bloque=BLOQUE) -> Comprobante:
    return Comprobante(tipo_cp="91", serie="INV", numero="1042", fecha_emision="2026-09-10",
                       contraparte_tipo_doc="0", contraparte_doc="X0000001",
                       contraparte_nombre="PROVEEDOR DEL EXTERIOR", moneda="USD", tipo_cambio="3.750",
                       valor_no_gravado="100.00", total="100.00", origen="manual", no_domiciliado=bloque)


def test_el_bloque_se_normaliza_como_el_estandar_lo_publica():
    bloque = _del_exterior().no_domiciliado
    # Los importes, en texto con dos decimales; los códigos de ancho fijo, con su ancho; y lo vacío, fuera.
    assert bloque["renta_bruta"] == "375.00"
    assert bloque["impuesto_retenido"] == "112.50"
    assert bloque["vinculo"] == "00"
    assert bloque["porcentaje"] == "30"
    assert "convenio" not in bloque, "una clave vacía es «el documento no lo dice», y se omite"
    assert bloque["modalidad"] == "3", "la modalidad no lleva ceros: su tabla numera 1, 2, 3"


def test_nadie_lo_dijo_no_es_un_bloque_vacio():
    assert _del_exterior(None).no_domiciliado is None
    assert _del_exterior({}).no_domiciliado == {}


def test_una_clave_que_no_es_del_bloque_se_rechaza_nombrandola():
    with pytest.raises(ValueError, match="tasa_retencion"):
        _del_exterior({"pais": "9249", "tasa_retencion": "30"})
    with pytest.raises(ValueError, match="porcentaje"):
        _del_exterior({"pais": "9249", "porcentaje": "treinta"})


def test_las_claves_del_modelo_son_las_del_esquema_publicado():
    """La lección de `referencia_de_pago` en la 3.0: si las claves viven solo en Python, un validador que use el JSON
    publicado acepta lo que el motor rechaza, o al revés."""
    esquema = api.esquema_open_accounting()
    del_esquema = esquema["$defs"]["no_domiciliado"]["properties"]
    assert tuple(del_esquema) == CLAVES_NO_DOMICILIADO
    assert esquema["$defs"]["no_domiciliado"]["additionalProperties"] is False
    assert "no_domiciliado" in esquema["$defs"]["comprobante"]["properties"]


def test_viaja_hasta_la_cabecera_y_vuelve_al_documento_tal_cual():
    c = _del_exterior()
    cabecera = cabecera_de(c)
    assert cabecera.no_domiciliado == c.no_domiciliado
    escrito = cabecera.como_comprobante()
    assert escrito["no_domiciliado"] == c.no_domiciliado
    # Y el comprobante escrito valida contra el esquema publicado, que es la otra mitad de la ida y vuelta.
    documento = {"open_accounting": api.OPEN_ACCOUNTING,
                 "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202609",
                           "tipo": "compra"},
                 "comprobantes": [escrito]}
    jsonschema.Draft202012Validator(api.esquema_open_accounting()).validate(documento)
    assert Comprobante.de_dict(json.loads(json.dumps(c.a_dict()))).no_domiciliado == c.no_domiciliado


def test_un_comprobante_sin_el_bloque_no_lo_escribe():
    c = _del_exterior(None)
    assert "no_domiciliado" not in cabecera_de(c).como_comprobante()


# El TXT 080500 que SUNAT aceptó en setiembre de 2026, de un contribuyente real y fuera de Git. Si no está, se salta. Los
# mensajes dicen cuántas filas, nunca qué dicen.
PRIVADO = pathlib.Path(__file__).parent / "fixtures" / "privado" / "sire"


def _registro_real() -> tuple[bytes, str]:
    archivos = sorted(PRIVADO.glob("LE*080500*.txt")) if PRIVADO.is_dir() else []
    if not archivos:
        pytest.skip("sin el registro de no domiciliados real en tests/fixtures/privado/sire (fuera de Git)")
    return archivos[0].read_bytes(), archivos[0].name


def test_el_registro_real_entra_entero_al_bloque():
    from contaperu.comprobantes import sire_txt
    from contaperu.modelo import Libro

    datos, nombre = _registro_real()
    libro = Libro(ruc=nombre[2:13], razon_social="", periodo=nombre[13:19], tipo="compra")
    comprobantes = sire_txt.parsear(datos, libro, archivo_nombre=nombre)
    assert comprobantes, "el registro real no dio ninguna compra"
    sin_pais = sum(1 for c in comprobantes if not (c.no_domiciliado or {}).get("pais"))
    sin_renta = sum(1 for c in comprobantes if not (c.no_domiciliado or {}).get("tipo_renta"))
    assert (sin_pais, sin_renta) == (0, 0), f"{sin_pais} fila(s) sin país y {sin_renta} sin tipo de renta"
    # Y el documento entero valida contra el esquema publicado, escrito como lo escribe un driver.
    documento = {"open_accounting": api.OPEN_ACCOUNTING,
                 "libro": {"ruc": libro.ruc, "razon_social": "CONTRIBUYENTE", "periodo": libro.periodo,
                           "tipo": "compra"},
                 "comprobantes": [cabecera_de(c).como_comprobante() for c in comprobantes]}
    errores = list(jsonschema.Draft202012Validator(api.esquema_open_accounting()).iter_errors(documento))
    assert not errores, f"{len(errores)} error(es) de esquema en el registro real, el primero en " \
                        f"{'/'.join(str(p) for p in errores[0].absolute_path)}"


def test_el_bloque_no_entra_en_ningun_asiento():
    """El 91 se asienta como una compra común. El IGV de utilización y la renta retenida son otro paso, con un caso
    real: hasta entonces, el mismo comprobante con o sin el bloque produce el mismo asiento."""
    def asiento(bloque):
        c = _del_exterior(bloque)
        c.id_externo = "X"
        escrito = cabecera_de(c).como_comprobante()
        documento = {"open_accounting": api.OPEN_ACCOUNTING,
                     "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202609",
                               "tipo": "compra"},
                     "comprobantes": [escrito]}
        r = api.generar_asiento(documento, driver="asiento_contable",
                                imputacion={"X": {"cuenta_contable": "6361101"}})
        return [{k: v for k, v in linea.items() if k != "documento"} for linea in r["asiento"]], r["_asiento"]["huella"]

    con, huella_con = asiento(BLOQUE)
    sin, huella_sin = asiento(None)
    assert con == sin
    assert huella_con == huella_sin
    assert con, "y hay asiento: el 91 se asienta como compra común"


# ── El preliminar de no domiciliados (5.39), medido el 04-nov-2026 (15.6.1) ────────────────────────────────────────
def _como_el_preliminar(c: Comprobante) -> bytes:
    """Un 080500 escrito por el driver, puesto en la forma del preliminar que exporta SUNAT: una cabecera, filas de 35
    campos sin palote, LF, el CAR que pone SUNAT y un 0 en la exoneración, el art. 76 y el año de la DUA."""
    from contaperu.drivers import sire_no_domiciliados as nd
    from contaperu.modelo import Libro

    libro = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202609", tipo="compra")
    campos = nd.linea(c, libro, 1).rstrip("\r\n").split("|")[:35]
    campos[1] = "2026091234567"                       # el CAR, que en el preliminar ya está
    for indice in (11, 30, 33):                       # año de la DUA (12), exoneración (31) y art. 76 (34)
        campos[indice] = "0"
    cabecera = ["Periodo", "CAR SUNAT"] + [f"Rotulo {i}" for i in range(3, 36)] + [f"CLU{i}" for i in range(1, 11)]
    return ("|".join(cabecera) + "\n" + "|".join(campos)).encode("utf-8")


def test_el_cero_del_preliminar_es_vacio_y_no_da_avisos():
    """SUNAT escribe un 0 donde lo declarado deja vacíos la exoneración, el art. 76 y el año de la DUA. Leído tal cual, el
    0 no es ningún código de la Tabla 21 y cada fila daba dos avisos falsos."""
    from contaperu.comprobantes import sire_txt
    from contaperu.modelo import Libro
    from contaperu.tributos import validar

    libro = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202609", tipo="compra")
    [leido] = sire_txt.parsear(_como_el_preliminar(_del_exterior()), libro, archivo_nombre="preliminar.txt")
    assert not ({"exoneracion", "art_76", "sustento_anio_dua"} & set(leido.no_domiciliado))
    validar.validar(leido, libro)
    assert not {o.codigo for o in leido.observaciones} & {"EXONERACION_DESCONOCIDA", "EXONERACION_CON_IMPUESTO"}


def test_un_codigo_de_exoneracion_de_verdad_se_sigue_leyendo():
    """Lo que se vacía es el 0, no la columna: una exoneración que sí está en la tabla entra al bloque."""
    from contaperu.comprobantes import sire_txt
    from contaperu.modelo import Libro

    libro = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202609", tipo="compra")
    crudo = _como_el_preliminar(_del_exterior()).decode("utf-8").split("\n")
    fila = crudo[1].split("|")
    fila[30] = "1"
    [leido] = sire_txt.parsear(("\n".join([crudo[0], "|".join(fila)])).encode("utf-8"), libro,
                               archivo_nombre="preliminar.txt")
    assert leido.no_domiciliado["exoneracion"] == "1"


def test_el_preliminar_real_y_lo_declarado_dicen_lo_mismo():
    """El mismo mes en las dos formas en que SUNAT lo da: el preliminar de no domiciliados (5.39) y lo declarado (5.51).
    Tienen que dar las mismas facturas, campo a campo —la tasa, como número: el preliminar la escribe sin decimales—, y
    los mismos avisos. Se salta si los dos archivos reales no están en tests/fixtures/privado/sire (fuera de Git)."""
    from decimal import Decimal

    from contaperu.comprobantes import sire_txt
    from contaperu.modelo import Libro
    from contaperu.tributos import validar

    datos, nombre = _registro_real()
    preliminares = sorted(PRIVADO.glob("preliminar-no-domiciliados-*.txt"))
    if not preliminares:
        pytest.skip("sin el preliminar de no domiciliados real en tests/fixtures/privado/sire (fuera de Git)")
    libro = Libro(ruc=nombre[2:13], razon_social="", periodo=nombre[13:19], tipo="compra")

    def leer(crudo: bytes, archivo: str) -> dict:
        cs = sire_txt.parsear(crudo, libro, archivo_nombre=archivo)
        for c in cs:
            validar.validar(c, libro)
        return {(c.serie, c.numero, c.contraparte_doc): c for c in cs}

    declarado = leer(datos, nombre)
    preliminar = leer(preliminares[0].read_bytes(), preliminares[0].name)
    assert set(preliminar) == set(declarado), "no son las mismas facturas"
    distintos = []
    for clave, p in preliminar.items():
        d = declarado[clave]
        bp, bd = dict(p.no_domiciliado or {}), dict(d.no_domiciliado or {})
        if Decimal(bp.pop("porcentaje", "0")) != Decimal(bd.pop("porcentaje", "0")):
            distintos.append("porcentaje")
        distintos += [k for k in set(bp) | set(bd) if bp.get(k) != bd.get(k)]
        for campo in ("tipo_cp", "fecha_emision", "moneda", "tipo_cambio", "valor_no_gravado", "total",
                      "contraparte_nombre"):
            if getattr(p, campo) != getattr(d, campo):
                distintos.append(campo)
        if sorted(o.codigo for o in p.observaciones) != sorted(o.codigo for o in d.observaciones):
            distintos.append("avisos")
    assert not distintos, f"lo que el preliminar dice distinto que lo declarado: {sorted(set(distintos))}"
